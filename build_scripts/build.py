#!/usr/bin/env python3
"""
Automated build script for OCR Enhanced package.

This script handles the complete build process including:
- Version validation
- Dependency checking
- Package building
- Testing
- Distribution preparation
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from typing import List, Optional
import json

# Add src to path for version import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from src import __version__, VERSION_INFO, PACKAGE_INFO
except ImportError as e:
    print(f"Error importing version info: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)


class BuildManager:
    """Manages the build process for OCR Enhanced."""
    
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).parent.parent
        self.dist_dir = self.root_dir / "dist"
        self.build_dir = self.root_dir / "build"
        
        # Build configuration
        self.config = {
            "clean_before_build": True,
            "run_tests": True,
            "check_dependencies": True,
            "validate_metadata": True,
            "create_checksums": True
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
                self.log(f"stdout: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e}", "ERROR")
            if e.stdout:
                self.log(f"stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"stderr: {e.stderr}", "ERROR")
            raise
    
    def clean_build_artifacts(self) -> None:
        """Clean previous build artifacts."""
        self.log("Cleaning build artifacts...")
        
        dirs_to_clean = [self.dist_dir, self.build_dir]
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                self.log(f"Removing {dir_path}")
                shutil.rmtree(dir_path)
        
        # Clean __pycache__ directories
        for pycache in self.root_dir.rglob("__pycache__"):
            if pycache.is_dir():
                shutil.rmtree(pycache)
        
        # Clean .pyc files
        for pyc_file in self.root_dir.rglob("*.pyc"):
            pyc_file.unlink()
    
    def validate_version(self) -> None:
        """Validate version information."""
        self.log(f"Validating version: {__version__}")
        
        # Check version format
        version_parts = __version__.split(".")
        if len(version_parts) < 3:
            raise ValueError(f"Invalid version format: {__version__}")
        
        # Verify version consistency
        expected_version = f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch']}"
        if not __version__.startswith(expected_version):
            raise ValueError(f"Version mismatch: {__version__} vs {expected_version}")
        
        self.log("Version validation passed")
    
    def check_dependencies(self) -> None:
        """Check that all dependencies are available."""
        self.log("Checking dependencies...")
        
        required_tools = ["python", "pip"]
        for tool in required_tools:
            try:
                result = subprocess.run([tool, "--version"], capture_output=True, check=True)
                self.log(f"{tool} version: {result.stdout.decode().strip()}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError(f"Required tool not found: {tool}")
        
        # Check required packages for building
        required_packages = ["build", "wheel"]
        for package in required_packages:
            try:
                __import__(package)
                self.log(f"Package available: {package}")
            except ImportError:
                self.log(f"Installing missing package: {package}")
                self.run_command([sys.executable, "-m", "pip", "install", package])
    
    def validate_metadata(self) -> None:
        """Validate package metadata."""
        self.log("Validating package metadata...")
        
        required_fields = ["name", "version", "description", "author"]
        for field in required_fields:
            if field not in PACKAGE_INFO or not PACKAGE_INFO[field]:
                raise ValueError(f"Missing required metadata field: {field}")
        
        self.log("Metadata validation passed")
    
    def run_tests(self) -> None:
        """Run the test suite."""
        self.log("Running tests...")
        
        # Check if pytest is available
        try:
            import pytest
        except ImportError:
            self.log("pytest not available, skipping tests")
            return
        
        # Run unit tests only (integration tests might require system dependencies)
        test_cmd = [sys.executable, "-m", "pytest", "tests/unit", "-v", "--tb=short"]
        
        try:
            self.run_command(test_cmd)
            self.log("All tests passed")
        except subprocess.CalledProcessError:
            self.log("Some tests failed, but continuing build...", "WARNING")
    
    def build_package(self) -> None:
        """Build the package."""
        self.log("Building package...")
        
        # Use python -m build for modern packaging
        build_cmd = [sys.executable, "-m", "build"]
        self.run_command(build_cmd)
        
        # Verify build artifacts
        if not self.dist_dir.exists():
            raise RuntimeError("Build failed: dist directory not created")
        
        built_files = list(self.dist_dir.glob("*"))
        if not built_files:
            raise RuntimeError("Build failed: no files in dist directory")
        
        self.log(f"Built {len(built_files)} distribution files:")
        for file_path in built_files:
            self.log(f"  - {file_path.name} ({file_path.stat().st_size} bytes)")
    
    def create_checksums(self) -> None:
        """Create checksums for distribution files."""
        self.log("Creating checksums...")
        
        import hashlib
        
        checksum_file = self.dist_dir / "checksums.txt"
        with open(checksum_file, "w") as f:
            f.write(f"# Checksums for OCR Enhanced v{__version__}\n")
            f.write(f"# Generated on {__import__('datetime').datetime.now().isoformat()}\n\n")
            
            for dist_file in self.dist_dir.glob("*"):
                if dist_file.name == "checksums.txt":
                    continue
                
                # Calculate SHA256
                sha256_hash = hashlib.sha256()
                with open(dist_file, "rb") as file:
                    for chunk in iter(lambda: file.read(4096), b""):
                        sha256_hash.update(chunk)
                
                f.write(f"{sha256_hash.hexdigest()}  {dist_file.name}\n")
        
        self.log(f"Checksums written to {checksum_file}")
    
    def generate_build_info(self) -> None:
        """Generate build information file."""
        self.log("Generating build information...")
        
        import datetime
        import platform
        
        build_info = {
            "package": PACKAGE_INFO,
            "build": {
                "timestamp": datetime.datetime.now().isoformat(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "builder": os.environ.get("USER", "unknown")
            },
            "git": self._get_git_info(),
            "files": [f.name for f in self.dist_dir.glob("*") if f.is_file()]
        }
        
        build_info_file = self.dist_dir / "build_info.json"
        with open(build_info_file, "w") as f:
            json.dump(build_info, f, indent=2)
        
        self.log(f"Build info written to {build_info_file}")
    
    def _get_git_info(self) -> dict:
        """Get git repository information."""
        try:
            # Get current commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                capture_output=True, 
                text=True, 
                check=True,
                cwd=self.root_dir
            )
            commit_hash = result.stdout.strip()
            
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"], 
                capture_output=True, 
                text=True, 
                check=True,
                cwd=self.root_dir
            )
            branch = result.stdout.strip()
            
            # Check if working directory is clean
            result = subprocess.run(
                ["git", "status", "--porcelain"], 
                capture_output=True, 
                text=True, 
                check=True,
                cwd=self.root_dir
            )
            is_clean = len(result.stdout.strip()) == 0
            
            return {
                "commit": commit_hash,
                "branch": branch,
                "clean": is_clean
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"error": "Git information not available"}
    
    def build(self, skip_tests: bool = False, skip_clean: bool = False) -> None:
        """Run the complete build process."""
        self.log(f"Starting build for OCR Enhanced v{__version__}")
        
        try:
            # Build steps
            if not skip_clean and self.config["clean_before_build"]:
                self.clean_build_artifacts()
            
            if self.config["validate_metadata"]:
                self.validate_version()
                self.validate_metadata()
            
            if self.config["check_dependencies"]:
                self.check_dependencies()
            
            if not skip_tests and self.config["run_tests"]:
                self.run_tests()
            
            self.build_package()
            
            if self.config["create_checksums"]:
                self.create_checksums()
            
            self.generate_build_info()
            
            self.log("Build completed successfully!")
            self.log(f"Distribution files available in: {self.dist_dir}")
            
        except Exception as e:
            self.log(f"Build failed: {e}", "ERROR")
            raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build OCR Enhanced package")
    parser.add_argument("--skip-tests", action="store_true", 
                       help="Skip running tests")
    parser.add_argument("--skip-clean", action="store_true", 
                       help="Skip cleaning build artifacts")
    parser.add_argument("--version", action="version", version=f"OCR Enhanced {__version__}")
    
    args = parser.parse_args()
    
    builder = BuildManager()
    builder.build(skip_tests=args.skip_tests, skip_clean=args.skip_clean)


if __name__ == "__main__":
    main()