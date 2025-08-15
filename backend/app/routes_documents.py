import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .db import get_db
from .export import get_export_service
from .models import Document, ProcessingJob
from .redaction import get_redaction_service
from .s3_client import generate_presigned_upload
from .schemas import (
    DocumentCreate,
    DocumentOut,
    PresignedUploadRequest,
    PresignedUploadResponse,
)
from .tasks import (
    process_document_ocr,
    process_document_thumbnails,
    process_document_tiling,
)

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


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    description: str = "",
    source: str = "",
    language: str = "en",
    db: Session = Depends(get_db),
):
    """Direct file upload endpoint for testing"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)

    # Save file locally for processing
    file_path = uploads_dir / file.filename
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Create document record
    document = Document(
        title=file.filename,
        description=description or f"Uploaded document: {file.filename}",
        source=source or "Direct Upload",
        language=language,
        uploader_id=1,  # TODO: Get from authenticated user
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Enqueue processing jobs
    _enqueue_processing_jobs(document.id, db)

    return document


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


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete document by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete associated processing jobs first
    db.query(ProcessingJob).filter(ProcessingJob.document_id == document_id).delete()

    # Delete the document
    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}


@router.delete("/")
def delete_all_documents(db: Session = Depends(get_db)):
    """Delete all documents (for testing purposes)"""
    # Delete all processing jobs first
    db.query(ProcessingJob).delete()

    # Delete all documents
    db.query(Document).delete()
    db.commit()

    return {"message": "All documents deleted successfully"}


@router.get("/{document_id}/jobs")
def get_document_jobs(document_id: int, db: Session = Depends(get_db)):
    """Get processing jobs for a document"""
    jobs = (
        db.query(ProcessingJob).filter(ProcessingJob.document_id == document_id).all()
    )
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


@router.post("/{document_id}/pages/{page_number}/redact")
async def apply_redactions(
    document_id: int,
    page_number: int,
    redaction_data: dict,
    db: Session = Depends(get_db),
):
    """Apply redactions to a specific page"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    redaction_regions = redaction_data.get("redactions", [])
    if not redaction_regions:
        raise HTTPException(status_code=400, detail="No redaction regions provided")

    redaction_service = get_redaction_service()
    result = await redaction_service.apply_redactions(
        document_id, page_number, redaction_regions
    )

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Redaction failed")
        )

    return result


@router.delete("/{document_id}/pages/{page_number}/redact")
async def remove_redactions(
    document_id: int, page_number: int, db: Session = Depends(get_db)
):
    """Remove redactions from a specific page"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    redaction_service = get_redaction_service()
    result = await redaction_service.remove_redactions(document_id, page_number)

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Failed to remove redactions")
        )

    return result


@router.get("/{document_id}/redactions")
async def list_redacted_pages(document_id: int, db: Session = Depends(get_db)):
    """List all redacted pages for a document"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    redaction_service = get_redaction_service()
    redacted_pages = await redaction_service.list_redacted_pages(document_id)

    return {
        "document_id": document_id,
        "redacted_pages": redacted_pages,
        "total_redacted_pages": len(redacted_pages),
    }


@router.get("/{document_id}/pages/{page_number}/redactions/verify")
async def verify_redaction_integrity(
    document_id: int, page_number: int, db: Session = Depends(get_db)
):
    """Verify redaction integrity for a specific page"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    redaction_service = get_redaction_service()
    result = await redaction_service.verify_redaction_integrity(
        document_id, page_number
    )

    if not result["success"]:
        raise HTTPException(
            status_code=404, detail=result.get("error", "No redactions found")
        )

    return result


@router.post("/{document_id}/export")
async def export_document(
    document_id: int, export_request: dict, db: Session = Depends(get_db)
):
    """Export document as PDF or images with optional page ranges"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    export_format = export_request.get("format", "pdf")
    page_ranges_str = export_request.get("page_ranges")
    include_redacted = export_request.get("include_redacted", True)
    quality = export_request.get("quality", "high")

    export_service = get_export_service()

    # Parse page ranges if provided
    page_ranges = None
    if page_ranges_str:
        try:
            # For now, assume total pages is 100 (would get from document metadata)
            page_ranges = export_service.parse_page_ranges(page_ranges_str, 100)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid page ranges: {str(e)}"
            )

    result = await export_service.export_pdf(
        document_id=document_id,
        page_ranges=page_ranges,
        include_redacted=include_redacted,
        export_format=export_format,
        quality=quality,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Export failed")
        )

    return result


@router.get("/{document_id}/exports")
async def list_document_exports(document_id: int, db: Session = Depends(get_db)):
    """List all available exports for a document"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    export_service = get_export_service()
    result = await export_service.list_exports(document_id)

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Failed to list exports")
        )

    return result


@router.get("/{document_id}/tiles/page_{page_number}/")
async def get_document_tiles(
    document_id: int, page_number: int, db: Session = Depends(get_db)
):
    """Serve document tiles for OpenSeadragon viewer"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # For now, return a simple tile configuration
    # In production, this would serve actual tile files
    return {
        "type": "image",
        "url": f"/api/documents/{document_id}/thumbnail/{page_number}",
        "width": 2000,
        "height": 3000,
        "tileSize": 256,
        "overlap": 1
    }


@router.get("/{document_id}/thumbnail/{page_number}")
async def get_document_thumbnail(
    document_id: int, page_number: int, db: Session = Depends(get_db)
):
    """Get document page thumbnail"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # For now, return a placeholder response
    # In production, this would serve actual thumbnail files
    from fastapi.responses import Response
    
    # Create a simple placeholder image
    from PIL import Image, ImageDraw
    import io
    
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), f"Document: {document.title}\nPage: {page_number + 1}", fill='black')
    
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return Response(content=img_bytes.getvalue(), media_type="image/png")


@router.get("/{document_id}/download")
async def download_document(
    document_id: int, db: Session = Depends(get_db)
):
    """Download original document file"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # For now, return document info
    # In production, this would serve the actual file
    return {
        "success": True,
        "document_id": document_id,
        "filename": document.title,
        "download_url": f"/api/documents/{document_id}/file"
    }


@router.post("/{document_id}/comments")
async def add_comment(
    document_id: int, comment_data: dict, db: Session = Depends(get_db)
):
    """Add a comment to a document"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # For now, return success
    # In production, this would save to database
    return {
        "success": True,
        "comment_id": 1,
        "message": "Comment added successfully"
    }


@router.get("/{document_id}/comments")
async def get_comments(
    document_id: int, db: Session = Depends(get_db)
):
    """Get all comments for a document"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Return empty comments for now
    return {
        "success": True,
        "comments": [],
        "total": 0
    }


@router.delete("/{document_id}/exports/{filename}")
async def delete_document_export(
    document_id: int, filename: str, db: Session = Depends(get_db)
):
    """Delete a specific export file"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    export_service = get_export_service()
    result = await export_service.delete_export(document_id, filename)

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Failed to delete export")
        )

    return result
