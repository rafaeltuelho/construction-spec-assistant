#!/usr/bin/env python3
"""
Test script for HybridChunker implementation.

This script tests the new HybridChunker functionality with a real submittal document.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.core.chunker import get_chunk_statistics, hybrid_chunk_document, simple_chunk_markdown
from app.core.docling_parser import parse_document_with_fallback


async def test_hybrid_chunker():
    """Test HybridChunker with a real submittal document."""
    print("=" * 80)
    print("HYBRID CHUNKER TEST")
    print("=" * 80)
    print()

    # Find a submittal document
    # data_dir = Path("data")
    # pdf_files = list(data_dir.glob("*.pdf"))

    # if not pdf_files:
    #     print("❌ No PDF files found in data/ directory")
    #     return

    # Use the first PDF as test document
    test_pdf = Path("data/TKE_endura_product_brochure.pdf") #pdf_files[0]
    print(f"Test document: {test_pdf.name}")
    print(f"File size: {test_pdf.stat().st_size / 1024:.1f} KB")
    print()

    # Parse with Docling (get both markdown and Docling document)
    print("Step 1: Parsing PDF with Docling...")
    markdown_content, parse_metadata, docling_doc = await parse_document_with_fallback(
        test_pdf, try_without_ocr_first=False, return_docling_doc=True
    )

    print(f"✅ Parsed successfully")
    print(f"   - Used OCR: {parse_metadata['used_ocr']}")
    print(f"   - Parse time: {parse_metadata['parse_time']:.2f}s")
    print(f"   - Markdown length: {len(markdown_content)} chars")
    print(f"   - Docling doc available: {docling_doc is not None}")
    print()

    if not docling_doc:
        print("❌ Docling document not available, cannot test HybridChunker")
        return

    # Test HybridChunker
    print("Step 2: Testing HybridChunker...")
    hybrid_chunks = hybrid_chunk_document(docling_doc, max_tokens=512, merge_peers=True)

    hybrid_stats = get_chunk_statistics(hybrid_chunks)
    print(f"✅ HybridChunker completed")
    print(f"   - Total chunks: {hybrid_stats['total_chunks']}")
    print(f"   - Total tokens: {hybrid_stats['total_tokens']}")
    print(f"   - Avg tokens/chunk: {hybrid_stats['avg_tokens']:.1f}")
    print(f"   - Min tokens: {hybrid_stats['min_tokens']}")
    print(f"   - Max tokens: {hybrid_stats['max_tokens']}")
    print()

    # Test simple chunker for comparison
    print("Step 3: Testing simple chunker (for comparison)...")
    simple_chunks = simple_chunk_markdown(markdown_content, max_tokens=512, overlap_tokens=50)

    simple_stats = get_chunk_statistics(simple_chunks)
    print(f"✅ Simple chunker completed")
    print(f"   - Total chunks: {simple_stats['total_chunks']}")
    print(f"   - Total tokens: {simple_stats['total_tokens']}")
    print(f"   - Avg tokens/chunk: {simple_stats['avg_tokens']:.1f}")
    print(f"   - Min tokens: {simple_stats['min_tokens']}")
    print(f"   - Max tokens: {simple_stats['max_tokens']}")
    print()

    # Comparison
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    print(f"Chunk count:")
    print(f"  - HybridChunker: {hybrid_stats['total_chunks']}")
    print(f"  - Simple chunker: {simple_stats['total_chunks']}")
    print(f"  - Difference: {abs(hybrid_stats['total_chunks'] - simple_stats['total_chunks'])}")
    print()

    print(f"Total tokens:")
    print(f"  - HybridChunker: {hybrid_stats['total_tokens']}")
    print(f"  - Simple chunker: {simple_stats['total_tokens']}")
    print(f"  - Difference: {abs(hybrid_stats['total_tokens'] - simple_stats['total_tokens'])}")
    print()

    print(f"Average tokens per chunk:")
    print(f"  - HybridChunker: {hybrid_stats['avg_tokens']:.1f}")
    print(f"  - Simple chunker: {simple_stats['avg_tokens']:.1f}")
    print()

    # Show sample chunks
    print("=" * 80)
    print("SAMPLE CHUNKS")
    print("=" * 80)
    print()

    print("HybridChunker - First 3 chunks:")
    print("-" * 80)
    for i, chunk in enumerate(hybrid_chunks[:3]):
        print(f"\nChunk {i + 1}:")
        print(f"  Section: {chunk.section_title}")
        print(f"  Tokens: {chunk.token_count}")
        print(f"  Content preview (first 200 chars):")
        print(f"  {chunk.content[:200]}...")
        print()

    print("\nSimple chunker - First 3 chunks:")
    print("-" * 80)
    for i, chunk in enumerate(simple_chunks[:3]):
        print(f"\nChunk {i + 1}:")
        print(f"  Section: {chunk.section_title}")
        print(f"  Tokens: {chunk.token_count}")
        print(f"  Content preview (first 200 chars):")
        print(f"  {chunk.content[:200]}...")
        print()

    # Check for tables in chunks
    print("=" * 80)
    print("TABLE DETECTION")
    print("=" * 80)
    print()

    hybrid_tables = sum(1 for chunk in hybrid_chunks if "|" in chunk.content and "---" in chunk.content)
    simple_tables = sum(1 for chunk in simple_chunks if "|" in chunk.content and "---" in chunk.content)

    print(f"Chunks with markdown tables:")
    print(f"  - HybridChunker: {hybrid_tables} / {len(hybrid_chunks)} ({hybrid_tables/len(hybrid_chunks)*100:.1f}%)")
    print(f"  - Simple chunker: {simple_tables} / {len(simple_chunks)} ({simple_tables/len(simple_chunks)*100:.1f}%)")
    print()

    if hybrid_tables > 0:
        print("✅ HybridChunker successfully preserved table structure!")
    else:
        print("⚠️  No tables detected in chunks (document may not contain tables)")

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_hybrid_chunker())

