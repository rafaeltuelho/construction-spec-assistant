#!/usr/bin/env python3
"""
Test script to verify Tavily integration with langchain-tavily package.

This script tests:
1. Import of TavilySearch from langchain-tavily
2. Initialization with API key
3. Async invocation with ainvoke()
4. Response format validation
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import Settings


async def test_tavily_integration():
    """Test Tavily integration with langchain-tavily package."""
    
    print("=" * 80)
    print("Testing Tavily Integration")
    print("=" * 80)
    
    # Load settings
    settings = Settings()
    
    print(f"\n1. Configuration:")
    print(f"   - TAVILY_SEARCH_ENABLED: {settings.tavily_search_enabled}")
    print(f"   - TAVILY_API_KEY: {'***' + settings.tavily_api_key[-8:] if settings.tavily_api_key else 'NOT SET'}")
    print(f"   - TAVILY_MAX_RESULTS: {settings.tavily_max_results}")
    print(f"   - TAVILY_SEARCH_DEPTH: {settings.tavily_search_depth}")
    
    if not settings.tavily_search_enabled:
        print("\n❌ TAVILY_SEARCH_ENABLED is False")
        return False
    
    if not settings.tavily_api_key:
        print("\n❌ TAVILY_API_KEY is not set")
        return False
    
    # Test import
    print(f"\n2. Testing import...")
    try:
        from langchain_tavily import TavilySearch
        print("   ✅ Successfully imported TavilySearch from langchain-tavily")
    except ImportError as e:
        print(f"   ❌ Failed to import: {e}")
        return False
    
    # Test initialization
    print(f"\n3. Testing initialization...")
    try:
        search_tool = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=settings.tavily_max_results,
            search_depth=settings.tavily_search_depth,
        )
        print(f"   ✅ Successfully initialized TavilySearch")
        print(f"      - max_results: {settings.tavily_max_results}")
        print(f"      - search_depth: {settings.tavily_search_depth}")
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}")
        return False
    
    # Test ainvoke method
    print(f"\n4. Testing ainvoke() method...")
    try:
        test_query = "Python programming language"
        print(f"   Query: '{test_query}'")
        
        response = await search_tool.ainvoke(test_query)
        
        print(f"   ✅ Successfully called ainvoke()")
        print(f"      - Response type: {type(response)}")
        
        if isinstance(response, dict):
            print(f"      - Response keys: {list(response.keys())}")
            
            # Validate expected keys
            expected_keys = ['query', 'results', 'response_time']
            missing_keys = [k for k in expected_keys if k not in response]
            if missing_keys:
                print(f"   ⚠️  Missing expected keys: {missing_keys}")
            
            # Check results
            results = response.get('results', [])
            print(f"      - Number of results: {len(results)}")
            
            if results:
                first_result = results[0]
                print(f"      - First result keys: {list(first_result.keys())}")
                print(f"      - First result URL: {first_result.get('url', 'N/A')}")
                print(f"      - First result title: {first_result.get('title', 'N/A')[:60]}...")
                print(f"      - First result score: {first_result.get('score', 'N/A')}")
        else:
            print(f"   ⚠️  Unexpected response type: {type(response)}")
            print(f"      Response: {response}")
            
    except Exception as e:
        print(f"   ❌ Failed to call ainvoke(): {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n{'=' * 80}")
    print("✅ All tests passed!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_tavily_integration())
    sys.exit(0 if success else 1)

