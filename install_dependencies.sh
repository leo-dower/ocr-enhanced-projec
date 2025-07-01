#!/bin/bash
# Script para instalar dependências do OCR Hybrid

echo "=== Instalador de Dependências - OCR Hybrid ==="
echo "Este script instalará todas as dependências necessárias"
echo "para o sistema OCR híbrido (local + cloud)"
echo ""

# Função para verificar se comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Função para detectar distribuição Linux
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo $ID
    elif command_exists lsb_release; then
        lsb_release -si | tr '[:upper:]' '[:lower:]'
    else
        echo "unknown"
    fi
}

# Função para verificar sucesso do comando
check_success() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
        return 0
    else
        echo "❌ $1"
        return 1
    fi
}

# Verificar se é sistema Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Este script é para sistemas Linux"
    echo "Para Windows/Mac, instale manualmente:"
    echo "- Tesseract OCR"
    echo "- Python packages: pip install pytesseract pdf2image pillow PyMuPDF"
    exit 1
fi

# Verificar se não está rodando como root
if [[ $EUID -eq 0 ]]; then
    echo "⚠️ Este script não deve ser executado como root"
    echo "Execute como usuário normal (usará sudo quando necessário)"
    exit 1
fi

echo "🔍 Detectando sistema..."
DISTRO=$(detect_distro)
echo "Sistema detectado: $DISTRO"
echo ""

# Verificar se sudo está disponível
if ! command_exists sudo; then
    echo "❌ sudo não está instalado. Instale sudo primeiro:"
    echo "   su -c 'apt install sudo && usermod -aG sudo $USER'"
    exit 1
fi

# Atualizar lista de pacotes
echo "📦 Atualizando lista de pacotes..."
case $DISTRO in
    ubuntu|debian)
        sudo apt update
        check_success "Lista de pacotes atualizada"
        ;;
    fedora)
        sudo dnf check-update || true
        check_success "Lista de pacotes atualizada"
        ;;
    centos|rhel)
        sudo yum check-update || true
        check_success "Lista de pacotes atualizada"
        ;;
    arch|manjaro)
        sudo pacman -Sy
        check_success "Lista de pacotes atualizada"
        ;;
    *)
        echo "⚠ Distribuição não reconhecida, tentando apt..."
        sudo apt update 2>/dev/null || echo "⚠ Falha ao atualizar pacotes"
        ;;
esac

echo ""
echo "🔧 Instalando Tesseract OCR e dependências do sistema..."

# Instalar Tesseract e dependências do sistema
INSTALL_SUCCESS=true

case $DISTRO in
    ubuntu|debian)
        sudo apt install -y tesseract-ocr tesseract-ocr-por tesseract-ocr-eng tesseract-ocr-spa poppler-utils python3-pip
        check_success "Tesseract e dependências instalados" || INSTALL_SUCCESS=false
        ;;
    fedora)
        sudo dnf install -y tesseract tesseract-langpack-por tesseract-langpack-eng tesseract-langpack-spa poppler-utils python3-pip
        check_success "Tesseract e dependências instalados" || INSTALL_SUCCESS=false
        ;;
    centos|rhel)
        # EPEL repository necessário para Tesseract
        sudo yum install -y epel-release
        sudo yum install -y tesseract tesseract-langpack-por tesseract-langpack-eng tesseract-langpack-spa poppler-utils python3-pip
        check_success "Tesseract e dependências instalados" || INSTALL_SUCCESS=false
        ;;
    arch|manjaro)
        sudo pacman -S --noconfirm tesseract tesseract-data-por tesseract-data-eng tesseract-data-spa poppler python-pip
        check_success "Tesseract e dependências instalados" || INSTALL_SUCCESS=false
        ;;
    *)
        echo "⚠ Tentando instalação genérica..."
        sudo apt install -y tesseract-ocr tesseract-ocr-por tesseract-ocr-eng tesseract-ocr-spa poppler-utils python3-pip 2>/dev/null || \
        sudo yum install -y tesseract tesseract-langpack-por tesseract-langpack-eng tesseract-langpack-spa poppler-utils python3-pip 2>/dev/null || \
        { echo "❌ Falha na instalação automática. Instale manualmente o Tesseract OCR"; INSTALL_SUCCESS=false; }
        ;;
esac

if [ "$INSTALL_SUCCESS" = false ]; then
    echo ""
    echo "❌ Houve problemas na instalação dos pacotes do sistema"
    echo "💡 Tente instalar manualmente:"
    echo "   sudo apt install tesseract-ocr tesseract-ocr-por poppler-utils python3-pip"
    echo ""
fi

echo ""
echo "🐍 Instalando pacotes Python..."

# Garantir que pip está atualizado
if command_exists pip3; then
    echo "📦 Atualizando pip..."
    python3 -m pip install --upgrade pip --user
    PIP_CMD="pip3"
elif command_exists pip; then
    echo "📦 Atualizando pip..."
    python3 -m pip install --upgrade pip --user
    PIP_CMD="pip"
else
    echo "❌ pip não encontrado. Instalando..."
    case $DISTRO in
        ubuntu|debian)
            sudo apt install -y python3-pip
            ;;
        fedora)
            sudo dnf install -y python3-pip
            ;;
        *)
            echo "❌ Não foi possível instalar pip automaticamente"
            echo "Instale manualmente: sudo apt install python3-pip"
            exit 1
            ;;
    esac
    PIP_CMD="pip3"
fi

# Instalar dependências Python
echo "🐍 Instalando dependências Python..."
PYTHON_PACKAGES=("pytesseract" "pdf2image" "pillow" "PyMuPDF" "requests" "PyPDF2")
FAILED_PACKAGES=()

for package in "${PYTHON_PACKAGES[@]}"; do
    echo "  Instalando $package..."
    if python3 -m pip install --user "$package"; then
        echo "  ✅ $package instalado"
    else
        echo "  ❌ Falha ao instalar $package"
        FAILED_PACKAGES+=("$package")
    fi
done

echo ""
echo "✅ Verificando instalações..."

# Verificar Tesseract
if command_exists tesseract; then
    echo "✅ Tesseract OCR instalado:"
    tesseract --version | head -1
    
    echo "📋 Idiomas disponíveis:"
    if tesseract --list-langs 2>/dev/null | grep -E "(por|eng|spa)"; then
        echo "✅ Idiomas necessários encontrados"
    else
        echo "⚠ Alguns idiomas podem não estar disponíveis"
        echo "💡 Instale manualmente: sudo apt install tesseract-ocr-por tesseract-ocr-eng"
    fi
else
    echo "❌ Tesseract não foi instalado corretamente"
    echo "💡 Instale manualmente: sudo apt install tesseract-ocr"
fi

echo ""

# Verificar Python packages
echo "🐍 Verificando pacotes Python..."
python3 -c "
import sys
packages = ['pytesseract', 'pdf2image', 'PIL', 'fitz', 'requests', 'PyPDF2']
missing = []

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
        missing.append(pkg)

if missing:
    print(f'\\n⚠ Pacotes em falta: {missing}')
    print('Execute: python3 -m pip install --user ' + ' '.join(missing))
    sys.exit(1)
else:
    print('\\n🎉 Todos os pacotes Python estão instalados!')
    sys.exit(0)
"

PYTHON_CHECK_RESULT=$?

echo ""

# Verificar se poppler-utils está instalado
if command_exists pdftoppm; then
    echo "✅ poppler-utils instalado (necessário para pdf2image)"
else
    echo "❌ poppler-utils não encontrado"
    echo "💡 Instale com: sudo apt install poppler-utils"
fi

echo ""
echo "🧪 Teste rápido do Tesseract..."

# Testar Tesseract básico
if command_exists tesseract; then
    python3 -c "
try:
    from PIL import Image, ImageDraw
    import pytesseract
    
    # Criar imagem de teste
    img = Image.new('RGB', (300, 100), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), 'Teste OCR 123', fill='black')
    
    # Testar OCR
    texto = pytesseract.image_to_string(img, lang='por')
    print(f'✅ Teste OCR funcionando: \"{texto.strip()}\"')
    
except Exception as e:
    print(f'❌ Erro no teste OCR: {e}')
    print('💡 Verifique se Tesseract está no PATH')
"
else
    echo "⚠ Tesseract não disponível para teste"
fi

echo ""
echo "📄 Teste de conversão PDF..."

python3 -c "
try:
    from pdf2image import convert_from_path
    print('✅ pdf2image funcionando')
except Exception as e:
    print(f'❌ Erro no pdf2image: {e}')
    print('💡 Instale poppler-utils: sudo apt install poppler-utils')
"

echo ""
echo "=== INSTALAÇÃO CONCLUÍDA ==="
echo ""

# Verificar status geral
if [ $PYTHON_CHECK_RESULT -eq 0 ] && command_exists tesseract && command_exists pdftoppm; then
    echo "🎉 SUCESSO TOTAL! Todas as dependências estão funcionando"
    echo ""
    echo "🚀 Para executar o OCR Hybrid:"
    echo "   python3 OCR_Enhanced_Hybrid_v1.py"
    echo ""
    echo "🧪 Para testar o sistema:"
    echo "   python3 test_hybrid_setup.py"
else
    echo "⚠ INSTALAÇÃO PARCIAL - Alguns componentes podem não funcionar"
    echo ""
    if [ ${#FAILED_PACKAGES[@]} -gt 0 ]; then
        echo "❌ Pacotes Python com falha: ${FAILED_PACKAGES[*]}"
        echo "💡 Reinstale: python3 -m pip install --user ${FAILED_PACKAGES[*]}"
        echo ""
    fi
    
    echo "🔧 RESOLUÇÃO DE PROBLEMAS:"
    echo "1. Verifique conexão com internet"
    echo "2. Execute: sudo apt update && sudo apt upgrade"
    echo "3. Reinstale pip: sudo apt install --reinstall python3-pip"
    echo "4. Limpe cache: python3 -m pip cache purge"
fi

echo ""
echo "📋 RESUMO:"
echo "✅ Tesseract OCR - Engine de OCR local"
echo "✅ Idiomas: Português, Inglês, Espanhol"
echo "✅ pytesseract - Interface Python para Tesseract"
echo "✅ pdf2image - Conversão PDF para imagem"
echo "✅ PyMuPDF - Geração de PDF pesquisável"
echo "✅ Pillow - Processamento de imagens"
echo ""
echo "💡 MODOS DISPONÍVEIS:"
echo "- 🔄 Híbrido: Tenta local primeiro, cloud se necessário"
echo "- ☁️ Cloud: Apenas Mistral AI"
echo "- 💻 Local: Apenas Tesseract (privacidade total)"
echo "- 🔒 Privacy: Forçar processamento local"
echo ""