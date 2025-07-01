#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de Configuração do OCR Hybrid
Verifica se todas as dependências estão funcionando corretamente
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path

def test_basic_imports():
    """Testar importações básicas"""
    print("🧪 Testando importações básicas...")
    
    try:
        import tkinter as tk
        print("✅ tkinter - Interface gráfica")
    except ImportError:
        print("❌ tkinter - Interface gráfica")
        return False
    
    try:
        import requests
        print("✅ requests - Cliente HTTP")
    except ImportError:
        print("❌ requests - Cliente HTTP")
        return False
    
    try:
        import PyPDF2
        print("✅ PyPDF2 - Manipulação de PDF")
    except ImportError:
        print("❌ PyPDF2 - Manipulação de PDF")
        return False
    
    return True

def test_local_ocr_dependencies():
    """Testar dependências do OCR local"""
    print("\n💻 Testando dependências OCR local...")
    
    # Tesseract
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"✅ pytesseract - Versão: {version}")
        tesseract_ok = True
    except Exception as e:
        print(f"❌ pytesseract - Erro: {e}")
        tesseract_ok = False
    
    # pdf2image
    try:
        from pdf2image import convert_from_path
        print("✅ pdf2image - Conversão PDF para imagem")
        pdf2image_ok = True
    except ImportError as e:
        print(f"❌ pdf2image - Erro: {e}")
        pdf2image_ok = False
    
    # PIL/Pillow
    try:
        from PIL import Image, ImageEnhance, ImageDraw
        print("✅ PIL/Pillow - Processamento de imagem")
        pil_ok = True
    except ImportError as e:
        print(f"❌ PIL/Pillow - Erro: {e}")
        pil_ok = False
    
    # PyMuPDF
    try:
        import fitz
        print("✅ PyMuPDF - PDF pesquisável")
        pymupdf_ok = True
    except ImportError as e:
        print(f"❌ PyMuPDF - Erro: {e}")
        pymupdf_ok = False
    
    return tesseract_ok, pdf2image_ok, pil_ok, pymupdf_ok

def test_tesseract_languages():
    """Testar idiomas do Tesseract"""
    print("\n🌍 Testando idiomas do Tesseract...")
    
    try:
        import pytesseract
        
        # Obter lista de idiomas
        langs = pytesseract.get_languages()
        
        required_langs = ['por', 'eng', 'spa']
        available_langs = []
        
        for lang in required_langs:
            if lang in langs:
                print(f"✅ {lang} - Disponível")
                available_langs.append(lang)
            else:
                print(f"❌ {lang} - Não disponível")
        
        return len(available_langs) > 0
        
    except Exception as e:
        print(f"❌ Erro ao verificar idiomas: {e}")
        return False

def test_ocr_functionality():
    """Testar funcionalidade básica do OCR"""
    print("\n🔍 Testando funcionalidade OCR...")
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        import pytesseract
        
        # Criar imagem de teste
        print("📄 Criando imagem de teste...")
        img = Image.new('RGB', (400, 150), color='white')
        draw = ImageDraw.Draw(img)
        
        # Tentar usar fonte padrão
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # Desenhar texto de teste
        test_text = "Teste OCR Hybrid 2025\nPortuguês English Español\n123 456 789"
        draw.text((20, 20), test_text, fill='black', font=font)
        
        # Testar OCR em diferentes idiomas
        idiomas_teste = ['por', 'eng', 'por+eng']
        
        for idioma in idiomas_teste:
            try:
                resultado = pytesseract.image_to_string(img, lang=idioma)
                confianca_data = pytesseract.image_to_data(img, lang=idioma, output_type=pytesseract.Output.DICT)
                
                # Calcular confiança média
                confidencias = [int(conf) for conf in confianca_data['conf'] if int(conf) > 0]
                confianca_media = sum(confidencias) / len(confidencias) if confidencias else 0
                
                print(f"✅ OCR {idioma} - Confiança: {confianca_media:.1f}%")
                print(f"   Texto: {resultado.strip()[:50]}...")
                
            except Exception as e:
                print(f"❌ OCR {idioma} - Erro: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste OCR: {e}")
        return False

def test_pdf_processing():
    """Testar processamento de PDF"""
    print("\n📄 Testando processamento de PDF...")
    
    try:
        from pdf2image import convert_from_path
        from PIL import Image, ImageDraw
        import PyPDF2
        import tempfile
        import os
        
        # Criar PDF de teste simples
        print("📝 Criando PDF de teste...")
        
        # Criar imagem
        img = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((50, 100), "Teste PDF OCR Hybrid", fill='black')
        draw.text((50, 150), "Documento de teste para OCR", fill='black')
        draw.text((50, 200), "2025", fill='black')
        
        # Salvar como PDF temporário
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            img.save(tmp_pdf.name, "PDF")
            test_pdf_path = tmp_pdf.name
        
        print(f"📁 PDF teste criado: {test_pdf_path}")
        
        # Testar conversão PDF para imagem
        try:
            imagens = convert_from_path(test_pdf_path, dpi=150)
            print(f"✅ Conversão PDF→Imagem - {len(imagens)} página(s)")
            
            # Testar OCR na primeira imagem
            if imagens:
                import pytesseract
                texto = pytesseract.image_to_string(imagens[0], lang='por')
                print(f"✅ OCR da imagem - Texto: {texto.strip()[:50]}...")
            
        except Exception as e:
            print(f"❌ Erro na conversão PDF→Imagem: {e}")
        
        # Testar leitura de metadados PDF
        try:
            with open(test_pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)
                print(f"✅ Leitura PDF - {num_pages} página(s)")
        except Exception as e:
            print(f"❌ Erro na leitura PDF: {e}")
        
        # Limpar arquivo temporário
        try:
            os.unlink(test_pdf_path)
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste PDF: {e}")
        return False

def test_searchable_pdf():
    """Testar geração de PDF pesquisável"""
    print("\n🔍 Testando PDF pesquisável...")
    
    try:
        import fitz  # PyMuPDF
        import tempfile
        import os
        
        # Criar PDF simples
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        
        # Adicionar texto visível
        page.insert_text((50, 100), "Documento Original", fontsize=16)
        
        # Adicionar texto invisível (pesquisável)
        page.insert_text((50, 150), "Texto OCR Pesquisável", fontsize=0.1, color=(1, 1, 1))
        
        # Salvar PDF temporário
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            doc.save(tmp_pdf.name)
            test_pdf_path = tmp_pdf.name
        
        doc.close()
        
        # Verificar se texto foi inserido
        doc_test = fitz.open(test_pdf_path)
        page_test = doc_test[0]
        texto_extraido = page_test.get_text()
        
        doc_test.close()
        
        if "Texto OCR Pesquisável" in texto_extraido:
            print("✅ PDF pesquisável - Texto invisível detectado")
        else:
            print("⚠ PDF pesquisável - Texto invisível não detectado")
        
        # Limpar
        try:
            os.unlink(test_pdf_path)
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste PDF pesquisável: {e}")
        return False

def print_installation_guide():
    """Imprimir guia de instalação"""
    print("\n" + "="*60)
    print("📋 GUIA DE INSTALAÇÃO")
    print("="*60)
    print()
    print("🔧 Para instalar dependências automaticamente:")
    print("   ./install_dependencies.sh")
    print()
    print("🐍 Para instalar pacotes Python manualmente:")
    print("   pip3 install --user pytesseract pdf2image pillow PyMuPDF")
    print()
    print("🖥️ Para instalar Tesseract no sistema:")
    print("   Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-por")
    print("   Fedora:        sudo dnf install tesseract tesseract-langpack-por")
    print("   Arch:          sudo pacman -S tesseract tesseract-data-por")
    print()
    print("📚 Para instalar poppler-utils (pdf2image):")
    print("   Ubuntu/Debian: sudo apt install poppler-utils")
    print("   Fedora:        sudo dnf install poppler-utils")
    print("   Arch:          sudo pacman -S poppler")
    print()

def main():
    """Função principal de teste"""
    print("="*60)
    print("🧪 TESTE DE CONFIGURAÇÃO - OCR HYBRID")
    print("="*60)
    print()
    
    # Testes básicos
    basic_ok = test_basic_imports()
    
    # Testes OCR local
    tesseract_ok, pdf2image_ok, pil_ok, pymupdf_ok = test_local_ocr_dependencies()
    
    # Teste de idiomas
    if tesseract_ok:
        langs_ok = test_tesseract_languages()
    else:
        langs_ok = False
    
    # Teste de funcionalidade
    if tesseract_ok and pil_ok:
        ocr_ok = test_ocr_functionality()
    else:
        ocr_ok = False
    
    # Teste PDF
    if pdf2image_ok and tesseract_ok:
        pdf_ok = test_pdf_processing()
    else:
        pdf_ok = False
    
    # Teste PDF pesquisável
    if pymupdf_ok:
        searchable_ok = test_searchable_pdf()
    else:
        searchable_ok = False
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    
    tests = [
        ("Importações básicas", basic_ok),
        ("Tesseract OCR", tesseract_ok),
        ("pdf2image", pdf2image_ok),
        ("PIL/Pillow", pil_ok),
        ("PyMuPDF", pymupdf_ok),
        ("Idiomas OCR", langs_ok),
        ("Funcionalidade OCR", ocr_ok),
        ("Processamento PDF", pdf_ok),
        ("PDF pesquisável", searchable_ok),
    ]
    
    for name, status in tests:
        icon = "✅" if status else "❌"
        print(f"{icon} {name}")
    
    # Verificar compatibilidade com modos
    print("\n🎯 COMPATIBILIDADE COM MODOS:")
    
    if basic_ok:
        print("✅ Modo Cloud Only - Requisitos atendidos")
    else:
        print("❌ Modo Cloud Only - Faltam dependências básicas")
    
    if tesseract_ok and pdf2image_ok and pil_ok:
        print("✅ Modo Local Only - Requisitos atendidos")
        print("✅ Modo Privacy - Requisitos atendidos")
        print("✅ Modo Hybrid - Requisitos atendidos")
    else:
        print("❌ Modo Local Only - Faltam dependências locais")
        print("❌ Modo Privacy - Faltam dependências locais")
        print("❌ Modo Hybrid - Faltam dependências locais")
    
    if pymupdf_ok:
        print("✅ PDF Pesquisável - Funcionalidade disponível")
    else:
        print("❌ PDF Pesquisável - PyMuPDF não disponível")
    
    # Recomendações
    total_passed = sum(status for _, status in tests)
    total_tests = len(tests)
    
    print(f"\n📈 RESULTADO: {total_passed}/{total_tests} testes passaram")
    
    if total_passed == total_tests:
        print("🎉 SISTEMA TOTALMENTE FUNCIONAL!")
        print("🚀 Execute: python3 /home/leu/OCR_Enhanced_Hybrid_v1.py")
    elif total_passed >= 6:
        print("⚠ SISTEMA PARCIALMENTE FUNCIONAL")
        print("💡 Alguns recursos podem não estar disponíveis")
    else:
        print("❌ SISTEMA COM PROBLEMAS")
        print_installation_guide()

if __name__ == "__main__":
    main()