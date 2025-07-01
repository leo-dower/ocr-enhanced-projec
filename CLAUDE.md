# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Python OCR batch processing application using Mistral AI's OCR API. The application provides a GUI for processing PDF documents through OCR with support for both local and cloud processing.

## Architecture

### Main Components

- **OCRBatchApp**: Core Tkinter GUI application class that handles:
  - File selection and batch processing
  - Robust HTTP session management with retry logic
  - PDF splitting for large documents
  - OCR processing via Mistral AI API
  - Result saving in JSON and Markdown formats

### Key Features

- Automatic PDF splitting for large documents (configurable page limits)
- Robust error handling with configurable retry attempts
- Conservative processing mode for rate limiting
- Detailed logging with timestamps and diagnostic information
- Progress tracking and status monitoring

## Dependencies

The application requires:
- `tkinter` - GUI framework
- `requests` - HTTP client with retry strategies
- `PyPDF2` - PDF manipulation
- `pathlib` - File path handling

## Running the Application

### Latest Version (Recommended)
```bash
python OCR_Enhanced_Hybrid_v1.py
```

### Legacy Version
```bash
python "SCRIPT OCR - MISTRAL OCR  - requisicao direta http v6 grafico - atualizado - LOTES BATCH - v2 cm log aprimorado.PY"
```

## Configuration

### Folder Selection (NEW)
- **Input Folder**: User-selectable via "Choose" button (where to find PDF files)
- **Output Folder**: User-selectable via "Choose" button (where to save results)
- **Default Folders**: Configurable fallback directories
- **Auto-Creation**: Output folders created automatically if needed

### Processing Settings
- Max pages per batch: 200 (configurable)
- Max retry attempts: 3 (configurable)
- Processing modes: Hybrid, Cloud-only, Local-only, Privacy

## API Integration

The application integrates with Mistral AI's OCR API endpoints:
- Upload: `https://api.mistral.ai/v1/files`
- OCR Processing: `https://api.mistral.ai/v1/ocr`
- Model verification: `https://api.mistral.ai/v1/models`

## Enhanced Version with Local Processing

An enhanced version with local OCR capabilities has been created: `OCR_Enhanced_with_Local_Processing.py`

### New Features

- **Local OCR Processing**: Uses Tesseract OCR for offline document processing
- **Hybrid Processing**: Try local first, fallback to cloud if quality is insufficient
- **Privacy Mode**: Process documents locally only (no data sent to cloud)
- **Quality Control**: Configurable confidence thresholds for local processing
- **Multi-language Support**: Portuguese, English, Spanish, and auto-detection
- **Processing Statistics**: Real-time tracking of local vs cloud processing

### Installation Requirements

```bash
# Run the installation script
./install_dependencies.sh

# Or install manually:
sudo apt install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng poppler-utils
pip3 install pytesseract pdf2image pillow requests PyPDF2
```

### Usage Modes

1. **Cloud Only**: Traditional mode using Mistral AI API
2. **Local Only**: Privacy mode using only Tesseract (no API key needed)
3. **Hybrid**: Try local first, use cloud if quality below threshold
4. **Privacy**: Force local processing for sensitive documents

### Testing Setup

```bash
# Test if all dependencies are properly installed
python3 test_ocr_setup.py
```

## Executável (.exe)

Um pacote completo para criar executável foi criado: `Enhanced_OCR_Executable_Package.zip`

### Conteúdo do Pacote

- `OCR_Enhanced_with_Local_Processing.py` - Código fonte
- `build.bat` - Script para Windows 
- `build.sh` - Script para Linux/Mac
- `requirements.txt` - Dependências Python
- `README_Executavel.txt` - Instruções completas

### Como Criar o Executável

**Windows:**
1. Extraia o ZIP
2. Execute `build.bat`
3. Executável criado em `dist/Enhanced_OCR.exe`

**Linux/Mac:**
1. Extraia o ZIP
2. Execute `./build.sh`
3. Executável criado em `dist/Enhanced_OCR`

### Pré-requisitos

- Python 3.8+
- Tesseract OCR instalado no sistema de destino
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt install tesseract-ocr tesseract-ocr-por`

## Versão Completa com PDF Pesquisável

A versão mais avançada inclui geração de PDFs pesquisáveis: `OCR_Enhanced_with_Searchable_PDF.py`

### Novas Funcionalidades

- **PDF Pesquisável**: Gera PDFs onde o texto pode ser selecionado e copiado
- **Texto Invisível**: Adiciona camada de texto por cima da imagem original
- **Múltiplos Formatos**: JSON + Markdown + PDF pesquisável
- **Controle de Qualidade**: Configura confiança mínima para incluir texto
- **Preservação Original**: PDF original permanece visualmente idêntico

### Como Funciona

1. **OCR Extrai Texto**: Local (Tesseract) ou Cloud (Mistral AI)
2. **Texto Invisível**: Sobreposto na posição correta do PDF
3. **PDF Resultante**: Visualmente igual, mas com texto selecionável
4. **Compatibilidade**: Funciona em qualquer visualizador de PDF

### Dependências Adicionais

```bash
# Instalar dependências para PDF pesquisável
./install_pdf_dependencies.sh

# Ou manualmente:
pip install PyMuPDF reportlab
```

### Formatos de Saída

- **JSON**: Dados completos do OCR com metadados
- **Markdown**: Texto limpo e formatado para leitura
- **PDF Pesquisável**: PDF original + camada de texto selecionável

### Vantagens do PDF Pesquisável

- 🔍 **Pesquisar** palavras com Ctrl+F
- 📋 **Selecionar e copiar** texto com mouse
- 📧 **Compartilhar** PDFs pesquisáveis
- 🗂️ **Organizar** biblioteca digital de documentos
- ✅ **Manter** aparência original do documento

## Dynamic Folder Selection (Latest Feature)

### Overview
The latest version (`OCR_Enhanced_Hybrid_v1.py`) includes dynamic folder selection, allowing users to choose custom input and output directories through the GUI.

### New Capabilities

#### Input Folder Selection
- **Purpose**: Choose where to look for PDF files
- **Interface**: "Choose" button in Basic Settings section
- **Features**: 
  - Shows PDF count in selected folder
  - Validates read permissions
  - Updates all file dialogs to start from selected folder

#### Output Folder Selection
- **Purpose**: Choose where to save OCR results (JSON, MD, searchable PDF)
- **Interface**: "Choose" button in Basic Settings section  
- **Features**:
  - Auto-creates folder if it doesn't exist
  - Validates write permissions
  - Shows available disk space
  - Updates all save operations to use selected folder

### User Experience Improvements
- **Visual Feedback**: Color-coded labels (blue for input, green for output)
- **Path Truncation**: Long paths displayed elegantly with "..." prefix
- **Tooltips**: Helpful explanations for each button and field
- **Validation**: Real-time permission and existence checks
- **Logging**: Detailed feedback about folder changes and validation

### Backward Compatibility
- **Default Behavior**: Falls back to original hardcoded paths if no custom folders selected
- **Configuration**: Default folders can still be modified in code for deployment
- **Legacy Support**: All existing functionality preserved