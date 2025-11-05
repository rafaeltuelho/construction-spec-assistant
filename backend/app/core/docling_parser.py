"""
Docling-based PDF parser with OCR support.

This module provides async wrappers around Docling's DocumentConverter
for parsing PDF files into markdown format with optional OCR.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
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
from docling_core.types.doc import DoclingDocument

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
        # When OCR is disabled, still need to provide default OCR options
        # but set do_ocr=False in pipeline options
        ocr_options = EasyOcrOptions(
            lang=["en"],
            confidence_threshold=0.7,
            use_gpu=True,
            recog_network="standard",
            force_full_page_ocr=False,
        )

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


def extract_page_number_mapping(docling_doc: DoclingDocument) -> Dict[int, List[int]]:
    """
    Extract page number mapping from Docling document.

    Creates a mapping from character positions in the markdown to page numbers.
    This allows us to determine which page a section or chunk belongs to.

    Args:
        docling_doc: Docling document object

    Returns:
        Dictionary mapping character positions to page numbers (0-indexed)
        Format: {char_position: [page_no, ...]}

    Example:
        {
            0: [0],      # Characters 0-100 are on page 0
            100: [0],
            200: [1],    # Characters 200-300 are on page 1
            ...
        }
    """
    page_mapping: Dict[int, List[int]] = {}

    try:
        # Iterate through all document items to extract provenance
        for item, _level in docling_doc.iterate_items():
            if hasattr(item, "prov") and item.prov:
                # Get the first provenance item (usually there's only one)
                prov = item.prov[0]
                page_no = prov.page_no  # 0-indexed page number

                # Get character span if available
                if hasattr(prov, "charspan") and prov.charspan:
                    start_char = prov.charspan[0]
                    end_char = prov.charspan[1]

                    # Map character positions to page numbers
                    for char_pos in range(start_char, end_char + 1, 10):  # Sample every 10 chars
                        if char_pos not in page_mapping:
                            page_mapping[char_pos] = []
                        if page_no not in page_mapping[char_pos]:
                            page_mapping[char_pos].append(page_no)

        logger.debug(f"Extracted page mapping with {len(page_mapping)} character positions")

    except Exception as e:
        logger.warning(f"Failed to extract page number mapping: {str(e)}")
        # Return empty mapping on error
        return {}

    return page_mapping


def get_page_number_for_position(
    char_position: int, page_mapping: Dict[int, List[int]]
) -> Optional[int]:
    """
    Get the page number for a given character position in the markdown.

    Args:
        char_position: Character position in the markdown text
        page_mapping: Page number mapping from extract_page_number_mapping()

    Returns:
        Page number (0-indexed) or None if not found
    """
    if not page_mapping:
        return None

    # Find the closest character position in the mapping
    closest_pos = None
    min_distance = float("inf")

    for pos in page_mapping.keys():
        distance = abs(pos - char_position)
        if distance < min_distance:
            min_distance = distance
            closest_pos = pos

    if closest_pos is not None and page_mapping[closest_pos]:
        return page_mapping[closest_pos][0]  # Return first page number

    return None


def _parse_pdf_sync(
    pdf_path: Path,
    pipeline_options: PdfPipelineOptions,
    return_docling_doc: bool = False,
    extract_page_mapping: bool = False,
) -> Tuple[str, Optional[DoclingDocument], Optional[Dict[int, List[int]]]]:
    """
    Synchronous PDF parsing with Docling (runs in thread pool).

    Args:
        pdf_path: Path to PDF file
        pipeline_options: Docling pipeline configuration
        return_docling_doc: If True, also return the Docling document object
        extract_page_mapping: If True, extract page number mapping from provenance

    Returns:
        Tuple of (markdown_content, docling_document, page_mapping)
        - If return_docling_doc is False, docling_document will be None
        - If extract_page_mapping is False, page_mapping will be None

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

        # Return document object if requested
        docling_doc = result.document if return_docling_doc else None

        # Extract page mapping if requested
        page_mapping = None
        if extract_page_mapping and result.document:
            page_mapping = extract_page_number_mapping(result.document)
            logger.info(f"Extracted page mapping with {len(page_mapping)} character positions")

        return markdown_content, docling_doc, page_mapping

    except Exception as e:
        logger.error(f"Failed to parse PDF {pdf_path.name}: {str(e)}")
        raise DocumentProcessingError(f"PDF parsing failed: {str(e)}")


async def parse_document_with_docling(
    pdf_path: Path,
    use_ocr: bool = True,
    ocr_engine: str = "easyocr",
    return_docling_doc: bool = False,
    extract_page_mapping: bool = False,
) -> Tuple[str, Optional[DoclingDocument], Optional[Dict[int, List[int]]]]:
    """
    Parse PDF document to markdown using Docling (async).

    Args:
        pdf_path: Path to PDF file
        use_ocr: Whether to enable OCR
        ocr_engine: OCR engine to use
        return_docling_doc: If True, also return the Docling document object
        extract_page_mapping: If True, extract page number mapping from provenance

    Returns:
        Tuple of (markdown_content, docling_document, page_mapping)
        - If return_docling_doc is False, docling_document will be None
        - If extract_page_mapping is False, page_mapping will be None

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
    markdown_content, docling_doc, page_mapping = await loop.run_in_executor(
        _executor,
        _parse_pdf_sync,
        pdf_path,
        pipeline_options,
        return_docling_doc,
        extract_page_mapping,
    )

    return markdown_content, docling_doc, page_mapping


async def parse_document_with_fallback(
    pdf_path: Path,
    try_without_ocr_first: bool = True,
    return_docling_doc: bool = False,
    extract_page_mapping: bool = False,
) -> Tuple[str, Dict[str, Any], Optional[DoclingDocument], Optional[Dict[int, List[int]]]]:
    """
    Parse PDF with automatic OCR fallback.

    Tries parsing without OCR first (faster), then falls back to OCR if needed.

    Args:
        pdf_path: Path to PDF file
        try_without_ocr_first: Whether to try without OCR first
        return_docling_doc: If True, also return the Docling document object
        extract_page_mapping: If True, extract page number mapping from provenance

    Returns:
        Tuple of (markdown_content, metadata, docling_document, page_mapping)
        - metadata includes: used_ocr, ocr_engine, parse_time
        - If return_docling_doc is False, docling_document will be None
        - If extract_page_mapping is False, page_mapping will be None

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
                markdown_content, docling_doc, page_mapping = await parse_document_with_docling(
                    pdf_path,
                    use_ocr=False,
                    return_docling_doc=return_docling_doc,
                    extract_page_mapping=extract_page_mapping,
                )
                metadata["used_ocr"] = False
                metadata["parse_time"] = time.time() - start_time
                return markdown_content, metadata, docling_doc, page_mapping

            except Exception as e:
                logger.warning(f"Parsing without OCR failed: {str(e)}, trying with OCR")
                metadata["fallback_used"] = True

        # Parse with OCR
        logger.info(f"Parsing {pdf_path.name} with OCR")
        markdown_content, docling_doc, page_mapping = await parse_document_with_docling(
            pdf_path,
            use_ocr=True,
            ocr_engine="easyocr",
            return_docling_doc=return_docling_doc,
            extract_page_mapping=extract_page_mapping,
        )
        metadata["used_ocr"] = True
        metadata["ocr_engine"] = "easyocr"
        metadata["parse_time"] = time.time() - start_time

        return markdown_content, metadata, docling_doc, page_mapping

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
