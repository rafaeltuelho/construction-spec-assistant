# LangSmith Traceability Specification

## Purpose

This document specifies the implementation of LangSmith traceability for observing LLM calls and agent workflows in the Construction Specification Assistant. LangSmith provides comprehensive tracing, debugging, and monitoring capabilities for LangChain-based applications.

## Overview

The application currently uses LangChain and LLMs in two primary areas:

1. **Fact Extraction** - LLM-based extraction of structured facts from specification documents
2. **Comparison Agent** - LangGraph-based workflow for comparing specification facts against submittal documents

LangSmith integration will enable:
- Real-time tracing of LLM calls and agent workflows
- Performance monitoring and latency analysis
- Token usage tracking and cost estimation
- Debugging of prompts, responses, and intermediate states
- Error tracking and diagnostics
- Historical analysis and comparison of runs

---

## Current LLM/LangChain Usage

### 1. Fact Extraction Service

**Location**: `backend/app/services/fact_extraction.py`

**LLM Calls**:
- Function: `extract_facts_from_chunk()`
- Purpose: Extract structured facts from document chunks
- LLM Client: `ChatOpenAI` or `ChatTogether`
- Method: `llm_client.ainvoke(messages)`
- Prompt: System prompt + user prompt with chunk text
- Response: JSONL format with extracted facts

**Key Operations**:
```python
async def extract_facts_from_chunk(
    chunk: DocumentChunk,
    document_id: str,
    llm_client: Union[ChatOpenAI, ChatTogether],
    entity_hint: Optional[str] = None,
    temperature: float = 0.0,
) -> List[Fact]:
    # Prepare prompts
    messages = [
        SystemMessage(content=FACT_EXTRACTOR_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt)
    ]
    
    # Call LLM
    response = await llm_client.ainvoke(messages)
    
    # Parse response
    items = parse_jsonl(response.content)
```

**Batch Processing**:
- Function: `harvest_facts_for_doc()`
- Processes multiple chunks concurrently (batch_size=10)
- Progress tracking via callback
- Aggregates results from all chunks

---

### 2. Comparison Agent (LangGraph)

**Location**: `backend/app/agents/comparison_graph.py`

**Agent Workflow**:
1. **Retrieve Node** - Retrieve relevant submittal chunks using RAG
2. **Compare Node** - Compare spec fact against retrieved evidence using LLM
3. **END** - Return verdict and reasoning

**LLM Calls**:
- Function: `compare_node()`
- Purpose: Determine if submittal meets specification requirement
- LLM Client: `ChatOpenAI` or `ChatTogether`
- Method: `llm_client.ainvoke(messages)`
- Prompt: System prompt + comparison prompt with context
- Response: JSON with verdict, confidence, evidence, reasoning

**Key Operations**:
```python
async def compare_node(state: ComparisonState) -> ComparisonState:
    # Build context from retrieved documents
    context = "\n\n".join([
        f"[Chunk {i + 1}] (Score: {doc.metadata.get('relevance_score', 0):.3f})\n{doc.page_content}"
        for i, doc in enumerate(retrieved_docs)
    ])
    
    # Build comparison prompt
    prompt = COMPARISON_PROMPT_TEMPLATE.format(
        entity=entity_str,
        attribute=attribute_str,
        operator=operator,
        value=value_str,
        context=context,
    )
    
    # Call LLM
    messages = [
        SystemMessage(content=COMPARISON_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = await llm_client.ainvoke(messages)
```

**Graph Creation**:
```python
def create_comparison_graph(
    retriever: BaseRetriever,
    llm_client: Union[ChatOpenAI, ChatTogether],
    top_k: int = 5,
    filters: Dict[str, Any] = None,
) -> StateGraph:
    # Create state graph
    workflow = StateGraph(ComparisonState)
    
    # Add nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("compare", compare_node)
    
    # Add edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "compare")
    workflow.add_edge("compare", END)
    
    return workflow.compile()
```

---

## LangSmith Integration Requirements

### 1. Configuration

**Environment Variables** (already defined in `backend/app/config.py`):

```python
# LangSmith Settings
langsmith_api_key: Optional[str] = Field(
    default=None, description="LangSmith API key for tracing"
)
langsmith_project: Optional[str] = Field(
    default="construction-spec-assistant", description="LangSmith project name"
)
```

**Additional Configuration Needed**:

```python
# Add to backend/app/config.py
langsmith_enabled: bool = Field(
    default=False, description="Enable LangSmith tracing"
)
langsmith_endpoint: str = Field(
    default="https://api.smith.langchain.com", 
    description="LangSmith API endpoint"
)
langsmith_tracing_v2: bool = Field(
    default=True, 
    description="Enable LangSmith tracing v2"
)
```

**Environment Variables** (`.env` file):

```bash
# LangSmith Configuration
LANGSMITH_ENABLED=true
LANGSMITH_API_KEY=your-langsmith-api-key-here
LANGSMITH_PROJECT=construction-spec-assistant
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING_V2=true
```

---

### 2. Initialization

**Location**: `backend/app/dependencies.py`

**Add LangSmith Initialization Function**:

```python
import os
from app.config import settings

async def init_langsmith() -> None:
    """
    Initialize LangSmith tracing.
    
    Sets environment variables required by LangChain for automatic tracing.
    """
    if not settings.langsmith_enabled:
        logger.info("LangSmith tracing is disabled")
        return
    
    if not settings.langsmith_api_key:
        logger.warning("LangSmith API key not set. Tracing will be disabled.")
        return
    
    try:
        # Set environment variables for LangChain tracing
        os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langsmith_tracing_v2).lower()
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
        
        logger.info(f"LangSmith tracing enabled for project: {settings.langsmith_project}")
        logger.info(f"LangSmith endpoint: {settings.langsmith_endpoint}")
        
    except Exception as e:
        logger.warning(f"Failed to initialize LangSmith: {e}")
        logger.warning("Application will continue without LangSmith tracing.")
```

**Update Startup Dependencies**:

```python
# In backend/app/dependencies.py

async def startup_dependencies() -> None:
    """Initialize all application dependencies on startup."""
    await init_mongodb()
    await init_qdrant()
    await init_llm()
    await init_langsmith()  # Add this line
```

---

### 3. Custom Metadata and Tags

**Add Metadata to LLM Calls**:

LangSmith automatically traces LangChain LLM calls, but we can enhance traces with custom metadata and tags.

**For Fact Extraction** (`backend/app/services/fact_extraction.py`):

```python
from langchain_core.runnables import RunnableConfig

async def extract_facts_from_chunk(
    chunk: DocumentChunk,
    document_id: str,
    llm_client: Union[ChatOpenAI, ChatTogether],
    entity_hint: Optional[str] = None,
    temperature: float = 0.0,
) -> List[Fact]:
    # Prepare messages
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    # Add LangSmith metadata
    config = RunnableConfig(
        tags=["fact-extraction", f"doc:{document_id}", f"chunk:{chunk.chunk_id}"],
        metadata={
            "document_id": document_id,
            "chunk_id": chunk.chunk_id,
            "section_id": chunk.section_id,
            "section_title": chunk.section_title,
            "entity_hint": entity_hint,
            "temperature": temperature,
        }
    )
    
    # Call LLM with config
    response = await llm_client.ainvoke(messages, config=config)
```

**For Comparison Agent** (`backend/app/agents/comparison_graph.py`):

```python
from langchain_core.runnables import RunnableConfig

async def compare_node(state: ComparisonState) -> ComparisonState:
    # Build prompt
    messages = [
        SystemMessage(content=COMPARISON_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    # Add LangSmith metadata
    config = RunnableConfig(
        tags=[
            "comparison-agent",
            f"spec:{state['spec_fact'].get('fact_id', 'unknown')}",
            f"submittal:{state['submittal_document_id']}"
        ],
        metadata={
            "spec_fact_id": state["spec_fact"].get("fact_id"),
            "submittal_document_id": state["submittal_document_id"],
            "retrieval_strategy": state.get("retrieval_strategy", "unknown"),
            "num_retrieved_chunks": len(state.get("retrieved_docs", [])),
            "entity": state["spec_fact"].get("entity"),
            "attribute": state["spec_fact"].get("attribute"),
        }
    )
    
    # Call LLM with config
    response = await llm_client.ainvoke(messages, config=config)
```

---

## Implementation Steps

### Phase 1: Basic Integration

1. **Update Configuration** (`backend/app/config.py`)
   - Add `langsmith_enabled` field
   - Add `langsmith_endpoint` field
   - Add `langsmith_tracing_v2` field

2. **Add Initialization** (`backend/app/dependencies.py`)
   - Create `init_langsmith()` function
   - Add to `startup_dependencies()`

3. **Update Environment Variables**
   - Add LangSmith variables to `.env.example`
   - Document in README

4. **Test Basic Tracing**
   - Enable LangSmith in development
   - Run fact extraction
   - Run comparison
   - Verify traces appear in LangSmith dashboard

### Phase 2: Enhanced Metadata

1. **Add Metadata to Fact Extraction**
   - Update `extract_facts_from_chunk()` to include RunnableConfig
   - Add document and chunk metadata
   - Add tags for filtering

2. **Add Metadata to Comparison Agent**
   - Update `compare_node()` to include RunnableConfig
   - Add spec fact and submittal metadata
   - Add tags for filtering

3. **Add Metadata to Batch Operations**
   - Update `harvest_facts_for_doc()` to propagate metadata
   - Update `compare_document_to_submittal()` to propagate metadata

### Phase 3: Custom Runs and Feedback

1. **Create Custom Run Names**
   - Use descriptive run names for easier identification
   - Include document IDs and operation types

2. **Add Feedback Mechanism**
   - Allow users to provide feedback on comparison results
   - Send feedback to LangSmith for analysis

3. **Add Performance Monitoring**
   - Track token usage per operation
   - Track latency per operation
   - Set up alerts for anomalies

---

## Benefits

### 1. Debugging and Development

- **Prompt Engineering**: View exact prompts sent to LLM and responses received
- **Error Diagnosis**: Identify failures in LLM calls or agent workflows
- **Performance Analysis**: Identify slow operations and bottlenecks
- **Response Quality**: Compare different prompts and models

### 2. Production Monitoring

- **Real-time Observability**: Monitor LLM calls in production
- **Cost Tracking**: Track token usage and estimate costs
- **Error Tracking**: Get alerts for failed LLM calls
- **Usage Analytics**: Understand usage patterns and trends

### 3. Optimization

- **A/B Testing**: Compare different prompts, models, or parameters
- **Quality Metrics**: Track accuracy and consistency of extractions/comparisons
- **User Feedback**: Collect and analyze user feedback on results
- **Model Selection**: Compare performance across different LLM providers

---

## Security Considerations

1. **API Key Management**
   - Store LangSmith API key in environment variables
   - Never commit API keys to version control
   - Use different projects for dev/staging/production

2. **Data Privacy**
   - LangSmith stores prompts and responses
   - Ensure compliance with data privacy requirements
   - Consider data retention policies
   - Review LangSmith's data handling practices

3. **Access Control**
   - Limit access to LangSmith dashboard
   - Use role-based access control
   - Audit access logs regularly

---

## Testing

### Manual Testing

1. **Enable LangSmith**:
   ```bash
   export LANGSMITH_ENABLED=true
   export LANGSMITH_API_KEY=your-key-here
   export LANGSMITH_PROJECT=construction-spec-assistant-dev
   ```

2. **Run Fact Extraction**:
   - Upload a document
   - Trigger fact extraction
   - Check LangSmith dashboard for traces

3. **Run Comparison**:
   - Run a comparison job
   - Check LangSmith dashboard for agent workflow traces

4. **Verify Metadata**:
   - Check that custom tags appear
   - Check that metadata is populated
   - Verify filtering works

### Automated Testing

1. **Unit Tests**:
   - Test `init_langsmith()` function
   - Test with and without API key
   - Test error handling

2. **Integration Tests**:
   - Test fact extraction with tracing enabled
   - Test comparison agent with tracing enabled
   - Verify traces are created (if possible)

---

## Documentation

### User Documentation

1. **Setup Guide**:
   - How to obtain LangSmith API key
   - How to configure environment variables
   - How to access LangSmith dashboard

2. **Usage Guide**:
   - How to view traces
   - How to filter by tags
   - How to analyze performance
   - How to provide feedback

### Developer Documentation

1. **Architecture**:
   - How LangSmith integration works
   - Where tracing is enabled
   - How to add custom metadata

2. **Best Practices**:
   - When to use tags vs metadata
   - How to name runs
   - How to structure metadata

---

## Future Enhancements

1. **Custom Evaluators**:
   - Create LangSmith evaluators for fact extraction quality
   - Create evaluators for comparison accuracy

2. **Datasets**:
   - Create test datasets in LangSmith
   - Run evaluations against datasets

3. **Experiments**:
   - Use LangSmith experiments for A/B testing
   - Compare different prompts and models

4. **Feedback Loop**:
   - Integrate user feedback from UI
   - Use feedback to improve prompts and models

---

## References

- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [LangChain Tracing](https://python.langchain.com/docs/langsmith/walkthrough)
- [LangGraph Tracing](https://langchain-ai.github.io/langgraph/how-tos/tracing/)
- [LangSmith Python SDK](https://github.com/langchain-ai/langsmith-sdk)

