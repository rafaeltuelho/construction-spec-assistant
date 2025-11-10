#!/usr/bin/env python3
"""
Test script to verify LLM tool calling integration with Tavily search.

This script tests:
1. TavilySearch tool binding to LLM
2. LLM's ability to decide when to use the tool
3. Tool call execution and response handling
4. Final verdict generation after tool use
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import Settings
from langchain_tavily import TavilySearch
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


async def test_llm_tool_calling():
    """Test LLM tool calling with Tavily search."""

    print("=" * 80)
    print("Testing LLM Tool Calling with Tavily Search")
    print("=" * 80)

    # Load settings
    settings = Settings()

    print(f"\n1. Configuration:")
    print(f"   - TAVILY_SEARCH_ENABLED: {settings.tavily_search_enabled}")
    print(
        f"   - TAVILY_API_KEY: {'***' + settings.tavily_api_key[-8:] if settings.tavily_api_key else 'NOT SET'}"
    )
    print(
        f"   - OPENAI_API_KEY: {'***' + settings.openai_api_key[-8:] if settings.openai_api_key else 'NOT SET'}"
    )

    if not settings.tavily_search_enabled or not settings.tavily_api_key:
        print("\n❌ Tavily search not enabled or API key not set")
        return False

    if not settings.openai_api_key:
        print("\n❌ OpenAI API key not set")
        return False

    # Initialize Tavily search tool
    print(f"\n2. Initializing Tavily search tool...")
    try:
        search_tool = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=3,
            search_depth="advanced",
        )
        print("   ✅ TavilySearch initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize TavilySearch: {e}")
        return False

    # Initialize LLM
    print(f"\n3. Initializing OpenAI LLM...")
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.openai_api_key,
        )
        print("   ✅ OpenAI LLM initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize LLM: {e}")
        return False

    # Bind tool to LLM
    print(f"\n4. Binding Tavily tool to LLM...")
    try:
        llm_with_tools = llm.bind_tools([search_tool])
        print("   ✅ Tool binding successful")
    except Exception as e:
        print(f"   ❌ Failed to bind tool: {e}")
        return False

    # Test 1: Simple query that should NOT trigger tool use
    print(f"\n5. Test 1: Query with sufficient information (should NOT use tool)")
    print("   Query: 'Is 42 inches >= 40 inches?'")

    messages = [
        SystemMessage(content="You are a helpful assistant. Answer the question directly."),
        HumanMessage(
            content="Is 42 inches >= 40 inches? Answer with yes or no and explain briefly."
        ),
    ]

    try:
        response = await llm_with_tools.ainvoke(messages)

        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"   ⚠️  LLM made tool calls (unexpected): {len(response.tool_calls)} call(s)")
        else:
            print(f"   ✅ LLM answered directly without tool use")
            print(f"   Response: {response.content[:100]}...")
    except Exception as e:
        print(f"   ❌ Test 1 failed: {e}")
        return False

    # Test 2: Query that SHOULD trigger tool use
    print(f"\n6. Test 2: Query needing external information (should USE tool)")
    print("   Query: 'What is the standard capacity for Otis Gen2 elevators?'")

    messages = [
        SystemMessage(
            content="""You are a construction specification expert.
        
When you need external information, use the web search tool to find it.
Always cite your sources when using web search results."""
        ),
        HumanMessage(
            content="What is the standard capacity for Otis Gen2 elevators? Use web search if needed."
        ),
    ]

    try:
        response = await llm_with_tools.ainvoke(messages)

        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"   ✅ LLM made tool calls: {len(response.tool_calls)} call(s)")

            for i, tool_call in enumerate(response.tool_calls, 1):
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                print(f"   Tool call #{i}:")
                print(f"     - Name: {tool_name}")
                print(f"     - Query: {tool_args.get('query', 'N/A')}")

                # Execute the tool
                if tool_name == "tavily_search":
                    query = tool_args.get("query", "")
                    print(f"     - Executing search...")

                    search_response = await search_tool.ainvoke(query)
                    search_results = search_response.get("results", [])

                    print(f"     - Results: {len(search_results)} found")
                    if search_results:
                        first_result = search_results[0]
                        print(f"     - Top result: {first_result.get('title', 'N/A')}")
                        print(f"     - URL: {first_result.get('url', 'N/A')}")
                        print(f"     - Score: {first_result.get('score', 0.0):.2f}")
        else:
            print(f"   ⚠️  LLM did NOT make tool calls (unexpected)")
            print(f"   Response: {response.content[:200]}...")
    except Exception as e:
        print(f"   ❌ Test 2 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 3: Full conversation with tool use
    print(f"\n7. Test 3: Full conversation with tool execution")
    print("   Simulating comparison workflow...")

    messages = [
        SystemMessage(
            content="""You are an expert at comparing construction specifications.

When submittal information is insufficient, use the web search tool to find additional details.

Provide your verdict in JSON format:
{
  "verdict": "consistent" | "inconsistent" | "unclear",
  "confidence": 0.0-1.0,
  "evidence": "quote or source",
  "reasoning": "explanation"
}"""
        ),
        HumanMessage(
            content="""Compare this requirement:
        
Specification: Otis Gen2 elevator capacity must be >= 3500 lbs

Submittal: "Otis Gen2 elevator, model not specified"

The submittal doesn't provide capacity information. Use web search to find typical Otis Gen2 capacities."""
        ),
    ]

    try:
        # Initial call
        response = await llm_with_tools.ainvoke(messages)
        iteration = 0
        max_iterations = 3

        while (
            hasattr(response, "tool_calls") and response.tool_calls and iteration < max_iterations
        ):
            iteration += 1
            print(
                f"   Iteration {iteration}: LLM requested {len(response.tool_calls)} tool call(s)"
            )

            # Add assistant message
            messages.append(response)

            # Execute tools
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", "unknown")

                if tool_name == "tavily_search":
                    query = tool_args.get("query", "")
                    print(f"     - Searching: {query}")

                    search_response = await search_tool.ainvoke(query)
                    search_results = search_response.get("results", [])

                    # Format for LLM
                    tool_result = {
                        "query": query,
                        "num_results": len(search_results),
                        "results": [
                            {
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "content": r.get("content", "")[:300],
                                "score": r.get("score", 0.0),
                            }
                            for r in search_results[:3]
                        ],
                    }

                    from langchain_core.messages import ToolMessage
                    import json

                    messages.append(
                        ToolMessage(
                            content=json.dumps(tool_result),
                            tool_call_id=tool_id,
                        )
                    )
                    print(f"     - Found {len(search_results)} results")

            # Call LLM again
            response = await llm_with_tools.ainvoke(messages)

        print(f"   ✅ Conversation complete after {iteration} iteration(s)")
        print(f"   Final response: {response.content[:300]}...")

    except Exception as e:
        print(f"   ❌ Test 3 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print(f"\n{'=' * 80}")
    print("✅ All tests passed!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_llm_tool_calling())
    sys.exit(0 if success else 1)
