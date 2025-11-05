"""
Test script to validate retrieval of documents containing "ASME A17.1".

This script tests the refactored retrieval mechanism to ensure it can properly
retrieve documents containing technical terms like "ASME A17.1".
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
import logging

from app.config import settings
from app.db.mongodb import get_document, list_documents, get_facts_by_document
from app.services.comparison import compare_spec_to_submittal
from app.retrievers import build_query_terms_from_fact, bm25_query_from_sparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_query_preprocessing():
    """Test query preprocessing for ASME A17.1."""
    print("\n" + "=" * 80)
    print("TEST 1: Query Preprocessing for ASME A17.1")
    print("=" * 80)
    
    # Create a test spec fact with ASME A17.1
    spec_fact = {
        "entity": {"type": "Elevator", "raw": "Elevator"},
        "attribute": {"raw": "safety code"},
        "value": {"raw": "ASME A17.1", "type": "text"},
        "op": "="
    }
    
    print("\nInput Spec Fact:")
    print(f"  Entity: {spec_fact['entity']['raw']}")
    print(f"  Attribute: {spec_fact['attribute']['raw']}")
    print(f"  Value: {spec_fact['value']['raw']}")
    print(f"  Operator: {spec_fact['op']}")
    
    # Build query terms
    query_terms = build_query_terms_from_fact(spec_fact)
    
    print("\nGenerated Query Terms:")
    print(f"  Dense Query: {query_terms.dense}")
    print(f"  Sparse Query:")
    print(f"    - Must: {query_terms.sparse.get('must', [])}")
    print(f"    - Should: {query_terms.sparse.get('should', [])}")
    print(f"    - Boost: {query_terms.sparse.get('boost', {})}")
    
    # Preprocess for BM25
    bm25_query = bm25_query_from_sparse(query_terms.sparse)
    
    print(f"\n  BM25 Query (preprocessed): {bm25_query}")
    print(f"  BM25 Query Length: {len(bm25_query.split())} tokens")
    
    # Check if ASME A17.1 is in the BM25 query (case-insensitive)
    bm25_lower = bm25_query.lower()
    if "asme" in bm25_lower and ("a17" in bm25_lower or "a171" in bm25_lower):
        print("\n✅ PASS: 'ASME A17.1' terms found in BM25 query")
    else:
        print("\n❌ FAIL: 'ASME A17.1' terms not found in BM25 query")
    
    return query_terms


async def test_retrieval_with_real_documents(query_terms):
    """Test retrieval with real documents from MongoDB."""
    print("\n" + "=" * 80)
    print("TEST 2: Retrieval with Real Documents")
    print("=" * 80)
    
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(settings.mongodb_url)
    db = mongo_client[settings.mongodb_database]

    # Connect to Qdrant
    qdrant_client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )
    
    try:
        # List available documents
        print("\nListing available documents...")
        documents, total = await list_documents(db, skip=0, limit=10)
        
        if not documents:
            print("❌ No documents found in database")
            print("\nPlease upload and process documents first:")
            print("  1. Upload a submittal document via API")
            print("  2. Process it to create chunks and embeddings")
            return
        
        print(f"\nFound {total} documents in database:")
        for i, doc in enumerate(documents, 1):
            print(f"  {i}. {doc.filename} (ID: {doc.document_id}, Status: {doc.status})")
        
        # Find a submittal document
        submittal_doc = None
        for doc in documents:
            if "submittal" in doc.filename.lower() or "brochure" in doc.filename.lower():
                submittal_doc = doc
                break
        
        if not submittal_doc:
            # Use the first document
            submittal_doc = documents[0]
            print(f"\nNo submittal document found, using first document: {submittal_doc.filename}")
        else:
            print(f"\nUsing submittal document: {submittal_doc.filename}")
        
        # Check if document is processed
        if submittal_doc.status != "completed":
            print(f"❌ Document status is '{submittal_doc.status}', not 'completed'")
            print("Please ensure the document is fully processed before testing retrieval")
            return
        
        print(f"\n✅ Document is ready for retrieval")
        print(f"   - Document ID: {submittal_doc.document_id}")
        print(f"   - Filename: {submittal_doc.filename}")
        print(f"   - Status: {submittal_doc.status}")
        
        return submittal_doc.document_id
        
    finally:
        mongo_client.close()


async def test_comparison_pipeline(submittal_document_id: str):
    """Test the full comparison pipeline with ASME A17.1."""
    print("\n" + "=" * 80)
    print("TEST 3: Full Comparison Pipeline")
    print("=" * 80)
    
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(settings.mongodb_url)
    db = mongo_client[settings.mongodb_database]

    # Connect to Qdrant
    qdrant_client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )

    # Create LLM client
    if settings.llm_provider == "together":
        llm_client = ChatTogether(
            api_key=settings.together_api_key,
            model=settings.together_model,
            temperature=settings.together_temperature,
            max_tokens=settings.together_max_tokens,
        )
    else:
        llm_client = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
        )
    
    try:
        # Create test spec fact with ASME A17.1
        spec_fact = {
            "entity": {"type": "Elevator", "raw": "Elevator"},
            "attribute": {"raw": "safety code"},
            "value": {"raw": "ASME A17.1", "type": "text"},
            "op": "="
        }
        
        print("\nRunning comparison with ensemble retrieval (ParentDocument + BM25)...")
        print(f"  Spec Fact: Elevator safety code = ASME A17.1")
        print(f"  Submittal Document ID: {submittal_document_id}")
        
        # Run comparison
        result = await compare_spec_to_submittal(
            spec_fact=spec_fact,
            submittal_document_id=submittal_document_id,
            db=db,
            qdrant_client=qdrant_client,
            llm_client=llm_client,
            retrieval_strategy="ensemble",
            top_k=5,
        )
        
        print("\n" + "-" * 80)
        print("COMPARISON RESULT")
        print("-" * 80)
        print(f"Verdict: {result.get('verdict', 'N/A')}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"\nReasoning:")
        print(f"  {result.get('reasoning', 'N/A')}")
        print(f"\nSubmittal Evidence:")
        print(f"  {result.get('submittal_evidence', 'N/A')[:300]}...")
        
        # Check retrieved chunks
        retrieved_chunks = result.get('retrieved_chunks', [])
        print(f"\nRetrieved Chunks: {len(retrieved_chunks)}")
        
        # Check if any chunk contains ASME A17.1
        asme_found = False
        for i, chunk in enumerate(retrieved_chunks, 1):
            content = chunk.get('content', '')
            relevance = chunk.get('relevance_score', 0)
            
            print(f"\n  Chunk {i}:")
            print(f"    - Relevance Score: {relevance:.4f}")
            print(f"    - Content Preview: {content[:150]}...")
            
            if "ASME" in content or "A17.1" in content:
                asme_found = True
                print(f"    - ✅ Contains 'ASME' or 'A17.1'")
        
        print("\n" + "=" * 80)
        if asme_found:
            print("✅ SUCCESS: Retrieved chunks contain 'ASME' or 'A17.1'")
        else:
            print("⚠️  WARNING: No chunks contain 'ASME' or 'A17.1'")
            print("   This may indicate the submittal doesn't mention ASME A17.1")
        print("=" * 80)
        
        return result
        
    finally:
        mongo_client.close()


async def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("ASME A17.1 RETRIEVAL TEST")
    print("Testing the refactored retrieval mechanism")
    print("=" * 80)
    
    try:
        # Test 1: Query preprocessing
        query_terms = await test_query_preprocessing()
        
        # Test 2: Check for real documents
        submittal_document_id = await test_retrieval_with_real_documents(query_terms)
        
        if not submittal_document_id:
            print("\n❌ Cannot proceed with comparison test - no suitable documents found")
            return 1
        
        # Test 3: Full comparison pipeline
        result = await test_comparison_pipeline(submittal_document_id)
        
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETE")
        print("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

