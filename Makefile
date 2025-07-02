# OCR Enhanced - Makefile
# Simplified commands for building, testing, and releasing

.PHONY: help install test build build-exe publish release clean

# Default target
help:
	@echo "OCR Enhanced - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "Development:"
	@echo "  install     - Install development dependencies"
	@echo "  test        - Run test suite"
	@echo "  test-unit   - Run unit tests only"
	@echo "  test-int    - Run integration tests only"
	@echo "  lint        - Run code quality checks"
	@echo "  format      - Format code with black and isort"
	@echo ""
	@echo "Building:"
	@echo "  build       - Build Python packages"
	@echo "  build-exe   - Build standalone executables"
	@echo "  build-all   - Build packages and executables"
	@echo ""
	@echo "Distribution:"
	@echo "  publish-test - Publish to Test PyPI"
	@echo "  publish      - Publish to PyPI"
	@echo "  release      - Complete release process"
	@echo "  release-dry  - Dry run of release process"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean       - Clean build artifacts"
	@echo "  clean-all   - Clean all generated files"
	@echo "  deps-update - Update dependencies"
	@echo ""

# Development commands
install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"
	pre-commit install

test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/unit/ -v

test-int:
	python -m pytest tests/integration/ -v

test-cov:
	python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

lint:
	python -m black --check src tests
	python -m isort --check-only src tests
	python -m flake8 src tests
	python -m mypy src
	python -m bandit -r src

format:
	python -m black src tests
	python -m isort src tests

# Building commands
build:
	python build_scripts/build.py

build-exe:
	python build_scripts/build_executable.py --config all

build-all: build build-exe

# Distribution commands
publish-test:
	python build_scripts/publish.py --repository test

publish:
	python build_scripts/publish.py --repository pypi

release:
	python build_scripts/release.py

release-dry:
	python build_scripts/release.py --dry-run

release-minor:
	@echo "Please specify new version manually with: make release-version VERSION=x.y.z"

release-version:
	python build_scripts/release.py --version $(VERSION)

# Maintenance commands
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf build_executable/
	rm -rf dist_executable/
	rm -rf *.egg-info/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-all: clean
	rm -rf venv/
	rm -rf venv_build/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -f coverage.xml

deps-update:
	python -m pip install --upgrade pip
	python -m pip install --upgrade build wheel twine
	python -m pip install --upgrade -e ".[dev]"

# Platform-specific builds
build-windows:
	@echo "Run this on Windows: build_scripts\\build_windows.bat"

build-linux:
	./build_scripts/build_linux.sh

build-macos:
	./build_scripts/build_macos.sh

# CI/CD simulation
ci-test:
	python -m pytest tests/ --tb=short --strict-markers
	python -m mypy src
	python -m bandit -r src

ci-build:
	python build_scripts/build.py --skip-tests

# Docker support (if Dockerfile exists)
docker-build:
	@if [ -f "Dockerfile" ]; then \
		docker build -t ocr-enhanced:latest .; \
	else \
		echo "Dockerfile not found"; \
	fi

docker-run:
	@if [ -f "Dockerfile" ]; then \
		docker run -it --rm ocr-enhanced:latest; \
	else \
		echo "Dockerfile not found"; \
	fi

# Development shortcuts
dev-setup: install
	@echo "Development environment setup complete"

dev-test: test lint
	@echo "Development testing complete"

dev-build: clean build
	@echo "Development build complete"

# Quick commands
quick-test:
	python -m pytest tests/unit/ -x -v

quick-build:
	python build_scripts/build.py --skip-tests

quick-exe:
	python build_scripts/build_executable.py --config cli

# Documentation
docs-build:
	@echo "Documentation build not yet implemented"

docs-serve:
	@echo "Documentation serve not yet implemented"

# Version information
version:
	@python -c "from src import __version__; print(f'Current version: {__version__}')"

# Environment information
env-info:
	@echo "Environment Information:"
	@echo "======================="
	@python --version
	@echo "Python path: $$(which python)"
	@echo "Pip version: $$(pip --version)"
	@echo "Platform: $$(python -c 'import platform; print(platform.platform())')"
	@echo "Current directory: $$(pwd)"
	@echo "Git branch: $$(git branch --show-current 2>/dev/null || echo 'Not a git repository')"