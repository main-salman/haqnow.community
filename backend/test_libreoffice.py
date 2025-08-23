#!/usr/bin/env python3
"""
Test LibreOffice conversion in the container
"""

import subprocess
import tempfile
import os

def test_libreoffice():
    """Test if LibreOffice is properly installed and working"""
    print("🧪 Testing LibreOffice installation...")
    
    # Check if LibreOffice is installed
    try:
        result = subprocess.run(["libreoffice", "--version"], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ LibreOffice version: {result.stdout.strip()}")
        else:
            print(f"❌ LibreOffice version check failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ LibreOffice not found: {e}")
        return False
    
    # Test conversion with a simple document
    print("\n📄 Testing document conversion...")
    
    # Create a simple test Word document (RTF format, which LibreOffice can handle)
    test_rtf_content = r"""{\rtf1\ansi\deff0 {\fonttbl {\f0 Times New Roman;}}
\f0\fs24 Hello World! This is a test document.
\par
This document should convert to PDF properly.
\par
Test complete.}"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write test file
        input_path = os.path.join(temp_dir, "test.rtf")
        with open(input_path, "w") as f:
            f.write(test_rtf_content)
            
        print(f"📝 Created test file: {input_path}")
        print(f"📊 Test file size: {os.path.getsize(input_path)} bytes")
        
        # Convert using LibreOffice
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
            
            print(f"🔄 Conversion return code: {result.returncode}")
            print(f"📤 Conversion stdout: {result.stdout}")
            print(f"📤 Conversion stderr: {result.stderr}")
            
            # Check if PDF was created
            pdf_path = os.path.join(temp_dir, "test.pdf")
            if os.path.exists(pdf_path):
                pdf_size = os.path.getsize(pdf_path)
                print(f"✅ PDF created: {pdf_path}")
                print(f"📊 PDF size: {pdf_size} bytes")
                
                if pdf_size < 500:
                    print("⚠️  PDF seems very small - might be empty")
                    
                # Try to read PDF with PyMuPDF
                try:
                    import fitz
                    doc = fitz.open(pdf_path)
                    print(f"📑 PDF pages: {len(doc)}")
                    if len(doc) > 0:
                        page = doc[0]
                        text = page.get_text()
                        print(f"📝 PDF text content: {repr(text[:100])}")
                    doc.close()
                except Exception as e:
                    print(f"❌ PDF reading failed: {e}")
                    
                return True
            else:
                print(f"❌ PDF not created at expected path: {pdf_path}")
                print(f"📂 Directory contents: {os.listdir(temp_dir)}")
                return False
                
        except Exception as e:
            print(f"❌ Conversion failed: {e}")
            return False

if __name__ == "__main__":
    test_libreoffice()