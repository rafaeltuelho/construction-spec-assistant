"""Document parsing service using Docling for PDF processing."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
from docling.datamodel.pipeline_options import EasyOcrOptions
from docling_core.types.doc import ImageRefMode

from ..models.documents import Section, SectionChunk, sectionize_markdown, chunk_sections
from ..utils.token_counter import count_tokens

logger = logging.getLogger(__name__)


def create_docling_config(full_page_ocr: bool = False) -> Dict[str, Any]:
    """Create Docling configuration optimized for construction documents."""
    
    # PDF pipeline options based on real construction document analysis
    pdf_options = PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=True,
        ocr_options=EasyOcrOptions(
            lang=["en"],  # Specify your language(s)
            confidence_threshold=0.7,  # Higher threshold for better quality
            use_gpu=True,  # Enable GPU acceleration if available
            recog_network="ROSENet",  # Use ROSENet recognition network
            force_full_page_ocr=full_page_ocr # processes each page purely via OCR (often slower than hybrid detection)
        ),
        generate_picture_images=True,
        images_scale=2.0,  # Higher scale for better text recognition
        force_backend_text=False  # Let OCR generate the text
    )
    
    # Format options
    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
    }
    
    return format_options


class DocumentParser:
    """Service for parsing documents using Docling."""
    
    def __init__(self):
        """Initialize the document parser."""
        self.converter = None
        self.ocr_converter = None
    
    def _get_converter(self, full_page_ocr: bool = False) -> DocumentConverter:
        """Get or create a document converter."""
        if full_page_ocr:
            if self.ocr_converter is None:
                self.ocr_converter = DocumentConverter(format_options=create_docling_config(full_page_ocr=True))
            return self.ocr_converter
        else:
            if self.converter is None:
                self.converter = DocumentConverter(format_options=create_docling_config())
            return self.converter
    
    def parse_document_with_docling(
        self,
        pdf_path: Path,
        is_csi_spec: bool = False,
        save_pictures: bool = False,
        save_tables: bool = False,
        write_artifacts: bool = True,
        token_counter: Optional[Callable[[str], int]] = None,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Parse a single PDF document using Docling.
        
        Args:
            pdf_path: Path to the PDF file
            is_csi_spec: Whether this is a CSI specification document
            save_pictures: Whether to save extracted pictures
            save_tables: Whether to save extracted tables
            write_artifacts: Whether to write artifacts to disk
            token_counter: Token counting function
            output_dir: Directory to save artifacts (defaults to data/parsed)
            
        Returns:
            Dictionary containing parsed document information
        """
        document_name = pdf_path.stem
        logger.info(f"Parsing {document_name}...")
        start_time = datetime.now()
        
        # Use full page OCR for submittals, hybrid for specs
        full_page_ocr = not is_csi_spec
        converter = self._get_converter(full_page_ocr)
        
        try:
            # Convert document
            conv_res = converter.convert(str(pdf_path))
            doc = conv_res.document
            
            # Extract basic document information
            md_text = doc.export_to_markdown()
            section_dicts = []
            section_chunk_dicts = []
            
            # sectionize and chunk CSI Spec
            if is_csi_spec:
                sections = sectionize_markdown(md_text)
                section_dicts = [self._section_to_dict(s) for s in sections]
                section_chunks = chunk_sections(
                    sections, 
                    max_tokens=700, 
                    overlap_tokens=80, 
                    token_counter=token_counter or count_tokens
                )
                section_chunk_dicts = [self._section_chunk_to_dict(c) for c in section_chunks]

            doc_info: Dict[str, Any] = {
                "filename": pdf_path.name,
                "document_name": document_name,
                "parse_timestamp": start_time.isoformat(),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "success": True,
                "error": None,
                "full_text": md_text,
                "sections": section_dicts,
                "section_chunks": section_chunk_dicts,
                "tables": [],
                "figures": []
            }
            
            # Save artifacts (optional)
            if write_artifacts:
                self._save_artifacts(
                    doc, doc_info, output_dir or Path("data/parsed"),
                    is_csi_spec, section_dicts, section_chunk_dicts
                )

            # Extract tables and figures (optional)
            if save_tables or save_pictures:
                self._extract_tables_and_figures(
                    conv_res, doc_info, save_tables, save_pictures, output_dir
                )
                
            logger.info(f"Successfully parsed {document_name}")
            logger.info(f"Processing time: {doc_info['processing_time_seconds']:.2f} seconds")
            logger.info(f"Sections: {len(doc_info['sections'])}")
            logger.info(f"Section chunks: {len(doc_info['section_chunks'])}")
            logger.info(f"Tables: {len(doc_info['tables'])}")
            logger.info(f"Figures: {len(doc_info['figures'])}")
            
            return doc_info
            
        except Exception as e:
            error_info = {
                "filename": pdf_path.name,
                "document_name": document_name,
                "parse_timestamp": start_time.isoformat(),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "success": False,
                "error": str(e),
                "full_text": None,
                "sections": [],
                "section_chunks": [],
                "tables": [],
                "figures": [],
            }
            
            logger.error(f"Error parsing {document_name}: {e}")
            return error_info
    
    def _section_to_dict(self, section: Section) -> Dict[str, Any]:
        """Convert Section to dictionary."""
        return {
            "id": section.id,
            "level": section.level,
            "header": section.header,
            "header_path": section.header_path,
            "page_start": section.page_start,
            "page_end": section.page_end,
            "text": section.text
        }
    
    def _section_chunk_to_dict(self, chunk: SectionChunk) -> Dict[str, Any]:
        """Convert SectionChunk to dictionary."""
        return {
            "section_id": chunk.section_id,
            "header_path": chunk.header_path,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text
        }
    
    def _save_artifacts(
        self,
        doc,
        doc_info: Dict[str, Any],
        output_dir: Path,
        is_csi_spec: bool,
        section_dicts: List[Dict[str, Any]],
        section_chunk_dicts: List[Dict[str, Any]]
    ):
        """Save document artifacts to disk."""
        import json
        
        parsed_dir = Path(output_dir)
        parsed_dir.mkdir(parents=True, exist_ok=True)

        # Save the full text content to a Markdown file
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        md_filename = parsed_dir / f"{doc_info['document_name']}_{ts}.md"
        doc.save_as_markdown(md_filename, image_mode=ImageRefMode.REFERENCED)

        if is_csi_spec:
            # Sections JSONL
            sections_file = parsed_dir / f"{doc_info['document_name']}_{ts}.sections.jsonl"
            with sections_file.open("w", encoding="utf-8") as fp:
                for s in section_dicts:
                    fp.write(json.dumps(s, ensure_ascii=False) + "\n")

            # Section Chunks JSONL
            chunks_file = parsed_dir / f"{doc_info['document_name']}_{ts}.section_chunks.jsonl"
            with chunks_file.open("w", encoding="utf-8") as fp:
                for c in section_chunk_dicts:
                    fp.write(json.dumps(c, ensure_ascii=False) + "\n")
    
    def _extract_tables_and_figures(
        self,
        conv_res,
        doc_info: Dict[str, Any],
        save_tables: bool,
        save_pictures: bool,
        output_dir: Optional[Path]
    ):
        """Extract tables and figures from document."""
        import pandas as pd
        from docling_core.types.doc import TableItem, PictureItem
        
        table_counter = 0
        picture_counter = 0
        
        for element, _level in conv_res.document.iterate_items():
            if save_tables and isinstance(element, TableItem):
                table_counter += 1
                table_df: pd.DataFrame = element.export_to_dataframe()
                table_info = {
                    "table_id": table_counter,
                    "markdown": table_df.to_markdown()
                }
                doc_info["tables"].append(table_info)

            if save_pictures and isinstance(element, PictureItem):
                picture_counter += 1
                figure_info = {
                    "figure_id": picture_counter,
                    "bbox": element.bbox if hasattr(element, 'bbox') else None,
                    "caption": element.caption if hasattr(element, 'caption') else None
                }
                doc_info["figures"].append(figure_info)
                
                if output_dir:
                    element_image_filename = output_dir / f"{doc_info['document_name']}-figure-{picture_counter}.png"
                    with element_image_filename.open("wb") as fp:
                        element.get_image(conv_res.document).save(fp, "PNG")
