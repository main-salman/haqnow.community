#!/usr/bin/env python3
"""
Debug script to examine tile generation issues
"""

import os
import sys
import io
from PIL import Image

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document
from app.processing import generate_tiles, rasterize_pdf_pages
from app.tasks import _load_processing_file_bytes
from app.config import get_settings

def debug_document_tiles(document_id: int):
    """Debug tile generation for a specific document"""
    print(f"🔍 Debugging tiles for document {document_id}")
    
    with SessionLocal() as db:
        settings = get_settings()
        
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"❌ Document {document_id} not found")
            return
            
        print(f"📄 Document: {document.title}")
        print(f"📊 Status: {document.status}")
        
        try:
            # Load file data
            file_data = _load_processing_file_bytes(settings, document)
            print(f"📦 Loaded file data: {len(file_data)} bytes")
            
            # Rasterize pages
            if document.title.lower().endswith(('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.csv', '.txt')):
                pages = rasterize_pdf_pages(file_data, dpi=300)
            else:
                from app.processing import rasterize_image
                pages = rasterize_image(file_data, dpi=300)
                
            print(f"📑 Rasterized {len(pages)} pages")
            
            for page_num, page_image_data in pages:
                print(f"\n🖼️  Page {page_num}: {len(page_image_data)} bytes")
                
                # Analyze the source image
                try:
                    image = Image.open(io.BytesIO(page_image_data))
                    print(f"   📐 Image size: {image.size}")
                    print(f"   🎨 Image mode: {image.mode}")
                    
                    # Check if image is mostly empty/white
                    if image.mode in ('RGB', 'RGBA'):
                        # Sample some pixels to see if they're mostly white
                        width, height = image.size
                        sample_pixels = [
                            image.getpixel((0, 0)),
                            image.getpixel((width//2, height//2)),
                            image.getpixel((width-1, height-1)),
                            image.getpixel((width//4, height//4)),
                            image.getpixel((3*width//4, 3*height//4))
                        ]
                        print(f"   🎨 Sample pixels: {sample_pixels}")
                        
                        # Check if all samples are white-ish
                        white_count = 0
                        for pixel in sample_pixels:
                            if image.mode == 'RGB':
                                r, g, b = pixel
                                if r > 240 and g > 240 and b > 240:
                                    white_count += 1
                            elif image.mode == 'RGBA':
                                r, g, b, a = pixel
                                if r > 240 and g > 240 and b > 240:
                                    white_count += 1
                        
                        print(f"   ⚪ White-ish pixels: {white_count}/{len(sample_pixels)}")
                        
                    # Generate tiles
                    print(f"   🔲 Generating tiles...")
                    tiles = generate_tiles(page_image_data, tile_size=256, quality=80)
                    print(f"   🔲 Generated {len(tiles)} tiles")
                    
                    # Analyze first few tiles
                    for i, (x, y, tile_data) in enumerate(tiles[:5]):
                        print(f"   🔲 Tile ({x},{y}): {len(tile_data)} bytes")
                        
                        # Try to analyze the tile content
                        try:
                            tile_img = Image.open(io.BytesIO(tile_data))
                            print(f"      📐 Tile size: {tile_img.size}")
                            
                            # Sample the tile's center pixel
                            tw, th = tile_img.size
                            if tw > 0 and th > 0:
                                center_pixel = tile_img.getpixel((tw//2, th//2))
                                print(f"      🎨 Center pixel: {center_pixel}")
                        except Exception as e:
                            print(f"      ❌ Tile analysis error: {e}")
                    
                    break  # Only analyze first page
                    
                except Exception as e:
                    print(f"   ❌ Image analysis error: {e}")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_tiles.py <document_id>")
        sys.exit(1)
        
    document_id = int(sys.argv[1])
    debug_document_tiles(document_id)