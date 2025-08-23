#!/usr/bin/env python3
"""
Test conversion of document 913 specifically
"""

import subprocess
import tempfile
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document
from app.conversion import convert_document_to_pdf
from app.tasks import _load_original_file_bytes
from app.config import get_settings

def test_document_913():
    """Test conversion of document 913"""
    print("🧪 Testing document 913 conversion...")
    
    with SessionLocal() as db:
        settings = get_settings()
        
        # Get document 913
        document = db.query(Document).filter(Document.id == 913).first()
        if not document:
            print("❌ Document 913 not found")
            return False
            
        print(f"📄 Document: {document.title}")
        print(f"📊 Status: {document.status}")
        
        try:
            # Load original file data
            original_data = _load_original_file_bytes(settings, document)
            print(f"📦 Original file size: {len(original_data)} bytes")
            
            # Test LibreOffice conversion directly
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write original file
                input_path = os.path.join(temp_dir, "11356_AIPAC 2013 Revised Lecture3.doc")
                with open(input_path, "wb") as f:
                    f.write(original_data)
                
                print(f"📝 Wrote original file: {input_path}")
                print(f"📊 File size on disk: {os.path.getsize(input_path)} bytes")
                
                # Try conversion with LibreOffice
                try:
                    result = subprocess.run([
                        "libreoffice",
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        temp_dir,
                        input_path,
                    ], capture_output=True, text=True, timeout=60)
                    
                    print(f"🔄 LibreOffice return code: {result.returncode}")
                    print(f"📤 LibreOffice stdout: {result.stdout}")
                    print(f"📤 LibreOffice stderr: {result.stderr}")
                    
                    # Check if PDF was created
                    pdf_path = os.path.join(temp_dir, "11356_AIPAC 2013 Revised Lecture3.pdf")
                    if os.path.exists(pdf_path):
                        pdf_size = os.path.getsize(pdf_path)
                        print(f"✅ PDF created: {pdf_path}")
                        print(f"📊 PDF size: {pdf_size} bytes")
                        
                        # Analyze PDF content
                        try:
                            import fitz
                            doc = fitz.open(pdf_path)
                            print(f"📑 PDF pages: {len(doc)}")
                            if len(doc) > 0:
                                page = doc[0]
                                text = page.get_text()
                                print(f"📝 PDF text content length: {len(text)} chars")
                                print(f"📝 First 200 chars: {repr(text[:200])}")
                                
                                # Check if mostly whitespace
                                if len(text.strip()) < 10:
                                    print("⚠️  PDF contains very little text - likely conversion issue")
                            doc.close()
                        except Exception as e:
                            print(f"❌ PDF analysis failed: {e}")
                            
                    else:
                        print(f"❌ PDF not created")
                        print(f"📂 Directory contents: {os.listdir(temp_dir)}")
                        
                except Exception as e:
                    print(f"❌ LibreOffice conversion failed: {e}")
            
            # Also test our conversion function
            print("\n🧪 Testing our conversion function...")
            try:
                pdf_data, pdf_filename = convert_document_to_pdf(original_data, document.title)
                print(f"✅ Our converter produced: {len(pdf_data)} bytes, filename: {pdf_filename}")
                
                # Analyze our PDF
                import fitz
                doc = fitz.open(stream=pdf_data, filetype="pdf")
                print(f"📑 Our PDF pages: {len(doc)}")
                if len(doc) > 0:
                    page = doc[0]
                    text = page.get_text()
                    print(f"📝 Our PDF text length: {len(text)} chars")
                    print(f"📝 Our PDF first 200 chars: {repr(text[:200])}")
                doc.close()
                
            except Exception as e:
                print(f"❌ Our conversion failed: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_document_913()