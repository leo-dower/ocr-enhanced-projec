#!/bin/bash
# Instalação manual passo-a-passo das dependências

echo "=== Instalação Manual - OCR Hybrid ==="
echo "Este script instala dependências uma por vez com feedback detalhado"
echo ""

# Função para verificar comandos
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Função para pausar e confirmar
confirm_step() {
    echo ""
    read -p "Pressione Enter para continuar ou Ctrl+C para cancelar..."
    echo ""
}

echo "🔍 Verificando sistema atual..."
echo "Sistema: $(uname -a)"
echo "Distribuição: $(cat /etc/os-release | grep PRETTY_NAME)"
echo "Python: $(python3 --version)"
echo ""

# Passo 1: Atualizar sistema
echo "📦 PASSO 1: Atualizar lista de pacotes"
echo "Comando: sudo apt update"
confirm_step

sudo apt update
if [ $? -eq 0 ]; then
    echo "✅ Lista de pacotes atualizada"
else
    echo "❌ Erro ao atualizar. Verifique conexão de internet."
    exit 1
fi

# Passo 2: Instalar Python pip
echo ""
echo "🐍 PASSO 2: Instalar Python pip"
if command_exists pip3; then
    echo "✅ pip3 já está instalado"
else
    echo "Comando: sudo apt install -y python3-pip"
    confirm_step
    
    sudo apt install -y python3-pip
    if [ $? -eq 0 ]; then
        echo "✅ python3-pip instalado"
    else
        echo "❌ Erro ao instalar python3-pip"
        exit 1
    fi
fi

# Passo 3: Instalar Tesseract
echo ""
echo "🔧 PASSO 3: Instalar Tesseract OCR"
if command_exists tesseract; then
    echo "✅ Tesseract já está instalado"
    tesseract --version | head -1
else
    echo "Comando: sudo apt install -y tesseract-ocr"
    confirm_step
    
    sudo apt install -y tesseract-ocr
    if [ $? -eq 0 ]; then
        echo "✅ tesseract-ocr instalado"
    else
        echo "❌ Erro ao instalar tesseract-ocr"
        exit 1
    fi
fi

# Passo 4: Instalar idiomas do Tesseract
echo ""
echo "🌍 PASSO 4: Instalar idiomas do Tesseract"
echo "Comando: sudo apt install -y tesseract-ocr-por tesseract-ocr-eng tesseract-ocr-spa"
confirm_step

sudo apt install -y tesseract-ocr-por tesseract-ocr-eng tesseract-ocr-spa
if [ $? -eq 0 ]; then
    echo "✅ Idiomas do Tesseract instalados"
    echo "📋 Verificando idiomas disponíveis:"
    tesseract --list-langs 2>/dev/null | grep -E "(por|eng|spa)" || echo "⚠ Alguns idiomas podem não ter sido instalados"
else
    echo "❌ Erro ao instalar idiomas. Continuando..."
fi

# Passo 5: Instalar poppler-utils
echo ""
echo "📄 PASSO 5: Instalar poppler-utils (para conversão PDF)"
if command_exists pdftoppm; then
    echo "✅ poppler-utils já está instalado"
else
    echo "Comando: sudo apt install -y poppler-utils"
    confirm_step
    
    sudo apt install -y poppler-utils
    if [ $? -eq 0 ]; then
        echo "✅ poppler-utils instalado"
    else
        echo "❌ Erro ao instalar poppler-utils"
        exit 1
    fi
fi

# Passo 6: Atualizar pip
echo ""
echo "🔄 PASSO 6: Atualizar pip"
echo "Comando: python3 -m pip install --upgrade pip --user"
confirm_step

python3 -m pip install --upgrade pip --user
if [ $? -eq 0 ]; then
    echo "✅ pip atualizado"
else
    echo "⚠ Aviso: Erro ao atualizar pip, mas continuando..."
fi

# Passo 7: Instalar pacotes Python individualmente
echo ""
echo "🐍 PASSO 7: Instalar pacotes Python"
PACKAGES=("pytesseract" "pdf2image" "pillow" "PyMuPDF" "requests" "PyPDF2")

for package in "${PACKAGES[@]}"; do
    echo ""
    echo "📦 Instalando $package..."
    echo "Comando: python3 -m pip install --user $package"
    
    # Verificar se já está instalado
    if python3 -c "import $package" 2>/dev/null; then
        echo "✅ $package já está instalado"
        continue
    fi
    
    confirm_step
    
    python3 -m pip install --user "$package"
    if [ $? -eq 0 ]; then
        echo "✅ $package instalado com sucesso"
        
        # Verificar importação
        if python3 -c "import $package" 2>/dev/null; then
            echo "✅ $package importa corretamente"
        else
            echo "⚠ $package instalado mas com problemas de importação"
        fi
    else
        echo "❌ Erro ao instalar $package"
        echo "💡 Tente: python3 -m pip install --user --upgrade $package"
    fi
done

# Passo 8: Verificação final
echo ""
echo "✅ PASSO 8: Verificação final"
echo ""

# Verificar comandos do sistema
echo "🔧 Comandos do sistema:"
for cmd in tesseract pdftoppm python3 pip3; do
    if command_exists "$cmd"; then
        echo "✅ $cmd"
    else
        echo "❌ $cmd"
    fi
done

echo ""
echo "🐍 Pacotes Python:"
python3 -c "
packages = ['pytesseract', 'pdf2image', 'PIL', 'fitz', 'requests', 'PyPDF2']
for pkg in packages:
    try:
        if pkg == 'PIL':
            import PIL
        elif pkg == 'fitz':
            import fitz
        else:
            __import__(pkg)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg}')
"

echo ""
echo "🧪 TESTE FINAL: OCR básico"
python3 -c "
try:
    from PIL import Image, ImageDraw
    import pytesseract
    
    # Criar imagem de teste
    img = Image.new('RGB', (300, 80), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), 'Teste OCR Manual', fill='black')
    
    # Testar OCR
    texto = pytesseract.image_to_string(img, lang='por')
    print(f'✅ OCR funcionando: \"{texto.strip()}\"')
    
except Exception as e:
    print(f'❌ Erro no teste: {e}')
"

echo ""
echo "=== INSTALAÇÃO MANUAL CONCLUÍDA ==="
echo ""
echo "🚀 Para testar o sistema completo:"
echo "   python3 test_hybrid_setup.py"
echo ""
echo "🏃 Para executar o OCR Hybrid:"
echo "   python3 OCR_Enhanced_Hybrid_v1.py"
echo ""
echo "💡 Se houver problemas:"
echo "1. Reinicie o terminal"
echo "2. Verifique PATH: echo \$PATH"
echo "3. Teste importações individuais: python3 -c 'import pytesseract'"
echo ""