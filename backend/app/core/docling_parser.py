"""
Docling-based PDF parser with OCR support.

This module provides async wrappers around Docling's DocumentConverter
for parsing PDF files into markdown format with optional OCR.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import logging

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    EasyOcrOptions,
    TesseractOcrOptions,
)
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

from app.utils.logging import get_logger
from app.utils.exceptions import DocumentProcessingError

logger = get_logger(__name__)

# Thread pool for running synchronous Docling operations
_executor = ThreadPoolExecutor(max_workers=4)


def create_docling_config(
    use_ocr: bool = True, ocr_engine: str = "easyocr", full_page_ocr: bool = False
) -> PdfPipelineOptions:
    """
    Create Docling pipeline configuration.

    Args:
        use_ocr: Whether to enable OCR for scanned PDFs
        ocr_engine: OCR engine to use ("easyocr" or "tesseract")
        full_page_ocr: Force full page OCR (slower but more accurate)

    Returns:
        PdfPipelineOptions configured for document parsing

    Note:
        Based on notebook implementation (lines 369-397).
        Uses EasyOcrOptions or TesseractOcrOptions directly instead of
        setting ocr_options.use_easyocr (which doesn't exist in the API).
    """
    # Configure OCR options based on engine
    if use_ocr:
        if ocr_engine == "easyocr":
            ocr_options = EasyOcrOptions(
                lang=["en"],  # English language
                confidence_threshold=0.7,  # Higher threshold for better quality
                use_gpu=True,  # Enable GPU acceleration if available
                recog_network="standard",  # Standard recognition network
                force_full_page_ocr=full_page_ocr,  # Full page OCR mode
            )
        elif ocr_engine == "tesseract":
            ocr_options = TesseractOcrOptions(
                lang=["eng"],  # English language
                psm=6,  # Uniform block of text (good for most documents)
            )
        else:
            logger.warning(f"Unknown OCR engine: {ocr_engine}, using easyocr")
            ocr_options = EasyOcrOptions(
                lang=["en"],
                confidence_threshold=0.7,
                use_gpu=True,
                recog_network="standard",
                force_full_page_ocr=full_page_ocr,
            )
    else:
        ocr_options = None

    # Create pipeline options
    pipeline_options = PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=use_ocr,
        ocr_options=ocr_options,
        generate_picture_images=True,
        images_scale=2.0,  # Higher scale for better text recognition
        force_backend_text=False,  # Let OCR generate the text
    )

    return pipeline_options


def _parse_pdf_sync(pdf_path: Path, pipeline_options: PdfPipelineOptions) -> str:
    """
    Synchronous PDF parsing with Docling (runs in thread pool).

    Args:
        pdf_path: Path to PDF file
        pipeline_options: Docling pipeline configuration

    Returns:
        Markdown content

    Raises:
        DocumentProcessingError: If parsing fails
    """
    try:
        # Create document converter
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options, backend=PyPdfiumDocumentBackend
                )
            }
        )

        # Convert document
        result = converter.convert(str(pdf_path))

        # Export to markdown
        markdown_content = result.document.export_to_markdown()

        logger.info(f"Successfully parsed PDF: {pdf_path.name}")
        return markdown_content

    except Exception as e:
        logger.error(f"Failed to parse PDF {pdf_path.name}: {str(e)}")
        raise DocumentProcessingError(f"PDF parsing failed: {str(e)}")


async def parse_document_with_docling(
    pdf_path: Path, use_ocr: bool = True, ocr_engine: str = "easyocr"
) -> str:
    """
    Parse PDF document to markdown using Docling (async).

    Args:
        pdf_path: Path to PDF file
        use_ocr: Whether to enable OCR
        ocr_engine: OCR engine to use

    Returns:
        Markdown content

    Raises:
        DocumentProcessingError: If parsing fails
    """
    if not pdf_path.exists():
        raise DocumentProcessingError(f"PDF file not found: {pdf_path}")

    if not pdf_path.suffix.lower() == ".pdf":
        raise DocumentProcessingError(f"File is not a PDF: {pdf_path}")

    logger.info(f"Parsing PDF with Docling: {pdf_path.name} (OCR: {use_ocr})")

    # Create pipeline configuration
    pipeline_options = create_docling_config(use_ocr=use_ocr, ocr_engine=ocr_engine)

    # Run synchronous parsing in thread pool
    loop = asyncio.get_event_loop()
    markdown_content = await loop.run_in_executor(
        _executor, _parse_pdf_sync, pdf_path, pipeline_options
    )

    return markdown_content


async def parse_document_with_fallback(
    pdf_path: Path, try_without_ocr_first: bool = True
) -> tuple[str, Dict[str, Any]]:
    """
    Parse PDF with automatic OCR fallback.

    Tries parsing without OCR first (faster), then falls back to OCR if needed.

    Args:
        pdf_path: Path to PDF file
        try_without_ocr_first: Whether to try without OCR first

    Returns:
        Tuple of (markdown_content, metadata)
        metadata includes: used_ocr, ocr_engine, parse_time

    Raises:
        DocumentProcessingError: If all parsing attempts fail
    """
    import time

    metadata = {"used_ocr": False, "ocr_engine": None, "parse_time": 0.0, "fallback_used": False}

    start_time = time.time()

    try:
        if try_without_ocr_first:
            # Try without OCR first (faster for digital PDFs)
            logger.info(f"Attempting to parse {pdf_path.name} without OCR")
            try:
                markdown_content = await parse_document_with_docling(pdf_path, use_ocr=False)
                metadata["used_ocr"] = False
                metadata["parse_time"] = time.time() - start_time
                return markdown_content, metadata

            except Exception as e:
                logger.warning(f"Parsing without OCR failed: {str(e)}, trying with OCR")
                metadata["fallback_used"] = True

        # Parse with OCR
        logger.info(f"Parsing {pdf_path.name} with OCR")
        markdown_content = await parse_document_with_docling(
            pdf_path, use_ocr=True, ocr_engine="easyocr"
        )
        metadata["used_ocr"] = True
        metadata["ocr_engine"] = "easyocr"
        metadata["parse_time"] = time.time() - start_time

        return markdown_content, metadata

    except Exception as e:
        logger.error(f"All parsing attempts failed for {pdf_path.name}: {str(e)}")
        raise DocumentProcessingError(f"Failed to parse PDF: {str(e)}")


def validate_pdf_file(file_path: Path, max_size_mb: int = 50) -> bool:
    """
    Validate PDF file before parsing.

    Args:
        file_path: Path to PDF file
        max_size_mb: Maximum file size in MB

    Returns:
        True if valid, False otherwise
    """
    if not file_path.exists():
        logger.error(f"File does not exist: {file_path}")
        return False

    if not file_path.suffix.lower() == ".pdf":
        logger.error(f"File is not a PDF: {file_path}")
        return False

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        logger.error(f"File too large: {file_size_mb:.2f}MB > {max_size_mb}MB")
        return False

    return True
