import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .db import get_db
from .export import get_export_service
from .models import Document, DocumentShare, ProcessingJob
from .redaction import get_redaction_service
from .routes_auth import get_current_user
from .s3_client import generate_presigned_upload
from .schemas import (
    DocumentCreate,
    DocumentOut,
    DocumentShareCreate,
    DocumentShareOut,
    DocumentShareUpdate,
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
    # Always save into backend/uploads so worker and API share a consistent path in dev/prod
    uploads_dir = (
        Path("backend/uploads") if Path("backend").exists() else Path("uploads")
    )
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
        "overlap": 1,
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

    import os

    from fastapi.responses import Response

    # Try to serve actual processed thumbnail
    local_path = f"/srv/processed/thumbnails/{document_id}/page_{page_number}.webp"
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            thumbnail_data = f.read()
        return Response(content=thumbnail_data, media_type="image/webp")

    # Fallback: Create a placeholder image
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 1000), color="white")
    draw = ImageDraw.Draw(img)
    draw.text(
        (50, 50), f"Document: {document.title}\nPage: {page_number + 1}", fill="black"
    )

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    return Response(content=img_bytes.getvalue(), media_type="image/png")


@router.get("/{document_id}/download")
async def download_document(document_id: int, db: Session = Depends(get_db)):
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
        "download_url": f"/api/documents/{document_id}/file",
    }


@router.post("/{document_id}/comments")
async def add_comment(
    document_id: int,
    comment_data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add a comment to a document"""
    from .models import Comment

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Create comment
    comment = Comment(
        document_id=document_id,
        user_id=current_user.id,
        page_number=comment_data.get("page_number", 0),
        x_position=comment_data.get("x_position", 0.0),
        y_position=comment_data.get("y_position", 0.0),
        content=comment_data.get("content", ""),
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "content": comment.content,
        "page_number": comment.page_number,
        "x_position": comment.x_position,
        "y_position": comment.y_position,
        "user_name": current_user.full_name or current_user.email,
        "created_at": comment.created_at.isoformat(),
    }


@router.get("/{document_id}/comments")
async def get_comments(document_id: int, db: Session = Depends(get_db)):
    """Get all comments for a document"""
    from .models import Comment, User

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get comments with user info
    comments = (
        db.query(Comment, User)
        .join(User, Comment.user_id == User.id)
        .filter(Comment.document_id == document_id)
        .order_by(Comment.created_at.desc())
        .all()
    )

    return {
        "comments": [
            {
                "id": comment.id,
                "content": comment.content,
                "page_number": comment.page_number,
                "x_position": comment.x_position,
                "y_position": comment.y_position,
                "user_name": user.full_name or user.email,
                "created_at": comment.created_at.isoformat(),
                "is_resolved": comment.is_resolved,
            }
            for comment, user in comments
        ]
    }


@router.post("/{document_id}/redactions")
async def add_redaction(
    document_id: int,
    redaction_data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add a redaction to a document"""
    from .models import Redaction

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Create redaction
    redaction = Redaction(
        document_id=document_id,
        user_id=current_user.id,
        page_number=redaction_data.get("page_number", 0),
        x_start=redaction_data.get("x_start", 0.0),
        y_start=redaction_data.get("y_start", 0.0),
        x_end=redaction_data.get("x_end", 0.0),
        y_end=redaction_data.get("y_end", 0.0),
        reason=redaction_data.get("reason", ""),
    )

    db.add(redaction)
    db.commit()
    db.refresh(redaction)

    return {
        "id": redaction.id,
        "page_number": redaction.page_number,
        "x_start": redaction.x_start,
        "y_start": redaction.y_start,
        "x_end": redaction.x_end,
        "y_end": redaction.y_end,
        "reason": redaction.reason,
        "created_at": redaction.created_at.isoformat(),
    }


@router.get("/{document_id}/redactions")
async def get_redactions(document_id: int, db: Session = Depends(get_db)):
    """Get all redactions for a document"""
    from .models import Redaction

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get redactions
    redactions = db.query(Redaction).filter(Redaction.document_id == document_id).all()

    return {
        "redactions": [
            {
                "id": redaction.id,
                "page_number": redaction.page_number,
                "x_start": redaction.x_start,
                "y_start": redaction.y_start,
                "x_end": redaction.x_end,
                "y_end": redaction.y_end,
                "reason": redaction.reason,
                "created_at": redaction.created_at.isoformat(),
            }
            for redaction in redactions
        ]
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


# Document Sharing Endpoints


@router.post("/{document_id}/shares", response_model=DocumentShareOut)
async def share_document(
    document_id: int,
    share_data: DocumentShareCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Share a document with specific users or everyone"""
    # Verify document exists and user has permission
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if user owns the document or has edit permission
    if document.uploader_id != current_user.id and current_user.role not in [
        "admin",
        "manager",
    ]:
        # Check if user has edit permission through existing shares
        existing_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_email == current_user.email,
                DocumentShare.permission_level == "edit",
            )
            .first()
        )
        if not existing_share:
            raise HTTPException(status_code=403, detail="Permission denied")

    # Validate permission level
    if share_data.permission_level not in ["view", "edit"]:
        raise HTTPException(
            status_code=400, detail="Permission level must be 'view' or 'edit'"
        )

    # Check for existing share
    existing_share = None
    if share_data.is_everyone:
        existing_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.is_everyone == True,
            )
            .first()
        )
    elif share_data.shared_with_email:
        existing_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_email == share_data.shared_with_email,
            )
            .first()
        )

    if existing_share:
        # Update existing share
        existing_share.permission_level = share_data.permission_level
        existing_share.expires_at = share_data.expires_at
        db.commit()
        db.refresh(existing_share)
        return existing_share

    # Create new share
    document_share = DocumentShare(
        document_id=document_id,
        shared_by_user_id=current_user.id,
        shared_with_email=share_data.shared_with_email
        if not share_data.is_everyone
        else None,
        permission_level=share_data.permission_level,
        is_everyone=share_data.is_everyone,
        expires_at=share_data.expires_at,
    )

    db.add(document_share)
    db.commit()
    db.refresh(document_share)

    return document_share


@router.get("/{document_id}/shares", response_model=list[DocumentShareOut])
async def get_document_shares(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all shares for a document"""
    # Verify document exists and user has permission
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if user owns the document or has permission
    if document.uploader_id != current_user.id and current_user.role not in [
        "admin",
        "manager",
    ]:
        # Check if user has any permission through existing shares
        user_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_email == current_user.email,
            )
            .first()
        )
        everyone_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.is_everyone == True,
            )
            .first()
        )
        if not user_share and not everyone_share:
            raise HTTPException(status_code=403, detail="Permission denied")

    shares = (
        db.query(DocumentShare).filter(DocumentShare.document_id == document_id).all()
    )
    return shares


@router.get("/{document_id}/access")
async def check_document_access(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Check user's access level to a document"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check access level
    access_level = "none"

    # Document owner has full access
    if document.uploader_id == current_user.id:
        access_level = "owner"
    # Admin/Manager have full access
    elif current_user.role in ["admin", "manager"]:
        access_level = "admin"
    else:
        # Check specific user shares
        user_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_email == current_user.email,
            )
            .first()
        )

        # Check everyone shares
        everyone_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.is_everyone == True,
            )
            .first()
        )

        # Determine highest permission level
        permissions = []
        if user_share:
            permissions.append(user_share.permission_level)
        if everyone_share:
            permissions.append(everyone_share.permission_level)

        if "edit" in permissions:
            access_level = "edit"
        elif "view" in permissions:
            access_level = "view"

    return {
        "document_id": document_id,
        "access_level": access_level,
        "can_view": access_level in ["view", "edit", "owner", "admin"],
        "can_edit": access_level in ["edit", "owner", "admin"],
        "can_share": access_level in ["owner", "admin"],
    }
