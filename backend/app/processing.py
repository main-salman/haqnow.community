import io
import math
import os
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageDraw

from .config import get_settings
from .s3_client import upload_to_s3

## S3 download helper moved to app.s3_client.download_from_s3 to avoid duplication


def generate_single_page_image(image_data: bytes, dpi: int = 300) -> bytes:
    """
    Generate a single 300 DPI image from page data
    This follows the requirement: 'each page in the document should be a single 300 DPI image'
    """
    image = Image.open(io.BytesIO(image_data))

    # Ensure RGB mode
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Calculate target size for 300 DPI
    # Standard page size at 300 DPI is approximately 2550x3300 pixels (8.5x11 inches)
    target_width = 2550
    target_height = 3300

    # Resize image to target DPI while maintaining aspect ratio
    original_width, original_height = image.size
    aspect_ratio = original_width / original_height

    if aspect_ratio > (target_width / target_height):
        # Image is wider - fit to width
        new_width = target_width
        new_height = int(target_width / aspect_ratio)
    else:
        # Image is taller - fit to height
        new_height = target_height
        new_width = int(target_height * aspect_ratio)

    # Resize image
    image = image.resize((new_width, new_height), Image.LANCZOS)

    # Create white canvas at target size and center the image
    canvas = Image.new("RGB", (target_width, target_height), "white")
    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2
    canvas.paste(image, (x_offset, y_offset))

    # Convert to high-quality WebP (better compression than PNG)
    output = io.BytesIO()
    canvas.save(output, format="WEBP", quality=95, method=6)
    return output.getvalue()


def rasterize_pdf_pages(pdf_data: bytes, dpi: int = 300) -> List[Tuple[int, bytes]]:
    """Rasterize PDF pages to PNG images at specified DPI"""
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    pages = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)

        # Calculate matrix for desired DPI
        zoom = dpi / 72.0  # 72 DPI is default
        mat = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to PNG bytes
        png_data = pix.tobytes("png")
        pages.append((page_num, png_data))

        pix = None  # Free memory

    doc.close()
    return pages


def rasterize_image(image_data: bytes, dpi: int = 300) -> List[Tuple[int, bytes]]:
    """Convert image to standardized format"""
    image = Image.open(io.BytesIO(image_data))

    # Convert to RGB if needed
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Resize to target DPI if metadata available
    if hasattr(image, "info") and "dpi" in image.info:
        current_dpi = (
            image.info["dpi"][0]
            if isinstance(image.info["dpi"], tuple)
            else image.info["dpi"]
        )
        if current_dpi != dpi:
            scale_factor = dpi / current_dpi
            new_size = (
                int(image.width * scale_factor),
                int(image.height * scale_factor),
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)

    # Save as PNG
    output = io.BytesIO()
    image.save(output, format="PNG", dpi=(dpi, dpi))
    png_data = output.getvalue()

    return [(0, png_data)]  # Single page for images


def generate_tiles(
    image_data: bytes, tile_size: int = 256, quality: int = 80
) -> List[Tuple[int, int, bytes]]:
    """Generate WebP tiles from page image"""
    image = Image.open(io.BytesIO(image_data))
    width, height = image.size

    # Calculate number of tiles needed
    tiles_x = math.ceil(width / tile_size)
    tiles_y = math.ceil(height / tile_size)

    tiles = []

    for y in range(tiles_y):
        for x in range(tiles_x):
            # Calculate tile bounds
            left = x * tile_size
            top = y * tile_size
            right = min(left + tile_size, width)
            bottom = min(top + tile_size, height)

            # Extract tile
            tile = image.crop((left, top, right, bottom))

            # If tile is smaller than tile_size, pad with white
            if tile.size != (tile_size, tile_size):
                padded = Image.new("RGB", (tile_size, tile_size), "white")
                padded.paste(tile, (0, 0))
                tile = padded

            # Save as WebP
            output = io.BytesIO()
            tile.save(output, format="WebP", quality=quality)
            tile_data = output.getvalue()

            tiles.append((x, y, tile_data))

    return tiles


def generate_thumbnail(
    image_data: bytes, max_size: Tuple[int, int] = (2400, 3600)
) -> bytes:
    """Generate high-resolution thumbnail from page image for 300 DPI viewing"""
    image = Image.open(io.BytesIO(image_data))

    # Calculate thumbnail size maintaining aspect ratio
    image.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Save as WebP with maximum quality for 300 DPI
    output = io.BytesIO()
    image.save(output, format="WebP", quality=100, method=6)
    return output.getvalue()


def extract_text_from_image(image_data: bytes, language: str = "eng") -> str:
    """Extract text from image using optimized Tesseract OCR"""
    try:
        image = Image.open(io.BytesIO(image_data))
        
        # Optimize image for OCR - resize to optimal DPI if too large
        width, height = image.size
        if width > 2000 or height > 2000:  # If image is too large (300 DPI), resize for OCR
            # Calculate optimal size for OCR (around 150-200 DPI equivalent)
            scale_factor = min(1500 / width, 1500 / height)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert to grayscale for better OCR performance
        if image.mode != 'L':
            image = image.convert('L')

        # Optimized Tesseract configuration for speed and accuracy
        config = "--oem 3 --psm 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?@#$%^&*()_+-=[]{}|;:'\",.<>?/~` "
        
        # Extract text
        text = pytesseract.image_to_string(image, lang=language, config=config)

        return text.strip()
    except Exception as e:
        print(f"OCR failed: {e}")
        return ""


def apply_redactions_to_image(
    image_data: bytes, redaction_regions: List[Tuple[int, int, int, int]]
) -> bytes:
    """Apply redaction rectangles to image by filling with black"""
    image = Image.open(io.BytesIO(image_data))
    draw = ImageDraw.Draw(image)

    # Fill redaction regions with black
    for x1, y1, x2, y2 in redaction_regions:
        draw.rectangle([x1, y1, x2, y2], fill="black")

    # Save as PNG to preserve quality
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def get_document_info(file_data: bytes, filename: str) -> dict:
    """Get basic info about a document"""
    info = {
        "filename": filename,
        "size": len(file_data),
        "pages": 0,
        "file_type": "unknown",
    }

    # Detect file type
    if filename.lower().endswith(".pdf"):
        info["file_type"] = "pdf"
        try:
            doc = fitz.open(stream=file_data, filetype="pdf")
            info["pages"] = len(doc)
            doc.close()
        except:
            pass
    elif filename.lower().endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")):
        info["file_type"] = "image"
        info["pages"] = 1
    elif filename.lower().endswith((".docx", ".pptx", ".xlsx")):
        info["file_type"] = "office"
        # Would need LibreOffice conversion to get page count
        info["pages"] = 1  # Placeholder

    return info
