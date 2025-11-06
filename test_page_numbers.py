#!/usr/bin/env python3
"""
Test script for page number extraction from Docling provenance metadata.

This script tests:
1. Page number mapping extraction from Docling documents
2. Page number assignment to sections during sectionization
3. Page number propagation to chunks
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.core.chunker import chunk_sections, hybrid_chunk_document
from app.core.docling_parser import parse_document_with_fallback
from app.core.sectionizer import flatten_sections, sectionize_markdown


async def test_page_numbers():
    """Test page number extraction and propagation."""
    
    # Find a test PDF
    test_pdf = Path("data/Spec 14 24 00 - Hydraulic Elevators.pdf")
    
    if not test_pdf.exists():
        print(f"❌ Test PDF not found: {test_pdf}")
        print("Looking for other PDFs...")
        pdf_files = list(Path("data").glob("*.pdf"))
        if pdf_files:
            test_pdf = pdf_files[0]
            print(f"✅ Using: {test_pdf}")
        else:
            print("❌ No PDF files found in data/ directory")
            return
    
    print(f"\n{'='*80}")
    print(f"Testing Page Number Extraction")
    print(f"{'='*80}\n")
    print(f"📄 Document: {test_pdf.name}")
    
    # Parse document with page mapping
    print("\n1️⃣ Parsing document with Docling (extracting page mapping)...")
    markdown, metadata, docling_doc, page_mapping = await parse_document_with_fallback(
        test_pdf,
        try_without_ocr_first=True,
        return_docling_doc=True,
        extract_page_mapping=True,
    )
    
    print(f"   ✅ Parsed {len(markdown)} characters of markdown")
    print(f"   ✅ Page mapping: {len(page_mapping) if page_mapping else 0} character positions")
    
    if page_mapping:
        # Show sample of page mapping
        sample_positions = sorted(page_mapping.keys())[:5]
        print(f"   📊 Sample page mapping:")
        for pos in sample_positions:
            pages = page_mapping[pos]
            print(f"      - Char {pos}: Page(s) {pages}")
    
    # Test sectionization with page mapping
    print("\n2️⃣ Sectionizing with page number mapping...")
    sections = sectionize_markdown(
        markdown,
        use_notebook_logic=True,
        page_mapping=page_mapping,
    )
    
    print(f"   ✅ Created {len(sections)} top-level sections")
    
    # Count sections with page numbers
    flat_sections = flatten_sections(sections)
    sections_with_pages = [s for s in flat_sections if s.page_start is not None]
    
    print(f"   ✅ Sections with page numbers: {len(sections_with_pages)}/{len(flat_sections)}")
    
    # Show sample sections with page numbers
    print(f"\n   📊 Sample sections with page numbers:")
    for section in sections_with_pages[:5]:
        page_info = f"Page {section.page_start}"
        if section.page_end and section.page_end != section.page_start:
            page_info += f"-{section.page_end}"
        print(f"      - {section.title[:50]:50s} | {page_info}")
    
    # Test chunking with page numbers
    print("\n3️⃣ Chunking sections (page numbers should propagate)...")
    chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=50)
    
    print(f"   ✅ Created {len(chunks)} chunks")
    
    # Count chunks with page numbers
    chunks_with_pages = [c for c in chunks if c.page_start is not None]
    
    print(f"   ✅ Chunks with page numbers: {len(chunks_with_pages)}/{len(chunks)}")
    
    # Show sample chunks with page numbers
    print(f"\n   📊 Sample chunks with page numbers:")
    for chunk in chunks_with_pages[:5]:
        page_info = f"Page {chunk.page_start}"
        if chunk.page_end and chunk.page_end != chunk.page_start:
            page_info += f"-{chunk.page_end}"
        content_preview = chunk.content[:50].replace('\n', ' ')
        print(f"      - {content_preview:50s} | {page_info}")
    
    # Test HybridChunker with page numbers (if docling_doc available)
    if docling_doc:
        print("\n4️⃣ Testing HybridChunker with page number extraction...")
        hybrid_chunks = hybrid_chunk_document(docling_doc, max_tokens=512)
        
        print(f"   ✅ Created {len(hybrid_chunks)} hybrid chunks")
        
        # Count hybrid chunks with page numbers
        hybrid_chunks_with_pages = [c for c in hybrid_chunks if c.page_start is not None]
        
        print(f"   ✅ Hybrid chunks with page numbers: {len(hybrid_chunks_with_pages)}/{len(hybrid_chunks)}")
        
        # Show sample hybrid chunks with page numbers
        print(f"\n   📊 Sample hybrid chunks with page numbers:")
        for chunk in hybrid_chunks_with_pages[:5]:
            page_info = f"Page {chunk.page_start}"
            if chunk.page_end and chunk.page_end != chunk.page_start:
                page_info += f"-{chunk.page_end}"
            content_preview = chunk.content[:50].replace('\n', ' ')
            print(f"      - {content_preview:50s} | {page_info}")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")
    
    print(f"✅ Page mapping extracted: {len(page_mapping) if page_mapping else 0} positions")
    print(f"✅ Sections with page numbers: {len(sections_with_pages)}/{len(flat_sections)} ({len(sections_with_pages)/len(flat_sections)*100:.1f}%)")
    print(f"✅ Chunks with page numbers: {len(chunks_with_pages)}/{len(chunks)} ({len(chunks_with_pages)/len(chunks)*100:.1f}%)")
    
    if docling_doc:
        print(f"✅ Hybrid chunks with page numbers: {len(hybrid_chunks_with_pages)}/{len(hybrid_chunks)} ({len(hybrid_chunks_with_pages)/len(hybrid_chunks)*100:.1f}%)")
    
    print(f"\n{'='*80}")
    print(f"✅ Page number extraction test complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(test_page_numbers())

