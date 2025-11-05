"""
Simple test script to validate BM25 query preprocessing for "ASME A17.1".

This script tests only the query preprocessing logic without requiring database access.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.retrievers import build_query_terms_from_fact, bm25_query_from_sparse


def test_asme_query_preprocessing():
    """Test query preprocessing for ASME A17.1."""
    print("\n" + "=" * 80)
    print("ASME A17.1 QUERY PREPROCESSING TEST")
    print("=" * 80)
    
    # Test Case 1: ASME A17.1 safety code
    print("\n" + "-" * 80)
    print("Test Case 1: Elevator safety code = ASME A17.1")
    print("-" * 80)
    
    spec_fact_1 = {
        "entity": {"type": "Elevator", "raw": "Elevator"},
        "attribute": {"raw": "safety code"},
        "value": {"raw": "ASME A17.1", "type": "text"},
        "op": "="
    }
    
    query_terms_1 = build_query_terms_from_fact(spec_fact_1)
    bm25_query_1 = bm25_query_from_sparse(query_terms_1.sparse)
    
    print(f"\nDense Query: {query_terms_1.dense}")
    print(f"\nSparse Query:")
    print(f"  Must: {query_terms_1.sparse.get('must', [])}")
    print(f"  Should: {query_terms_1.sparse.get('should', [])}")
    print(f"  Boost: {query_terms_1.sparse.get('boost', {})}")
    print(f"\nBM25 Query: {bm25_query_1}")
    
    # Check if ASME terms are present
    bm25_lower = bm25_query_1.lower()
    has_asme = "asme" in bm25_lower
    has_a17 = "a17" in bm25_lower or "a171" in bm25_lower
    
    if has_asme and has_a17:
        print("\n✅ PASS: ASME A17.1 terms found in BM25 query")
        test1_pass = True
    else:
        print("\n❌ FAIL: ASME A17.1 terms not found in BM25 query")
        test1_pass = False
    
    # Test Case 2: CSA B44 safety code
    print("\n" + "-" * 80)
    print("Test Case 2: Elevator safety code = CSA B44")
    print("-" * 80)
    
    spec_fact_2 = {
        "entity": {"type": "Elevator", "raw": "Elevator"},
        "attribute": {"raw": "safety code"},
        "value": {"raw": "CSA B44", "type": "text"},
        "op": "="
    }
    
    query_terms_2 = build_query_terms_from_fact(spec_fact_2)
    bm25_query_2 = bm25_query_from_sparse(query_terms_2.sparse)
    
    print(f"\nDense Query: {query_terms_2.dense}")
    print(f"\nSparse Query:")
    print(f"  Must: {query_terms_2.sparse.get('must', [])}")
    print(f"  Should: {query_terms_2.sparse.get('should', [])}")
    print(f"  Boost: {query_terms_2.sparse.get('boost', {})}")
    print(f"\nBM25 Query: {bm25_query_2}")
    
    # Check if CSA B44 terms are present
    bm25_lower = bm25_query_2.lower()
    has_csa = "csa" in bm25_lower
    has_b44 = "b44" in bm25_lower
    
    if has_csa and has_b44:
        print("\n✅ PASS: CSA B44 terms found in BM25 query")
        test2_pass = True
    else:
        print("\n❌ FAIL: CSA B44 terms not found in BM25 query")
        test2_pass = False
    
    # Test Case 3: Numeric value with units
    print("\n" + "-" * 80)
    print("Test Case 3: Elevator capacity >= 2500 lbs")
    print("-" * 80)
    
    spec_fact_3 = {
        "entity": {"type": "Elevator", "raw": "Elevator"},
        "attribute": {"raw": "capacity"},
        "value": {"raw": "2500 lbs", "type": "quantity", "normalized": 2500, "unit": "lbs"},
        "op": ">="
    }
    
    query_terms_3 = build_query_terms_from_fact(spec_fact_3)
    bm25_query_3 = bm25_query_from_sparse(query_terms_3.sparse)
    
    print(f"\nDense Query: {query_terms_3.dense}")
    print(f"\nSparse Query:")
    print(f"  Must: {query_terms_3.sparse.get('must', [])}")
    print(f"  Should: {query_terms_3.sparse.get('should', [])}")
    print(f"  Boost: {query_terms_3.sparse.get('boost', {})}")
    print(f"\nBM25 Query: {bm25_query_3}")
    
    # Check if capacity and numeric terms are present
    bm25_lower = bm25_query_3.lower()
    has_capacity = "capacity" in bm25_lower
    has_numeric = "2500" in bm25_query_3 or "lbs" in bm25_lower
    
    if has_capacity and has_numeric:
        print("\n✅ PASS: Capacity and numeric terms found in BM25 query")
        test3_pass = True
    else:
        print("\n❌ FAIL: Capacity or numeric terms not found in BM25 query")
        test3_pass = False
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (ASME A17.1): {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (CSA B44): {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (Numeric): {'✅ PASS' if test3_pass else '❌ FAIL'}")
    
    all_pass = test1_pass and test2_pass and test3_pass
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_pass else '❌ SOME TESTS FAILED'}")
    print("=" * 80)
    
    return 0 if all_pass else 1


def test_bm25_boost_logic():
    """Test that boost terms are repeated correctly."""
    print("\n" + "=" * 80)
    print("BM25 BOOST LOGIC TEST")
    print("=" * 80)
    
    # Create a sparse query with boost
    sparse_query = {
        "must": ["safety code"],
        "should": ["ASME", "A17.1"],
        "boost": {"safety code": 3.0, "ASME": 2.0}
    }
    
    bm25_query = bm25_query_from_sparse(sparse_query)
    
    print(f"\nInput Sparse Query:")
    print(f"  Must: {sparse_query['must']}")
    print(f"  Should: {sparse_query['should']}")
    print(f"  Boost: {sparse_query['boost']}")
    
    print(f"\nBM25 Query: {bm25_query}")
    
    # Count occurrences
    tokens = bm25_query.split()
    safety_code_count = sum(1 for t in tokens if t.lower() == "safety" or t.lower() == "code")
    asme_count = sum(1 for t in tokens if t.lower() == "asme")
    
    print(f"\nToken Counts:")
    print(f"  'safety'/'code': {safety_code_count}")
    print(f"  'ASME': {asme_count}")
    
    # Verify boost logic
    # "safety code" should appear 3 times (boost=3.0)
    # "ASME" should appear 2 times (boost=2.0)
    if safety_code_count >= 3 and asme_count >= 2:
        print("\n✅ PASS: Boost logic working correctly")
        return 0
    else:
        print("\n❌ FAIL: Boost logic not working as expected")
        return 1


def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("BM25 QUERY PREPROCESSING VALIDATION")
    print("Testing the refactored query preprocessing for technical terms")
    print("=" * 80)
    
    # Run tests
    result1 = test_asme_query_preprocessing()
    result2 = test_bm25_boost_logic()
    
    # Overall result
    if result1 == 0 and result2 == 0:
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nThe refactored retrieval mechanism correctly preprocesses queries")
        print("for BM25, including technical terms like 'ASME A17.1'.")
        return 0
    else:
        print("\n" + "=" * 80)
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())

