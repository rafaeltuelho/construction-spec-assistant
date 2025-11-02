"""
Document processing service.

This service orchestrates the full document processing pipeline:
1. Parse PDF with Docling
2. Sectionize markdown into CSI hierarchy
3. Chunk sections with token limits
4. Store in MongoDB
5. Index in Qdrant
"""

import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import QdrantClient

from app.core.docling_parser import parse_document_with_fallback, validate_pdf_file
from app.core.sectionizer import sectionize_markdown, flatten_sections, count_sections
from app.core.chunker import chunk_sections, get_chunk_statistics, simple_chunk_markdown
from app.db.mongodb import (
    store_document,
    update_document_status,
    update_document,
    store_document_sections,
    store_document_chunks
)
from app.db.qdrant import index_chunks_in_qdrant
from app.models.document import (
    Document,
    DocumentMetadata,
    DocumentStatus,
    DocumentType,
    DocumentSection,
    DocumentChunk,
    ProcessingStats,
    ProcessingError
)
from app.utils.logging import get_logger
from app.utils.exceptions import DocumentProcessingError

logger = get_logger(__name__)


async def process_document(
    pdf_path: Path,
    mongodb: AsyncIOMotorDatabase,
    qdrant: QdrantClient,
    document_type: DocumentType,
    title: Optional[str] = None,
    use_ocr: bool = True,
    max_chunk_tokens: int = 500,
    chunk_overlap_tokens: int = 50
) -> Document:
    """
    Process a PDF document through the full pipeline.

    Processing differs based on document type:
    - SPECIFICATION: Uses CSI-aware sectionization and hierarchical chunking
    - SUBMITTAL/PRODUCT_DESCRIPTION/DRAWING: Uses simple paragraph-based chunking

    Args:
        pdf_path: Path to PDF file
        mongodb: MongoDB database instance
        qdrant: Qdrant client
        document_type: Type of document (specification, submittal, etc.)
        title: Document title (defaults to filename)
        use_ocr: Enable OCR for scanned PDFs
        max_chunk_tokens: Maximum tokens per chunk
        chunk_overlap_tokens: Overlap between chunks

    Returns:
        Processed document

    Raises:
        DocumentProcessingError: If processing fails
    """
    document_id = str(uuid.uuid4())
    doc_title = title or pdf_path.stem

    logger.info(f"Starting document processing: {doc_title} ({document_id}) [type={document_type.value}]")

    # Validate PDF
    if not validate_pdf_file(pdf_path):
        raise DocumentProcessingError(f"Invalid PDF file: {pdf_path}")

    # Create initial document
    metadata = DocumentMetadata(
        document_type=document_type,
        filename=pdf_path.name,
        file_size=pdf_path.stat().st_size,
        mime_type="application/pdf"
    )
    
    document = Document(
        document_id=document_id,
        title=doc_title,
        status=DocumentStatus.PENDING,
        metadata=metadata
    )
    
    # Store initial document
    await store_document(mongodb, document)
    
    try:
        # Update status to processing
        await update_document_status(mongodb, document_id, DocumentStatus.PROCESSING)
        
        # Step 1: Parse PDF with Docling
        logger.info(f"[{document_id}] Step 1: Parsing PDF")
        markdown_content, parse_metadata = await parse_document_with_fallback(
            pdf_path,
            try_without_ocr_first=not use_ocr
        )
        
        # Update metadata
        metadata.used_ocr = parse_metadata["used_ocr"]
        metadata.ocr_engine = parse_metadata.get("ocr_engine")
        metadata.parse_time = parse_metadata["parse_time"]
        metadata.processing_timestamp = datetime.utcnow()
        
        await update_document(mongodb, document_id, {
            "markdown_content": markdown_content,
            "metadata": metadata.model_dump()
        })

        # Step 2 & 3: Process based on document type
        if document_type == DocumentType.SPECIFICATION:
            # CSI Specification: Use hierarchical sectionization
            logger.info(f"[{document_id}] Step 2: Sectionizing CSI specification")
            sections = sectionize_markdown(markdown_content)

            if not sections:
                logger.warning(f"[{document_id}] No sections found in document")

            section_counts = count_sections(sections)
            logger.info(f"[{document_id}] Found sections: {section_counts}")

            # Step 3: Chunk sections with CSI hierarchy
            logger.info(f"[{document_id}] Step 3: Chunking sections (CSI-aware)")
            chunks = chunk_sections(
                sections,
                max_tokens=max_chunk_tokens,
                overlap_tokens=chunk_overlap_tokens
            )

            chunk_stats = get_chunk_statistics(chunks)
            logger.info(f"[{document_id}] Created {chunk_stats['total_chunks']} chunks")

            # Step 4: Store sections in MongoDB
            logger.info(f"[{document_id}] Step 4: Storing sections")
            flat_sections = flatten_sections(sections)

            document_sections = []
            for idx, section in enumerate(flat_sections):
                doc_section = DocumentSection(
                    section_id=f"{document_id}_section_{idx}",
                    document_id=document_id,
                    title=section.title,
                    level=section.level,
                    section_number=section.section_number,
                    content=section.content,
                    order_index=idx
                )
                document_sections.append(doc_section)

            await store_document_sections(mongodb, document_sections)

        else:
            # Submittal/Product Description/Drawing: Use simple chunking
            logger.info(f"[{document_id}] Step 2: Skipping CSI sectionization (document type: {document_type.value})")

            # Step 3: Simple chunking without hierarchy
            logger.info(f"[{document_id}] Step 3: Simple chunking (paragraph-based)")
            chunks = simple_chunk_markdown(
                markdown_content,
                max_tokens=max_chunk_tokens,
                overlap_tokens=chunk_overlap_tokens
            )

            chunk_stats = get_chunk_statistics(chunks)
            logger.info(f"[{document_id}] Created {chunk_stats['total_chunks']} simple chunks")

            # No sections to store for non-CSI documents
            section_counts = {}
            document_sections = []
        
        # Step 5: Store chunks in MongoDB
        logger.info(f"[{document_id}] Step 5: Storing chunks")
        document_chunks = []
        for chunk in chunks:
            doc_chunk = DocumentChunk(
                chunk_id=chunk.chunk_id,
                document_id=document_id,
                section_id=f"{document_id}_section_0",  # Simplified
                section_title=chunk.section_title,
                section_number=chunk.section_number,
                section_level=chunk.section_level,
                content=chunk.content,
                token_count=chunk.token_count,
                chunk_index=chunk.chunk_index,
                total_chunks=chunk.total_chunks
            )
            document_chunks.append(doc_chunk)
        
        await store_document_chunks(mongodb, document_chunks)
        
        # Step 6: Index chunks in Qdrant
        logger.info(f"[{document_id}] Step 6: Indexing in Qdrant")
        await index_chunks_in_qdrant(qdrant, document_chunks)
        
        # Update processing stats
        processing_stats = ProcessingStats(
            total_sections=len(document_sections),
            sections_by_level=section_counts,
            total_chunks=chunk_stats["total_chunks"],
            total_tokens=chunk_stats["total_tokens"],
            avg_chunk_tokens=chunk_stats["avg_tokens"]
        )
        
        await update_document(mongodb, document_id, {
            "status": DocumentStatus.COMPLETED.value,
            "processing_stats": processing_stats.model_dump()
        })
        
        logger.info(f"[{document_id}] Document processing completed successfully")
        
        # Return updated document
        document.status = DocumentStatus.COMPLETED
        document.markdown_content = markdown_content
        document.processing_stats = processing_stats
        
        return document
        
    except Exception as e:
        logger.error(f"[{document_id}] Document processing failed: {str(e)}")
        
        # Update status to failed
        await update_document_status(
            mongodb,
            document_id,
            DocumentStatus.FAILED,
            error=str(e)
        )
        
        raise DocumentProcessingError(f"Document processing failed: {str(e)}")

