#!/usr/bin/env python3
"""
Test script to verify OCR setup
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing Python module imports...")
    
    modules = [
        ('tkinter', 'GUI framework'),
        ('requests', 'HTTP client'),
        ('PyPDF2', 'PDF processing'),
        ('json', 'JSON handling'),
        ('threading', 'Multi-threading'),
        ('datetime', 'Date/time handling'),
        ('pathlib', 'Path handling')
    ]
    
    optional_modules = [
        ('pytesseract', 'Tesseract OCR wrapper'),
        ('pdf2image', 'PDF to image conversion'),
        ('PIL', 'Image processing (Pillow)')
    ]
    
    # Test required modules
    all_required_ok = True
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}: OK ({description})")
        except ImportError as e:
            print(f"  ❌ {module_name}: MISSING ({description})")
            all_required_ok = False
    
    # Test optional modules (for local OCR)
    local_ocr_ok = True
    for module_name, description in optional_modules:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}: OK ({description})")
        except ImportError as e:
            print(f"  ⚠️  {module_name}: MISSING ({description})")
            local_ocr_ok = False
    
    return all_required_ok, local_ocr_ok

def test_tesseract():
    """Test Tesseract installation"""
    print("\n🔍 Testing Tesseract OCR...")
    
    try:
        import pytesseract
        from PIL import Image
        
        # Check Tesseract executable
        try:
            version = pytesseract.get_tesseract_version()
            print(f"  ✅ Tesseract version: {version}")
        except Exception as e:
            print(f"  ❌ Tesseract executable not found: {e}")
            return False
        
        # Check available languages
        try:
            languages = pytesseract.get_languages()
            print(f"  ✅ Available languages: {', '.join(languages)}")
            
            # Check for Portuguese and English
            required_langs = ['por', 'eng']
            missing_langs = [lang for lang in required_langs if lang not in languages]
            
            if missing_langs:
                print(f"  ⚠️  Missing language packs: {', '.join(missing_langs)}")
                print("      Install with: sudo apt install tesseract-ocr-por tesseract-ocr-eng")
            else:
                print("  ✅ Required language packs (por, eng) are available")
                
        except Exception as e:
            print(f"  ⚠️  Could not check languages: {e}")
        
        # Test basic OCR functionality
        try:
            # Create a simple test image
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a white image with black text
            img = Image.new('RGB', (200, 100), color='white')
            draw = ImageDraw.Draw(img)
            
            # Try to use a font, fallback to default if not available
            try:
                font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            draw.text((10, 30), "Test OCR", fill='black', font=font)
            
            # Test OCR
            text = pytesseract.image_to_string(img, lang='eng')
            if 'Test' in text or 'OCR' in text:
                print("  ✅ Basic OCR test: PASSED")
            else:
                print(f"  ⚠️  Basic OCR test: UNCLEAR (got: '{text.strip()}')")
                
        except Exception as e:
            print(f"  ⚠️  Could not test OCR functionality: {e}")
        
        return True
        
    except ImportError:
        print("  ❌ pytesseract or PIL not available")
        return False

def test_pdf_processing():
    """Test PDF processing capabilities"""
    print("\n🔍 Testing PDF processing...")
    
    try:
        import PyPDF2
        print("  ✅ PyPDF2: Available")
    except ImportError:
        print("  ❌ PyPDF2: Not available")
        return False
    
    try:
        from pdf2image import convert_from_path
        print("  ✅ pdf2image: Available")
        
        # Check if poppler is installed
        import subprocess
        result = subprocess.run(['which', 'pdftoppm'], capture_output=True)
        if result.returncode == 0:
            print("  ✅ poppler-utils: Available")
        else:
            print("  ⚠️  poppler-utils: Not found (install with: sudo apt install poppler-utils)")
            
    except ImportError:
        print("  ❌ pdf2image: Not available")
        return False
    
    return True

def main():
    """Main test function"""
    print("=== Enhanced OCR Setup Test ===\n")
    
    # Test imports
    required_ok, local_ok = test_imports()
    
    # Test Tesseract if available
    if local_ok:
        tesseract_ok = test_tesseract()
    else:
        tesseract_ok = False
        print("\n⚠️  Skipping Tesseract test (dependencies missing)")
    
    # Test PDF processing
    pdf_ok = test_pdf_processing()
    
    # Summary
    print("\n" + "="*50)
    print("📊 SUMMARY")
    print("="*50)
    
    if required_ok:
        print("✅ Basic functionality: READY")
        print("   - Can run the application")
        print("   - Cloud OCR will work (with API key)")
    else:
        print("❌ Basic functionality: NOT READY")
        print("   - Missing required Python modules")
        return False
    
    if local_ok and tesseract_ok:
        print("✅ Local OCR: READY")
        print("   - Tesseract is installed and working")
        print("   - Local processing available")
        print("   - Privacy mode available")
    elif local_ok:
        print("⚠️  Local OCR: PARTIALLY READY")
        print("   - Python modules available")
        print("   - Tesseract needs configuration")
    else:
        print("❌ Local OCR: NOT READY")
        print("   - Missing dependencies")
        print("   - Run: ./install_dependencies.sh")
    
    if pdf_ok:
        print("✅ PDF processing: READY")
    else:
        print("❌ PDF processing: NOT READY")
    
    print("\n🚀 To run the enhanced OCR application:")
    print("   python3 /home/leu/OCR_Enhanced_with_Local_Processing.py")
    
    if not (local_ok and tesseract_ok):
        print("\n💡 To install missing dependencies:")
        print("   ./install_dependencies.sh")
    
    return required_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)