#!/usr/bin/env python3
"""
PyPI publishing script for OCR Enhanced package.

This script handles the complete publishing process including:
- Authentication validation
- Package verification
- Test PyPI upload (optional)
- Production PyPI upload
- Post-release validation
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import getpass

# Add src to path for version import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from src import __version__, PACKAGE_INFO
except ImportError as e:
    print(f"Error importing version info: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)


class PyPIPublisher:
    """Manages PyPI publishing for OCR Enhanced."""
    
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).parent.parent
        self.dist_dir = self.root_dir / "dist"
        
        # PyPI repositories
        self.repositories = {
            "test": {
                "url": "https://test.pypi.org/simple/",
                "upload_url": "https://test.pypi.org/legacy/",
                "web_url": "https://test.pypi.org/project/ocr-enhanced/"
            },
            "pypi": {
                "url": "https://pypi.org/simple/",
                "upload_url": "https://upload.pypi.org/legacy/",
                "web_url": "https://pypi.org/project/ocr-enhanced/"
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
        
        # Check twine is available
        try:
            result = subprocess.run(["twine", "--version"], capture_output=True, check=True)
            self.log(f"Twine version: {result.stdout.decode().strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("Installing twine...")
            self.run_command([sys.executable, "-m", "pip", "install", "twine"])
        
        # Check distribution files exist
        if not self.dist_dir.exists():
            raise RuntimeError("Distribution directory not found. Run build first.")
        
        dist_files = list(self.dist_dir.glob("*.whl")) + list(self.dist_dir.glob("*.tar.gz"))
        if not dist_files:
            raise RuntimeError("No distribution files found. Run build first.")
        
        self.log(f"Found {len(dist_files)} distribution files")
        for file_path in dist_files:
            self.log(f"  - {file_path.name}")
    
    def validate_package(self) -> None:
        """Validate the package before uploading."""
        self.log("Validating package...")
        
        # Use twine check to validate
        dist_files = list(self.dist_dir.glob("*.whl")) + list(self.dist_dir.glob("*.tar.gz"))
        check_cmd = ["twine", "check"] + [str(f) for f in dist_files]
        
        try:
            self.run_command(check_cmd)
            self.log("Package validation passed")
        except subprocess.CalledProcessError:
            self.log("Package validation failed", "ERROR")
            raise
    
    def check_version_exists(self, repository: str = "pypi") -> bool:
        """Check if the current version already exists on PyPI."""
        self.log(f"Checking if version {__version__} exists on {repository}...")
        
        try:
            import requests
            
            if repository == "test":
                url = f"https://test.pypi.org/pypi/ocr-enhanced/{__version__}/json"
            else:
                url = f"https://pypi.org/pypi/ocr-enhanced/{__version__}/json"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.log(f"Version {__version__} already exists on {repository}", "WARNING")
                return True
            elif response.status_code == 404:
                self.log(f"Version {__version__} not found on {repository} (good)")
                return False
            else:
                self.log(f"Unexpected response from {repository}: {response.status_code}", "WARNING")
                return False
        
        except ImportError:
            self.log("requests not available, skipping version check", "WARNING")
            return False
        except Exception as e:
            self.log(f"Error checking version on {repository}: {e}", "WARNING")
            return False
    
    def get_credentials(self, repository: str = "pypi") -> Dict[str, str]:
        """Get PyPI credentials."""
        self.log(f"Getting credentials for {repository}...")
        
        # Check environment variables first
        if repository == "test":
            token_env = "TEST_PYPI_API_TOKEN"
            username_env = "TEST_PYPI_USERNAME"
            password_env = "TEST_PYPI_PASSWORD"
        else:
            token_env = "PYPI_API_TOKEN"
            username_env = "PYPI_USERNAME"
            password_env = "PYPI_PASSWORD"
        
        # Try API token first (recommended)
        api_token = os.environ.get(token_env)
        if api_token:
            self.log("Using API token authentication")
            return {
                "username": "__token__",
                "password": api_token
            }
        
        # Try username/password
        username = os.environ.get(username_env)
        password = os.environ.get(password_env)
        
        if username and password:
            self.log(f"Using username/password authentication for user: {username}")
            return {
                "username": username,
                "password": password
            }
        
        # Ask interactively
        self.log("No credentials found in environment variables")
        print(f"\nPlease provide {repository} credentials:")
        print("You can use either:")
        print("1. API Token (recommended)")
        print("2. Username and password")
        
        use_token = input("Use API token? (y/n): ").lower().startswith('y')
        
        if use_token:
            token = getpass.getpass("API Token: ")
            return {
                "username": "__token__",
                "password": token
            }
        else:
            username = input("Username: ")
            password = getpass.getpass("Password: ")
            return {
                "username": username,
                "password": password
            }
    
    def upload_to_repository(self, repository: str = "pypi", force: bool = False) -> None:
        """Upload package to specified repository."""
        self.log(f"Uploading to {repository}...")
        
        # Check if version already exists
        if not force and self.check_version_exists(repository):
            raise RuntimeError(f"Version {__version__} already exists on {repository}. Use --force to override.")
        
        # Get credentials
        credentials = self.get_credentials(repository)
        
        # Prepare upload command
        dist_files = list(self.dist_dir.glob("*.whl")) + list(self.dist_dir.glob("*.tar.gz"))
        
        upload_cmd = ["twine", "upload"]
        
        if repository == "test":
            upload_cmd.extend(["--repository", "testpypi"])
        
        upload_cmd.extend([str(f) for f in dist_files])
        
        # Set credentials via environment
        env = os.environ.copy()
        env["TWINE_USERNAME"] = credentials["username"]
        env["TWINE_PASSWORD"] = credentials["password"]
        
        try:
            result = subprocess.run(
                upload_cmd,
                cwd=self.root_dir,
                check=True,
                capture_output=True,
                text=True,
                env=env
            )
            
            self.log(f"Successfully uploaded to {repository}")
            self.log(f"Package URL: {self.repositories[repository]['web_url']}")
            
        except subprocess.CalledProcessError as e:
            self.log(f"Upload failed: {e}", "ERROR")
            if e.stdout:
                self.log(f"stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"stderr: {e.stderr}", "ERROR")
            raise
    
    def verify_upload(self, repository: str = "pypi") -> None:
        """Verify that the upload was successful."""
        self.log(f"Verifying upload to {repository}...")
        
        try:
            import requests
            import time
            
            # Wait a bit for PyPI to process
            self.log("Waiting for PyPI to process upload...")
            time.sleep(10)
            
            if repository == "test":
                url = f"https://test.pypi.org/pypi/ocr-enhanced/{__version__}/json"
            else:
                url = f"https://pypi.org/pypi/ocr-enhanced/{__version__}/json"
            
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.log(f"✓ Package verified on {repository}")
                self.log(f"  Version: {data['info']['version']}")
                self.log(f"  Upload date: {data['urls'][0]['upload_time'] if data['urls'] else 'unknown'}")
                return True
            else:
                self.log(f"✗ Package not found on {repository}: {response.status_code}", "WARNING")
                return False
        
        except ImportError:
            self.log("requests not available, skipping verification", "WARNING")
            return True
        except Exception as e:
            self.log(f"Verification failed: {e}", "WARNING")
            return False
    
    def create_release_notes(self) -> None:
        """Create release notes file."""
        self.log("Creating release notes...")
        
        release_notes = f"""# OCR Enhanced v{__version__} Release Notes

## Package Information
- **Version**: {__version__}
- **Release Date**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}
- **Package Name**: {PACKAGE_INFO['name']}

## Installation

### From PyPI
```bash
pip install ocr-enhanced=={__version__}
```

### From Source
```bash
git clone https://github.com/leo-dower/ocr-enhanced-projec.git
cd ocr-enhanced-projec
pip install -e .
```

## What's New in v{__version__}

### Features
- Enhanced OCR processing with local (Tesseract) and cloud (Mistral AI) support
- Hybrid processing workflows with automatic fallback
- Multiple output formats (JSON, Markdown, PDF)
- Comprehensive testing infrastructure
- Professional packaging and distribution

### Improvements
- Modern Python packaging with pyproject.toml
- Type hints and static analysis
- Comprehensive error handling
- Performance optimizations
- Cross-platform compatibility

### Technical Details
- Python 3.8+ support
- Multi-platform testing (Linux, Windows, macOS)
- Comprehensive test coverage
- Professional CI/CD pipeline

## Documentation
- Repository: https://github.com/leo-dower/ocr-enhanced-projec
- Issues: https://github.com/leo-dower/ocr-enhanced-projec/issues

## System Requirements
- Python 3.8 or higher
- Tesseract OCR (for local processing)
- 2GB+ RAM recommended
- 100MB+ disk space

## Support
For questions, issues, or contributions, please visit our GitHub repository.
"""
        
        release_file = self.root_dir / f"RELEASE_v{__version__}.md"
        with open(release_file, "w", encoding="utf-8") as f:
            f.write(release_notes)
        
        self.log(f"Release notes written to {release_file}")
    
    def publish(self, repository: str = "pypi", force: bool = False, skip_test: bool = False) -> None:
        """Run the complete publishing process."""
        self.log(f"Starting publication process for OCR Enhanced v{__version__}")
        
        try:
            self.check_prerequisites()
            self.validate_package()
            
            # Upload to test PyPI first (unless skipped)
            if not skip_test and repository == "pypi":
                self.log("Uploading to Test PyPI first...")
                self.upload_to_repository("test", force)
                self.verify_upload("test")
                
                # Ask for confirmation to proceed to production
                confirm = input("\nTest PyPI upload successful. Proceed to production PyPI? (y/n): ")
                if not confirm.lower().startswith('y'):
                    self.log("Publication cancelled by user")
                    return
            
            # Upload to target repository
            self.upload_to_repository(repository, force)
            self.verify_upload(repository)
            
            # Create release notes
            self.create_release_notes()
            
            self.log("Publication completed successfully!")
            self.log(f"Package is now available at: {self.repositories[repository]['web_url']}")
            
        except Exception as e:
            self.log(f"Publication failed: {e}", "ERROR")
            raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Publish OCR Enhanced package to PyPI")
    parser.add_argument("--repository", choices=["test", "pypi"], default="pypi",
                       help="Target repository (default: pypi)")
    parser.add_argument("--force", action="store_true",
                       help="Force upload even if version exists")
    parser.add_argument("--skip-test", action="store_true",
                       help="Skip test PyPI upload")
    parser.add_argument("--version", action="version", version=f"OCR Enhanced {__version__}")
    
    args = parser.parse_args()
    
    publisher = PyPIPublisher()
    publisher.publish(
        repository=args.repository,
        force=args.force,
        skip_test=args.skip_test
    )


if __name__ == "__main__":
    main()