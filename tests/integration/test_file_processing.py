"""
Integration tests for file processing workflows.

Tests complete file processing pipelines including different file types,
formats, and processing modes.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

from src.core.config import OCRConfig
from src.utils.logger import setup_logger
from src.ocr.base import OCREngine, OCRResult, OCROptions, OCREngineManager


class TestFileTypeEngine(OCREngine):
    """Test engine that simulates different processing for different file types."""
    
    def __init__(self, name="test_file_engine"):
        super().__init__(name)
        self.processing_history = []
    
    def is_available(self):
        return True
    
    def process_image(self, image_path, options):
        self.processing_history.append(('image', str(image_path)))
        
        # Simulate image-specific processing
        return OCRResult(
            text=f"Image text extracted from {image_path.name}",
            confidence=0.88,
            pages=[{"page": 1, "text": f"Image content: {image_path.suffix}"}],
            processing_time=0.8,
            engine=self.name,
            language=options.language,
            file_path=str(image_path)
        )
    
    def process_pdf(self, pdf_path, options):
        self.processing_history.append(('pdf', str(pdf_path)))
        
        # Simulate multi-page PDF processing
        pages = []
        num_pages = 3  # Simulate 3-page PDF
        
        for page_num in range(1, num_pages + 1):
            pages.append({
                "page": page_num,
                "text": f"PDF page {page_num} content from {pdf_path.name}",
                "confidence": 0.85 + (page_num * 0.02)
            })
        
        combined_text = "\n".join([page["text"] for page in pages])
        avg_confidence = sum(page["confidence"] for page in pages) / len(pages)
        
        return OCRResult(
            text=combined_text,
            confidence=avg_confidence,
            pages=pages,
            processing_time=1.5,
            engine=self.name,
            language=options.language,
            file_path=str(pdf_path)
        )


@pytest.mark.integration
class TestFileTypeProcessing:
    """Test processing different file types."""
    
    def test_pdf_file_processing(self, temp_dir, sample_pdf_file):
        """Test complete PDF file processing workflow."""
        config = OCRConfig(
            input_folder=str(temp_dir / "pdf_input"),
            output_folder=str(temp_dir / "pdf_output"),
            language="eng"
        )
        
        engine = TestFileTypeEngine("pdf_processor")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        options = OCROptions(language=config.language)
        result = manager.process_with_fallback(sample_pdf_file, options=options)
        
        # Verify PDF-specific processing
        assert result.success is True
        assert result.engine == "pdf_processor"
        assert len(result.pages) == 3  # Multi-page PDF
        assert "PDF page 1 content" in result.text
        assert "PDF page 2 content" in result.text
        assert "PDF page 3 content" in result.text
        
        # Verify processing history
        assert len(engine.processing_history) == 1
        assert engine.processing_history[0][0] == 'pdf'
    
    def test_image_file_processing(self, temp_dir, sample_image_file):
        """Test complete image file processing workflow."""
        config = OCRConfig(language="por")
        
        engine = TestFileTypeEngine("image_processor")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        options = OCROptions(language=config.language)
        result = manager.process_with_fallback(sample_image_file, options=options)
        
        # Verify image-specific processing
        assert result.success is True
        assert result.engine == "image_processor"
        assert result.language == "por"
        assert "Image text extracted" in result.text
        assert len(result.pages) == 1  # Single page for image
        
        # Verify processing history
        assert len(engine.processing_history) == 1
        assert engine.processing_history[0][0] == 'image'
    
    def test_mixed_file_batch_processing(self, temp_dir):
        """Test processing a batch with mixed file types."""
        input_dir = temp_dir / "mixed_input"
        input_dir.mkdir()
        
        # Create mixed file types
        pdf_file = input_dir / "document.pdf"
        pdf_file.write_bytes(b"Mock PDF content")
        
        jpg_file = input_dir / "image.jpg"
        jpg_file.write_bytes(b"Mock JPEG content")
        
        png_file = input_dir / "scan.png"
        png_file.write_bytes(b"Mock PNG content")
        
        files = [pdf_file, jpg_file, png_file]
        
        engine = TestFileTypeEngine("mixed_processor")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        # Process each file type
        results = []
        for file_path in files:
            result = manager.process_with_fallback(file_path)
            results.append(result)
        
        # Verify all files processed successfully
        assert len(results) == 3
        assert all(r.success for r in results)
        
        # Verify correct processing methods were used
        processing_types = [call[0] for call in engine.processing_history]
        assert 'pdf' in processing_types
        assert 'image' in processing_types
        assert processing_types.count('image') == 2  # JPG and PNG


@pytest.mark.integration
class TestOutputGeneration:
    """Test output file generation and formatting."""
    
    def test_json_output_generation(self, temp_dir, sample_pdf_file):
        """Test JSON output file generation."""
        output_dir = temp_dir / "json_output"
        output_dir.mkdir()
        
        engine = TestFileTypeEngine("json_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(sample_pdf_file)
        
        # Generate JSON output
        json_file = output_dir / f"{sample_pdf_file.stem}_result.json"
        
        output_data = {
            "metadata": {
                "original_file": str(sample_pdf_file),
                "processing_engine": result.engine,
                "processing_time": result.processing_time,
                "timestamp": "2024-01-01T12:00:00Z",
                "language": result.language
            },
            "ocr_result": {
                "text": result.text,
                "confidence": result.confidence,
                "word_count": result.word_count,
                "character_count": result.character_count,
                "success": result.success
            },
            "pages": result.pages
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        # Verify JSON file created and valid
        assert json_file.exists()
        
        with open(json_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        assert loaded_data["metadata"]["processing_engine"] == "json_test"
        assert loaded_data["ocr_result"]["success"] is True
        assert len(loaded_data["pages"]) == 3
        assert "PDF page 1 content" in loaded_data["ocr_result"]["text"]
    
    def test_markdown_output_generation(self, temp_dir, sample_pdf_file):
        """Test Markdown output file generation."""
        output_dir = temp_dir / "md_output"
        output_dir.mkdir()
        
        engine = TestFileTypeEngine("markdown_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(sample_pdf_file)
        
        # Generate Markdown output
        md_file = output_dir / f"{sample_pdf_file.stem}_result.md"
        
        md_content = f"""# OCR Result: {sample_pdf_file.name}
        
## Document Information
- **Original File**: {sample_pdf_file.name}
- **Processing Engine**: {result.engine}
- **Language**: {result.language}
- **Confidence**: {result.confidence:.2%}
- **Processing Time**: {result.processing_time:.2f}s
- **Word Count**: {result.word_count}
- **Character Count**: {result.character_count}

## Extracted Text

{result.text}

## Page Details

"""
        
        for i, page in enumerate(result.pages, 1):
            md_content += f"""### Page {page['page']}
            
{page['text']}

"""
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        # Verify Markdown file created
        assert md_file.exists()
        
        content = md_file.read_text(encoding='utf-8')
        assert f"# OCR Result: {sample_pdf_file.name}" in content
        assert "## Document Information" in content
        assert "## Extracted Text" in content
        assert "### Page 1" in content
        assert result.text in content
    
    def test_multiple_output_formats(self, temp_dir, sample_image_file):
        """Test generating multiple output formats for single file."""
        output_dir = temp_dir / "multi_output"
        output_dir.mkdir()
        
        engine = TestFileTypeEngine("multi_format_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(sample_image_file)
        
        # Generate multiple output formats
        base_name = sample_image_file.stem
        
        # 1. JSON format
        json_file = output_dir / f"{base_name}.json"
        json_data = {
            "text": result.text,
            "confidence": result.confidence,
            "pages": result.pages
        }
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        # 2. Plain text format
        txt_file = output_dir / f"{base_name}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(result.text)
        
        # 3. CSV format (page-by-page)
        csv_file = output_dir / f"{base_name}.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("Page,Text,Confidence\n")
            for page in result.pages:
                page_conf = page.get('confidence', result.confidence)
                f.write(f"{page['page']},\"{page['text']}\",{page_conf}\n")
        
        # Verify all files created
        assert json_file.exists()
        assert txt_file.exists()
        assert csv_file.exists()
        
        # Verify content consistency
        json_content = json.loads(json_file.read_text())
        txt_content = txt_file.read_text(encoding='utf-8')
        csv_content = csv_file.read_text(encoding='utf-8')
        
        assert json_content["text"] == result.text
        assert txt_content.strip() == result.text.strip()
        assert "Page,Text,Confidence" in csv_content
        assert str(result.pages[0]['page']) in csv_content


@pytest.mark.integration
class TestLargeFileProcessing:
    """Test processing of large files and batches."""
    
    def test_large_batch_processing(self, temp_dir):
        """Test processing a large batch of files."""
        input_dir = temp_dir / "large_batch"
        output_dir = temp_dir / "large_output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Create large batch (50 files)
        batch_size = 50
        test_files = []
        
        for i in range(batch_size):
            file_path = input_dir / f"batch_file_{i:03d}.pdf"
            file_path.write_bytes(f"Content for file {i}".encode())
            test_files.append(file_path)
        
        config = OCRConfig(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            max_pages_per_batch=10  # Small batch size for testing
        )
        
        engine = TestFileTypeEngine("large_batch_engine")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        # Process in batches
        processed_count = 0
        failed_count = 0
        processing_times = []
        
        for file_path in test_files:
            try:
                import time
                start_time = time.time()
                
                result = manager.process_with_fallback(file_path)
                
                end_time = time.time()
                processing_times.append(end_time - start_time)
                
                if result.success:
                    processed_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
        
        # Verify batch processing results
        assert processed_count >= batch_size * 0.9  # At least 90% success rate
        assert failed_count <= batch_size * 0.1  # At most 10% failure rate
        
        # Verify performance characteristics
        avg_processing_time = sum(processing_times) / len(processing_times)
        assert avg_processing_time < 5.0  # Should be reasonably fast
        
        # Verify engine processed all files
        assert len(engine.processing_history) == processed_count
    
    def test_memory_efficient_processing(self, temp_dir):
        """Test that processing doesn't consume excessive memory."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create files to process
        input_dir = temp_dir / "memory_test"
        input_dir.mkdir()
        
        # Create moderate number of files
        test_files = []
        for i in range(20):
            file_path = input_dir / f"memory_test_{i}.pdf"
            # Create slightly larger content to test memory usage
            content = f"File {i} content. " * 100  # Repeat to make larger
            file_path.write_bytes(content.encode())
            test_files.append(file_path)
        
        engine = TestFileTypeEngine("memory_test_engine")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        memory_readings = []
        
        # Process files while monitoring memory
        for file_path in test_files:
            result = manager.process_with_fallback(file_path)
            assert result.success is True
            
            # Take memory reading
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_readings.append(current_memory)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be reasonable (less than 50MB for this test)
        assert memory_growth < 50, f"Memory grew by {memory_growth:.2f}MB"
        
        # Memory should not grow significantly during processing
        if len(memory_readings) > 5:
            max_memory = max(memory_readings)
            min_memory = min(memory_readings)
            memory_variance = max_memory - min_memory
            assert memory_variance < 30, f"Memory variance of {memory_variance:.2f}MB is too high"


@pytest.mark.integration
class TestSpecialFileHandling:
    """Test handling of special file cases and edge conditions."""
    
    def test_empty_file_handling(self, temp_dir):
        """Test handling of empty files."""
        empty_pdf = temp_dir / "empty.pdf"
        empty_pdf.write_bytes(b"")  # Empty file
        
        engine = TestFileTypeEngine("empty_file_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(empty_pdf)
        
        # Should handle empty file gracefully
        assert result.success is False
        assert "File not found" in result.error_message or "empty" in result.error_message.lower()
    
    def test_corrupted_file_handling(self, temp_dir):
        """Test handling of corrupted/invalid files."""
        corrupted_pdf = temp_dir / "corrupted.pdf"
        corrupted_pdf.write_bytes(b"This is not a valid PDF file content")
        
        class StrictFileEngine(TestFileTypeEngine):
            def process_pdf(self, pdf_path, options):
                # Simulate strict validation that catches corruption
                content = pdf_path.read_bytes()
                if not content.startswith(b"%PDF"):
                    return OCRResult(
                        text="", confidence=0.0, pages=[], processing_time=0.1,
                        engine=self.name, language=options.language, success=False,
                        error_message="Invalid PDF format detected", file_path=str(pdf_path)
                    )
                return super().process_pdf(pdf_path, options)
        
        engine = StrictFileEngine("corruption_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(corrupted_pdf)
        
        # Should detect and handle corruption
        assert result.success is False
        assert "Invalid PDF format" in result.error_message
    
    def test_large_file_handling(self, temp_dir):
        """Test handling of very large files."""
        large_pdf = temp_dir / "large.pdf"
        
        # Create a file with substantial content
        large_content = b"Large file content. " * 10000  # ~200KB
        large_pdf.write_bytes(large_content)
        
        class SizeAwareEngine(TestFileTypeEngine):
            def process_pdf(self, pdf_path, options):
                file_size = pdf_path.stat().st_size
                
                # Simulate longer processing time for large files
                processing_time = min(file_size / 100000, 5.0)  # Scale with size, max 5s
                
                result = super().process_pdf(pdf_path, options)
                result.processing_time = processing_time
                
                # Add size information to metadata
                result.file_size = file_size
                
                return result
        
        engine = SizeAwareEngine("large_file_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(large_pdf)
        
        # Should handle large file successfully
        assert result.success is True
        assert hasattr(result, 'file_size')
        assert result.file_size > 100000  # Should be substantial
        assert result.processing_time > 0.5  # Should take some time
    
    def test_unicode_filename_handling(self, temp_dir):
        """Test handling of files with Unicode characters in names."""
        unicode_files = [
            temp_dir / "documento_português.pdf",
            temp_dir / "文档_中文.pdf",
            temp_dir / "документ_русский.pdf",
            temp_dir / "مستند_عربي.pdf"
        ]
        
        engine = TestFileTypeEngine("unicode_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        results = []
        for file_path in unicode_files:
            # Create file with Unicode name
            file_path.write_bytes(b"Unicode filename test content")
            
            result = manager.process_with_fallback(file_path)
            results.append(result)
        
        # All Unicode filenames should be handled correctly
        assert len(results) == 4
        assert all(r.success for r in results)
        
        # Verify file paths are preserved correctly
        for result, original_file in zip(results, unicode_files):
            assert result.file_path == str(original_file)
            assert original_file.name in result.text  # Should reference correct filename