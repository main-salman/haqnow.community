import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from .config import get_settings
from .processing import generate_thumbnail, generate_tiles, rasterize_pdf_pages
from .s3_client import get_s3_client, upload_to_s3

logger = logging.getLogger(__name__)


class RedactionService:
    def __init__(self):
        self.settings = get_settings()

    async def apply_redactions(
        self,
        document_id: int,
        page_number: int,
        redaction_regions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Apply redactions to a specific page by burning them into the image

        Args:
            document_id: ID of the document
            page_number: Page number to redact (0-based)
            redaction_regions: List of redaction rectangles with coordinates
                Format: [{"x": int, "y": int, "width": int, "height": int, "color": str}]

        Returns:
            Dict with success status and updated page info
        """
        try:
            # Download original document
            original_key = f"uploads/{document_id}/original"
            s3_client = get_s3_client()

            try:
                response = s3_client.get_object(
                    Bucket=self.settings.s3_bucket_originals, Key=original_key
                )
                file_data = response["Body"].read()
            except Exception as e:
                logger.error(f"Failed to download original document {document_id}: {e}")
                return {"success": False, "error": "Original document not found"}

            # Rasterize the specific page
            pages = rasterize_pdf_pages(file_data, dpi=300)

            if page_number >= len(pages):
                return {"success": False, "error": f"Page {page_number} not found"}

            page_num, page_image_data = pages[page_number]

            # Load the page image
            page_image = Image.open(io.BytesIO(page_image_data))

            # Apply redactions
            redacted_image = self._apply_redaction_rectangles(
                page_image, redaction_regions
            )

            # Save redacted page image
            redacted_image_data = self._image_to_bytes(redacted_image, format="PNG")

            # Upload redacted page
            redacted_key = f"redacted/{document_id}/page_{page_number}.png"
            upload_to_s3("derivatives", redacted_key, redacted_image_data, "image/png")

            # Generate new tiles for the redacted page
            tiles = generate_tiles(redacted_image_data, tile_size=256, quality=80)

            # Upload new tiles
            for x, y, tile_data in tiles:
                tile_key = (
                    f"tiles/{document_id}/page_{page_number}/redacted/tile_{x}_{y}.webp"
                )
                upload_to_s3("derivatives", tile_key, tile_data, "image/webp")

            # Generate new thumbnail
            thumbnail = generate_thumbnail(redacted_image_data, max_size=(200, 300))
            thumb_key = f"thumbnails/{document_id}/page_{page_number}_redacted.webp"
            upload_to_s3("derivatives", thumb_key, thumbnail, "image/webp")

            # Store redaction metadata
            redaction_metadata = {
                "document_id": document_id,
                "page_number": page_number,
                "redactions": redaction_regions,
                "redacted_at": "2024-01-01T00:00:00Z",  # Would use datetime.utcnow()
                "tiles_updated": True,
                "thumbnail_updated": True,
            }

            metadata_key = f"redactions/{document_id}/page_{page_number}_metadata.json"
            upload_to_s3(
                "derivatives",
                metadata_key,
                json.dumps(redaction_metadata).encode(),
                "application/json",
            )

            return {
                "success": True,
                "document_id": document_id,
                "page_number": page_number,
                "redactions_applied": len(redaction_regions),
                "tiles_updated": len(tiles),
                "redacted_image_url": f"/api/documents/{document_id}/pages/{page_number}/redacted",
            }

        except Exception as e:
            logger.error(
                f"Failed to apply redactions to document {document_id}, page {page_number}: {e}"
            )
            return {"success": False, "error": str(e)}

    def _apply_redaction_rectangles(
        self, image: Image.Image, redaction_regions: List[Dict[str, Any]]
    ) -> Image.Image:
        """Apply redaction rectangles to an image by filling with black"""
        # Create a copy of the image
        redacted_image = image.copy()
        draw = ImageDraw.Draw(redacted_image)

        for region in redaction_regions:
            x = region.get("x", 0)
            y = region.get("y", 0)
            width = region.get("width", 0)
            height = region.get("height", 0)
            color = region.get("color", "black")

            # Calculate rectangle coordinates
            x1, y1 = x, y
            x2, y2 = x + width, y + height

            # Fill the rectangle with the specified color (default black)
            draw.rectangle([x1, y1, x2, y2], fill=color)

            # Optionally add a border
            draw.rectangle([x1, y1, x2, y2], outline="black", width=2)

        return redacted_image

    def _image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """Convert PIL Image to bytes"""
        output = io.BytesIO()
        image.save(output, format=format)
        return output.getvalue()

    async def get_redaction_metadata(
        self, document_id: int, page_number: int
    ) -> Optional[Dict[str, Any]]:
        """Get redaction metadata for a specific page"""
        try:
            s3_client = get_s3_client()
            metadata_key = f"redactions/{document_id}/page_{page_number}_metadata.json"

            response = s3_client.get_object(Bucket="derivatives", Key=metadata_key)
            metadata = json.loads(response["Body"].read().decode("utf-8"))
            return metadata

        except Exception as e:
            logger.warning(
                f"No redaction metadata found for document {document_id}, page {page_number}: {e}"
            )
            return None

    async def list_redacted_pages(self, document_id: int) -> List[int]:
        """List all pages that have been redacted for a document"""
        try:
            s3_client = get_s3_client()
            prefix = f"redactions/{document_id}/"

            response = s3_client.list_objects_v2(Bucket="derivatives", Prefix=prefix)

            redacted_pages = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith("_metadata.json"):
                    # Extract page number from key
                    filename = key.split("/")[-1]  # page_X_metadata.json
                    page_part = filename.split("_")[1]  # X
                    try:
                        page_number = int(page_part)
                        redacted_pages.append(page_number)
                    except ValueError:
                        continue

            return sorted(redacted_pages)

        except Exception as e:
            logger.error(
                f"Failed to list redacted pages for document {document_id}: {e}"
            )
            return []

    async def remove_redactions(
        self, document_id: int, page_number: int
    ) -> Dict[str, Any]:
        """Remove redactions from a page by regenerating from original"""
        try:
            # Download original document
            original_key = f"uploads/{document_id}/original"
            s3_client = get_s3_client()

            response = s3_client.get_object(
                Bucket=self.settings.s3_bucket_originals, Key=original_key
            )
            file_data = response["Body"].read()

            # Rasterize the specific page (clean version)
            pages = rasterize_pdf_pages(file_data, dpi=300)

            if page_number >= len(pages):
                return {"success": False, "error": f"Page {page_number} not found"}

            page_num, page_image_data = pages[page_number]

            # Generate new clean tiles
            tiles = generate_tiles(page_image_data, tile_size=256, quality=80)

            # Upload clean tiles (overwrite redacted ones)
            for x, y, tile_data in tiles:
                tile_key = f"tiles/{document_id}/page_{page_number}/tile_{x}_{y}.webp"
                upload_to_s3("derivatives", tile_key, tile_data, "image/webp")

            # Generate new clean thumbnail
            thumbnail = generate_thumbnail(page_image_data, max_size=(200, 300))
            thumb_key = f"thumbnails/{document_id}/page_{page_number}.webp"
            upload_to_s3("derivatives", thumb_key, thumbnail, "image/webp")

            # Remove redaction metadata
            metadata_key = f"redactions/{document_id}/page_{page_number}_metadata.json"
            try:
                s3_client.delete_object(Bucket="derivatives", Key=metadata_key)
            except:
                pass  # Metadata might not exist

            # Remove redacted page image
            redacted_key = f"redacted/{document_id}/page_{page_number}.png"
            try:
                s3_client.delete_object(Bucket="derivatives", Key=redacted_key)
            except:
                pass  # Redacted image might not exist

            return {
                "success": True,
                "document_id": document_id,
                "page_number": page_number,
                "message": "Redactions removed, page restored to original",
            }

        except Exception as e:
            logger.error(
                f"Failed to remove redactions from document {document_id}, page {page_number}: {e}"
            )
            return {"success": False, "error": str(e)}

    async def verify_redaction_integrity(
        self, document_id: int, page_number: int
    ) -> Dict[str, Any]:
        """Verify that redactions have been properly applied and are irreversible"""
        try:
            # Check if redacted version exists
            redacted_key = f"redacted/{document_id}/page_{page_number}.png"
            s3_client = get_s3_client()

            try:
                response = s3_client.get_object(Bucket="derivatives", Key=redacted_key)
                redacted_data = response["Body"].read()
            except:
                return {"success": False, "error": "No redacted version found"}

            # Load redacted image
            redacted_image = Image.open(io.BytesIO(redacted_data))

            # Get redaction metadata
            metadata = await self.get_redaction_metadata(document_id, page_number)
            if not metadata:
                return {"success": False, "error": "No redaction metadata found"}

            # Verify redaction regions are properly blacked out
            verification_results = []
            for region in metadata.get("redactions", []):
                x, y, width, height = (
                    region["x"],
                    region["y"],
                    region["width"],
                    region["height"],
                )

                # Sample pixels in the redacted region
                sample_points = [
                    (x + width // 4, y + height // 4),
                    (x + width // 2, y + height // 2),
                    (x + 3 * width // 4, y + 3 * height // 4),
                ]

                region_verified = True
                for px, py in sample_points:
                    if px < redacted_image.width and py < redacted_image.height:
                        pixel = redacted_image.getpixel((px, py))
                        # Check if pixel is black (or very dark)
                        if isinstance(pixel, tuple):
                            brightness = sum(pixel[:3]) / 3  # Average RGB
                        else:
                            brightness = pixel

                        if brightness > 50:  # Not sufficiently dark
                            region_verified = False
                            break

                verification_results.append(
                    {"region": region, "verified": region_verified}
                )

            all_verified = all(r["verified"] for r in verification_results)

            return {
                "success": True,
                "document_id": document_id,
                "page_number": page_number,
                "all_redactions_verified": all_verified,
                "verification_details": verification_results,
                "total_redactions": len(verification_results),
            }

        except Exception as e:
            logger.error(
                f"Failed to verify redaction integrity for document {document_id}, page {page_number}: {e}"
            )
            return {"success": False, "error": str(e)}


# Global redaction service instance
_redaction_service = None


def get_redaction_service() -> RedactionService:
    """Get the global redaction service instance"""
    global _redaction_service
    if _redaction_service is None:
        _redaction_service = RedactionService()
    return _redaction_service
