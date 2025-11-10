#!/usr/bin/env python3
"""
Test script to investigate what the LLM response looks like after tool calls.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import Settings
from langchain_tavily import TavilySearch
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage


async def test_tool_call_response():
    """Test what the LLM response looks like after tool calls."""
    
    print("=" * 80)
    print("Testing LLM Response After Tool Calls")
    print("=" * 80)
    
    # Load settings
    settings = Settings()
    
    # Initialize
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=settings.openai_api_key,
    )
    
    tool = TavilySearch(
        tavily_api_key=settings.tavily_api_key,
        max_results=3,
    )
    
    llm_with_tools = llm.bind_tools([tool])
    
    # Create messages
    messages = [
        SystemMessage(content="""You are a construction specification expert.

When you need external information, use the web search tool.

Provide your final answer in JSON format:
{
  "verdict": "consistent" | "inconsistent" | "unclear",
  "confidence": 0.0-1.0,
  "evidence": "quote or source",
  "reasoning": "explanation"
}"""),
        HumanMessage(content="""Compare this requirement:

Specification: Otis Gen2 elevator capacity must be >= 3500 lbs

Submittal: "Otis Gen2 elevator, model not specified"

The submittal doesn't provide capacity. Use web search to find typical capacities."""),
    ]
    
    print("\n1. Initial LLM call...")
    response = await llm_with_tools.ainvoke(messages)
    
    print(f"   - Has tool_calls: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")
    print(f"   - Content length: {len(response.content) if response.content else 0}")
    print(f"   - Content preview: {response.content[:100] if response.content else 'EMPTY'}")
    
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"\n2. LLM requested {len(response.tool_calls)} tool call(s)")
        
        # Add assistant message
        messages.append(response)
        
        # Execute tools
        for i, tool_call in enumerate(response.tool_calls, 1):
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "unknown")
            
            print(f"\n   Tool call #{i}:")
            print(f"   - Name: {tool_name}")
            print(f"   - Args: {tool_args}")
            
            if tool_name == "tavily_search":
                query = tool_args.get("query", "")
                print(f"   - Executing search: {query}")
                
                search_response = await tool.ainvoke(query)
                results = search_response.get("results", [])
                
                tool_result = {
                    "query": query,
                    "num_results": len(results),
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "content": r.get("content", "")[:200],
                        }
                        for r in results[:2]
                    ],
                }
                
                messages.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        tool_call_id=tool_id,
                    )
                )
                print(f"   - Found {len(results)} results")
        
        # Call LLM again
        print(f"\n3. Calling LLM again with tool results...")
        response = await llm_with_tools.ainvoke(messages)
        
        print(f"   - Has tool_calls: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")
        print(f"   - Content length: {len(response.content) if response.content else 0}")
        print(f"   - Content type: {type(response.content)}")
        print(f"   - Content is empty string: {response.content == ''}")
        print(f"   - Content preview: {response.content[:200] if response.content else 'EMPTY'}")
        
        # Try to parse as JSON
        print(f"\n4. Attempting to parse as JSON...")
        try:
            if not response.content or response.content.strip() == "":
                print("   ❌ Content is empty or whitespace only!")
                print(f"   Response object: {response}")
                print(f"   Response type: {type(response)}")
                print(f"   Response attributes: {dir(response)}")
                
                # Check if there are additional tool calls
                if hasattr(response, "tool_calls") and response.tool_calls:
                    print(f"   ⚠️  Response has MORE tool calls: {len(response.tool_calls)}")
                    for tc in response.tool_calls:
                        print(f"      - {tc.get('name')}: {tc.get('args')}")
            else:
                result = json.loads(response.content)
                print(f"   ✅ Successfully parsed JSON")
                print(f"   Verdict: {result.get('verdict')}")
                print(f"   Confidence: {result.get('confidence')}")
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parsing failed: {e}")
            print(f"   Content: '{response.content}'")
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
    else:
        print("\n   No tool calls made")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_tool_call_response())

