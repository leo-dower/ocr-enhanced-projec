# OCR Enhanced - Guia de Distribuição

Este documento descreve o processo completo de distribuição do OCR Enhanced, incluindo build, empacotamento e publicação.

## Visão Geral

O OCR Enhanced oferece múltiplas formas de distribuição:

1. **Pacote Python (PyPI)** - Instalação via `pip install`
2. **Executáveis Standalone** - Aplicações independentes para Windows, Linux e macOS
3. **Código Fonte** - Instalação a partir do repositório GitHub

## Estrutura de Distribuição

```
build_scripts/
├── build.py                 # Script principal de build
├── publish.py               # Script de publicação no PyPI
├── build_executable.py      # Script para executáveis
├── build_windows.bat        # Build Windows automatizado
├── build_linux.sh          # Build Linux automatizado
└── build_macos.sh           # Build macOS automatizado
```

## 1. Distribuição via PyPI

### Pré-requisitos

- Python 3.8+
- Conta no PyPI e Test PyPI
- Token de API configurado

### Build do Pacote

```bash
# Build manual
python build_scripts/build.py

# Build com opções
python build_scripts/build.py --skip-tests --skip-clean
```

### Publicação

```bash
# Publicação no Test PyPI (recomendado primeiro)
python build_scripts/publish.py --repository test

# Publicação no PyPI produção
python build_scripts/publish.py --repository pypi

# Forçar upload (sobrescrever versão existente)
python build_scripts/publish.py --force
```

### Configuração de Credenciais

#### Opção 1: Variáveis de Ambiente (Recomendado)
```bash
# PyPI Production
export PYPI_API_TOKEN="pypi-your-token-here"

# Test PyPI
export TEST_PYPI_API_TOKEN="pypi-your-test-token-here"
```

#### Opção 2: Username/Password
```bash
export PYPI_USERNAME="your-username"
export PYPI_PASSWORD="your-password"
```

### Instalação do Usuário

```bash
# Instalação básica
pip install ocr-enhanced

# Instalação com dependências de desenvolvimento
pip install ocr-enhanced[dev]

# Instalação com documentação
pip install ocr-enhanced[docs]
```

## 2. Executáveis Standalone

### Pré-requisitos por Plataforma

#### Windows
- Python 3.8+
- PyInstaller
- Visual Studio Build Tools (opcional)

#### Linux
- Python 3.8+
- PyInstaller
- Tesseract OCR
- Bibliotecas de sistema:
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por poppler-utils
  ```

#### macOS
- Python 3.8+
- PyInstaller
- Tesseract OCR via Homebrew:
  ```bash
  brew install tesseract poppler
  ```

### Build de Executáveis

#### Build Automático por Plataforma

**Windows:**
```cmd
build_scripts\build_windows.bat
```

**Linux:**
```bash
./build_scripts/build_linux.sh
```

**macOS:**
```bash
./build_scripts/build_macos.sh
```

#### Build Manual Multiplataforma

```bash
# Build todas as configurações (GUI + CLI)
python build_scripts/build_executable.py --config all

# Build apenas GUI
python build_scripts/build_executable.py --config gui

# Build apenas CLI
python build_scripts/build_executable.py --config cli
```

### Estrutura dos Executáveis

Os executáveis são empacotados com:

- **Aplicação principal** (GUI ou CLI)
- **Documentação** (README, LICENSE, instruções)
- **Scripts de instalação** por plataforma
- **Checksums** para verificação de integridade

### Distribuição dos Executáveis

Os executáveis são empacotados em:
- **Windows**: Arquivo ZIP
- **Linux**: Arquivo TAR.GZ
- **macOS**: Arquivo TAR.GZ (com .app bundle para GUI)

## 3. Versionamento Automático

### Sistema de Versões

O projeto usa versionamento semântico (SemVer):
- **MAJOR.MINOR.PATCH** (ex: 2.0.0)
- **Pre-releases**: 2.1.0-alpha, 2.1.0-beta, 2.1.0-rc1
- **Build metadata**: 2.0.0+build.123

### Configuração de Versão

```python
# src/__init__.py
VERSION_INFO = {
    "major": 2,
    "minor": 0,
    "patch": 0,
    "pre_release": None,  # alpha, beta, rc
    "build": None
}
```

### Atualização de Versão

1. Editar `src/__init__.py`
2. Atualizar `VERSION_INFO`
3. Verificar consistência com `__version__`
4. Executar build para validar

## 4. CI/CD Automático

### GitHub Actions

O projeto inclui pipeline CI/CD completo:

```yaml
# .github/workflows/ci.yml
- Build automático em múltiplas plataformas
- Testes unitários e de integração
- Verificação de qualidade de código
- Publicação automática no PyPI (em releases)
- Build de executáveis multiplataforma
```

### Configuração de Secrets

No GitHub, configure os seguintes secrets:

```
PYPI_API_TOKEN          # Token para PyPI produção
TEST_PYPI_API_TOKEN     # Token para Test PyPI
CODECOV_TOKEN           # Token para Codecov (opcional)
```

### Processo de Release

1. **Atualizar versão** em `src/__init__.py`
2. **Criar commit** com mudanças
3. **Criar tag** de versão:
   ```bash
   git tag -a v2.0.0 -m "Release v2.0.0"
   git push origin v2.0.0
   ```
4. **Criar Release** no GitHub
5. **CI/CD executa automaticamente**:
   - Testes
   - Build de pacotes
   - Publicação no PyPI
   - Build de executáveis
   - Upload de artifacts

## 5. Distribuição via GitHub

### Releases

Cada release inclui:

- **Código fonte** (ZIP e TAR.GZ)
- **Executáveis** para Windows, Linux, macOS
- **Pacotes Python** (.whl e .tar.gz)
- **Documentação** e notas de release
- **Checksums** para verificação

### Download Direto

```bash
# Última versão
wget https://github.com/leo-dower/ocr-enhanced-projec/releases/latest/download/OCR-Enhanced-v2.0.0-linux-x86_64.tar.gz

# Versão específica
wget https://github.com/leo-dower/ocr-enhanced-projec/releases/download/v2.0.0/OCR-Enhanced-v2.0.0-windows-x86_64.zip
```

## 6. Instalação para Usuários

### Via PyPI (Recomendado)

```bash
# Instalação simples
pip install ocr-enhanced

# Atualização
pip install --upgrade ocr-enhanced

# Instalação de versão específica
pip install ocr-enhanced==2.0.0
```

### Via Executáveis

1. **Download** do executável para sua plataforma
2. **Extrair** o arquivo
3. **Instalar dependências** do sistema (Tesseract OCR)
4. **Executar** a aplicação

### Via Código Fonte

```bash
# Clone do repositório
git clone https://github.com/leo-dower/ocr-enhanced-projec.git
cd ocr-enhanced-projec

# Instalação em modo desenvolvimento
pip install -e .

# Ou instalação normal
pip install .
```

## 7. Verificação e Validação

### Checksums

Todos os arquivos distribuídos incluem checksums SHA256:

```bash
# Verificar integridade
sha256sum -c checksums.txt
```

### Assinatura Digital

Para executáveis macOS, suporte a code signing:

```bash
# Verificar assinatura
codesign -v dist_executable/OCR-Enhanced-GUI.app
```

### Testes de Distribuição

```bash
# Testar pacote PyPI
pip install ocr-enhanced --index-url https://test.pypi.org/simple/

# Testar executável
./OCR-Enhanced-CLI --version
```

## 8. Suporte Multiplataforma

### Sistemas Suportados

| Plataforma | Versões | Arquitetura | Status |
|------------|---------|-------------|--------|
| Windows    | 10, 11  | x64, x86    | ✅ Full |
| Linux      | Ubuntu 18.04+ | x64     | ✅ Full |
| Linux      | CentOS 8+     | x64     | ✅ Full |
| macOS      | 10.14+        | x64, ARM | ✅ Full |

### Dependências por Plataforma

#### Windows
- Tesseract OCR (manual)
- Visual C++ Redistributable (automático)

#### Linux
```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por poppler-utils

# CentOS/RHEL/Fedora
sudo dnf install tesseract tesseract-langpack-eng tesseract-langpack-por poppler-utils
```

#### macOS
```bash
# Via Homebrew
brew install tesseract poppler

# Verificar instalação
tesseract --version
```

## 9. Resolução de Problemas

### Problemas Comuns

#### Build Falha
```bash
# Limpar cache
python build_scripts/build.py --clean

# Reinstalar dependências
pip install --force-reinstall pyinstaller
```

#### Executável Não Inicia
- Verificar dependências do sistema
- Executar em modo console para ver erros
- Verificar permissões de execução

#### PyPI Upload Falha
- Verificar credenciais
- Confirmar que versão não existe
- Usar `--force` se necessário

### Logs de Debug

```bash
# Build verbose
python build_scripts/build.py --verbose

# PyInstaller debug
pyinstaller --debug all script.py
```

## 10. Manutenção

### Atualização de Dependências

```bash
# Atualizar requirements
pip-compile requirements.in
pip-compile requirements/dev.in

# Testar compatibilidade
python build_scripts/build.py --skip-clean
```

### Monitoramento

- **PyPI downloads**: https://pypistats.org/packages/ocr-enhanced
- **GitHub releases**: Insights > Traffic
- **Dependências**: Dependabot alerts

### Cronograma de Releases

- **Patch releases**: Mensalmente (bug fixes)
- **Minor releases**: Trimestralmente (novas features)
- **Major releases**: Anualmente (breaking changes)

## Conclusão

Este sistema de distribuição oferece flexibilidade máxima para usuários:

- **Desenvolvedores**: Instalação via pip
- **Usuários finais**: Executáveis standalone
- **Sistemas corporativos**: Build a partir do código fonte

O processo é amplamente automatizado via CI/CD, garantindo qualidade e consistência em todas as plataformas.