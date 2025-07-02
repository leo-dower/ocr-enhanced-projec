#!/usr/bin/env python3
"""
Master release script for OCR Enhanced.

This script orchestrates the complete release process including:
- Version validation and bumping
- Building packages and executables
- Running tests
- Publishing to PyPI
- Creating GitHub releases
- Generating release notes
"""

import os
import sys
import subprocess
import argparse
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import re

# Add src to path for version import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from src import __version__, VERSION_INFO, PACKAGE_INFO
except ImportError as e:
    print(f"Error importing version info: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)


class ReleaseManager:
    """Manages the complete release process for OCR Enhanced."""
    
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).parent.parent
        self.scripts_dir = self.root_dir / "build_scripts"
        
        # Release configuration
        self.config = {
            "build_packages": True,
            "build_executables": True,
            "run_tests": True,
            "publish_pypi": True,
            "create_github_release": True,
            "dry_run": False
        }
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with timestamp."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a command and return the result."""
        self.log(f"Running: {' '.join(cmd)}")
        
        if self.config["dry_run"]:
            self.log("DRY RUN: Command not executed")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
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
    
    def validate_version(self, new_version: Optional[str] = None) -> str:
        """Validate and optionally update version."""
        current_version = __version__
        
        if new_version:
            self.log(f"Updating version from {current_version} to {new_version}")
            self._update_version(new_version)
            return new_version
        else:
            self.log(f"Using current version: {current_version}")
            return current_version
    
    def _update_version(self, new_version: str) -> None:
        """Update version in source files."""
        # Parse new version
        version_match = re.match(r"(\d+)\.(\d+)\.(\d+)(?:-(\w+))?(?:\+(.+))?", new_version)
        if not version_match:
            raise ValueError(f"Invalid version format: {new_version}")
        
        major, minor, patch, pre_release, build = version_match.groups()
        
        # Update src/__init__.py
        init_file = self.root_dir / "src" / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        
        # Update __version__
        content = re.sub(
            r'__version__ = "[^"]*"',
            f'__version__ = "{new_version}"',
            content
        )
        
        # Update VERSION_INFO
        version_info_new = f'''VERSION_INFO = {{
    "major": {major},
    "minor": {minor},
    "patch": {patch},
    "pre_release": {f'"{pre_release}"' if pre_release else "None"},
    "build": {f'"{build}"' if build else "None"}
}}'''
        
        content = re.sub(
            r'VERSION_INFO = \{[^}]*\}',
            version_info_new,
            content,
            flags=re.MULTILINE | re.DOTALL
        )
        
        init_file.write_text(content, encoding="utf-8")
        self.log(f"Updated version in {init_file}")
    
    def check_git_status(self) -> Dict[str, Any]:
        """Check git repository status."""
        self.log("Checking git repository status...")
        
        try:
            # Check if we're in a git repository
            result = self.run_command(["git", "rev-parse", "--git-dir"])
            
            # Get current branch
            result = self.run_command(["git", "branch", "--show-current"])
            current_branch = result.stdout.strip()
            
            # Check for uncommitted changes
            result = self.run_command(["git", "status", "--porcelain"])
            has_changes = bool(result.stdout.strip())
            
            # Get current commit
            result = self.run_command(["git", "rev-parse", "HEAD"])
            current_commit = result.stdout.strip()
            
            git_info = {
                "branch": current_branch,
                "commit": current_commit,
                "has_changes": has_changes,
                "is_clean": not has_changes
            }
            
            self.log(f"Git status: branch={current_branch}, clean={not has_changes}")
            return git_info
            
        except subprocess.CalledProcessError:
            self.log("Not in a git repository or git not available", "WARNING")
            return {"error": "Git not available"}
    
    def run_tests(self) -> None:
        """Run the test suite."""
        if not self.config["run_tests"]:
            self.log("Skipping tests (disabled in config)")
            return
        
        self.log("Running test suite...")
        
        # Run build script which includes tests
        build_script = self.scripts_dir / "build.py"
        self.run_command([sys.executable, str(build_script)])
        
        self.log("Tests completed successfully")
    
    def build_packages(self) -> None:
        """Build Python packages."""
        if not self.config["build_packages"]:
            self.log("Skipping package build (disabled in config)")
            return
        
        self.log("Building Python packages...")
        
        build_script = self.scripts_dir / "build.py"
        self.run_command([sys.executable, str(build_script)])
        
        self.log("Package build completed")
    
    def build_executables(self, platforms: Optional[List[str]] = None) -> None:
        """Build standalone executables."""
        if not self.config["build_executables"]:
            self.log("Skipping executable build (disabled in config)")
            return
        
        current_platform = sys.platform
        self.log(f"Building executables for current platform: {current_platform}")
        
        executable_script = self.scripts_dir / "build_executable.py"
        self.run_command([sys.executable, str(executable_script), "--config", "all"])
        
        self.log("Executable build completed")
    
    def publish_pypi(self, repository: str = "pypi") -> None:
        """Publish to PyPI."""
        if not self.config["publish_pypi"]:
            self.log("Skipping PyPI publication (disabled in config)")
            return
        
        self.log(f"Publishing to {repository}...")
        
        publish_script = self.scripts_dir / "publish.py"
        cmd = [sys.executable, str(publish_script), "--repository", repository]
        
        if repository == "pypi":
            # For production, always upload to test first
            cmd.append("--skip-test")  # We'll handle test upload separately
            
            # Upload to test PyPI first
            self.log("Uploading to Test PyPI first...")
            test_cmd = [sys.executable, str(publish_script), "--repository", "test"]
            self.run_command(test_cmd)
            
            # Ask for confirmation
            if not self.config["dry_run"]:
                confirm = input("Test PyPI upload successful. Proceed to production? (y/n): ")
                if not confirm.lower().startswith('y'):
                    self.log("PyPI publication cancelled by user")
                    return
        
        self.run_command(cmd)
        self.log("PyPI publication completed")
    
    def create_git_tag(self, version: str) -> None:
        """Create git tag for the release."""
        self.log(f"Creating git tag v{version}...")
        
        tag_name = f"v{version}"
        
        # Check if tag already exists
        try:
            self.run_command(["git", "rev-parse", tag_name], check=True)
            self.log(f"Tag {tag_name} already exists", "WARNING")
            return
        except subprocess.CalledProcessError:
            pass  # Tag doesn't exist, good
        
        # Create annotated tag
        tag_message = f"Release v{version}"
        self.run_command(["git", "tag", "-a", tag_name, "-m", tag_message])
        
        # Push tag
        self.run_command(["git", "push", "origin", tag_name])
        
        self.log(f"Git tag {tag_name} created and pushed")
    
    def generate_release_notes(self, version: str) -> str:
        """Generate release notes."""
        self.log("Generating release notes...")
        
        # Try to get git log since last tag
        try:
            # Get previous tag
            result = self.run_command(["git", "describe", "--tags", "--abbrev=0", "HEAD^"], check=False)
            if result.returncode == 0:
                prev_tag = result.stdout.strip()
                self.log(f"Previous tag: {prev_tag}")
                
                # Get commits since previous tag
                result = self.run_command(["git", "log", f"{prev_tag}..HEAD", "--oneline"])
                commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
            else:
                self.log("No previous tag found, using all commits")
                result = self.run_command(["git", "log", "--oneline"])
                commits = result.stdout.strip().split('\n')[:10]  # Last 10 commits
                
        except subprocess.CalledProcessError:
            self.log("Could not get git history", "WARNING")
            commits = []
        
        # Generate release notes
        release_notes = f"""# OCR Enhanced v{version}

## Release Information
- **Version**: {version}
- **Release Date**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}
- **Platform Support**: Windows, Linux, macOS

## Installation

### From PyPI
```bash
pip install ocr-enhanced=={version}
```

### Standalone Executables
Download the appropriate package for your platform from the GitHub releases page.

## What's New

### Features and Improvements
- Enhanced OCR processing with local (Tesseract) and cloud (Mistral AI) support
- Hybrid processing workflows with automatic fallback
- Multiple output formats (JSON, Markdown, PDF)
- Comprehensive testing infrastructure
- Professional packaging and distribution

### Technical Changes
"""
        
        if commits:
            release_notes += "\n#### Recent Commits\n"
            for commit in commits:
                if commit.strip():
                    release_notes += f"- {commit.strip()}\n"
        
        release_notes += f"""
## Documentation
- [Repository](https://github.com/leo-dower/ocr-enhanced-projec)
- [Installation Guide](https://github.com/leo-dower/ocr-enhanced-projec#installation)
- [Distribution Guide](DISTRIBUTION.md)

## System Requirements
- Python 3.8+ (for pip installation)
- Tesseract OCR (for local processing)
- 2GB+ RAM recommended
- 100MB+ disk space

## Support
For questions or issues, please visit our [GitHub repository](https://github.com/leo-dower/ocr-enhanced-projec/issues).
"""
        
        # Save release notes
        release_notes_file = self.root_dir / f"RELEASE_NOTES_v{version}.md"
        release_notes_file.write_text(release_notes, encoding="utf-8")
        
        self.log(f"Release notes saved to {release_notes_file}")
        return release_notes
    
    def create_github_release(self, version: str, release_notes: str) -> None:
        """Create GitHub release."""
        if not self.config["create_github_release"]:
            self.log("Skipping GitHub release (disabled in config)")
            return
        
        self.log("Creating GitHub release...")
        
        # Check if gh CLI is available
        try:
            self.run_command(["gh", "--version"])
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("GitHub CLI (gh) not available. Skipping GitHub release.", "WARNING")
            self.log("You can create the release manually at: https://github.com/leo-dower/ocr-enhanced-projec/releases")
            return
        
        # Create release
        tag_name = f"v{version}"
        release_title = f"OCR Enhanced v{version}"
        
        # Save release notes to temporary file
        notes_file = self.root_dir / "temp_release_notes.md"
        notes_file.write_text(release_notes, encoding="utf-8")
        
        try:
            cmd = [
                "gh", "release", "create", tag_name,
                "--title", release_title,
                "--notes-file", str(notes_file)
            ]
            
            # Add distribution files if they exist
            dist_files = []
            
            # Python packages
            dist_dir = self.root_dir / "dist"
            if dist_dir.exists():
                dist_files.extend(dist_dir.glob("*.whl"))
                dist_files.extend(dist_dir.glob("*.tar.gz"))
            
            # Executables
            exec_dist_dir = self.root_dir / "dist_executable"
            if exec_dist_dir.exists():
                dist_files.extend(exec_dist_dir.glob("*.zip"))
                dist_files.extend(exec_dist_dir.glob("*.tar.gz"))
            
            if dist_files:
                cmd.extend([str(f) for f in dist_files])
            
            self.run_command(cmd)
            self.log("GitHub release created successfully")
            
        finally:
            # Clean up temporary file
            if notes_file.exists():
                notes_file.unlink()
    
    def release(
        self, 
        version: Optional[str] = None,
        skip_tests: bool = False,
        skip_build: bool = False,
        pypi_repository: str = "pypi",
        dry_run: bool = False
    ) -> None:
        """Run the complete release process."""
        
        # Update configuration
        self.config.update({
            "run_tests": not skip_tests,
            "build_packages": not skip_build,
            "build_executables": not skip_build,
            "dry_run": dry_run
        })
        
        if dry_run:
            self.log("DRY RUN MODE - No actual changes will be made")
        
        try:
            self.log(f"Starting release process for OCR Enhanced")
            
            # 1. Validate version
            release_version = self.validate_version(version)
            
            # 2. Check git status
            git_info = self.check_git_status()
            if git_info.get("has_changes") and not dry_run:
                self.log("Warning: Working directory has uncommitted changes", "WARNING")
                confirm = input("Continue anyway? (y/n): ")
                if not confirm.lower().startswith('y'):
                    self.log("Release cancelled by user")
                    return
            
            # 3. Run tests
            if self.config["run_tests"]:
                self.run_tests()
            
            # 4. Build packages
            if self.config["build_packages"]:
                self.build_packages()
            
            # 5. Build executables
            if self.config["build_executables"]:
                self.build_executables()
            
            # 6. Create git tag
            if not dry_run:
                self.create_git_tag(release_version)
            
            # 7. Generate release notes
            release_notes = self.generate_release_notes(release_version)
            
            # 8. Publish to PyPI
            if self.config["publish_pypi"]:
                self.publish_pypi(pypi_repository)
            
            # 9. Create GitHub release
            if self.config["create_github_release"]:
                self.create_github_release(release_version, release_notes)
            
            self.log("Release process completed successfully!")
            self.log(f"Release v{release_version} is now available")
            
        except Exception as e:
            self.log(f"Release process failed: {e}", "ERROR")
            raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="OCR Enhanced Release Manager")
    parser.add_argument("--version", help="New version to release (optional)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-build", action="store_true", help="Skip building packages/executables")
    parser.add_argument("--pypi-repository", choices=["test", "pypi"], default="pypi",
                       help="PyPI repository to publish to")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without making changes")
    parser.add_argument("--current-version", action="version", version=f"Current version: {__version__}")
    
    args = parser.parse_args()
    
    manager = ReleaseManager()
    manager.release(
        version=args.version,
        skip_tests=args.skip_tests,
        skip_build=args.skip_build,
        pypi_repository=args.pypi_repository,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()