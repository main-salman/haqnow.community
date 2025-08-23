#!/usr/bin/env python3
"""
Test if the file loading fix works
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document
from app.tasks import _load_processing_file_bytes
from app.config import get_settings

def test_file_loading_fix():
    """Test if document 913 can now load the correct file"""
    print("🧪 Testing file loading fix for document 913...")
    
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
            # Test file loading
            file_data = _load_processing_file_bytes(settings, document)
            print(f"📦 Loaded file size: {len(file_data)} bytes")
            
            if len(file_data) < 1000:
                print("❌ File is too small - likely still a placeholder")
                return False
            elif len(file_data) > 100000:
                print("✅ File size looks good - real document loaded")
                
                # Try to check if it's a real PDF vs placeholder
                try:
                    import fitz
                    doc = fitz.open(stream=file_data, filetype="pdf")
                    print(f"📑 PDF has {len(doc)} pages")
                    if len(doc) > 0:
                        page = doc[0]
                        text = page.get_text()
                        print(f"📝 Text content length: {len(text)} chars")
                        
                        # Check for placeholder text
                        if "placeholder" in text.lower() or "uploaded file not found" in text.lower():
                            print("❌ Still getting placeholder content")
                            return False
                        else:
                            print("✅ Real content detected!")
                            print(f"📄 Sample text: {text[:150]}...")
                            return True
                    doc.close()
                except Exception as e:
                    print(f"❌ PDF analysis failed: {e}")
                    return False
            else:
                print("⚠️  File size moderate - checking content...")
                
        except Exception as e:
            print(f"❌ File loading failed: {e}")
            return False

if __name__ == "__main__":
    success = test_file_loading_fix()
    if success:
        print("\n🎉 Fix appears to be working!")
    else:
        print("\n❌ Fix did not resolve the issue")