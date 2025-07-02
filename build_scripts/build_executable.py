#!/usr/bin/env python3
"""
Executable build script for OCR Enhanced.

This script creates standalone executables for Windows, Linux, and macOS using PyInstaller.
Supports both GUI and CLI versions with proper dependency management.
"""

import os
import sys
import subprocess
import shutil
import argparse
import platform
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

# Add src to path for version import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from src import __version__, PACKAGE_INFO
except ImportError as e:
    print(f"Error importing version info: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)


class ExecutableBuilder:
    """Builds standalone executables for OCR Enhanced."""
    
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).parent.parent
        self.build_dir = self.root_dir / "build_executable"
        self.dist_dir = self.root_dir / "dist_executable"
        
        # Platform detection
        self.platform = platform.system().lower()
        self.architecture = platform.machine().lower()
        
        # Executable configurations
        self.configs = {
            "gui": {
                "name": "OCR-Enhanced-GUI",
                "script": "src/gui/main_window.py",
                "windowed": True,
                "icon": None,  # Will be set if available
                "console": False
            },
            "cli": {
                "name": "OCR-Enhanced-CLI", 
                "script": "src/core/cli.py",
                "windowed": False,
                "icon": None,
                "console": True
            }
        }
        
        # Platform-specific settings
        self.platform_settings = {
            "windows": {
                "extension": ".exe",
                "separator": "\\",
                "hidden_imports": ["win32gui", "win32con"],
                "exclude_modules": ["tkinter"] if "cli" in sys.argv else []
            },
            "linux": {
                "extension": "",
                "separator": "/",
                "hidden_imports": [],
                "exclude_modules": []
            },
            "darwin": {  # macOS
                "extension": ".app",
                "separator": "/", 
                "hidden_imports": [],
                "exclude_modules": []
            }
        }
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with timestamp."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a command and return the result."""
        self.log(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, 
                cwd=self.root_dir, 
                check=check,
                capture_output=True,
                text=True
            )
            if result.stdout:
                self.log(f"Output: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e}", "ERROR")
            if e.stdout:
                self.log(f"stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"stderr: {e.stderr}", "ERROR")
            raise
    
    def check_prerequisites(self) -> None:
        """Check that all prerequisites are met."""
        self.log("Checking prerequisites...")
        
        # Check PyInstaller
        try:
            result = subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
            self.log(f"PyInstaller version: {result.stdout.decode().strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("Installing PyInstaller...")
            self.run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
        # Check platform-specific dependencies
        if self.platform == "windows":
            try:
                import win32gui
                self.log("Windows dependencies available")
            except ImportError:
                self.log("Installing Windows dependencies...")
                self.run_command([sys.executable, "-m", "pip", "install", "pywin32"])
        
        # Check for required system libraries
        self._check_system_libraries()
    
    def _check_system_libraries(self) -> None:
        """Check for required system libraries."""
        self.log("Checking system libraries...")
        
        if self.platform == "linux":
            # Check for Tesseract
            try:
                result = subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
                self.log("Tesseract available")
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log("Tesseract not found. Please install: sudo apt install tesseract-ocr", "WARNING")
        
        elif self.platform == "darwin":
            # Check for Tesseract on macOS
            try:
                result = subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
                self.log("Tesseract available")
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log("Tesseract not found. Please install: brew install tesseract", "WARNING")
    
    def prepare_build_environment(self) -> None:
        """Prepare the build environment."""
        self.log("Preparing build environment...")
        
        # Clean previous builds
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        
        self.build_dir.mkdir(exist_ok=True)
        self.dist_dir.mkdir(exist_ok=True)
    
    def create_spec_file(self, config_name: str) -> Path:
        """Create PyInstaller spec file for the given configuration."""
        self.log(f"Creating spec file for {config_name}...")
        
        config = self.configs[config_name]
        platform_settings = self.platform_settings.get(self.platform, self.platform_settings["linux"])
        
        # Determine entry point
        script_path = self.root_dir / config["script"]
        if not script_path.exists():
            # Create a minimal entry point if script doesn't exist
            script_path = self._create_entry_point(config_name)
        
        # Build PyInstaller arguments
        pyinstaller_args = [
            "pyinstaller",
            "--name", config["name"],
            "--distpath", str(self.dist_dir),
            "--workpath", str(self.build_dir),
            "--specpath", str(self.build_dir),
            "--onefile",  # Single file executable
            "--clean",
        ]
        
        # Add windowed mode for GUI
        if config["windowed"]:
            pyinstaller_args.append("--windowed")
        
        # Add console mode for CLI
        if config["console"]:
            pyinstaller_args.append("--console")
        
        # Add icon if available
        icon_path = self._find_icon()
        if icon_path:
            pyinstaller_args.extend(["--icon", str(icon_path)])
        
        # Add hidden imports
        all_hidden_imports = [
            "src", "src.core", "src.utils", "src.ocr",
            "pytesseract", "PIL", "PyPDF2", "requests",
            "pathlib", "json", "logging", "configparser"
        ] + platform_settings.get("hidden_imports", [])
        
        for import_name in all_hidden_imports:
            pyinstaller_args.extend(["--hidden-import", import_name])
        
        # Exclude unnecessary modules
        exclude_modules = platform_settings.get("exclude_modules", [])
        for module in exclude_modules:
            pyinstaller_args.extend(["--exclude-module", module])
        
        # Add data files
        data_files = self._get_data_files()
        for src, dst in data_files:
            pyinstaller_args.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        
        # Add version info for Windows
        if self.platform == "windows":
            version_file = self._create_version_file()
            if version_file:
                pyinstaller_args.extend(["--version-file", str(version_file)])
        
        # Add the script path
        pyinstaller_args.append(str(script_path))
        
        # Run PyInstaller to create spec file
        self.run_command(pyinstaller_args)
        
        # Return the created spec file
        spec_file = self.build_dir / f"{config['name']}.spec"
        return spec_file
    
    def _create_entry_point(self, config_name: str) -> Path:
        """Create a minimal entry point script."""
        self.log(f"Creating entry point for {config_name}...")
        
        if config_name == "gui":
            entry_content = f'''#!/usr/bin/env python3
"""
OCR Enhanced GUI Entry Point
Version: {__version__}
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    try:
        # Try to import and run GUI
        from src.gui.main_window import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"Error: Could not import GUI components: {{e}}")
        print("Please ensure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        else:  # CLI
            entry_content = f'''#!/usr/bin/env python3
"""
OCR Enhanced CLI Entry Point
Version: {__version__}
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    try:
        # Try to import and run CLI
        from src.core.cli import main as cli_main
        cli_main()
    except ImportError as e:
        print(f"Error: Could not import CLI components: {{e}}")
        print("Please ensure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        entry_file = self.build_dir / f"{config_name}_entry.py"
        with open(entry_file, "w", encoding="utf-8") as f:
            f.write(entry_content)
        
        return entry_file
    
    def _find_icon(self) -> Optional[Path]:
        """Find application icon file."""
        icon_extensions = [".ico", ".png", ".icns"]
        icon_names = ["icon", "logo", "app_icon", "ocr_icon"]
        
        search_dirs = [
            self.root_dir,
            self.root_dir / "assets",
            self.root_dir / "icons",
            self.root_dir / "resources"
        ]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            
            for name in icon_names:
                for ext in icon_extensions:
                    icon_path = search_dir / f"{name}{ext}"
                    if icon_path.exists():
                        self.log(f"Found icon: {icon_path}")
                        return icon_path
        
        self.log("No icon file found", "WARNING")
        return None
    
    def _get_data_files(self) -> List[tuple]:
        """Get list of data files to include."""
        data_files = []
        
        # Include configuration files
        config_files = [
            "pyproject.toml",
            "requirements.txt",
            "README.md",
            "LICENSE"
        ]
        
        for config_file in config_files:
            file_path = self.root_dir / config_file
            if file_path.exists():
                data_files.append((str(file_path), "."))
        
        # Include requirements directory if it exists
        requirements_dir = self.root_dir / "requirements"
        if requirements_dir.exists():
            for req_file in requirements_dir.glob("*.txt"):
                data_files.append((str(req_file), "requirements"))
        
        return data_files
    
    def _create_version_file(self) -> Optional[Path]:
        """Create Windows version file."""
        if self.platform != "windows":
            return None
        
        self.log("Creating Windows version file...")
        
        version_parts = __version__.split(".")
        while len(version_parts) < 4:
            version_parts.append("0")
        
        version_info = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),
    prodvers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'{PACKAGE_INFO["author"]}'),
            StringStruct(u'FileDescription', u'{PACKAGE_INFO["description"]}'),
            StringStruct(u'FileVersion', u'{__version__}'),
            StringStruct(u'InternalName', u'OCR Enhanced'),
            StringStruct(u'LegalCopyright', u'Copyright (c) 2024 {PACKAGE_INFO["author"]}'),
            StringStruct(u'OriginalFilename', u'OCR-Enhanced.exe'),
            StringStruct(u'ProductName', u'OCR Enhanced'),
            StringStruct(u'ProductVersion', u'{__version__}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
        
        version_file = self.build_dir / "version_info.txt"
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(version_info)
        
        return version_file
    
    def build_executable(self, config_name: str) -> Path:
        """Build executable for the given configuration."""
        self.log(f"Building {config_name} executable...")
        
        spec_file = self.create_spec_file(config_name)
        
        # Build the executable using the spec file
        build_cmd = ["pyinstaller", "--clean", str(spec_file)]
        self.run_command(build_cmd)
        
        # Find the built executable
        config = self.configs[config_name]
        platform_settings = self.platform_settings.get(self.platform, self.platform_settings["linux"])
        
        exe_name = config["name"] + platform_settings["extension"]
        exe_path = self.dist_dir / exe_name
        
        if not exe_path.exists():
            raise RuntimeError(f"Executable not found: {exe_path}")
        
        self.log(f"Built executable: {exe_path}")
        return exe_path
    
    def create_package(self, executables: List[Path]) -> None:
        """Create distribution package with executables."""
        self.log("Creating distribution package...")
        
        # Create package directory
        package_name = f"OCR-Enhanced-v{__version__}-{self.platform}-{self.architecture}"
        package_dir = self.dist_dir / package_name
        package_dir.mkdir(exist_ok=True)
        
        # Copy executables
        for exe_path in executables:
            dest_path = package_dir / exe_path.name
            shutil.copy2(exe_path, dest_path)
            self.log(f"Copied {exe_path.name} to package")
        
        # Copy documentation
        docs_to_copy = ["README.md", "LICENSE", "CLAUDE.md"]
        for doc in docs_to_copy:
            doc_path = self.root_dir / doc
            if doc_path.exists():
                shutil.copy2(doc_path, package_dir)
        
        # Create installation instructions
        install_instructions = self._create_install_instructions()
        with open(package_dir / "INSTALL.txt", "w", encoding="utf-8") as f:
            f.write(install_instructions)
        
        # Create archive
        archive_path = self._create_archive(package_dir)
        
        self.log(f"Package created: {archive_path}")
        return archive_path
    
    def _create_install_instructions(self) -> str:
        """Create installation instructions."""
        platform_instructions = {
            "windows": """
OCR Enhanced v{version} - Windows Installation

QUICK START:
1. Extract this archive to a folder of your choice
2. Install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki
3. Run OCR-Enhanced-GUI.exe for the graphical interface
   OR run OCR-Enhanced-CLI.exe for command-line interface

SYSTEM REQUIREMENTS:
- Windows 10 or later
- 4GB RAM minimum, 8GB recommended
- 100MB free disk space
- Tesseract OCR (for local processing)

TESSERACT INSTALLATION:
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki
Make sure to select language packs during installation.

USAGE:
- GUI: Double-click OCR-Enhanced-GUI.exe
- CLI: Open Command Prompt and run OCR-Enhanced-CLI.exe --help

TROUBLESHOOTING:
- If executables don't run, try "Run as Administrator"
- Ensure Tesseract is in your PATH environment variable
- Check Windows Defender/antivirus settings
""",
            "linux": """
OCR Enhanced v{version} - Linux Installation

QUICK START:
1. Extract this archive: tar -xzf ocr-enhanced-*.tar.gz
2. Install Tesseract: sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por
3. Make executables executable: chmod +x OCR-Enhanced-*
4. Run ./OCR-Enhanced-GUI for graphical interface
   OR ./OCR-Enhanced-CLI for command-line interface

SYSTEM REQUIREMENTS:
- Ubuntu 18.04+ / Debian 10+ / CentOS 8+ (or equivalent)
- 4GB RAM minimum, 8GB recommended
- 100MB free disk space
- Tesseract OCR

DEPENDENCIES:
Ubuntu/Debian:
  sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por poppler-utils

CentOS/RHEL/Fedora:
  sudo dnf install tesseract tesseract-langpack-eng tesseract-langpack-por poppler-utils

USAGE:
- GUI: ./OCR-Enhanced-GUI
- CLI: ./OCR-Enhanced-CLI --help

TROUBLESHOOTING:
- Ensure executables have execute permissions
- Check that Tesseract is installed and in PATH
- Install missing system libraries if needed
""",
            "darwin": """
OCR Enhanced v{version} - macOS Installation

QUICK START:
1. Extract this archive
2. Install Tesseract: brew install tesseract
3. Run OCR-Enhanced-GUI.app for graphical interface
   OR run OCR-Enhanced-CLI in Terminal

SYSTEM REQUIREMENTS:
- macOS 10.14 (Mojave) or later
- 4GB RAM minimum, 8GB recommended
- 100MB free disk space
- Tesseract OCR

DEPENDENCIES:
Install Homebrew if not already installed:
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

Install Tesseract:
  brew install tesseract

USAGE:
- GUI: Double-click OCR-Enhanced-GUI.app
- CLI: Open Terminal and run ./OCR-Enhanced-CLI --help

TROUBLESHOOTING:
- Allow apps from unidentified developers in Security preferences
- Ensure Tesseract is installed via Homebrew
- Check Gatekeeper settings if apps won't run
"""
        }
        
        return platform_instructions.get(self.platform, platform_instructions["linux"]).format(version=__version__)
    
    def _create_archive(self, package_dir: Path) -> Path:
        """Create archive of the package."""
        if self.platform == "windows":
            # Create ZIP archive for Windows
            archive_path = package_dir.with_suffix(".zip")
            shutil.make_archive(str(package_dir), "zip", package_dir.parent, package_dir.name)
        else:
            # Create TAR.GZ archive for Unix-like systems
            archive_path = package_dir.with_suffix(".tar.gz")
            shutil.make_archive(str(package_dir), "gztar", package_dir.parent, package_dir.name)
        
        return archive_path
    
    def build_all(self, configs: Optional[List[str]] = None) -> None:
        """Build all specified configurations."""
        if configs is None:
            configs = list(self.configs.keys())
        
        self.log(f"Building executables for {self.platform} ({self.architecture})")
        self.log(f"Configurations: {', '.join(configs)}")
        
        try:
            self.check_prerequisites()
            self.prepare_build_environment()
            
            executables = []
            for config_name in configs:
                if config_name not in self.configs:
                    self.log(f"Unknown configuration: {config_name}", "WARNING")
                    continue
                
                exe_path = self.build_executable(config_name)
                executables.append(exe_path)
            
            if executables:
                archive_path = self.create_package(executables)
                self.log("Build completed successfully!")
                self.log(f"Executables built: {len(executables)}")
                self.log(f"Package: {archive_path}")
            else:
                self.log("No executables were built", "WARNING")
                
        except Exception as e:
            self.log(f"Build failed: {e}", "ERROR")
            raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build OCR Enhanced executables")
    parser.add_argument("--config", choices=["gui", "cli", "all"], default="all",
                       help="Configuration to build (default: all)")
    parser.add_argument("--version", action="version", version=f"OCR Enhanced {__version__}")
    
    args = parser.parse_args()
    
    configs = ["gui", "cli"] if args.config == "all" else [args.config]
    
    builder = ExecutableBuilder()
    builder.build_all(configs)


if __name__ == "__main__":
    main()