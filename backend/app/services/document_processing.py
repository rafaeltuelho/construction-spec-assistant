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

from app.config import settings
from app.core.docling_parser import parse_document_with_fallback, validate_pdf_file
from app.core.sectionizer import sectionize_markdown, flatten_sections, count_sections
from app.core.chunker import (
    chunk_sections,
    get_chunk_statistics,
    simple_chunk_markdown,
    hybrid_chunk_document,
)
from app.db.mongodb import (
    store_document,
    update_document_status,
    update_document,
    store_document_sections,
    store_document_chunks,
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
    ProcessingError,
)
from app.utils.logging import get_logger
from app.utils.exceptions import DocumentProcessingError

logger = get_logger(__name__)


async def update_processing_progress(
    mongodb: AsyncIOMotorDatabase,
    document_id: str,
    percentage: int,
    current_stage: str,
    estimated_completion: Optional[datetime] = None,
):
    """Update document processing progress in MongoDB."""
    from app.models.document import ProcessingProgress

    progress = ProcessingProgress(
        percentage=percentage,
        current_stage=current_stage,
        stages=["parsing", "sectionizing", "chunking", "indexing"],
        estimated_completion=estimated_completion,
    )

    await update_document(mongodb, document_id, {"progress": progress.model_dump()})
    logger.debug(f"[{document_id}] Progress updated: {percentage}% - {current_stage}")


async def process_document(
    pdf_path: Path,
    mongodb: AsyncIOMotorDatabase,
    qdrant: QdrantClient,
    document_type: DocumentType,
    title: Optional[str] = None,
    use_ocr: bool = True,
    max_chunk_tokens: int = 500,
    chunk_overlap_tokens: int = 50,
    document_id: Optional[str] = None,
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
        document_id: Optional existing document ID (for async processing)

    Returns:
        Processed document

    Raises:
        DocumentProcessingError: If processing fails
    """
    # Use existing document_id or generate new one
    if document_id is None:
        document_id = str(uuid.uuid4())
        doc_title = title or pdf_path.stem

        logger.info(
            f"Starting document processing: {doc_title} ({document_id}) [type={document_type.value}]"
        )

        # Validate PDF
        if not validate_pdf_file(pdf_path):
            raise DocumentProcessingError(f"Invalid PDF file: {pdf_path}")

        # Create initial document
        metadata = DocumentMetadata(
            document_type=document_type,
            filename=pdf_path.name,
            file_size=pdf_path.stat().st_size,
            mime_type="application/pdf",
        )

        document = Document(
            document_id=document_id,
            title=doc_title,
            status=DocumentStatus.PENDING,
            metadata=metadata,
        )

        # Store initial document
        await store_document(mongodb, document)
    else:
        # Document already exists, just get the title
        doc_title = title or pdf_path.stem
        logger.info(
            f"Continuing document processing: {doc_title} ({document_id}) [type={document_type.value}]"
        )

    try:
        # Update status to processing
        await update_document_status(mongodb, document_id, DocumentStatus.PROCESSING)
        await update_processing_progress(mongodb, document_id, 0, "parsing")

        # Step 1: Parse PDF with Docling
        logger.info(f"[{document_id}] Step 1: Parsing PDF")
        await update_processing_progress(mongodb, document_id, 10, "parsing")

        # For submittals/product descriptions, also get the Docling document for HybridChunker
        return_docling_doc = document_type in [
            DocumentType.SUBMITTAL,
            DocumentType.PRODUCT_DESCRIPTION,
        ]

        markdown_content, parse_metadata, docling_doc = await parse_document_with_fallback(
            pdf_path, try_without_ocr_first=not use_ocr, return_docling_doc=return_docling_doc
        )

        # Get metadata from existing document or create new
        from app.db.mongodb import get_document as get_doc

        existing_doc = await get_doc(mongodb, document_id)
        metadata = (
            existing_doc.metadata
            if existing_doc
            else DocumentMetadata(
                document_type=document_type,
                filename=pdf_path.name,
                file_size=pdf_path.stat().st_size,
                mime_type="application/pdf",
            )
        )

        # Update metadata
        metadata.used_ocr = parse_metadata["used_ocr"]
        metadata.ocr_engine = parse_metadata.get("ocr_engine")
        metadata.parse_time = parse_metadata["parse_time"]
        metadata.processing_timestamp = datetime.utcnow()

        await update_document(
            mongodb,
            document_id,
            {"markdown_content": markdown_content, "metadata": metadata.model_dump()},
        )

        await update_processing_progress(mongodb, document_id, 25, "parsing")

        # Step 2 & 3: Process based on document type
        if document_type == DocumentType.SPECIFICATION:
            # CSI Specification: Use notebook-style sectionization (CSI-aware)
            logger.info(f"[{document_id}] Step 2: Sectionizing CSI specification (notebook-style)")
            await update_processing_progress(mongodb, document_id, 30, "sectionizing")

            # Use notebook-style sectionization for better CSI structure detection
            sections = sectionize_markdown(markdown_content, use_notebook_logic=True)

            if not sections:
                logger.warning(f"[{document_id}] No sections found in document")

            section_counts = count_sections(sections)
            logger.info(f"[{document_id}] Found sections: {section_counts}")

            await update_processing_progress(mongodb, document_id, 50, "sectionizing")

            # Step 3: Chunk sections with CSI hierarchy
            logger.info(f"[{document_id}] Step 3: Chunking sections (CSI-aware)")
            await update_processing_progress(mongodb, document_id, 55, "chunking")

            chunks = chunk_sections(
                sections, max_tokens=max_chunk_tokens, overlap_tokens=chunk_overlap_tokens
            )

            chunk_stats = get_chunk_statistics(chunks)
            logger.info(f"[{document_id}] Created {chunk_stats['total_chunks']} chunks")

            await update_processing_progress(mongodb, document_id, 70, "chunking")

            # Step 4: Store sections in MongoDB
            logger.info(f"[{document_id}] Step 4: Storing sections")
            flat_sections = flatten_sections(sections)

            document_sections = []
            for idx, section in enumerate(flat_sections):
                # Use section_id from sectionizer if available, otherwise generate one
                section_id = (
                    section.section_id if section.section_id else f"{document_id}_section_{idx}"
                )

                doc_section = DocumentSection(
                    section_id=section_id,
                    document_id=document_id,
                    title=section.title,
                    level=section.level,
                    section_number=section.section_number,
                    content=section.content,
                    order_index=idx,
                    header_path=section.header_path,
                    page_start=section.page_start,
                    page_end=section.page_end,
                )
                document_sections.append(doc_section)

            await store_document_sections(mongodb, document_sections)

        else:
            # Submittal/Product Description/Drawing: Use HybridChunker or simple chunking
            logger.info(
                f"[{document_id}] Step 2: Skipping CSI sectionization (document type: {document_type.value})"
            )
            await update_processing_progress(mongodb, document_id, 30, "chunking")

            # Step 3: Chunking based on document type
            if docling_doc and document_type in [
                DocumentType.SUBMITTAL,
                DocumentType.PRODUCT_DESCRIPTION,
            ]:
                # Use HybridChunker for submittals/product descriptions (preserves tables)
                logger.info(
                    f"[{document_id}] Step 3: Hybrid chunking with table preservation (Docling HybridChunker)"
                )
                await update_processing_progress(mongodb, document_id, 40, "chunking")

                chunks = hybrid_chunk_document(
                    docling_doc, max_tokens=max_chunk_tokens, merge_peers=True
                )

                chunk_stats = get_chunk_statistics(chunks)
                logger.info(
                    f"[{document_id}] Created {chunk_stats['total_chunks']} hybrid chunks with table preservation"
                )
            else:
                # Use simple chunking for drawings or if Docling doc not available
                logger.info(f"[{document_id}] Step 3: Simple chunking (paragraph-based)")
                await update_processing_progress(mongodb, document_id, 40, "chunking")

                chunks = simple_chunk_markdown(
                    markdown_content,
                    max_tokens=max_chunk_tokens,
                    overlap_tokens=chunk_overlap_tokens,
                )

                chunk_stats = get_chunk_statistics(chunks)
                logger.info(f"[{document_id}] Created {chunk_stats['total_chunks']} simple chunks")

            await update_processing_progress(mongodb, document_id, 70, "chunking")

            # No sections to store for non-CSI documents
            section_counts = {}
            document_sections = []

        # Step 5: Store chunks in MongoDB
        logger.info(f"[{document_id}] Step 5: Storing chunks")
        await update_processing_progress(mongodb, document_id, 75, "chunking")

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
                total_chunks=chunk.total_chunks,
            )
            document_chunks.append(doc_chunk)

        await store_document_chunks(mongodb, document_chunks)
        await update_processing_progress(mongodb, document_id, 80, "indexing")

        # Step 6: Index chunks in Qdrant (ONLY for submittals/product descriptions, NOT specifications)
        # Per notebook logic: CSI specs are used for fact extraction only, not vector search
        # Only submittals/product descriptions are indexed for retrieval
        if document_type != DocumentType.SPECIFICATION:
            logger.info(
                f"[{document_id}] Step 6: Indexing in Qdrant (document type: {document_type.value})"
            )
            await index_chunks_in_qdrant(qdrant, document_chunks, settings.qdrant_collection_name)
            await update_processing_progress(mongodb, document_id, 95, "indexing")
        else:
            logger.info(
                f"[{document_id}] Step 6: Skipping Qdrant indexing (CSI specifications are not vector-indexed)"
            )
            await update_processing_progress(mongodb, document_id, 95, "indexing")

        # Update processing stats
        processing_stats = ProcessingStats(
            total_sections=len(document_sections),
            sections_by_level=section_counts,
            total_chunks=chunk_stats["total_chunks"],
            total_tokens=chunk_stats["total_tokens"],
            avg_chunk_tokens=chunk_stats["avg_tokens"],
        )

        # Set progress to 100% and mark as completed
        await update_processing_progress(mongodb, document_id, 100, "completed")

        await update_document(
            mongodb,
            document_id,
            {
                "status": DocumentStatus.COMPLETED.value,
                "processing_stats": processing_stats.model_dump(),
            },
        )

        logger.info(f"[{document_id}] Document processing completed successfully")

        # Return updated document
        from app.db.mongodb import get_document as get_doc

        document = await get_doc(mongodb, document_id)

        return document

    except Exception as e:
        logger.error(f"[{document_id}] Document processing failed: {str(e)}")

        # Update status to failed
        await update_document_status(mongodb, document_id, DocumentStatus.FAILED, error=str(e))

        raise DocumentProcessingError(f"Document processing failed: {str(e)}")
