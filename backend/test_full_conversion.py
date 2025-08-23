#!/usr/bin/env python3
"""
Test the full conversion process for document 913
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document
from app.tasks import _load_original_file_bytes
from app.conversion import convert_document_to_pdf
from app.config import get_settings

def test_full_conversion():
    """Test the full conversion process for document 913"""
    print("🧪 Testing full conversion process for document 913...")
    
    with SessionLocal() as db:
        settings = get_settings()
        
        # Get document 913
        document = db.query(Document).filter(Document.id == 913).first()
        if not document:
            print("❌ Document 913 not found")
            return False
            
        print(f"📄 Document title: {document.title}")
        print(f"📊 Status: {document.status}")
        
        try:
            # Load original file
            file_data = _load_original_file_bytes(settings, document)
            print(f"📦 Original file size: {len(file_data)} bytes")
            
            if len(file_data) < 1000:
                print("❌ Original file too small")
                return False
            
            # Test conversion
            print("\n🔄 Testing document conversion...")
            try:
                pdf_data, pdf_filename = convert_document_to_pdf(file_data, "11356_AIPAC 2013 Revised Lecture3.doc")
                print(f"✅ Conversion successful!")
                print(f"📦 PDF size: {len(pdf_data)} bytes")
                print(f"📄 PDF filename: {pdf_filename}")
                
                # Analyze converted PDF
                try:
                    import fitz
                    doc = fitz.open(stream=pdf_data, filetype="pdf")
                    print(f"📑 PDF has {len(doc)} pages")
                    
                    if len(doc) > 0:
                        page = doc[0]
                        text = page.get_text()
                        print(f"📝 PDF text length: {len(text)} chars")
                        
                        if len(text.strip()) < 10:
                            print("⚠️  PDF has very little text content")
                            return False
                        elif "placeholder" in text.lower() or "uploaded file not found" in text.lower():
                            print("❌ PDF still contains placeholder text")
                            return False
                        else:
                            print("✅ PDF contains real content!")
                            print(f"📄 Sample text: {text[:200]}...")
                            return True
                    else:
                        print("❌ PDF has no pages")
                        return False
                        
                    doc.close()
                    
                except Exception as e:
                    print(f"❌ PDF analysis failed: {e}")
                    return False
                    
            except Exception as e:
                print(f"❌ Conversion failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_full_conversion()
    if success:
        print("\n🎉 Full conversion process working!")
    else:
        print("\n❌ Conversion process still has issues")