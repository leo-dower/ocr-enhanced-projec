# Folder Configuration Guide

## Overview
This OCR application uses configurable folder paths for input and output files. This guide helps you set up folders correctly for your environment.

## Default Folder Structure

### Modern Versions (Recommended)
- **OCR_Enhanced_Hybrid_v1.py**: Dynamic folder selection via GUI buttons
- **OCR_Enhanced_with_Local_Processing.py**: Uses `~/Documents/OCR_Input` and `~/Documents/OCR_Output`
- **OCR_Enhanced_with_Searchable_PDF.py**: Uses `~/Documents/OCR_Input` and `~/Documents/OCR_Output`

### Legacy Version
- **SCRIPT OCR - MISTRAL...PY**: May require manual path configuration in code

## Setting Up Your Folders

### Option 1: Use Default Folders (Recommended)
The application will automatically create these folders in your Documents directory:

**Linux/Mac:**
```
~/Documents/OCR_Input/    # Place your PDF files here
~/Documents/OCR_Output/   # Results will be saved here
```

**Windows:**
```
C:\Users\[YourUsername]\Documents\OCR_Input\
C:\Users\[YourUsername]\Documents\OCR_Output\
```

### Option 2: Custom Folders (Latest Version Only)
In **OCR_Enhanced_Hybrid_v1.py**, you can select custom folders using the GUI:

1. Run the application
2. In "Basic Settings" section, click "Choose" next to "Input Folder"
3. Select where your PDF files are located
4. Click "Choose" next to "Output Folder"  
5. Select where you want results saved

### Option 3: Manual Configuration (All Versions)
To hardcode specific paths, edit these lines in the Python file:

```python
# Change these paths to your preferred directories
self.pasta_padrao = "/path/to/your/input/folder"   # Where PDF files are located
self.pasta_destino = "/path/to/your/output/folder" # Where results will be saved
```

## Examples

### Example 1: Personal Documents
```python
self.pasta_padrao = os.path.expanduser("~/Documents/PDFs_to_Process")
self.pasta_destino = os.path.expanduser("~/Documents/OCR_Results")
```

### Example 2: Business Environment
```python
self.pasta_padrao = "/shared/documents/incoming"
self.pasta_destino = "/shared/documents/processed"
```

### Example 3: Windows Paths
```python
self.pasta_padrao = r"C:\Work\Documents\Input"
self.pasta_destino = r"C:\Work\Documents\Output"
```

## Output Files

The application creates these files in the output folder:

- `filename_OCR_hybrid.json` - Complete OCR data with metadata
- `filename_OCR.md` - Clean text in Markdown format  
- `filename_pesquisavel.pdf` - Searchable PDF (if enabled)

## Troubleshooting

### Permissions
Make sure the application has read access to input folder and write access to output folder:

```bash
chmod 755 /path/to/input/folder
chmod 755 /path/to/output/folder
```

### Missing Folders
The application will automatically create output folders if they don't exist.

### Windows Path Format
Use raw strings (r"") or forward slashes for Windows paths:

```python
# Correct ways:
self.pasta_padrao = r"C:\Users\YourName\Documents\Input"
self.pasta_padrao = "C:/Users/YourName/Documents/Input"

# Incorrect way:
self.pasta_padrao = "C:\Users\YourName\Documents\Input"  # Backslashes cause issues
```

## Security Note

Never commit actual personal folder paths to version control. Use environment variables or configuration files for sensitive paths:

```python
import os
self.pasta_padrao = os.environ.get('OCR_INPUT_PATH', os.path.expanduser("~/Documents/OCR_Input"))
self.pasta_destino = os.environ.get('OCR_OUTPUT_PATH', os.path.expanduser("~/Documents/OCR_Output"))
```