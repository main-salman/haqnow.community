import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image

from .config import get_settings
from .db import SessionLocal
from .models import Document, Redaction
from .processing import rasterize_pdf_pages
from .redaction import get_redaction_service
from .s3_client import get_s3_client, upload_to_s3

logger = logging.getLogger(__name__)


class ExportService:
    def __init__(self):
        self.settings = get_settings()

    def _get_page_image_from_thumbnails(
        self, document_id: int, page_number: int
    ) -> Optional[Image.Image]:
        """Fallback: load pre-rendered page image from previews/thumbnails (S3 or local)."""
        s3_client = None
        try:
            s3_client = get_s3_client()
        except Exception:
            s3_client = None
        # Try S3 previews first (PNG)
        if s3_client is not None:
            try:
                preview_key = f"previews/{document_id}/page_{page_number}.png"
                resp = s3_client.get_object(
                    Bucket=self.settings.s3_bucket_thumbnails, Key=preview_key
                )
                data = resp["Body"].read()
                return Image.open(io.BytesIO(data))
            except Exception:
                pass
            # Try thumbnails (WEBP)
            try:
                thumb_key = f"thumbnails/{document_id}/page_{page_number}.webp"
                resp = s3_client.get_object(
                    Bucket=self.settings.s3_bucket_thumbnails, Key=thumb_key
                )
                data = resp["Body"].read()
                return Image.open(io.BytesIO(data))
            except Exception:
                pass
        # Local fallbacks
        local_preview = f"/srv/processed/previews/{document_id}/page_{page_number}.png"
        local_thumb = f"/srv/processed/thumbnails/{document_id}/page_{page_number}.webp"
        app_preview = f"/app/processed/previews/{document_id}/page_{page_number}.png"
        app_thumb = f"/app/processed/thumbnails/{document_id}/page_{page_number}.webp"
        for path in [app_preview, app_thumb, local_preview, local_thumb]:
            try:
                if os.path.exists(path) and os.path.isfile(path):
                    with open(path, "rb") as f:
                        return Image.open(io.BytesIO(f.read()))
            except Exception:
                continue
        return None

    async def export_pdf(
        self,
        document_id: int,
        page_ranges: List[Tuple[int, int]] = None,
        include_redacted: bool = True,
        export_format: str = "pdf",
        quality: str = "high",
    ) -> Dict[str, Any]:
        """
        Export document pages as PDF with optional page ranges

        Args:
            document_id: ID of the document to export
            page_ranges: List of (start, end) page ranges (0-based, inclusive)
                        If None, exports all pages
            include_redacted: Whether to use redacted versions of pages if available
            export_format: Output format ("pdf", "images")
            quality: Export quality ("high", "medium", "low")

        Returns:
            Dict with export info and download URL
        """
        try:
            # Get document title for key inference
            doc_title = None
            try:
                db = SessionLocal()
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc_title = doc.title
            except Exception:
                doc_title = None
            finally:
                try:
                    db.close()
                except Exception:
                    pass

            # Try to load original from S3; if not available, use local uploads path
            original_data = None
            try:
                s3_client = get_s3_client()
                # Try multiple key variants
                s3_keys = [
                    f"uploads/{document_id}/original",
                ]
                if doc_title:
                    s3_keys.extend(
                        [
                            f"uploads/{doc_title}",
                            f"{document_id}/{doc_title}",
                        ]
                    )
                last_err = None
                for key in s3_keys:
                    try:
                        response = s3_client.get_object(
                            Bucket=self.settings.s3_bucket_originals, Key=key
                        )
                        original_data = response["Body"].read()
                        break
                    except Exception as se:
                        last_err = se
                if original_data is None and last_err:
                    raise last_err
            except Exception:
                pass

            if original_data is None:
                # Attempt local path fallbacks (container paths)
                # Include variants by document title and id_title
                doc_title = None
                try:
                    db = SessionLocal()
                    doc = db.query(Document).filter(Document.id == document_id).first()
                    if doc:
                        doc_title = doc.title
                except Exception:
                    doc_title = None
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass

                candidates = [
                    f"/app/uploads/{document_id}.pdf",
                    f"/app/uploads/{document_id}",
                ]
                if doc_title:
                    candidates.extend(
                        [
                            f"/app/uploads/{doc_title}",
                            f"/app/uploads/{document_id}_{doc_title}",
                            f"/srv/backend/uploads/{doc_title}",
                            f"/srv/backend/uploads/{document_id}_{doc_title}",
                        ]
                    )
                candidates.extend(
                    [
                        f"/srv/backend/uploads/{document_id}.pdf",
                        f"/srv/backend/uploads/{document_id}",
                    ]
                )
                for path in candidates:
                    if os.path.exists(path) and os.path.isfile(path):
                        with open(path, "rb") as f:
                            original_data = f.read()
                            break
            if original_data is None:
                return {"success": False, "error": "Original document not found"}

            # Determine file type by title; default to PDF
            is_pdf = True
            title_lower = (doc_title or "").lower()
            if not title_lower.endswith(".pdf"):
                is_pdf = False

            # Get total page count
            if is_pdf:
                try:
                    pages = rasterize_pdf_pages(original_data, dpi=150)
                    total_pages = len(pages)
                except Exception:
                    # Fallback: treat as single-page image
                    is_pdf = False
                    total_pages = 1
            else:
                total_pages = 1

            # Determine which pages to export
            if page_ranges is None:
                # Export all pages
                pages_to_export = list(range(total_pages))
            else:
                # Export specified ranges
                pages_to_export = []
                for start, end in page_ranges:
                    # Validate range
                    start = max(0, min(start, total_pages - 1))
                    end = max(start, min(end, total_pages - 1))
                    pages_to_export.extend(range(start, end + 1))

                # Remove duplicates and sort
                pages_to_export = sorted(list(set(pages_to_export)))

            if not pages_to_export:
                return {"success": False, "error": "No valid pages to export"}

            # Set DPI based on quality. If including redactions, force 300 DPI for pixel accuracy
            dpi_map = {"high": 300, "medium": 200, "low": 150}
            export_dpi = 300 if include_redacted else dpi_map.get(quality, 300)

            if export_format == "pdf":
                result = await self._export_as_pdf(
                    document_id,
                    pages_to_export,
                    include_redacted,
                    export_dpi,
                    original_data,
                )
            elif export_format == "images":
                result = await self._export_as_images(
                    document_id,
                    pages_to_export,
                    include_redacted,
                    export_dpi,
                    original_data,
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported export format: {export_format}",
                }

            return result

        except Exception as e:
            logger.error(f"Failed to export document {document_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _export_as_pdf(
        self,
        document_id: int,
        pages_to_export: List[int],
        include_redacted: bool,
        dpi: int,
        original_data: bytes,
    ) -> Dict[str, Any]:
        """Export pages as a PDF document"""
        try:
            # Create new PDF document
            export_doc = fitz.open()

            # Get redaction service to check for redacted pages
            redaction_service = get_redaction_service()
            redacted_pages = (
                await redaction_service.list_redacted_pages(document_id)
                if include_redacted
                else []
            )

            # Process each page
            for page_num in pages_to_export:
                try:
                    # Choose base image
                    if include_redacted and page_num in redacted_pages:
                        page_image = await self._get_redacted_page_image(
                            document_id, page_num
                        )
                        if page_image is None:
                            page_image = await self._get_original_page_image(
                                original_data, page_num, dpi
                            )
                    else:
                        page_image = await self._get_original_page_image(
                            original_data, page_num, dpi
                        )
                        if page_image is None:
                            # Fallback: load thumbnails/previews
                            page_image = self._get_page_image_from_thumbnails(
                                document_id, page_num
                            )

                    # Paint DB redactions onto the image to guarantee burn-in
                    if include_redacted and page_image is not None:
                        regions = self._get_redaction_regions(
                            document_id,
                            page_num,
                            target_size=(page_image.width, page_image.height),
                        )
                        if regions:
                            page_image = self._apply_redaction_rectangles_local(
                                page_image, regions
                            )

                    if page_image:
                        # Convert PIL Image to PDF page
                        img_bytes = self._image_to_bytes(page_image, format="PNG")
                        img_doc = fitz.open(stream=img_bytes, filetype="png")
                        export_doc.insert_pdf(img_doc)
                        img_doc.close()

                except Exception as e:
                    logger.warning(f"Failed to process page {page_num}: {e}")
                    continue

            if export_doc.page_count == 0:
                export_doc.close()
                return {"success": False, "error": "No pages could be processed"}

            # Generate export filename
            export_filename = f"document_{document_id}_export.pdf"
            if include_redacted:
                export_filename = f"document_{document_id}_redacted_export.pdf"

            # Save PDF to bytes
            pdf_bytes = export_doc.tobytes()
            export_doc.close()

            # Upload to S3
            export_key = f"exports/{document_id}/{export_filename}"
            try:
                upload_to_s3(
                    self.settings.s3_bucket_exports,
                    export_key,
                    pdf_bytes,
                    "application/pdf",
                )
                download_url = f"/api/documents/{document_id}/exports/{export_filename}"
            except Exception:
                # Fallback to local filesystem
                base_dir = f"/app/processed/exports/{document_id}"
                os.makedirs(base_dir, exist_ok=True)
                local_path = f"{base_dir}/{export_filename}"
                with open(local_path, "wb") as f:
                    f.write(pdf_bytes)
                download_url = f"/api/documents/{document_id}/exports/{export_filename}"

            return {
                "success": True,
                "document_id": document_id,
                "export_format": "pdf",
                "filename": export_filename,
                "pages_exported": len(pages_to_export),
                "file_size": len(pdf_bytes),
                "download_url": download_url,
                "expires_at": "2024-12-31T23:59:59Z",  # Would calculate actual expiry
            }

        except Exception as e:
            logger.error(f"Failed to export PDF for document {document_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _export_as_images(
        self,
        document_id: int,
        pages_to_export: List[int],
        include_redacted: bool,
        dpi: int,
        original_data: bytes,
    ) -> Dict[str, Any]:
        """Export pages as individual image files"""
        try:
            # Get redaction service to check for redacted pages
            redaction_service = get_redaction_service()
            redacted_pages = (
                await redaction_service.list_redacted_pages(document_id)
                if include_redacted
                else []
            )

            exported_files = []
            total_size = 0

            # Process each page
            for page_num in pages_to_export:
                try:
                    if include_redacted and page_num in redacted_pages:
                        # Use redacted version
                        page_image = await self._get_redacted_page_image(
                            document_id, page_num
                        )
                        filename = f"page_{page_num:03d}_redacted.png"
                    else:
                        # Use original version
                        page_image = await self._get_original_page_image(
                            original_data, page_num, dpi
                        )
                        if page_image is None:
                            page_image = self._get_page_image_from_thumbnails(
                                document_id, page_num
                            )
                        filename = f"page_{page_num:03d}.png"

                    if page_image:
                        # Burn DB redactions as a guarantee (even if a pre-redacted image exists)
                        if include_redacted:
                            regions = self._get_redaction_regions(
                                document_id,
                                page_num,
                                target_size=(page_image.width, page_image.height),
                            )
                            if regions:
                                page_image = self._apply_redaction_rectangles_local(
                                    page_image, regions
                                )

                        # Save image
                        img_bytes = self._image_to_bytes(page_image, format="PNG")

                        # Upload to S3
                        export_key = f"exports/{document_id}/images/{filename}"
                        upload_to_s3(
                            self.settings.s3_bucket_exports,
                            export_key,
                            img_bytes,
                            "image/png",
                        )

                        exported_files.append(
                            {
                                "filename": filename,
                                "page_number": page_num,
                                "file_size": len(img_bytes),
                                "download_url": f"/api/documents/{document_id}/exports/images/{filename}",
                            }
                        )

                        total_size += len(img_bytes)

                except Exception as e:
                    logger.warning(f"Failed to export page {page_num} as image: {e}")
                    continue

            if not exported_files:
                return {"success": False, "error": "No pages could be exported"}

            return {
                "success": True,
                "document_id": document_id,
                "export_format": "images",
                "pages_exported": len(exported_files),
                "total_file_size": total_size,
                "files": exported_files,
                "expires_at": "2024-12-31T23:59:59Z",  # Would calculate actual expiry
            }

        except Exception as e:
            logger.error(f"Failed to export images for document {document_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _get_redacted_page_image(
        self, document_id: int, page_number: int
    ) -> Optional[Image.Image]:
        """Get redacted version of a page image"""
        try:
            s3_client = get_s3_client()
            redacted_key = f"redacted/{document_id}/page_{page_number}.png"

            response = s3_client.get_object(Bucket="derivatives", Key=redacted_key)
            image_data = response["Body"].read()

            return Image.open(io.BytesIO(image_data))

        except Exception as e:
            logger.warning(
                f"Failed to get redacted page {page_number} for document {document_id}: {e}"
            )
            return None

    async def _get_original_page_image(
        self, original_data: bytes, page_number: int, dpi: int
    ) -> Optional[Image.Image]:
        """Get original version of a page image (supports PDFs and images)."""
        # Try PDF rasterization first
        try:
            pages = rasterize_pdf_pages(original_data, dpi=dpi)
            if page_number < len(pages):
                _, page_image_data = pages[page_number]
                return Image.open(io.BytesIO(page_image_data))
        except Exception:
            pass
        # Fallback: treat original as a single image
        try:
            from .processing import rasterize_image

            pages = rasterize_image(original_data, dpi=dpi)
            if pages:
                _, page_image_data = pages[0]
                return Image.open(io.BytesIO(page_image_data))
        except Exception as e:
            logger.warning(f"Failed to get original page {page_number}: {e}")
        return None

    def _image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """Convert PIL Image to bytes"""
        output = io.BytesIO()
        image.save(output, format=format)
        return output.getvalue()

    def _get_redaction_regions(
        self,
        document_id: int,
        page_number: int,
        target_size: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, int]]:
        """Load redaction rectangles from DB and normalize to x,y,width,height in pixels.

        If target_size is provided, scale from a canonical base (default 2000x3000; fallback 2400x3600
        if stored coordinates indicate that scale) to the target image size.
        """
        try:
            db = SessionLocal()
            reds = (
                db.query(Redaction)
                .filter(
                    Redaction.document_id == document_id,
                    Redaction.page_number == page_number,
                )
                .all()
            )
            regions: List[Dict[str, int]] = []

            # Infer canonical base from stored coordinates to support legacy clients
            max_x = 0
            max_y = 0
            for r in reds:
                max_x = max(max_x, int(max(r.x_start, r.x_end)))
                max_y = max(max_y, int(max(r.y_start, r.y_end)))
            base_w = 2000
            base_h = 3000
            # If values exceed 2000/3000 notably, assume 2400x3600 canonical
            if max_x > 2200 or max_y > 3300:
                base_w = 2400
                base_h = 3600
            scale_x = 1.0
            scale_y = 1.0
            if target_size is not None and base_w > 0 and base_h > 0:
                scale_x = float(target_size[0]) / float(base_w)
                scale_y = float(target_size[1]) / float(base_h)

            for r in reds:
                x1 = int(min(r.x_start, r.x_end) * scale_x)
                y1 = int(min(r.y_start, r.y_end) * scale_y)
                x2 = int(max(r.x_start, r.x_end) * scale_x)
                y2 = int(max(r.y_start, r.y_end) * scale_y)
                regions.append(
                    {
                        "x": x1,
                        "y": y1,
                        "width": max(0, x2 - x1),
                        "height": max(0, y2 - y1),
                        "color": "black",
                    }
                )
            return regions
        except Exception:
            return []
        finally:
            try:
                db.close()
            except Exception:
                pass

    def _apply_redaction_rectangles_local(
        self, image: Image.Image, redaction_regions: List[Dict[str, Any]]
    ) -> Image.Image:
        from PIL import ImageDraw

        redacted = image.copy()
        draw = ImageDraw.Draw(redacted)
        for region in redaction_regions:
            x = int(region.get("x", 0))
            y = int(region.get("y", 0))
            w = int(region.get("width", 0))
            h = int(region.get("height", 0))
            if w <= 0 or h <= 0:
                continue
            draw.rectangle([x, y, x + w, y + h], fill="black")
        return redacted

    async def list_exports(self, document_id: int) -> Dict[str, Any]:
        """List all available exports for a document"""
        try:
            exports = []
            try:
                s3_client = get_s3_client()
                prefix = f"exports/{document_id}/"
                response = s3_client.list_objects_v2(
                    Bucket=self.settings.s3_bucket_exports, Prefix=prefix
                )
                for obj in response.get("Contents", []):
                    key = obj["Key"]
                    filename = key.split("/")[-1]
                    if filename:
                        exports.append(
                            {
                                "filename": filename,
                                "size": obj["Size"],
                                "created_at": obj["LastModified"].isoformat(),
                                "download_url": f"/api/documents/{document_id}/exports/{filename}",
                            }
                        )
            except Exception:
                # Fallback to local listing
                base_dir = f"/app/processed/exports/{document_id}"
                if os.path.isdir(base_dir):
                    for name in os.listdir(base_dir):
                        path = os.path.join(base_dir, name)
                        if os.path.isfile(path):
                            stat = os.stat(path)
                            exports.append(
                                {
                                    "filename": name,
                                    "size": stat.st_size,
                                    "created_at": "",
                                    "download_url": f"/api/documents/{document_id}/exports/{name}",
                                }
                            )

            return {
                "success": True,
                "document_id": document_id,
                "exports": exports,
                "total_exports": len(exports),
            }

        except Exception as e:
            logger.error(f"Failed to list exports for document {document_id}: {e}")
            return {"success": False, "error": str(e)}

    async def delete_export(self, document_id: int, filename: str) -> Dict[str, Any]:
        """Delete a specific export file"""
        try:
            s3_client = get_s3_client()
            export_key = f"exports/{document_id}/{filename}"

            # Check if file exists
            try:
                s3_client.head_object(
                    Bucket=self.settings.s3_bucket_exports, Key=export_key
                )
            except:
                return {"success": False, "error": "Export file not found"}

            # Delete the file
            s3_client.delete_object(
                Bucket=self.settings.s3_bucket_exports, Key=export_key
            )

            return {
                "success": True,
                "document_id": document_id,
                "filename": filename,
                "message": "Export deleted successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to delete export {filename} for document {document_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def parse_page_ranges(
        self, page_ranges_str: str, total_pages: int
    ) -> List[Tuple[int, int]]:
        """
        Parse page range string into list of (start, end) tuples

        Examples:
        - "1-5" -> [(0, 4)]  # Convert to 0-based
        - "1,3,5-7" -> [(0, 0), (2, 2), (4, 6)]
        - "1-3,7-10" -> [(0, 2), (6, 9)]
        """
        if not page_ranges_str:
            return None

        ranges = []
        parts = page_ranges_str.split(",")

        for part in parts:
            part = part.strip()
            if "-" in part:
                # Range like "1-5"
                start_str, end_str = part.split("-", 1)
                start = max(1, int(start_str.strip())) - 1  # Convert to 0-based
                end = min(total_pages, int(end_str.strip())) - 1  # Convert to 0-based
                if start <= end:
                    ranges.append((start, end))
            else:
                # Single page like "3"
                page = max(1, int(part)) - 1  # Convert to 0-based
                if page < total_pages:
                    ranges.append((page, page))

        return ranges


# Global export service instance
_export_service = None


def get_export_service() -> ExportService:
    """Get the global export service instance"""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
