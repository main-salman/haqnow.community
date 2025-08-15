from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .db import get_db
from .models import Document, ProcessingJob
from .schemas import DocumentCreate, DocumentOut, PresignedUploadRequest, PresignedUploadResponse
from .s3_client import generate_presigned_upload
from .tasks import process_document_tiling, process_document_thumbnails, process_document_ocr


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/presigned-upload", response_model=PresignedUploadResponse)
def create_presigned_upload(payload: PresignedUploadRequest):
    """Generate presigned URL for direct upload to SOS"""
    try:
        upload_info = generate_presigned_upload(
            filename=payload.filename,
            content_type=payload.content_type,
            size=payload.size,
        )
        return PresignedUploadResponse(**upload_info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=DocumentOut)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    """Register a document after successful upload"""
    # TODO: Add proper auth middleware to get uploader_id
    document = Document(
        title=payload.title,
        description=payload.description,
        source=payload.source,
        language=payload.language,
        uploader_id=1,  # TODO: Get from authenticated user
        published_date=payload.published_date,
        acquired_date=payload.acquired_date,
        event_date=payload.event_date,
        filing_date=payload.filing_date,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Enqueue processing jobs
    _enqueue_processing_jobs(document.id, db)
    
    return document


def _enqueue_processing_jobs(document_id: int, db: Session):
    """Enqueue background processing jobs for a document"""
    job_types = ["tiling", "thumbnails", "ocr"]
    
    for job_type in job_types:
        # Create job record
        job = ProcessingJob(
            document_id=document_id,
            job_type=job_type,
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Enqueue Celery task
        if job_type == "tiling":
            task = process_document_tiling.delay(document_id, job.id)
        elif job_type == "thumbnails":
            task = process_document_thumbnails.delay(document_id, job.id)
        elif job_type == "ocr":
            task = process_document_ocr.delay(document_id, job.id)
        
        # Update job with Celery task ID
        job.celery_task_id = task.id
        db.commit()


@router.get("/", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    """List documents with recent-first ordering"""
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return documents


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/jobs")
def get_document_jobs(document_id: int, db: Session = Depends(get_db)):
    """Get processing jobs for a document"""
    jobs = db.query(ProcessingJob).filter(ProcessingJob.document_id == document_id).all()
    return [
        {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }
        for job in jobs
    ]
