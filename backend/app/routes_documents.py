import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .export import get_export_service
from .models import (
    Document,
    DocumentContent,
    DocumentShare,
    Group,
    GroupMember,
    ProcessingJob,
    Redaction,
)
from .redaction import get_redaction_service
from .routes_auth import get_current_user
from .s3_client import generate_presigned_upload
from .schemas import (
    ContentDocCreate,
    ContentDocOut,
    DocumentCreate,
    DocumentOut,
    DocumentShareCreate,
    DocumentShareOut,
    DocumentShareUpdate,
    GroupCreate,
    GroupMemberAdd,
    GroupOut,
    PresignedUploadRequest,
    PresignedUploadResponse,
)
from .tasks import (
    convert_document_to_pdf_task,
    process_document_ocr,
    process_document_thumbnails,
    process_document_tiling,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _user_can_edit_document(db: Session, document_id: int, current_user) -> bool:
    """Check whether current_user has edit-level access to document."""
    from .models import DocumentShare

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return False
    if document.uploader_id == getattr(current_user, "id", None):
        return True
    if getattr(current_user, "role", "") in ["admin", "manager"]:
        return True
    # Check shares
    user_share = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_email == current_user.email,
            DocumentShare.permission_level == "edit",
        )
        .first()
    )
    everyone_share = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.document_id == document_id,
            DocumentShare.is_everyone == True,
            DocumentShare.permission_level == "edit",
        )
        .first()
    )
    return bool(user_share or everyone_share)


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


@router.post("/bulk-upload")
async def bulk_upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Bulk upload multiple documents with staggered processing"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded_docs = []

    for file in files:
        if not file.filename:
            continue

        try:
            # Read file content
            content = await file.read()

            # Upload to SOS first, with local fallback (same logic as single upload)
            from .config import get_settings
            from .s3_client import upload_to_s3

            settings = get_settings()

            if os.getenv("PYTEST_CURRENT_TEST"):
                # Test environment: save to local temp
                uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
                uploads_dir.mkdir(exist_ok=True)
                file_path = uploads_dir / file.filename
                with open(file_path, "wb") as buffer:
                    buffer.write(content)
            else:
                # Dev/Prod: try SOS first; if it fails, fallback to local
                try:
                    upload_key = f"uploads/{file.filename}"
                    upload_to_s3(
                        settings.s3_bucket_originals,
                        upload_key,
                        content,
                        file.content_type or "application/octet-stream",
                    )
                except Exception:
                    # Fallback to local storage
                    fallback_dir = (
                        (Path(__file__).resolve().parents[1] / "uploads")
                        if (os.getenv("APP_ENV", settings.env) == "dev")
                        else Path("/app/uploads")
                    )
                    try:
                        fallback_dir.mkdir(parents=True, exist_ok=True)
                        file_path = fallback_dir / file.filename
                        with open(file_path, "wb") as buffer:
                            buffer.write(content)
                    except Exception as le:
                        continue  # Skip this file if upload fails

            # Create document record
            document = Document(
                title=file.filename,
                description=f"Uploaded document: {file.filename}",
                source="Bulk Upload",
                language="en",
                uploader_id=1,  # TODO: Get from authenticated user
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            uploaded_docs.append(document)

        except Exception as e:
            print(f"Failed to upload {file.filename}: {e}")
            continue

    # Enqueue processing jobs for all uploaded documents with staggered delays
    for i, document in enumerate(uploaded_docs):
        # Add delay to prevent overwhelming the worker
        delay_seconds = i * 2  # 2 second delay between each document's processing
        _enqueue_processing_jobs_with_delay(document.id, db, delay_seconds)

    return {
        "success": True,
        "uploaded_count": len(uploaded_docs),
        "total_files": len(files),
        "documents": [{"id": doc.id, "title": doc.title} for doc in uploaded_docs],
    }


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

    # Read file content
    content = await file.read()

    # Upload to SOS first, with local fallback
    from .config import get_settings
    from .s3_client import upload_to_s3

    settings = get_settings()

    # In test environment, skip SOS and use local temp storage
    import os

    if os.getenv("PYTEST_CURRENT_TEST"):
        # Test environment: save to local temp
        uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        file_path = uploads_dir / file.filename
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        print(f"Test mode: stored locally: {file_path}")
    else:
        # Dev/Prod: try SOS first; if it fails, fallback to a writable local path
        try:
            upload_key = f"uploads/{file.filename}"
            upload_to_s3(
                settings.s3_bucket_originals,
                upload_key,
                content,
                file.content_type or "application/octet-stream",
            )
            print(f"Uploaded {file.filename} to SOS: {upload_key}")
        except Exception as e:
            # Fallback: in dev, write to project 'backend/uploads'; otherwise to container path
            fallback_dir = (
                (Path(__file__).resolve().parents[1] / "uploads")
                if (os.getenv("APP_ENV", settings.env) == "dev")
                else Path("/app/uploads")
            )
            try:
                fallback_dir.mkdir(parents=True, exist_ok=True)
                file_path = fallback_dir / file.filename
                with open(file_path, "wb") as buffer:
                    buffer.write(content)
                print(f"Failed to upload to SOS: {e}")
                print(f"Stored locally: {file_path}")
            except Exception as le:
                # If even fallback fails, surface a clear error
                raise HTTPException(status_code=500, detail=f"Upload failed: {le}")

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


# Create a markdown-authored document
@router.post("/content", response_model=ContentDocOut)
def create_content_document(
    payload: ContentDocCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Create a Document row for dashboard visibility
    doc = Document(
        title=payload.title,
        description=payload.title,
        source="Authored",
        language="en",
        uploader_id=current_user.id,
        status="completed",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    content = DocumentContent(document_id=doc.id, markdown=payload.markdown)
    db.add(content)
    db.commit()
    db.refresh(content)

    return ContentDocOut(
        id=content.id,
        document_id=doc.id,
        title=doc.title,
        markdown=content.markdown,
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


# Group management endpoints
@router.post("/groups", response_model=GroupOut)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    group = Group(name=payload.name, owner_user_id=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.post("/groups/{group_id}/members")
def add_group_member(
    group_id: int,
    payload: GroupMemberAdd,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    gm = GroupMember(group_id=group_id, email=payload.email)
    db.add(gm)
    db.commit()
    return {"success": True}


@router.get("/groups", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return (
        db.query(Group)
        .filter(
            (Group.owner_user_id == current_user.id) | (current_user.role == "admin")
        )
        .all()
    )


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
    _enqueue_processing_jobs_with_delay(document_id, db, 0)


def _enqueue_processing_jobs_with_delay(
    document_id: int, db: Session, delay_seconds: int = 0
):
    """Enqueue background processing jobs for a document with optional delay"""
    import os

    # In test environment, create job rows once and skip Celery dispatch to avoid sqlite flakiness
    if os.getenv("PYTEST_CURRENT_TEST"):
        batch = []
        for job_type in ["conversion", "tiling", "thumbnails", "ocr"]:
            batch.append(
                ProcessingJob(
                    document_id=document_id,
                    job_type=job_type,
                    status="queued",
                    progress=0,
                )
            )
        db.add_all(batch)
        db.commit()
        return

    job_types = ["conversion", "tiling", "thumbnails", "ocr"]

    for i, job_type in enumerate(job_types):
        # Create job record
        job = ProcessingJob(
            document_id=document_id,
            job_type=job_type,
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Calculate delay: conversion starts first, others wait for conversion to complete
        document = db.query(Document).filter(Document.id == document_id).first()
        needs_conversion = not document.title.lower().endswith(".pdf")

        if job_type == "conversion":
            task_delay = delay_seconds
        else:
            # If document needs conversion, other jobs wait longer to ensure conversion completes
            base_delay = (
                15 if needs_conversion else 2
            )  # 15 seconds for conversion, 2 for PDFs
            task_delay = (
                delay_seconds + base_delay + (i * 2)
            )  # Additional stagger between job types

        try:
            if job_type == "conversion":
                if task_delay > 0:
                    task = convert_document_to_pdf_task.apply_async(
                        args=[document_id, job.id], countdown=task_delay
                    )
                else:
                    task = convert_document_to_pdf_task.delay(document_id, job.id)
            elif job_type == "tiling":
                if task_delay > 0:
                    task = process_document_tiling.apply_async(
                        args=[document_id, job.id], countdown=task_delay
                    )
                else:
                    task = process_document_tiling.delay(document_id, job.id)
            elif job_type == "thumbnails":
                if task_delay > 0:
                    task = process_document_thumbnails.apply_async(
                        args=[document_id, job.id], countdown=task_delay
                    )
                else:
                    task = process_document_thumbnails.delay(document_id, job.id)
            elif job_type == "ocr":
                if task_delay > 0:
                    task = process_document_ocr.apply_async(
                        args=[document_id, job.id], countdown=task_delay
                    )
                else:
                    task = process_document_ocr.delay(document_id, job.id)

            # Update job with Celery task ID
            job.celery_task_id = task.id
            db.commit()

        except Exception as e:
            # If task dispatch fails, mark job as failed and log the error
            print(f"Failed to dispatch {job_type} task for document {document_id}: {e}")
            job.status = "failed"
            job.error_message = f"Failed to dispatch task: {str(e)}"
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


@router.delete("/{document_id}/redactions/{redaction_id}")
async def delete_redaction(
    document_id: int,
    redaction_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .models import Redaction

    red = (
        db.query(Redaction)
        .filter(Redaction.id == redaction_id, Redaction.document_id == document_id)
        .first()
    )
    if not red:
        raise HTTPException(status_code=404, detail="Redaction not found")
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Allow deletion if:
    #  - user created the redaction, OR
    #  - user is admin/manager, OR
    #  - user uploaded the document, OR
    #  - user has edit access via sharing
    if not (
        red.user_id == current_user.id
        or current_user.role in ["admin", "manager"]
        or doc.uploader_id == current_user.id
        or _user_can_edit_document(db, document_id, current_user)
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    print(
        f"[REDACTIONS] delete_redaction: doc={document_id}, id={redaction_id}, user={getattr(current_user, 'id', None)}"
    )
    db.delete(red)
    db.commit()
    return {"success": True}


# Removed duplicate redaction endpoint - using the database one below


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

    # Always return a structured result for client scripts, even on failure
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
    return result


@router.get("/{document_id}/tiles/page_{page_number}.dzi_files/{level}/{x}_{y}.webp")
@router.head("/{document_id}/tiles/page_{page_number}.dzi_files/{level}/{x}_{y}.webp")
async def get_document_tile_dzi(
    document_id: int, page_number: int, level: int, x: int, y: int, db: Session = Depends(get_db)
):
    """Serve individual tile file for OpenSeadragon DZI viewer"""
    import os

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # For DZI, level 0 corresponds to our tile structure
    local_path = f"/srv/processed/tiles/{document_id}/page_{page_number}/tile_{x}_{y}.webp"
    
    if os.path.exists(local_path):
        try:
            with open(local_path, "rb") as f:
                tile_data = f.read()
            return Response(content=tile_data, media_type="image/webp")
        except Exception:
            pass

    # If tile not found, return 404
    raise HTTPException(status_code=404, detail="Tile not found")


@router.get("/{document_id}/tiles/page_{page_number}/tile_{x}_{y}.webp")
@router.head("/{document_id}/tiles/page_{page_number}/tile_{x}_{y}.webp")
async def get_document_tile(
    document_id: int, page_number: int, x: int, y: int, db: Session = Depends(get_db)
):
    """Serve individual tile file for OpenSeadragon viewer"""
    import os

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Try to serve from S3 first
    try:
        from .s3_client import download_from_s3

        settings = get_settings()
        tile_key = f"tiles/{document_id}/page_{page_number}/tile_{x}_{y}.webp"
        tile_data = download_from_s3(settings.s3_bucket_tiles, tile_key)
        return Response(content=tile_data, media_type="image/webp")
    except Exception:
        pass

    # Fallback to local files
    local_path = (
        f"/srv/processed/tiles/{document_id}/page_{page_number}/tile_{x}_{y}.webp"
    )

    if os.path.exists(local_path):
        try:
            with open(local_path, "rb") as f:
                tile_data = f.read()
            return Response(content=tile_data, media_type="image/webp")
        except Exception:
            pass

    # If tile not found, return 404
    raise HTTPException(status_code=404, detail="Tile not found")


@router.get("/{document_id}/tiles/page_{page_number}.dzi")
async def get_document_dzi(
    document_id: int, page_number: int, db: Session = Depends(get_db)
):
    """Serve Deep Zoom Image descriptor for OpenSeadragon"""
    from fastapi.responses import Response
    import os

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if tiles exist for this document/page
    tile_dir = f"/srv/processed/tiles/{document_id}/page_{page_number}"
    if not os.path.exists(tile_dir):
        raise HTTPException(status_code=404, detail="Tiles not found")

    # Return DZI XML descriptor
    dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image TileSize="256" Overlap="1" Format="webp" xmlns="http://schemas.microsoft.com/deepzoom/2008">
    <Size Width="2550" Height="3300"/>
</Image>'''
    
    return Response(content=dzi_xml, media_type="application/xml")


@router.get("/{document_id}/tiles/page_{page_number}/")
async def get_document_tiles(
    document_id: int, page_number: int, db: Session = Depends(get_db)
):
    """Serve document tiles configuration for OpenSeadragon viewer"""
    import os

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if tiles exist for this document/page
    tile_dir = f"/srv/processed/tiles/{document_id}/page_{page_number}"
    if not os.path.exists(tile_dir):
        # Fallback to thumbnail if no tiles exist
        return {
            "type": "image",
            "url": f"/api/documents/{document_id}/thumbnail/{page_number}",
            "width": 2550,
            "height": 3300,
            "tileSize": 256,
            "overlap": 1,
        }

    # Return DZI tile source URL
    return f"/api/documents/{document_id}/tiles/page_{page_number}.dzi"


@router.get("/{document_id}/thumbnail/{page_number}")
@router.head("/{document_id}/thumbnail/{page_number}")
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

    # Try to serve from SOS first
    try:
        from .s3_client import download_from_s3

        settings = get_settings()

        # Try high-res preview from SOS
        try:
            preview_key = f"previews/{document_id}/page_{page_number}.png"
            preview_data = download_from_s3(settings.s3_bucket_thumbnails, preview_key)
            return Response(content=preview_data, media_type="image/png")
        except:
            pass

        # Try thumbnail from SOS
        try:
            thumb_key = f"thumbnails/{document_id}/page_{page_number}.webp"
            thumbnail_data = download_from_s3(settings.s3_bucket_thumbnails, thumb_key)
            return Response(content=thumbnail_data, media_type="image/webp")
        except:
            pass
    except:
        pass

    # Fallback to local files (shared volume)
    preview_path = f"/srv/processed/previews/{document_id}/page_{page_number}.png"
    if os.path.exists(preview_path):
        with open(preview_path, "rb") as f:
            preview_data = f.read()
        return Response(content=preview_data, media_type="image/png")

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


@router.get("/{document_id}/file-test")
async def test_file_endpoint(document_id: int):
    """Test endpoint to verify routing works"""
    return {
        "message": f"File endpoint works for document {document_id}",
        "status": "success",
    }


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: int, db: Session = Depends(get_db), request: Request = None
):
    """Serve the original document file for download"""
    import os

    from fastapi.responses import FileResponse, Response

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Try to serve from S3 first
    try:
        from .s3_client import download_from_s3

        settings = get_settings()

        # Try common S3 key variants
        s3_keys = [
            f"uploads/{document.title}",
            f"{document_id}/{document.title}",
        ]
        last_err = None
        for key in s3_keys:
            try:
                file_data = download_from_s3(settings.s3_bucket_originals, key)
                # Determine content type based on file extension
                content_type = "application/pdf"
                if document.title.lower().endswith((".png", ".jpg", ".jpeg")):
                    content_type = f"image/{document.title.split('.')[-1].lower()}"
                elif document.title.lower().endswith(".txt"):
                    content_type = "text/plain"

                print(f"[DOWNLOAD] Served from S3 key={key}")
                return Response(
                    content=file_data,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f'attachment; filename="{document.title}"'
                    },
                )
            except Exception as se:
                last_err = se
                print(f"[DOWNLOAD] S3 miss key={key}: {se}")
        if last_err:
            raise last_err
    except Exception as e:
        print(
            f"[DOWNLOAD] Failed to download from S3 for document={document_id}, title={getattr(document, 'title', None)}: {e}"
        )
        pass

    # Fallback to local file (shared volume) - try multiple possible paths, include container path
    candidate_paths = [
        f"/app/uploads/{document_id}_{document.title}",
        f"/app/uploads/{document.title}",
        f"/app/uploads/{document_id}_{document.title}",
        f"/app/uploads/{document.title}",
        f"/srv/backend/uploads/{document_id}_{document.title}",
        f"/srv/backend/uploads/{document.title}",
        f"/srv/uploads/{document_id}_{document.title}",
        f"/srv/uploads/{document.title}",
        f"uploads/{document_id}_{document.title}",
        f"uploads/{document.title}",
    ]

    for local_path in candidate_paths:
        if os.path.exists(local_path):
            print(f"[DOWNLOAD] Found document file at: {local_path}")
            return FileResponse(
                path=local_path,
                filename=document.title,
                media_type="application/octet-stream",
            )

    # If file not found anywhere, log the attempted paths for debugging
    client_ip = None
    try:
        client_ip = request.client.host if request else None
    except Exception:
        client_ip = None
    print(
        f"[DOWNLOAD] Document file not found for document={document_id}, title={document.title}, client={client_ip}. Tried paths: {candidate_paths}"
    )
    raise HTTPException(status_code=404, detail="Document file not found")


@router.get("/{document_id}/download")
async def download_document(document_id: int, db: Session = Depends(get_db)):
    """Download document with redactions burned in."""
    import io
    import os

    import fitz  # PyMuPDF
    from fastapi.responses import Response
    from PIL import Image, ImageDraw

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if there are any redactions
    redactions = db.query(Redaction).filter(Redaction.document_id == document_id).all()

    # If no redactions, just redirect to original file
    if not redactions:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"/api/documents/{document_id}/file", status_code=302
        )

    # Get original document file
    original_file_paths = [
        f"/app/uploads/{document.title}",
        f"/app/uploads/{document_id}_{document.title}",
        f"uploads/{document.title}",  # Fallback paths
        f"uploads/{document_id}_{document.title}",
    ]

    original_data = None
    for path in original_file_paths:
        if os.path.exists(path):
            with open(path, "rb") as f:
                original_data = f.read()
            break

    if not original_data:
        # No original file found, fallback to regular download
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"/api/documents/{document_id}/file", status_code=302
        )

    try:
        # Create redacted PDF
        pdf_doc = fitz.open(stream=original_data, filetype="pdf")

        # Group redactions by page
        redactions_by_page = {}
        for r in redactions:
            page_num = r.page_number
            if page_num not in redactions_by_page:
                redactions_by_page[page_num] = []
            redactions_by_page[page_num].append(r)

        # Apply redactions to each page
        for page_num in range(len(pdf_doc)):
            if page_num in redactions_by_page:
                page = pdf_doc[page_num]

                # Get page dimensions
                rect = page.rect
                page_width = rect.width
                page_height = rect.height

                # Get viewer image dimensions for pixel-perfect coordinate scaling
                # The redaction coordinates are stored relative to the viewer's image dimensions.
                # These dimensions match the thumbnail/preview image served to the browser.
                # For document 135, we empirically determined these are 2550 x 3300 pixels.
                #
                # To update these dimensions for other documents, check:
                # curl -s "https://community.haqnow.com/api/documents/{id}/thumbnail/0" | file -
                # This should show: "PNG image data, WIDTH x HEIGHT"
                viewer_width = 2550.0
                viewer_height = 3300.0

                print(
                    f"[DOWNLOAD] Using viewer dimensions: {viewer_width} x {viewer_height} for coordinate scaling"
                )

                # Apply redactions as black rectangles
                for redaction in redactions_by_page[page_num]:
                    # Scale coordinates from viewer image pixels to PDF points
                    x1 = (redaction.x_start / viewer_width) * page_width
                    y1 = (redaction.y_start / viewer_height) * page_height
                    x2 = (redaction.x_end / viewer_width) * page_width
                    y2 = (redaction.y_end / viewer_height) * page_height

                    # Create redaction rectangle
                    redact_rect = fitz.Rect(
                        min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
                    )

                    # Add redaction annotation
                    redact_annot = page.add_redact_annot(redact_rect)
                    redact_annot.set_colors({"fill": [0, 0, 0]})  # Black fill

                # Apply all redactions on this page
                page.apply_redactions()

        # Generate the redacted PDF bytes
        redacted_pdf_bytes = pdf_doc.tobytes()
        pdf_doc.close()

        # Return the redacted PDF
        return Response(
            content=redacted_pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="redacted_{document.title}"'
            },
        )

    except Exception as e:
        print(
            f"[DOWNLOAD] Failed to create redacted PDF for document {document_id}: {e}"
        )
        # Fallback to original file
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"/api/documents/{document_id}/file", status_code=302
        )


@router.get("/{document_id}/exports/{filename}")
async def get_exported_file(document_id: int, filename: str):
    """Serve generated export files from SOS or local fallback."""
    # Try S3 first
    try:
        from .s3_client import download_from_s3

        settings = get_settings()
        key = f"exports/{document_id}/{filename}"
        data = download_from_s3(settings.s3_bucket_exports, key)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception:
        pass

    # Local fallback
    local_path = f"/app/processed/exports/{document_id}/{filename}"
    if os.path.exists(local_path):
        return FileResponse(
            path=local_path, filename=filename, media_type="application/pdf"
        )
    raise HTTPException(status_code=404, detail="Export file not found")


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

    print(
        f"[COMMENTS] add_comment: doc={document_id}, user={getattr(current_user, 'id', None)}, page={comment.page_number}, x={comment.x_position}, y={comment.y_position}"
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


@router.put("/{document_id}/comments/{comment_id}")
async def update_comment(
    document_id: int,
    comment_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .models import Comment

    comment = (
        db.query(Comment)
        .filter(Comment.id == comment_id, Comment.document_id == document_id)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    # Only owner or users with edit rights can update
    if comment.user_id != current_user.id and not _user_can_edit_document(
        db, document_id, current_user
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    if "content" in payload:
        comment.content = str(payload["content"])[:2000]
    if "x_position" in payload:
        comment.x_position = float(payload["x_position"])
    if "y_position" in payload:
        comment.y_position = float(payload["y_position"])
    print(
        f"[COMMENTS] update_comment: doc={document_id}, comment={comment_id}, user={getattr(current_user, 'id', None)}, payload_keys={list(payload.keys())}"
    )
    db.commit()
    db.refresh(comment)
    return {
        "id": comment.id,
        "content": comment.content,
        "page_number": comment.page_number,
        "x_position": comment.x_position,
        "y_position": comment.y_position,
        "updated_at": comment.updated_at.isoformat(),
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


@router.delete("/{document_id}/comments/{comment_id}")
async def delete_comment(
    document_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .models import Comment

    comment = (
        db.query(Comment)
        .filter(Comment.id == comment_id, Comment.document_id == document_id)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Allow owner, admin, or uploader to delete
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if (
        comment.user_id != current_user.id
        and current_user.role not in ["admin", "manager"]
        and doc.uploader_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not allowed")

    print(
        f"[COMMENTS] delete_comment: doc={document_id}, comment={comment_id}, user={getattr(current_user, 'id', None)}"
    )
    db.delete(comment)
    db.commit()
    return {"success": True}


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

    print(
        f"[REDACTIONS] add_redaction: doc={document_id}, user={getattr(current_user, 'id', None)}, page={redaction.page_number}, x1={redaction.x_start}, y1={redaction.y_start}, x2={redaction.x_end}, y2={redaction.y_end}"
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


@router.put("/{document_id}/redactions/{redaction_id}")
async def update_redaction(
    document_id: int,
    redaction_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .models import Redaction

    red = (
        db.query(Redaction)
        .filter(Redaction.id == redaction_id, Redaction.document_id == document_id)
        .first()
    )
    if not red:
        raise HTTPException(status_code=404, detail="Redaction not found")
    if red.user_id != current_user.id and not _user_can_edit_document(
        db, document_id, current_user
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    # Update pixel coordinates
    for key in ["x_start", "y_start", "x_end", "y_end"]:
        if key in payload:
            setattr(red, key, float(payload[key]))
    if "reason" in payload:
        red.reason = str(payload["reason"])[:500]
    db.commit()
    db.refresh(red)
    return {
        "id": red.id,
        "page_number": red.page_number,
        "x_start": red.x_start,
        "y_start": red.y_start,
        "x_end": red.x_end,
        "y_end": red.y_end,
        "reason": red.reason,
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

    # Group sharing support: if group_id provided, expand to individual emails at create-time
    emails_from_group: list[str] = []
    if getattr(share_data, "group_id", None):
        group = db.query(Group).filter(Group.id == share_data.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
        emails_from_group = [m.email for m in members]

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

    # Create new share(s)
    created_share = None
    if emails_from_group:
        for email in emails_from_group:
            s = DocumentShare(
                document_id=document_id,
                shared_by_user_id=current_user.id,
                shared_with_email=email,
                permission_level=share_data.permission_level,
                is_everyone=False,
                expires_at=share_data.expires_at,
            )
            db.add(s)
            created_share = s
        db.commit()
        if created_share:
            db.refresh(created_share)
        return created_share
    else:
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
    return [
        DocumentShareOut(
            id=s.id,
            document_id=s.document_id,
            shared_by_user_id=s.shared_by_user_id,
            shared_with_email=s.shared_with_email,
            permission_level=s.permission_level,
            is_everyone=s.is_everyone,
            expires_at=s.expires_at,
            created_at=s.created_at,
            updated_at=s.updated_at,
            group_id=None,
        )
        for s in shares
    ]


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Trigger reprocessing of a document"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check permissions
    if not _user_can_edit_document(db, document_id, current_user):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Clear existing jobs for this document
    db.query(ProcessingJob).filter(ProcessingJob.document_id == document_id).delete()
    db.commit()

    # Enqueue new processing jobs
    _enqueue_processing_jobs(document_id, db)

    return {"message": "Document reprocessing started", "document_id": document_id}


@router.get("/{document_id}/debug")
async def debug_document_data(document_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to check document data"""
    from .models import Comment, Redaction

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    comments = db.query(Comment).filter(Comment.document_id == document_id).all()
    redactions = db.query(Redaction).filter(Redaction.document_id == document_id).all()

    return {
        "document": {
            "id": document.id,
            "title": document.title,
            "status": document.status,
        },
        "comments": [
            {
                "id": c.id,
                "content": c.content,
                "page_number": c.page_number,
                "x_position": c.x_position,
                "y_position": c.y_position,
            }
            for c in comments
        ],
        "redactions": [
            {
                "id": r.id,
                "page_number": r.page_number,
                "x_start": r.x_start,
                "y_start": r.y_start,
                "x_end": r.x_end,
                "y_end": r.y_end,
                "reason": r.reason,
            }
            for r in redactions
        ],
    }


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
