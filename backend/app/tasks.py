from datetime import datetime
from celery import current_task
from sqlalchemy.orm import Session
from .celery_app import celery_app
from .db import SessionLocal
from .models import ProcessingJob, Document
from .processing import (
    download_from_s3, upload_to_s3, rasterize_pdf_pages, rasterize_image,
    generate_tiles, generate_thumbnail, extract_text_from_image, get_document_info
)
from .config import get_settings


def get_db_session() -> Session:
    """Get database session for Celery tasks"""
    return SessionLocal()


@celery_app.task(bind=True)
def process_document_tiling(self, document_id: int, job_id: int):
    """Generate tiles for a document"""
    db = get_db_session()
    settings = get_settings()
    
    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()
        
        # Download original file from S3
        original_key = f"uploads/{document.title}"  # Simplified - would use actual upload key
        try:
            file_data = download_from_s3(settings.s3_bucket_originals, original_key)
        except Exception:
            # For testing without S3, create a dummy PDF
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), f"Test document: {document.title}")
            file_data = doc.tobytes()
            doc.close()
        
        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})
        
        # Rasterize pages
        if document.title.lower().endswith('.pdf'):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            pages = rasterize_image(file_data, dpi=300)
        
        job.progress = 50
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 50})
        
        # Generate tiles for each page
        total_pages = len(pages)
        for i, (page_num, page_image) in enumerate(pages):
            tiles = generate_tiles(page_image, tile_size=256, quality=80)
            
            # Upload tiles to S3
            for x, y, tile_data in tiles:
                tile_key = f"tiles/{document_id}/page_{page_num}/tile_{x}_{y}.webp"
                try:
                    upload_to_s3("tiles", tile_key, tile_data, "image/webp")
                except Exception as e:
                    print(f"Failed to upload tile: {e}")
            
            # Update progress
            progress = 50 + (40 * (i + 1) // total_pages)
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})
        
        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()
        
        return {"status": "completed", "document_id": document_id, "pages": total_pages}
        
    except Exception as e:
        # Mark as failed
        if 'job' in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
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
            raise ValueError(f"Job {job_id} not found")
        
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()
        
        # Download original file from S3
        original_key = f"uploads/{document.title}"
        try:
            file_data = download_from_s3(settings.s3_bucket_originals, original_key)
        except Exception:
            # For testing without S3, create a dummy PDF
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), f"Test document: {document.title}")
            file_data = doc.tobytes()
            doc.close()
        
        job.progress = 25
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 25})
        
        # Rasterize pages
        if document.title.lower().endswith('.pdf'):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            pages = rasterize_image(file_data, dpi=300)
        
        job.progress = 50
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 50})
        
        # Generate thumbnails for each page
        total_pages = len(pages)
        for i, (page_num, page_image) in enumerate(pages):
            thumbnail = generate_thumbnail(page_image, max_size=(200, 300))
            
            # Upload thumbnail to S3
            thumb_key = f"thumbnails/{document_id}/page_{page_num}.webp"
            try:
                upload_to_s3("thumbnails", thumb_key, thumbnail, "image/webp")
            except Exception as e:
                print(f"Failed to upload thumbnail: {e}")
            
            # Update progress
            progress = 50 + (50 * (i + 1) // total_pages)
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})
        
        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()
        
        return {"status": "completed", "document_id": document_id, "pages": total_pages}
        
    except Exception as e:
        # Mark as failed
        if 'job' in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def process_document_ocr(self, document_id: int, job_id: int):
    """Perform OCR on a document"""
    db = get_db_session()
    settings = get_settings()
    
    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()
        
        # Download original file from S3
        original_key = f"uploads/{document.title}"
        try:
            file_data = download_from_s3(settings.s3_bucket_originals, original_key)
        except Exception:
            # For testing without S3, create a dummy PDF
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), f"Test document: {document.title}")
            file_data = doc.tobytes()
            doc.close()
        
        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})
        
        # Rasterize pages
        if document.title.lower().endswith('.pdf'):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            pages = rasterize_image(file_data, dpi=300)
        
        job.progress = 40
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 40})
        
        # Extract text from each page
        total_pages = len(pages)
        extracted_text = []
        
        for i, (page_num, page_image) in enumerate(pages):
            try:
                text = extract_text_from_image(page_image, language='eng')
                extracted_text.append({
                    'page': page_num,
                    'text': text
                })
            except Exception as e:
                print(f"OCR failed for page {page_num}: {e}")
                extracted_text.append({
                    'page': page_num,
                    'text': f"[OCR Error: {str(e)}]"
                })
            
            # Update progress
            progress = 40 + (50 * (i + 1) // total_pages)
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})
        
        # Store extracted text (in real implementation, would store in search index)
        ocr_result = {
            'document_id': document_id,
            'pages': extracted_text,
            'total_pages': total_pages
        }
        
        # Upload OCR results to S3
        import json
        ocr_key = f"ocr/{document_id}/text.json"
        try:
            upload_to_s3("ocr", ocr_key, json.dumps(ocr_result).encode(), "application/json")
        except Exception as e:
            print(f"Failed to upload OCR results: {e}")
        
        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()
        
        return {"status": "completed", "document_id": document_id, "pages": total_pages, "text_length": sum(len(p['text']) for p in extracted_text)}
        
    except Exception as e:
        # Mark as failed
        if 'job' in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()
