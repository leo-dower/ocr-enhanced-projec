#!/bin/bash
# Instalação apenas dos pacotes Python (sem sudo)

echo "=== Instalação Python-only - OCR Hybrid ==="
echo "Este script instala apenas os pacotes Python necessários"
echo "Assume que Tesseract já está instalado no sistema"
echo ""

# Verificar se Python está disponível
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale primeiro:"
    echo "   sudo apt install python3"
    exit 1
fi

echo "🐍 Python encontrado: $(python3 --version)"

# Verificar se pip está disponível
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ pip não está disponível. Instalando via get-pip.py..."
    
    # Baixar e instalar pip sem sudo
    curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    python3 /tmp/get-pip.py --user
    
    if [ $? -eq 0 ]; then
        echo "✅ pip instalado localmente"
        # Adicionar pip ao PATH se necessário
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo "❌ Falha ao instalar pip"
        echo "💡 Tente manualmente: sudo apt install python3-pip"
        exit 1
    fi
fi

echo "📦 pip encontrado: $(python3 -m pip --version)"

# Atualizar pip
echo ""
echo "🔄 Atualizando pip..."
python3 -m pip install --upgrade pip --user

# Lista de pacotes Python necessários
PACKAGES=(
    "pytesseract"
    "pdf2image" 
    "pillow"
    "PyMuPDF"
    "requests"
    "PyPDF2"
)

echo ""
echo "🐍 Instalando pacotes Python..."

FAILED_PACKAGES=()

for package in "${PACKAGES[@]}"; do
    echo ""
    echo "📦 Instalando $package..."
    
    # Verificar se já está instalado
    if python3 -c "import $(echo $package | tr 'A-Z' 'a-z' | sed 's/pymupdf/fitz/')" 2>/dev/null; then
        echo "✅ $package já está instalado"
        continue
    fi
    
    # Instalar com diferentes estratégias
    if python3 -m pip install --user "$package"; then
        echo "✅ $package instalado com sucesso"
    elif python3 -m pip install --user --upgrade "$package"; then
        echo "✅ $package atualizado com sucesso"
    elif python3 -m pip install --user --no-cache-dir "$package"; then
        echo "✅ $package instalado (sem cache)"
    else
        echo "❌ Falha ao instalar $package"
        FAILED_PACKAGES+=("$package")
    fi
done

echo ""
echo "✅ Verificando instalações..."

# Verificar cada pacote
echo "🐍 Testando importações..."
python3 -c "
import sys
success_count = 0
total_packages = 6

packages_map = {
    'pytesseract': 'pytesseract',
    'pdf2image': 'pdf2image', 
    'PIL': 'pillow',
    'fitz': 'PyMuPDF',
    'requests': 'requests',
    'PyPDF2': 'PyPDF2'
}

for import_name, package_name in packages_map.items():
    try:
        __import__(import_name)
        print(f'✅ {package_name} ({import_name})')
        success_count += 1
    except ImportError as e:
        print(f'❌ {package_name} ({import_name}) - {e}')

print(f'\\n📊 Resultado: {success_count}/{total_packages} pacotes funcionando')

if success_count >= 4:
    print('🎉 Instalação suficiente para funcionamento básico!')
    sys.exit(0)
elif success_count >= 2:
    print('⚠ Instalação parcial - alguns recursos podem não funcionar')
    sys.exit(1)
else:
    print('❌ Instalação insuficiente')
    sys.exit(2)
"

IMPORT_RESULT=$?

echo ""

# Testar funcionalidade básica se possível
if [ $IMPORT_RESULT -eq 0 ]; then
    echo "🧪 Testando funcionalidade básica..."
    
    python3 -c "
try:
    from PIL import Image, ImageDraw
    import pytesseract
    
    print('✅ PIL e pytesseract disponíveis')
    
    # Criar imagem simples
    img = Image.new('RGB', (200, 50), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 15), 'Test 123', fill='black')
    
    print('✅ Criação de imagem funcionando')
    
    # Testar OCR se Tesseract estiver disponível
    try:
        texto = pytesseract.image_to_string(img)
        print(f'✅ OCR básico funcionando: \"{texto.strip()}\"')
    except Exception as e:
        print(f'⚠ OCR com problemas: {e}')
        print('💡 Tesseract pode não estar instalado no sistema')
    
except Exception as e:
    print(f'❌ Erro no teste: {e}')
"
fi

echo ""
echo "=== INSTALAÇÃO PYTHON CONCLUÍDA ==="
echo ""

if [ ${#FAILED_PACKAGES[@]} -eq 0 ]; then
    echo "🎉 SUCESSO! Todos os pacotes Python foram instalados"
elif [ ${#FAILED_PACKAGES[@]} -lt 3 ]; then
    echo "⚠ PARCIALMENTE COMPLETO"
    echo "❌ Pacotes com problemas: ${FAILED_PACKAGES[*]}"
    echo "💡 Reinstale manualmente: python3 -m pip install --user ${FAILED_PACKAGES[*]}"
else
    echo "❌ MUITOS PROBLEMAS na instalação"
    echo "❌ Pacotes com falha: ${FAILED_PACKAGES[*]}"
fi

echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo ""
echo "1. 🔧 Para instalar Tesseract OCR (se necessário):"
echo "   sudo apt install tesseract-ocr tesseract-ocr-por poppler-utils"
echo ""
echo "2. 🧪 Para testar o sistema completo:"
echo "   python3 test_hybrid_setup.py"
echo ""
echo "3. 🚀 Para executar o OCR Hybrid:"
echo "   python3 OCR_Enhanced_Hybrid_v1.py"
echo ""
echo "💡 RESOLUÇÃO DE PROBLEMAS:"
echo "- Se imports falharem, reinicie o terminal"
echo "- Verifique PATH: echo \$PATH"
echo "- Força reinstalação: python3 -m pip install --user --force-reinstall <pacote>"
echo "- Limpar cache: python3 -m pip cache purge"
echo ""