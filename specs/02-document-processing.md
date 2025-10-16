# Document Processing Specification

## Overview

This specification defines the document processing pipeline that extracts structured information from construction PDFs using Docling and transforms it into searchable and analyzable data.

## Docling Integration

### Installation and Setup

```python
# requirements.txt
docling==1.0.0
docling-core==1.0.0
pymupdf>=1.23.0
pillow>=10.0.0
```

### Configuration

```python
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

class DocumentProcessorConfig:
    """Configuration for document processing"""
    
    def __init__(self):
        self.pdf_options = PdfPipelineOptions(
            # Text extraction
            do_ocr=True,
            ocr_options={"lang": ["eng"]},
            
            # Table extraction
            do_table_structure=True,
            table_structure_options={
                "method": "table-transformer",
                "threshold": 0.8
            },
            
            # Figure extraction
            do_figure_extraction=True,
            figure_extraction_options={
                "extract_captions": True,
                "extract_alt_text": True
            },
            
            # Layout analysis
            do_chunking=True,
            chunking_options={
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        )
        
        self.converter_options = {
            "input_format": InputFormat.PDF,
            "pipeline_options": self.pdf_options
        }
```

### Document Converter Implementation

```python
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.docling_backend import DoclingDocument

class DocumentProcessor:
    """Main document processing class using Docling"""
    
    def __init__(self, config: DocumentProcessorConfig):
        self.config = config
        self.converter = DocumentConverter()
        
    async def process_document(
        self, 
        file_path: Path, 
        document_id: str
    ) -> Dict[str, Any]:
        """
        Process a PDF document and extract structured content
        
        Args:
            file_path: Path to the PDF file
            document_id: Unique identifier for the document
            
        Returns:
            Dictionary containing extracted content and metadata
        """
        try:
            # Convert document using Docling
            docling_doc = await self.converter.convert(
                file_path, 
                **self.config.converter_options
            )
            
            # Extract structured content
            extracted_data = await self._extract_content(docling_doc, document_id)
            
            return {
                "success": True,
                "document_id": document_id,
                "extracted_data": extracted_data,
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "document_id": document_id,
                "extracted_data": None,
                "error": str(e)
            }
    
    async def _extract_content(
        self, 
        docling_doc: DoclingDocument, 
        document_id: str
    ) -> Dict[str, Any]:
        """Extract structured content from Docling document"""
        
        content = {
            "document_id": document_id,
            "pages": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "metadata": {}
        }
        
        # Extract pages
        for page_idx, page in enumerate(docling_doc.iterate_pages()):
            page_data = await self._extract_page_content(page, page_idx)
            content["pages"].append(page_data)
        
        # Extract sections
        content["sections"] = await self._extract_sections(docling_doc)
        
        # Extract tables
        content["tables"] = await self._extract_tables(docling_doc)
        
        # Extract figures
        content["figures"] = await self._extract_figures(docling_doc)
        
        # Extract metadata
        content["metadata"] = await self._extract_metadata(docling_doc)
        
        return content
    
    async def _extract_page_content(self, page, page_idx: int) -> Dict[str, Any]:
        """Extract content from a single page"""
        page_data = {
            "page_number": page_idx + 1,
            "text_blocks": [],
            "images": [],
            "dimensions": {
                "width": page.width,
                "height": page.height
            }
        }
        
        # Extract text blocks
        for block in page.text_blocks:
            text_block = {
                "text": block.text,
                "bbox": {
                    "x1": block.bbox.x1,
                    "y1": block.bbox.y1,
                    "x2": block.bbox.x2,
                    "y2": block.bbox.y2
                },
                "font_size": block.font_size,
                "font_family": block.font_family,
                "is_bold": block.is_bold,
                "is_italic": block.is_italic
            }
            page_data["text_blocks"].append(text_block)
        
        # Extract images
        for image in page.images:
            image_data = {
                "bbox": {
                    "x1": image.bbox.x1,
                    "y1": image.bbox.y1,
                    "x2": image.bbox.x2,
                    "y2": image.bbox.y2
                },
                "image_data": image.image_data,
                "caption": image.caption
            }
            page_data["images"].append(image_data)
        
        return page_data
    
    async def _extract_sections(self, docling_doc: DoclingDocument) -> List[Dict[str, Any]]:
        """Extract document sections and headings"""
        sections = []
        
        for section in docling_doc.iterate_sections():
            section_data = {
                "id": section.id,
                "title": section.title,
                "level": section.level,
                "text": section.text,
                "page_number": section.page_number,
                "bbox": {
                    "x1": section.bbox.x1,
                    "y1": section.bbox.y1,
                    "x2": section.bbox.x2,
                    "y2": section.bbox.y2
                }
            }
            sections.append(section_data)
        
        return sections
    
    async def _extract_tables(self, docling_doc: DoclingDocument) -> List[Dict[str, Any]]:
        """Extract tables from document"""
        tables = []
        
        for table in docling_doc.iterate_tables():
            table_data = {
                "id": table.id,
                "caption": table.caption,
                "page_number": table.page_number,
                "bbox": {
                    "x1": table.bbox.x1,
                    "y1": table.bbox.y1,
                    "x2": table.bbox.x2,
                    "y2": table.bbox.y2
                },
                "headers": table.headers,
                "rows": [],
                "structure": table.structure
            }
            
            # Extract table rows
            for row in table.rows:
                row_data = {
                    "cells": [cell.text for cell in row.cells],
                    "row_type": row.row_type
                }
                table_data["rows"].append(row_data)
            
            tables.append(table_data)
        
        return tables
    
    async def _extract_figures(self, docling_doc: DoclingDocument) -> List[Dict[str, Any]]:
        """Extract figures and images from document"""
        figures = []
        
        for figure in docling_doc.iterate_figures():
            figure_data = {
                "id": figure.id,
                "caption": figure.caption,
                "alt_text": figure.alt_text,
                "page_number": figure.page_number,
                "bbox": {
                    "x1": figure.bbox.x1,
                    "y1": figure.bbox.y1,
                    "x2": figure.bbox.x2,
                    "y2": figure.bbox.y2
                },
                "image_data": figure.image_data,
                "figure_type": figure.figure_type
            }
            figures.append(figure_data)
        
        return figures
    
    async def _extract_metadata(self, docling_doc: DoclingDocument) -> Dict[str, Any]:
        """Extract document metadata"""
        return {
            "title": docling_doc.title,
            "author": docling_doc.author,
            "creation_date": docling_doc.creation_date,
            "modification_date": docling_doc.modification_date,
            "page_count": docling_doc.page_count,
            "language": docling_doc.language,
            "properties": docling_doc.properties
        }
```

## Passage Extraction and Chunking

### Semantic Chunking Strategy

```python
from typing import List, Dict, Any
import re
from dataclasses import dataclass

@dataclass
class ChunkingConfig:
    """Configuration for document chunking"""
    max_chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 100
    preserve_sections: bool = True
    preserve_tables: bool = True

class PassageExtractor:
    """Extract and chunk passages from processed documents"""
    
    def __init__(self, config: ChunkingConfig):
        self.config = config
        
    async def extract_passages(
        self, 
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract passages from document data
        
        Args:
            extracted_data: Raw extracted data from Docling
            
        Returns:
            List of passage dictionaries
        """
        passages = []
        
        # Extract section-based passages
        if self.config.preserve_sections:
            section_passages = await self._extract_section_passages(extracted_data)
            passages.extend(section_passages)
        
        # Extract table passages
        if self.config.preserve_tables:
            table_passages = await self._extract_table_passages(extracted_data)
            passages.extend(table_passages)
        
        # Extract page-based passages for remaining content
        page_passages = await self._extract_page_passages(extracted_data)
        passages.extend(page_passages)
        
        return passages
    
    async def _extract_section_passages(
        self, 
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract passages from document sections"""
        passages = []
        
        for section in extracted_data.get("sections", []):
            if len(section["text"]) >= self.config.min_chunk_size:
                passage = {
                    "passage_type": "section",
                    "text": section["text"],
                    "title": section["title"],
                    "page_number": section["page_number"],
                    "section_id": section["id"],
                    "heading_level": section["level"],
                    "bbox": section["bbox"]
                }
                passages.append(passage)
        
        return passages
    
    async def _extract_table_passages(
        self, 
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract passages from tables"""
        passages = []
        
        for table in extracted_data.get("tables", []):
            # Create table text representation
            table_text = self._format_table_text(table)
            
            if len(table_text) >= self.config.min_chunk_size:
                passage = {
                    "passage_type": "table",
                    "text": table_text,
                    "title": table["caption"],
                    "page_number": table["page_number"],
                    "table_id": table["id"],
                    "bbox": table["bbox"],
                    "table_headers": table["headers"],
                    "table_rows": table["rows"]
                }
                passages.append(passage)
        
        return passages
    
    async def _extract_page_passages(
        self, 
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract passages from page text blocks"""
        passages = []
        
        for page in extracted_data.get("pages", []):
            page_text = " ".join([block["text"] for block in page["text_blocks"]])
            
            # Split into chunks if too large
            if len(page_text) > self.config.max_chunk_size:
                chunks = self._split_text(page_text)
                for i, chunk in enumerate(chunks):
                    passage = {
                        "passage_type": "text",
                        "text": chunk,
                        "page_number": page["page_number"],
                        "chunk_index": i,
                        "bbox": self._calculate_chunk_bbox(page, i, len(chunks))
                    }
                    passages.append(passage)
            else:
                passage = {
                    "passage_type": "text",
                    "text": page_text,
                    "page_number": page["page_number"],
                    "bbox": page["dimensions"]
                }
                passages.append(passage)
        
        return passages
    
    def _format_table_text(self, table: Dict[str, Any]) -> str:
        """Format table data as readable text"""
        text_parts = []
        
        if table["caption"]:
            text_parts.append(f"Table: {table['caption']}")
        
        # Add headers
        if table["headers"]:
            header_text = " | ".join(table["headers"])
            text_parts.append(f"Headers: {header_text}")
        
        # Add rows
        for row in table["rows"]:
            row_text = " | ".join(row["cells"])
            text_parts.append(row_text)
        
        return "\n".join(text_parts)
    
    def _split_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        current_chunk = []
        current_size = 0
        
        for word in words:
            if current_size + len(word) > self.config.max_chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Start new chunk with overlap
                overlap_words = current_chunk[-self.config.chunk_overlap//10:]
                current_chunk = overlap_words + [word]
                current_size = sum(len(w) for w in current_chunk)
            else:
                current_chunk.append(word)
                current_size += len(word) + 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _calculate_chunk_bbox(self, page: Dict[str, Any], chunk_index: int, total_chunks: int) -> Dict[str, float]:
        """Calculate bounding box for text chunk"""
        page_height = page["dimensions"]["height"]
        chunk_height = page_height / total_chunks
        
        return {
            "x1": 0,
            "y1": chunk_index * chunk_height,
            "x2": page["dimensions"]["width"],
            "y2": (chunk_index + 1) * chunk_height
        }
```

## CSI Division Classification

### CSI Division Parser

```python
import re
from typing import Optional, List, Dict, Any

class CSIDivisionClassifier:
    """Classify document sections by CSI division codes"""
    
    def __init__(self):
        self.csi_patterns = {
            "01": r"\b01\s*\d{2}\s*\d{2}\b",  # General Requirements
            "02": r"\b02\s*\d{2}\s*\d{2}\b",  # Existing Conditions
            "03": r"\b03\s*\d{2}\s*\d{2}\b",  # Concrete
            "04": r"\b04\s*\d{2}\s*\d{2}\b",  # Masonry
            "05": r"\b05\s*\d{2}\s*\d{2}\b",  # Metals
            "06": r"\b06\s*\d{2}\s*\d{2}\b",  # Wood, Plastics, and Composites
            "07": r"\b07\s*\d{2}\s*\d{2}\b",  # Thermal and Moisture Protection
            "08": r"\b08\s*\d{2}\s*\d{2}\b",  # Openings
            "09": r"\b09\s*\d{2}\s*\d{2}\b",  # Finishes
            "10": r"\b10\s*\d{2}\s*\d{2}\b",  # Specialties
            "11": r"\b11\s*\d{2}\s*\d{2}\b",  # Equipment
            "12": r"\b12\s*\d{2}\s*\d{2}\b",  # Furnishings
            "13": r"\b13\s*\d{2}\s*\d{2}\b",  # Special Construction
            "14": r"\b14\s*\d{2}\s*\d{2}\b",  # Conveying Equipment
            "15": r"\b15\s*\d{2}\s*\d{2}\b",  # Fire Suppression
            "16": r"\b16\s*\d{2}\s*\d{2}\b",  # Plumbing
            "17": r"\b17\s*\d{2}\s*\d{2}\b",  # Heating, Ventilating, and Air Conditioning
            "18": r"\b18\s*\d{2}\s*\d{2}\b",  # Electrical
            "19": r"\b19\s*\d{2}\s*\d{2}\b",  # Communication
            "20": r"\b20\s*\d{2}\s*\d{2}\b",  # Electronic Safety and Security
            "21": r"\b21\s*\d{2}\s*\d{2}\b",  # Fire Suppression
            "22": r"\b22\s*\d{2}\s*\d{2}\b",  # Plumbing
            "23": r"\b23\s*\d{2}\s*\d{2}\b",  # Heating, Ventilating, and Air Conditioning
            "24": r"\b24\s*\d{2}\s*\d{2}\b",  # Electrical
            "25": r"\b25\s*\d{2}\s*\d{2}\b",  # Integrated Automation
            "26": r"\b26\s*\d{2}\s*\d{2}\b",  # Electrical
            "27": r"\b27\s*\d{2}\s*\d{2}\b",  # Communications
            "28": r"\b28\s*\d{2}\s*\d{2}\b",  # Electronic Safety and Security
            "29": r"\b29\s*\d{2}\s*\d{2}\b",  # Electronic Safety and Security
            "30": r"\b30\s*\d{2}\s*\d{2}\b",  # Electronic Safety and Security
            "31": r"\b31\s*\d{2}\s*\d{2}\b",  # Earthwork
            "32": r"\b32\s*\d{2}\s*\d{2}\b",  # Exterior Improvements
            "33": r"\b33\s*\d{2}\s*\d{2}\b",  # Utilities
            "34": r"\b34\s*\d{2}\s*\d{2}\b",  # Transportation
            "35": r"\b35\s*\d{2}\s*\d{2}\b",  # Waterway and Marine Construction
            "40": r"\b40\s*\d{2}\s*\d{2}\b",  # Process Integration
            "41": r"\b41\s*\d{2}\s*\d{2}\b",  # Material Processing and Handling Equipment
            "42": r"\b42\s*\d{2}\s*\d{2}\b",  # Process Heating, Cooling, and Drying Equipment
            "43": r"\b43\s*\d{2}\s*\d{2}\b",  # Process Gas and Liquid Handling, Purification and Storage Equipment
            "44": r"\b44\s*\d{2}\s*\d{2}\b",  # Pollution and Waste Control Equipment
            "45": r"\b45\s*\d{2}\s*\d{2}\b",  # Industry-Specific Manufacturing Equipment
            "46": r"\b46\s*\d{2}\s*\d{2}\b",  # Water and Wastewater Equipment
            "48": r"\b48\s*\d{2}\s*\d{2}\b",  # Electrical Power Generation
            "49": r"\b49\s*\d{2}\s*\d{2}\b",  # Electrical Power Generation
        }
    
    async def classify_passage(self, passage: Dict[str, Any]) -> List[str]:
        """
        Classify passage by CSI division codes
        
        Args:
            passage: Passage data with text content
            
        Returns:
            List of CSI division codes found in passage
        """
        text = passage.get("text", "")
        title = passage.get("title", "")
        
        # Search in both title and text
        search_text = f"{title} {text}"
        
        found_divisions = []
        
        for division, pattern in self.csi_patterns.items():
            if re.search(pattern, search_text, re.IGNORECASE):
                found_divisions.append(division)
        
        return found_divisions
    
    async def classify_document(self, extracted_data: Dict[str, Any]) -> List[str]:
        """
        Classify entire document by CSI divisions
        
        Args:
            extracted_data: Complete extracted document data
            
        Returns:
            List of all CSI division codes found in document
        """
        all_divisions = set()
        
        # Check sections
        for section in extracted_data.get("sections", []):
            divisions = await self.classify_passage(section)
            all_divisions.update(divisions)
        
        # Check tables
        for table in extracted_data.get("tables", []):
            divisions = await self.classify_passage(table)
            all_divisions.update(divisions)
        
        return list(all_divisions)
```

## Error Handling and Validation

### Processing Error Handling

```python
from enum import Enum
from typing import Optional, Dict, Any
import logging

class ProcessingErrorType(str, Enum):
    FILE_NOT_FOUND = "file_not_found"
    CORRUPTED_PDF = "corrupted_pdf"
    OCR_FAILED = "ocr_failed"
    EXTRACTION_FAILED = "extraction_failed"
    PARSING_ERROR = "parsing_error"
    VALIDATION_ERROR = "validation_error"

class ProcessingError(Exception):
    """Custom exception for document processing errors"""
    
    def __init__(
        self, 
        error_type: ProcessingErrorType,
        message: str,
        document_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_type = error_type
        self.message = message
        self.document_id = document_id
        self.details = details or {}
        super().__init__(message)

class DocumentProcessorValidator:
    """Validate processed document data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def validate_extracted_data(
        self, 
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate extracted document data
        
        Args:
            extracted_data: Raw extracted data
            
        Returns:
            Validation results with errors and warnings
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {}
        }
        
        # Check required fields
        required_fields = ["document_id", "pages", "sections", "tables", "figures"]
        for field in required_fields:
            if field not in extracted_data:
                validation_results["errors"].append(f"Missing required field: {field}")
                validation_results["valid"] = False
        
        # Validate page data
        page_errors = await self._validate_pages(extracted_data.get("pages", []))
        validation_results["errors"].extend(page_errors)
        
        # Validate sections
        section_errors = await self._validate_sections(extracted_data.get("sections", []))
        validation_results["errors"].extend(section_errors)
        
        # Validate tables
        table_errors = await self._validate_tables(extracted_data.get("tables", []))
        validation_results["errors"].extend(table_errors)
        
        # Generate statistics
        validation_results["statistics"] = self._generate_statistics(extracted_data)
        
        if validation_results["errors"]:
            validation_results["valid"] = False
        
        return validation_results
    
    async def _validate_pages(self, pages: List[Dict[str, Any]]) -> List[str]:
        """Validate page data"""
        errors = []
        
        if not pages:
            errors.append("No pages found in document")
            return errors
        
        for i, page in enumerate(pages):
            if "page_number" not in page:
                errors.append(f"Page {i}: Missing page_number")
            
            if "text_blocks" not in page:
                errors.append(f"Page {i}: Missing text_blocks")
            
            if "dimensions" not in page:
                errors.append(f"Page {i}: Missing dimensions")
            
            # Check for empty pages
            if not page.get("text_blocks") and not page.get("images"):
                errors.append(f"Page {i}: Empty page with no content")
        
        return errors
    
    async def _validate_sections(self, sections: List[Dict[str, Any]]) -> List[str]:
        """Validate section data"""
        errors = []
        
        for i, section in enumerate(sections):
            if "id" not in section:
                errors.append(f"Section {i}: Missing section ID")
            
            if "text" not in section or not section["text"].strip():
                errors.append(f"Section {i}: Empty section text")
        
        return errors
    
    async def _validate_tables(self, tables: List[Dict[str, Any]]) -> List[str]:
        """Validate table data"""
        errors = []
        
        for i, table in enumerate(tables):
            if "id" not in table:
                errors.append(f"Table {i}: Missing table ID")
            
            if "rows" not in table or not table["rows"]:
                errors.append(f"Table {i}: No table rows found")
            
            # Check table structure consistency
            if table.get("rows"):
                first_row_cols = len(table["rows"][0].get("cells", []))
                for j, row in enumerate(table["rows"]):
                    if len(row.get("cells", [])) != first_row_cols:
                        errors.append(f"Table {i}, Row {j}: Inconsistent column count")
        
        return errors
    
    def _generate_statistics(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate document statistics"""
        stats = {
            "page_count": len(extracted_data.get("pages", [])),
            "section_count": len(extracted_data.get("sections", [])),
            "table_count": len(extracted_data.get("tables", [])),
            "figure_count": len(extracted_data.get("figures", [])),
            "total_text_blocks": 0,
            "total_words": 0
        }
        
        # Count text blocks and words
        for page in extracted_data.get("pages", []):
            stats["total_text_blocks"] += len(page.get("text_blocks", []))
            for block in page.get("text_blocks", []):
                stats["total_words"] += len(block.get("text", "").split())
        
        return stats
```

## Performance Optimization

### Async Processing Pipeline

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

class AsyncDocumentProcessor:
    """Async document processing with parallel execution"""
    
    def __init__(self, config: DocumentProcessorConfig, max_workers: int = 4):
        self.config = config
        self.processor = DocumentProcessor(config)
        self.validator = DocumentProcessorValidator()
        self.classifier = CSIDivisionClassifier()
        self.extractor = PassageExtractor(ChunkingConfig())
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def process_documents_parallel(
        self, 
        file_paths: List[Path]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple documents in parallel
        
        Args:
            file_paths: List of PDF file paths
            
        Returns:
            List of processing results
        """
        tasks = [
            self._process_single_document(file_path, f"doc_{i}")
            for i, file_path in enumerate(file_paths)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "document_id": f"doc_{i}",
                    "error": str(result),
                    "extracted_data": None
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_document(
        self, 
        file_path: Path, 
        document_id: str
    ) -> Dict[str, Any]:
        """Process a single document with all steps"""
        
        # Step 1: Extract content with Docling
        extraction_result = await self.processor.process_document(file_path, document_id)
        
        if not extraction_result["success"]:
            return extraction_result
        
        # Step 2: Validate extracted data
        validation_result = await self.validator.validate_extracted_data(
            extraction_result["extracted_data"]
        )
        
        if not validation_result["valid"]:
            return {
                "success": False,
                "document_id": document_id,
                "error": "Validation failed",
                "validation_errors": validation_result["errors"]
            }
        
        # Step 3: Classify CSI divisions
        csi_divisions = await self.classifier.classify_document(
            extraction_result["extracted_data"]
        )
        
        # Step 4: Extract passages
        passages = await self.extractor.extract_passages(
            extraction_result["extracted_data"]
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "extracted_data": extraction_result["extracted_data"],
            "validation_results": validation_result,
            "csi_divisions": csi_divisions,
            "passages": passages,
            "error": None
        }
```

## Integration with Storage Systems

### Database Integration

```python
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any

class DocumentStorageManager:
    """Manage document storage and database operations"""
    
    def __init__(self, mongodb_url: str):
        self.client = AsyncIOMotorClient(mongodb_url)
        self.db = self.client.construction_specs
        
        # Collections
        self.documents = self.db.documents
        self.passages = self.db.passages
        self.facts = self.db.facts
    
    async def store_processed_document(
        self, 
        processing_result: Dict[str, Any],
        file_path: Path
    ) -> str:
        """
        Store processed document data in database
        
        Args:
            processing_result: Result from document processing
            file_path: Path to original file
            
        Returns:
            Document ID
        """
        document_id = processing_result["document_id"]
        
        # Store document metadata
        document_data = {
            "id": document_id,
            "filename": file_path.name,
            "file_path": str(file_path),
            "status": "processed",
            "page_count": len(processing_result["extracted_data"]["pages"]),
            "sections": [s["id"] for s in processing_result["extracted_data"]["sections"]],
            "csi_divisions": processing_result["csi_divisions"],
            "metadata": processing_result["validation_results"]["statistics"]
        }
        
        await self.documents.insert_one(document_data)
        
        # Store passages
        for passage in processing_result["passages"]:
            passage_data = {
                "id": f"{document_id}_passage_{len(processing_result['passages'])}",
                "document_id": document_id,
                **passage
            }
            await self.passages.insert_one(passage_data)
        
        return document_id
```

This document processing specification provides a comprehensive foundation for extracting structured information from construction PDFs using Docling, with robust error handling, validation, and integration capabilities.
