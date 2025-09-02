from datetime import datetime

from celery import current_task
from sqlalchemy.orm import Session

from .celery_app import celery_app
from .config import get_settings
from .conversion import convert_document_to_pdf
from .db import SessionLocal
from .models import Document, ProcessingJob, DocumentText
from .processing import (
    extract_text_from_image,
    extract_text_from_pdf,
    generate_single_page_image,
    generate_thumbnail,
    get_document_info,
    rasterize_image,
    rasterize_pdf_pages,
)
from .s3_client import download_from_s3, upload_to_s3, get_s3_client


def get_local_processed_path(subdir: str) -> str:
    """Get local path for processed files, works in both dev and production"""
    import os

    if os.path.exists("/srv"):
        return f"/srv/processed/{subdir}"
    else:
        # Local development
        base_dir = os.path.dirname(os.path.abspath(__file__))
        local_processed = os.path.join(base_dir, "..", "processed", subdir)
        return os.path.normpath(local_processed)


def get_db_session() -> Session:
    """Get database session for Celery tasks"""
    return SessionLocal()


def _update_document_status_if_complete(document_id: int, db: Session):
    """Check if all processing jobs are complete and update document status"""
    jobs = (
        db.query(ProcessingJob).filter(ProcessingJob.document_id == document_id).all()
    )

    if not jobs:
        return

    all_completed = all(job.status == "completed" for job in jobs)
    has_failed = any(job.status == "failed" for job in jobs)

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return

    if has_failed:
        if document.status != "error":
            document.status = "error"
            print(
                f"Updated document {document_id} status to 'error' due to failed jobs"
            )
            db.commit()
    elif all_completed:
        if document.status != "ready":
            document.status = "ready"
            print(
                f"Updated document {document_id} status to 'ready' - all jobs completed"
            )
            db.commit()


def _load_processing_file_bytes(settings, document: Document) -> bytes:
    """Load the appropriate file for processing (always prefer converted PDF if available)."""

    # For non-PDF documents, try to load the converted PDF first
    original_extension = (
        document.title.split(".")[-1].lower() if "." in document.title else ""
    )
    if original_extension not in ["pdf"]:
        # Try to load converted PDF from S3 (conversion task uploads here)
        try:
            s3 = get_s3_client()
            prefix = f"documents/{document.id}/"
            resp = s3.list_objects_v2(Bucket=settings.s3_bucket_originals, Prefix=prefix)
            contents = resp.get("Contents", [])
            pdf_keys = [obj["Key"] for obj in contents if obj["Key"].lower().endswith(".pdf")]
            if pdf_keys:
                # Prefer most recent
                pdf_keys.sort()
                key = pdf_keys[-1]
                data = download_from_s3(settings.s3_bucket_originals, key)
                if len(data) > 1000:
                    print(f"Using converted PDF from S3: {key} ({len(data)} bytes)")
                    return data
        except Exception as e:
            print(f"S3 lookup for converted PDF failed or not found: {e}")

        # Generate possible converted PDF names
        base_name = (
            document.title.rsplit(".", 1)[0]
            if "." in document.title
            else document.title
        )
        converted_filenames = [
            f"{document.id}_{base_name}.pdf",  # Standard pattern
            f"{base_name}.pdf",  # Simple pattern
        ]

        converted_paths = []
        for filename in converted_filenames:
            converted_paths.extend(
                [
                    f"/srv/uploads/{filename}",
                    f"/app/uploads/{filename}",
                    f"uploads/{filename}",
                ]
            )

        for path in converted_paths:
            try:
                with open(path, "rb") as f:
                    file_data = f.read()
                    if len(file_data) > 1000:  # Ensure it's not a tiny placeholder
                        print(f"Using converted PDF: {path} ({len(file_data)} bytes)")
                        return file_data
                    else:
                        print(
                            f"Skipping small converted PDF: {path} ({len(file_data)} bytes)"
                        )
            except FileNotFoundError:
                continue

        # If no converted PDF found, try to convert on-the-fly
        print(f"No converted PDF found for {document.title}, attempting conversion...")
        try:
            from .conversion import convert_document_to_pdf

            original_data = _load_original_file_bytes(settings, document)
            print(f"Loaded original file: {len(original_data)} bytes")

            if len(original_data) > 1000:  # Ensure we have real content
                pdf_data, pdf_filename = convert_document_to_pdf(
                    original_data, document.title
                )
                print(f"Converted to PDF: {len(pdf_data)} bytes")
                return pdf_data
            else:
                print("Original file too small, using as-is")
        except Exception as e:
            print(f"On-the-fly conversion failed: {e}")

        # If conversion fails, fall back to original loading
        print(
            f"Warning: Conversion failed for {document.title}, using original file loading"
        )

    # Use original file loading for PDFs and as fallback
    return _load_original_file_bytes(settings, document)


def _load_original_file_bytes(settings, document: Document) -> bytes:
    """Best-effort loader for original uploaded file bytes.

    Load order:
    1) S3 bucket `settings.s3_bucket_originals` at key `uploads/{document.title}`
    2) Local uploads within project layout used by API/worker: `/srv/backend/uploads/{filename}`
    3) Alternate local paths that may be used in dev: `/srv/uploads/{filename}`, `uploads/{filename}`
    4) Try with different extensions if title has been changed during conversion
    5) As a last resort, synthesize a simple one-page PDF indicating a placeholder
    """

    # Generate possible filenames - both current title and possible original extensions
    possible_filenames = [document.title]

    # If document title ends with .pdf but might have been converted, try common office extensions
    if document.title.lower().endswith(".pdf"):
        base_name = document.title.rsplit(".", 1)[0]
        # Try common document extensions
        for ext in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"]:
            possible_filenames.append(f"{base_name}{ext}")

    # 1) Try S3 with all possible filenames
    for filename in possible_filenames:
        original_key = f"uploads/{filename}"
        try:
            file_data = download_from_s3(settings.s3_bucket_originals, original_key)
            if len(file_data) > 100:  # Ensure we got real content
                print(
                    f"Found original file in S3: {original_key} ({len(file_data)} bytes)"
                )
                return file_data
        except Exception:
            continue

    # 2) and 3) Try local filesystem variants with all possible filenames
    import os

    for filename in possible_filenames:
        candidate_paths = [
            f"/app/uploads/{filename}",  # shared volume path
            f"/srv/backend/uploads/{filename}",  # container path when running `cd backend`
            f"/srv/uploads/{filename}",  # alternate mount path
            f"uploads/{filename}",  # relative path in dev
        ]
        for path in candidate_paths:
            if os.path.exists(path):
                try:
                    file_size = os.path.getsize(path)
                    if file_size > 100:  # Ensure it's not empty
                        with open(path, "rb") as f:
                            file_data = f.read()
                        print(
                            f"Found original file locally: {path} ({len(file_data)} bytes)"
                        )
                        return file_data
                except Exception:
                    continue

    # 4) Last resort: create a minimal placeholder PDF
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (100, 100), f"Uploaded file not found; placeholder for: {document.title}"
    )
    data = doc.tobytes()
    doc.close()
    return data


@celery_app.task(bind=True)
def process_document_tiling(self, document_id: int, job_id: int):
    """Generate tiles for a document"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            print(f"WARN: Job {job_id} not found; marking gracefully and returning")
            return {"status": "skipped", "reason": "job_missing"}

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Load appropriate file bytes (converted PDF if available, original otherwise)
        file_data = _load_processing_file_bytes(settings, document)

        # Ensure we operate on valid PDF bytes to avoid 'Failed to open stream'
        def _ensure_pdf_bytes(data: bytes) -> bytes:
            try:
                import fitz
                doc_try = fitz.open(stream=data, filetype="pdf")
                doc_try.close()
                return data
            except Exception:
                # Try converting original bytes inline
                try:
                    original_bytes = _load_original_file_bytes(settings, document)
                    pdf_bytes, _ = convert_document_to_pdf(original_bytes, document.title)
                    return pdf_bytes
                except Exception as conv_err:
                    print(f"Tiling inline conversion failed, using placeholder PDF: {conv_err}")
                    import fitz
                    doc_new = fitz.open()
                    page = doc_new.new_page()
                    page.insert_text((72, 72), f"Placeholder for: {document.title}")
                    out = doc_new.tobytes()
                    doc_new.close()
                    return out

        file_data = _ensure_pdf_bytes(file_data)

        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})

        # Rasterize pages - all documents should be PDFs after conversion
        # Only use image rasterization for formats that definitely can't be converted to PDF
        if document.title.lower().endswith(
            (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".txt")
        ):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            # For pure image files that weren't converted, try PDF first (in case they were converted)
            try:
                pages = rasterize_pdf_pages(file_data, dpi=300)
            except Exception:
                # Fallback to image processing
                pages = rasterize_image(file_data, dpi=300)

        job.progress = 50
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 50})

        # Generate single 300 DPI image for each page
        total_pages = len(pages) if pages is not None else 0
        for i, (page_num, page_image) in enumerate(pages):
            # Generate single high-quality image instead of tiles
            single_image_data = generate_single_page_image(page_image, dpi=300)

            # Upload single page image to S3 or store locally
            page_key = f"pages/{document_id}/page_{page_num}.webp"
            try:
                upload_to_s3(
                    settings.s3_bucket_tiles, page_key, single_image_data, "image/webp"
                )
            except Exception as e:
                # Store locally if S3 is not available
                import os

                local_dir = get_local_processed_path(f"pages/{document_id}")
                os.makedirs(local_dir, exist_ok=True)
                local_path = f"{local_dir}/page_{page_num}.webp"
                with open(local_path, "wb") as f:
                    f.write(single_image_data)
                print(f"Failed to upload page image to SOS: {e}")
                print(f"Stored page image locally: {local_path}")

            # Update progress
            progress = 50 + (40 * (i + 1) // max(total_pages, 1))
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})

        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        # Check if all jobs are complete and update document status
        _update_document_status_if_complete(document_id, db)

        return {"status": "completed", "document_id": document_id, "pages": total_pages}

    except Exception as e:
        # Mark as failed with better error isolation
        if "job" in locals():
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
            db.commit()
            
            # Update document status if all jobs are complete (including failed ones)
            _update_document_status_if_complete(document_id, db)
        
        # Don't re-raise for file corruption errors - let other tasks continue
        if "Failed to open stream" in str(e) or "FileDataError" in str(e):
            print(f"Skipping corrupted file for document {document_id} - continuing with other tasks")
            return {"status": "failed", "error": str(e)}
        
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def process_document_thumbnails(self, document_id: int, job_id: int):
    """Generate thumbnails for a document"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            print(f"WARN: Job {job_id} not found; marking gracefully and returning")
            return {"status": "skipped", "reason": "job_missing"}

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Load appropriate file bytes (converted PDF if available, original otherwise)
        file_data = _load_processing_file_bytes(settings, document)

        # Ensure we operate on valid PDF bytes to avoid 'Failed to open stream'
        def _ensure_pdf_bytes(data: bytes) -> bytes:
            try:
                import fitz
                doc_try = fitz.open(stream=data, filetype="pdf")
                doc_try.close()
                return data
            except Exception:
                # Try converting original bytes inline
                try:
                    original_bytes = _load_original_file_bytes(settings, document)
                    pdf_bytes, _ = convert_document_to_pdf(original_bytes, document.title)
                    return pdf_bytes
                except Exception as conv_err:
                    print(f"Thumbnails inline conversion failed, using placeholder PDF: {conv_err}")
                    import fitz
                    doc_new = fitz.open()
                    page = doc_new.new_page()
                    page.insert_text((72, 72), f"Placeholder for: {document.title}")
                    out = doc_new.tobytes()
                    doc_new.close()
                    return out

        file_data = _ensure_pdf_bytes(file_data)

        job.progress = 25
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 25})

        # Rasterize pages - all documents should be PDFs after conversion
        # Only use image rasterization for formats that definitely can't be converted to PDF
        if document.title.lower().endswith(
            (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".txt")
        ):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            # For pure image files that weren't converted, try PDF first (in case they were converted)
            try:
                pages = rasterize_pdf_pages(file_data, dpi=300)
            except Exception:
                # Fallback to image processing
                pages = rasterize_image(file_data, dpi=300)

        job.progress = 50
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 50})

        # Generate thumbnails and high-res previews for each page
        total_pages = len(pages) if pages is not None else 0
        for i, (page_num, page_image) in enumerate(pages):
            thumbnail = generate_thumbnail(page_image, max_size=(200, 300))

            # Upload thumbnail to S3 or store locally
            thumb_key = f"thumbnails/{document_id}/page_{page_num}.webp"
            try:
                upload_to_s3(
                    settings.s3_bucket_thumbnails, thumb_key, thumbnail, "image/webp"
                )
            except Exception as e:
                # Store locally if S3 is not available
                import os

                local_dir = get_local_processed_path(f"thumbnails/{document_id}")
                os.makedirs(local_dir, exist_ok=True)
                local_path = f"{local_dir}/page_{page_num}.webp"
                with open(local_path, "wb") as f:
                    f.write(thumbnail)
                print(f"Failed to upload thumbnail to SOS: {e}")
                print(f"Stored thumbnail locally: {local_path}")

            # Also persist a full-quality preview (PNG) for 300 DPI viewing
            try:
                import os

                preview_dir = get_local_processed_path(f"previews/{document_id}")
                os.makedirs(preview_dir, exist_ok=True)
                preview_path = f"{preview_dir}/page_{page_num}.png"
                with open(preview_path, "wb") as f:
                    f.write(page_image)
            except Exception as e:
                print(f"Failed to store preview image: {e}")

            # Update progress
            progress = 50 + (50 * (i + 1) // max(total_pages, 1))
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})

        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        # Check if all jobs are complete and update document status
        _update_document_status_if_complete(document_id, db)

        return {"status": "completed", "document_id": document_id, "pages": total_pages}

    except Exception as e:
        # Mark as failed with better error isolation
        if "job" in locals():
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
            db.commit()
            
            # Update document status if all jobs are complete (including failed ones)
            _update_document_status_if_complete(document_id, db)
        
        # Don't re-raise for file corruption errors - let other tasks continue
        if "Failed to open stream" in str(e) or "FileDataError" in str(e):
            print(f"Skipping corrupted file for document {document_id} - continuing with other tasks")
            return {"status": "failed", "error": str(e)}
        
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    time_limit=20 * 60,  # 20 minutes max for OCR
    soft_time_limit=18 * 60,  # 18 minutes soft limit
)
def process_document_ocr(self, document_id: int, job_id: int):
    """Perform OCR on a document"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            print(f"WARN: Job {job_id} not found; marking gracefully and returning")
            return {"status": "skipped", "reason": "job_missing"}

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Load appropriate file bytes (converted PDF if available, original otherwise)
        file_data = _load_processing_file_bytes(settings, document)

        # Ensure OCR operates on a valid PDF. If the source is not a PDF or bytes are not a
        # valid PDF stream (e.g., office doc bytes), attempt inline conversion. As a last
        # resort, synthesize a minimal placeholder PDF to keep pipeline stable.
        def _ensure_pdf_bytes(data: bytes) -> bytes:
            try:
                import fitz

                doc_try = fitz.open(stream=data, filetype="pdf")
                doc_try.close()
                return data
            except Exception:
                # Try converting original bytes inline
                try:
                    original_bytes = _load_original_file_bytes(settings, document)
                    pdf_bytes, pdf_filename = convert_document_to_pdf(
                        original_bytes, document.title
                    )
                    return pdf_bytes
                except Exception as conv_err:
                    print(f"OCR inline conversion failed, using placeholder PDF: {conv_err}")
                    # Create a minimal one-page placeholder PDF
                    import fitz

                    doc_new = fitz.open()
                    page = doc_new.new_page()
                    msg = f"Placeholder for unsupported file: {document.title}"
                    page.insert_text((72, 72), msg)
                    bytes_out = doc_new.tobytes()
                    doc_new.close()
                    return bytes_out

        file_data = _ensure_pdf_bytes(file_data)

        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})

        # Prefer fast PDF text layer extraction; fall back to OCR on images
        extracted_text = []
        used_pdf_layer = False
        try:
            pdf_text_pages = extract_text_from_pdf(file_data)
            # Only accept PDF text layer if it contains any real text
            if pdf_text_pages and any((t or "").strip() for _, t in pdf_text_pages):
                for page_num, text in pdf_text_pages:
                    extracted_text.append({"page": page_num, "text": text})
                used_pdf_layer = True
        except Exception as e:
            print(f"PDF text extraction error: {e}")

        # If no usable PDF text-layer, or text is too short, perform OCR
        if (not used_pdf_layer) or (sum(len((p.get("text") or "").strip()) for p in extracted_text) < 100):
            # Rasterize and OCR
            if document.title.lower().endswith(
                (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".txt")
            ):
                pages = rasterize_pdf_pages(file_data, dpi=150)  # Lower DPI for faster OCR
            else:
                # For pure image files that weren't converted, try PDF first (in case they were converted)
                try:
                    pages = rasterize_pdf_pages(file_data, dpi=150)  # Lower DPI for faster OCR
                except Exception:
                    # Fallback to image processing
                    pages = rasterize_image(file_data, dpi=150)  # Lower DPI for faster OCR

            job.progress = 40
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": 40})

            total_pages = len(pages) if pages is not None else 0
            for i, (page_num, page_image) in enumerate(pages):
                try:
                    text = extract_text_from_image(page_image, language="eng")
                    extracted_text.append({"page": page_num, "text": text})
                except Exception as e:
                    print(f"OCR failed for page {page_num}: {e}")
                    extracted_text.append({"page": page_num, "text": f"[OCR Error: {str(e)}]"})

                progress = 40 + (50 * (i + 1) // max(total_pages, 1))
                job.progress = progress
                db.commit()
                self.update_state(state="PROGRESS", meta={"progress": progress})

        # Store extracted text (in real implementation, would store in search index)
        ocr_result = {
            "document_id": document_id,
            "pages": extracted_text,
            "total_pages": len(extracted_text),
        }

        # Persist combined text to DB for search
        try:
            combined_text = "\n".join(p["text"] for p in extracted_text if p.get("text"))
            existing = (
                db.query(DocumentText)
                .filter(DocumentText.document_id == document_id)
                .first()
            )
            if existing:
                existing.text = combined_text
                existing.updated_at = datetime.utcnow()
            else:
                db.add(DocumentText(document_id=document_id, text=combined_text))
            db.commit()
        except Exception as e:
            print(f"Failed to persist OCR text for document {document_id}: {e}")

        # Upload OCR results to S3
        import json

        ocr_key = f"ocr/{document_id}/text.json"
        try:
            upload_to_s3(
                settings.s3_bucket_ocr,
                ocr_key,
                json.dumps(ocr_result).encode(),
                "application/json",
            )
        except Exception as e:
            print(f"Failed to upload OCR results to SOS: {e}")

        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        # Check if all jobs are complete and update document status
        _update_document_status_if_complete(document_id, db)

        return {
            "status": "completed",
            "document_id": document_id,
            "pages": len(extracted_text),
            "text_length": sum(len(p["text"]) for p in extracted_text),
        }

    except Exception as e:
        # Handle timeout and other errors with better isolation
        if "job" in locals():
            from billiard.exceptions import TimeLimitExceeded
            from celery.exceptions import SoftTimeLimitExceeded

            if isinstance(e, (TimeLimitExceeded, SoftTimeLimitExceeded)):
                if job:
                    job.status = "failed"
                    job.error_message = f"OCR timeout after {10 if isinstance(e, SoftTimeLimitExceeded) else 12} minutes"
                print(f"OCR task for document {document_id} timed out: {e}")
            else:
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                print(f"OCR task for document {document_id} failed: {e}")
                # Log error but don't print full traceback to avoid log spam
                print(f"OCR error details: {type(e).__name__}: {e}")

            if job:
                job.completed_at = datetime.utcnow()
            db.commit()
            
            # Update document status if all jobs are complete (including failed ones)
            _update_document_status_if_complete(document_id, db)
        
        # Don't re-raise for file corruption errors - let other tasks continue
        if "Failed to open stream" in str(e) or "FileDataError" in str(e):
            print(f"Skipping corrupted file for document {document_id} - continuing with other tasks")
            return {"status": "failed", "error": str(e)}
        
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def convert_document_to_pdf_task(self, document_id: int, job_id: int):
    """Convert a document to PDF format for standardization"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Get job and document
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            print(f"WARN: Job {job_id} not found; marking gracefully and returning")
            return {"status": "skipped", "reason": "job_missing"}

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Check if document is already a PDF
        if document.title.lower().endswith(".pdf"):
            job.status = "completed"
            job.progress = 100
            if job:
                job.completed_at = datetime.utcnow()
            db.commit()

            # Check if all jobs are complete and update document status
            _update_document_status_if_complete(document_id, db)

            return {"status": "skipped", "reason": "Document is already PDF"}

        # Load original file
        file_data = _load_original_file_bytes(settings, document)

        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})

        # Convert to PDF
        print(f"Converting {document.title} to PDF...")
        pdf_data, pdf_filename = convert_document_to_pdf(file_data, document.title)

        job.progress = 70
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 70})

        # Store converted PDF
        try:
            # Try to upload to S3 first
            s3_key = f"documents/{document_id}/{pdf_filename}"
            upload_to_s3(
                settings.s3_bucket_originals, s3_key, pdf_data, "application/pdf"
            )
            print(f"Uploaded converted PDF to S3: {s3_key}")
        except Exception as e:
            # Fall back to local storage
            print(f"S3 upload failed, storing locally: {e}")
            import os

            # Use local backend directory for development
            local_dir = f"uploads"
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, f"{document_id}_{pdf_filename}")
            with open(local_path, "wb") as f:
                f.write(pdf_data)
            print(f"Stored converted PDF locally: {local_path}")

        # Keep original document title - don't change it as it breaks file loading
        original_title = document.title
        # document.title = pdf_filename  # This breaks file loading - commenting out

        job.progress = 100
        job.status = "completed"
        if job:
            job.completed_at = datetime.utcnow()
        db.commit()

        # Check if all jobs are complete and update document status
        _update_document_status_if_complete(document_id, db)

        print(f"✅ Document conversion completed: {original_title} -> {pdf_filename}")
        return {
            "status": "completed",
            "original_filename": original_title,
            "converted_filename": pdf_filename,
            "size": len(pdf_data),
        }

    except Exception as e:
        print(f"❌ Document conversion failed: {e}")
        if "job" in locals():
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="monitor_stuck_jobs")
def monitor_stuck_jobs():
    """Periodic task to monitor and recover stuck processing jobs"""
    import logging

    from .job_monitor import monitor_and_recover_jobs

    logger = logging.getLogger(__name__)

    try:
        results = monitor_and_recover_jobs()
        logger.info(f"Job monitoring completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Job monitoring failed: {e}")
        return {"error": str(e)}
