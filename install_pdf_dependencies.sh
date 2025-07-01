#!/bin/bash

echo "=== Enhanced OCR - Instalação PDF Pesquisável ==="
echo "Este script instala as dependências para gerar PDFs pesquisáveis"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale primeiro."
    exit 1
fi

echo "🐍 Python encontrado: $(python3 --version)"

# Instalar dependências principais
echo "📦 Instalando dependências para PDF pesquisável..."

# ReportLab para geração de PDF
echo "📄 Instalando ReportLab..."
python3 -m pip install --user reportlab

# PyMuPDF para manipulação avançada de PDF
echo "🔧 Instalando PyMuPDF..."
python3 -m pip install --user PyMuPDF

# Dependências existentes (se não estiverem instaladas)
echo "📋 Verificando dependências existentes..."
python3 -m pip install --user requests PyPDF2 pytesseract pdf2image Pillow

echo ""
echo "🔍 Verificando instalação..."

# Testar importações
python3 -c "
import sys
print('📋 Testando dependências...')

# Dependências principais
try:
    import tkinter
    print('✅ tkinter: OK')
except ImportError:
    print('❌ tkinter: FALTANDO')

try:
    import requests
    print('✅ requests: OK')
except ImportError:
    print('❌ requests: FALTANDO')

try:
    import PyPDF2
    print('✅ PyPDF2: OK')
except ImportError:
    print('❌ PyPDF2: FALTANDO')

# Dependências para OCR local
try:
    import pytesseract
    print('✅ pytesseract: OK')
except ImportError:
    print('⚠️  pytesseract: FALTANDO (OCR local não funcionará)')

try:
    from pdf2image import convert_from_path
    print('✅ pdf2image: OK')
except ImportError:
    print('⚠️  pdf2image: FALTANDO (OCR local não funcionará)')

try:
    from PIL import Image
    print('✅ PIL (Pillow): OK')
except ImportError:
    print('⚠️  PIL: FALTANDO (OCR local não funcionará)')

# Dependências para PDF pesquisável
try:
    import reportlab
    print(f'✅ ReportLab: OK (versão {reportlab.Version})')
except ImportError:
    print('❌ ReportLab: FALTANDO (PDF pesquisável não funcionará)')

try:
    import fitz  # PyMuPDF
    print(f'✅ PyMuPDF: OK (versão {fitz.version[0]})')
except ImportError:
    print('❌ PyMuPDF: FALTANDO (PDF pesquisável não funcionará)')

print('')
print('🚀 Para executar a aplicação completa:')
print('   python3 OCR_Enhanced_with_Searchable_PDF.py')
"

echo ""
echo "💡 Notas importantes:"
echo "• Para OCR local: sudo apt install tesseract-ocr tesseract-ocr-por"
echo "• Para manipulação PDF: as dependências foram instaladas"
echo "• PDF pesquisável: ReportLab + PyMuPDF permitem criar PDFs com texto selecionável"
echo ""
echo "✅ Instalação concluída!"