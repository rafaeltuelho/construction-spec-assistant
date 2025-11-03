# RAG and Agent Architecture Specification

## Purpose

This document specifies the implementation of the RAG (Retrieval-Augmented Generation) system and LangGraph-based comparison agents for comparing specification facts against submittal documents.

## Overview

```
┌─────────────────┐
│  Spec Fact      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Query Builder  │
│  (Dense+Sparse) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Ensemble       │
│  Retriever      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LangGraph      │
│  Comparison     │
│  Agent          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Verdict +      │
│  Evidence       │
└─────────────────┘
```

---

## 1. Query Builder

### Module: `backend/app/retrievers/query_builder.py`

### Notebook Reference
- **Lines**: 1246+
- **Key Concept**: Build dense and sparse queries from spec facts

### Implementation

```python
from typing import Dict, List
from pydantic import BaseModel

class QueryTerms(BaseModel):
    """Query representations for hybrid search."""
    dense: str  # Natural language query for dense retrieval
    sparse: List[str]  # Keywords for BM25 sparse retrieval

def build_query_terms_from_fact(spec_fact: dict) -> QueryTerms:
    """
    Build query terms from a specification fact.
    
    Args:
        spec_fact: Fact dict with entity, attribute, value, operator
    
    Returns:
        QueryTerms with dense and sparse representations
    
    Example:
        Input: {
            "entity": "Elevator",
            "attribute": "capacity",
            "value": "2500 lbs",
            "operator": ">="
        }
        
        Output: QueryTerms(
            dense="What is the elevator capacity? Must be at least 2500 lbs.",
            sparse=["elevator", "capacity", "2500", "lbs", "pounds"]
        )
    """
    entity = spec_fact.get("entity", "")
    attribute = spec_fact.get("attribute", "")
    value = spec_fact.get("value", "")
    operator = spec_fact.get("operator", "=")
    
    # Build dense query (natural language)
    operator_text = {
        "=": "must be",
        ">=": "must be at least",
        "<=": "must not exceed",
        ">": "must be greater than",
        "<": "must be less than"
    }.get(operator, "is")
    
    dense = f"What is the {entity} {attribute}? It {operator_text} {value}."
    
    # Build sparse query (keywords)
    sparse = [
        entity.lower(),
        attribute.lower(),
        value.lower()
    ]
    
    # Add synonyms/variations
    if "capacity" in attribute.lower():
        sparse.extend(["load", "weight", "rating"])
    if "speed" in attribute.lower():
        sparse.extend(["velocity", "fpm", "feet per minute"])
    
    return QueryTerms(dense=dense, sparse=sparse)

def bm25_query_from_sparse(sparse_terms: List[str]) -> str:
    """
    Convert sparse terms to BM25 query string.
    
    Args:
        sparse_terms: List of keywords
    
    Returns:
        BM25 query string
    """
    return " ".join(sparse_terms)
```

---

## 2. Retrievers

### Base Retriever

#### Module: `backend/app/retrievers/base.py`

```python
from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document

class BaseRetriever(ABC):
    """Base class for all retrievers."""
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None
    ) -> List[Document]:
        """
        Retrieve relevant documents.
        
        Args:
            query: Query string
            top_k: Number of documents to retrieve
            filters: Optional filters (e.g., document_id)
        
        Returns:
            List of Document objects with relevance scores
        """
        pass
```

---

### Dense Retriever

#### Module: `backend/app/retrievers/dense.py`

### Notebook Reference
- **Lines**: 1246+
- **Key Concept**: Vector similarity search using embeddings

```python
from typing import List
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
import logging

logger = logging.getLogger(__name__)

class DenseRetriever(BaseRetriever):
    """Dense retriever using vector embeddings."""
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str = "construction_docs",
        embedding_model: str = "BAAI/bge-small-en-v1.5"
    ):
        self.client = qdrant_client
        self.collection_name = collection_name
        self.embedding_model = TextEmbedding(model_name=embedding_model)
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None
    ) -> List[Document]:
        """
        Retrieve documents using dense vector search.
        
        Args:
            query: Natural language query
            top_k: Number of documents to retrieve
            filters: Optional filters (e.g., {"document_id": "doc_123"})
        
        Returns:
            List of Document objects with relevance scores
        """
        try:
            # Generate query embedding
            query_embedding = list(self.embedding_model.embed([query]))[0]
            
            # Build Qdrant filter
            qdrant_filter = None
            if filters:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                conditions = [
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                    for key, value in filters.items()
                ]
                qdrant_filter = Filter(must=conditions)
            
            # Search Qdrant
            results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=qdrant_filter
            )
            
            # Convert to LangChain Documents
            documents = []
            for result in results:
                doc = Document(
                    page_content=result.payload["content"],
                    metadata={
                        "chunk_id": result.id,
                        "document_id": result.payload["document_id"],
                        "section_path": result.payload["section_path"],
                        "relevance_score": result.score,
                        "retrieval_method": "dense"
                    }
                )
                documents.append(doc)
            
            logger.info(f"Dense retrieval: {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}")
            return []
```

---

### Sparse Retriever (BM25)

#### Module: `backend/app/retrievers/sparse.py`

### Notebook Reference
- **Lines**: 1246+
- **Key Concept**: Keyword-based BM25 search

```python
from typing import List
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import logging

logger = logging.getLogger(__name__)

class SparseRetriever(BaseRetriever):
    """Sparse retriever using BM25 algorithm."""
    
    def __init__(self, corpus: List[Document]):
        """
        Initialize BM25 retriever.
        
        Args:
            corpus: List of all documents to search
        """
        self.corpus = corpus
        
        # Tokenize corpus
        tokenized_corpus = [doc.page_content.lower().split() for doc in corpus]
        
        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_corpus)
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None
    ) -> List[Document]:
        """
        Retrieve documents using BM25 keyword search.
        
        Args:
            query: Keyword query
            top_k: Number of documents to retrieve
            filters: Optional filters (e.g., {"document_id": "doc_123"})
        
        Returns:
            List of Document objects with BM25 scores
        """
        try:
            # Tokenize query
            tokenized_query = query.lower().split()
            
            # Get BM25 scores
            scores = self.bm25.get_scores(tokenized_query)
            
            # Get top-k indices
            top_indices = sorted(
                range(len(scores)),
                key=lambda i: scores[i],
                reverse=True
            )[:top_k]
            
            # Filter by document_id if provided
            if filters and "document_id" in filters:
                target_doc_id = filters["document_id"]
                top_indices = [
                    i for i in top_indices
                    if self.corpus[i].metadata.get("document_id") == target_doc_id
                ][:top_k]
            
            # Build result documents
            documents = []
            for idx in top_indices:
                doc = self.corpus[idx]
                doc.metadata["relevance_score"] = float(scores[idx])
                doc.metadata["retrieval_method"] = "sparse"
                documents.append(doc)
            
            logger.info(f"Sparse retrieval: {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Sparse retrieval failed: {e}")
            return []
```

---

### Ensemble Retriever

#### Module: `backend/app/retrievers/ensemble.py`

### Notebook Reference
- **Lines**: 1246+
- **Key Concept**: Combine dense + sparse with weighted scoring

```python
from typing import List
from langchain_core.documents import Document
import logging

logger = logging.getLogger(__name__)

class EnsembleRetriever(BaseRetriever):
    """Ensemble retriever combining dense and sparse methods."""
    
    def __init__(
        self,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5
    ):
        """
        Initialize ensemble retriever.
        
        Args:
            dense_retriever: Dense vector retriever
            sparse_retriever: Sparse BM25 retriever
            dense_weight: Weight for dense scores (0-1)
            sparse_weight: Weight for sparse scores (0-1)
        """
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None
    ) -> List[Document]:
        """
        Retrieve documents using ensemble of dense and sparse methods.
        
        Args:
            query: Query string
            top_k: Number of documents to retrieve
            filters: Optional filters
        
        Returns:
            List of Document objects with combined scores
        """
        try:
            # Retrieve from both methods
            dense_docs = await self.dense_retriever.retrieve(query, top_k * 2, filters)
            sparse_docs = await self.sparse_retriever.retrieve(query, top_k * 2, filters)
            
            # Combine and score
            doc_scores = {}
            
            for doc in dense_docs:
                chunk_id = doc.metadata["chunk_id"]
                score = doc.metadata["relevance_score"] * self.dense_weight
                doc_scores[chunk_id] = {"doc": doc, "score": score}
            
            for doc in sparse_docs:
                chunk_id = doc.metadata["chunk_id"]
                score = doc.metadata["relevance_score"] * self.sparse_weight
                
                if chunk_id in doc_scores:
                    doc_scores[chunk_id]["score"] += score
                else:
                    doc_scores[chunk_id] = {"doc": doc, "score": score}
            
            # Sort by combined score
            sorted_docs = sorted(
                doc_scores.values(),
                key=lambda x: x["score"],
                reverse=True
            )[:top_k]
            
            # Update metadata with combined score
            result_docs = []
            for item in sorted_docs:
                doc = item["doc"]
                doc.metadata["relevance_score"] = item["score"]
                doc.metadata["retrieval_method"] = "ensemble"
                result_docs.append(doc)
            
            logger.info(f"Ensemble retrieval: {len(result_docs)} documents")
            return result_docs
            
        except Exception as e:
            logger.error(f"Ensemble retrieval failed: {e}")
            return []
```

---

## 3. LangGraph Comparison Agent

### Module: `backend/app/agents/comparison_graph.py`

### Notebook Reference
- **Lines**: 1246+
- **Key Concept**: State machine for comparison workflow

### State Definition

```python
from typing import TypedDict, List
from langchain_core.documents import Document

class ComparisonState(TypedDict):
    """State for comparison workflow."""
    spec_fact: dict  # Input specification fact
    query: str  # Generated query
    retrieved_docs: List[Document]  # Retrieved submittal chunks
    result: dict  # Final comparison result
```

### Graph Construction

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)

def create_comparison_graph(
    retriever: BaseRetriever,
    llm_client: ChatOpenAI
) -> StateGraph:
    """
    Create LangGraph state machine for comparison workflow.
    
    Workflow:
    1. retrieve_node: Retrieve relevant submittal chunks
    2. compare_node: Compare spec fact against retrieved chunks
    3. END: Return verdict and evidence
    
    Args:
        retriever: Retriever instance (ensemble recommended)
        llm_client: OpenAI LLM client
    
    Returns:
        Compiled StateGraph
    """
    # Define nodes
    async def retrieve_node(state: ComparisonState) -> ComparisonState:
        """Retrieve relevant submittal chunks."""
        logger.info(f"Retrieving documents for query: {state['query']}")
        
        docs = await retriever.retrieve(
            query=state["query"],
            top_k=5
        )
        
        state["retrieved_docs"] = docs
        return state
    
    async def compare_node(state: ComparisonState) -> ComparisonState:
        """Compare spec fact against retrieved chunks."""
        logger.info("Comparing spec fact against submittal")
        
        # Build comparison prompt
        spec_fact = state["spec_fact"]
        retrieved_docs = state["retrieved_docs"]
        
        context = "\n\n".join([
            f"[Chunk {i+1}]\n{doc.page_content}"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        prompt = f"""Compare the specification requirement against the submittal information.

**Specification Requirement**:
- Entity: {spec_fact['entity']}
- Attribute: {spec_fact['attribute']}
- Required Value: {spec_fact['operator']} {spec_fact['value']}

**Submittal Information**:
{context}

**Task**:
Determine if the submittal meets the specification requirement.

**Output Format** (JSON):
{{
  "verdict": "consistent" | "inconsistent" | "unclear",
  "confidence": 0.0-1.0,
  "submittal_evidence": "Quote from submittal",
  "reasoning": "Explanation of verdict"
}}
"""
        
        # Call LLM
        from langchain_core.messages import SystemMessage, HumanMessage
        import json
        
        messages = [
            SystemMessage(content="You are an expert at comparing construction specifications against submittals."),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_client.ainvoke(messages)
        result = json.loads(response.content)
        
        state["result"] = result
        return state
    
    # Build graph
    workflow = StateGraph(ComparisonState)
    
    # Add nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("compare", compare_node)
    
    # Add edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "compare")
    workflow.add_edge("compare", END)
    
    # Compile
    return workflow.compile()
```

---

## 4. Comparison Service

### Module: `backend/app/services/comparison.py`

The comparison service provides two main functions:

1. **Single Fact Comparison**: Compare one specification fact against a submittal
2. **Document-Level Comparison**: Compare all facts from a specification document against a submittal

---

### 4.1 Single Fact Comparison

```python
from typing import Dict
import logging

logger = logging.getLogger(__name__)

async def compare_spec_to_submittal(
    spec_fact: dict,
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: ChatOpenAI,
    retrieval_strategy: str = "ensemble",
    top_k: int = 5
) -> dict:
    """
    Compare a specification fact against a submittal document.

    Args:
        spec_fact: Specification fact dict with entity, attribute, value, operator
        submittal_document_id: Submittal document ID
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client
        retrieval_strategy: "dense", "sparse", or "ensemble" (default)
        top_k: Number of documents to retrieve

    Returns:
        Comparison result dict with verdict, confidence, evidence, reasoning
    """
    # Build query
    query_terms = build_query_terms_from_fact(spec_fact)

    # Create retriever based on strategy
    retriever = await _create_retriever(
        strategy=retrieval_strategy,
        submittal_document_id=submittal_document_id,
        db=db,
        qdrant_client=qdrant_client
    )

    # Create comparison graph
    filters = {"document_id": submittal_document_id}
    graph = create_comparison_graph(
        retriever=retriever,
        llm_client=llm_client,
        top_k=top_k,
        filters=filters
    )

    # Run comparison
    initial_state = ComparisonState(
        spec_fact=spec_fact,
        query=query_terms.dense,
        retrieved_docs=[],
        result={},
        error=""
    )

    final_state = await graph.ainvoke(initial_state)

    return final_state["result"]
```

---

### 4.2 Document-Level Comparison

This function compares **all extracted facts** from a specification document against a submittal document in a single operation.

```python
async def compare_document_to_submittal(
    spec_document_id: str,
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: ChatOpenAI,
    retrieval_strategy: str = "ensemble",
    top_k: int = 5,
    limit: int = 100,
    offset: int = 0,
    verdict_filter: str = None
) -> Dict[str, Any]:
    """
    Compare all facts from a specification document against a submittal document.

    Workflow:
    1. Verify both documents exist in MongoDB
    2. Retrieve all facts from specification document
    3. For each fact, perform single fact comparison
    4. Aggregate results with summary statistics
    5. Apply verdict filter if specified
    6. Apply pagination (limit/offset)
    7. Return aggregated results

    Args:
        spec_document_id: Specification document ID containing facts
        submittal_document_id: Submittal document ID to compare against
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client
        retrieval_strategy: "dense", "sparse", or "ensemble" (default)
        top_k: Number of documents to retrieve per fact
        limit: Maximum number of comparisons to return (default: 100)
        offset: Pagination offset (default: 0)
        verdict_filter: Optional filter by verdict ('consistent', 'inconsistent', 'unclear')

    Returns:
        Document comparison result dict:
        {
            "comparison_id": "comp_doc_888",
            "spec_document_id": "doc_spec_123",
            "submittal_document_id": "doc_submittal_456",
            "total_facts": 67,
            "status": "completed",
            "summary": {
                "consistent": 45,
                "inconsistent": 12,
                "unclear": 10
            },
            "comparisons": [
                {
                    "comparison_id": "comp_789",
                    "spec_fact": {...},
                    "verdict": "consistent",
                    "confidence": 0.92,
                    "submittal_evidence": "...",
                    "retrieved_chunks": [...],
                    "reasoning": "..."
                },
                ...
            ],
            "compared_at": "2025-10-22T18:40:00Z"
        }

    Raises:
        NotFoundError: If specification or submittal document not found
        ComparisonError: If comparison fails
    """
    # Retrieve all facts from specification document
    facts = await get_facts_by_document(db, spec_document_id, limit=1000, offset=0)

    # Compare each fact against submittal
    all_comparisons = []
    summary = {"consistent": 0, "inconsistent": 0, "unclear": 0}

    for fact in facts:
        spec_fact = {
            "entity": fact.entity,
            "attribute": fact.attribute,
            "value": fact.value,
            "operator": fact.operator if hasattr(fact, "operator") else "="
        }

        comparison_result = await compare_spec_to_submittal(
            spec_fact=spec_fact,
            submittal_document_id=submittal_document_id,
            db=db,
            qdrant_client=qdrant_client,
            llm_client=llm_client,
            retrieval_strategy=retrieval_strategy,
            top_k=top_k
        )

        verdict = comparison_result.get("verdict", "unclear")
        if verdict in summary:
            summary[verdict] += 1

        all_comparisons.append(comparison_result)

    # Apply verdict filter and pagination
    if verdict_filter:
        all_comparisons = [c for c in all_comparisons if c.get("verdict") == verdict_filter]

    paginated_comparisons = all_comparisons[offset:offset + limit]

    return {
        "comparison_id": str(uuid.uuid4()),
        "spec_document_id": spec_document_id,
        "submittal_document_id": submittal_document_id,
        "total_facts": len(facts),
        "status": "completed",
        "summary": summary,
        "comparisons": paginated_comparisons,
        "compared_at": datetime.utcnow()
    }
```

**Key Features**:
- **Batch Processing**: Compares all facts in one request
- **Summary Statistics**: Returns counts of consistent/inconsistent/unclear verdicts
- **Filtering**: Optional verdict filter to show only specific results
- **Pagination**: Supports limit/offset for large result sets
- **Error Handling**: Continues processing even if individual fact comparisons fail

**API Endpoint**: `POST /api/v1/comparison/compare-document`

See `specs/03-api-design.md` for full API specification.

---

## Next Steps

Refer to the following specification document:

1. **07-evaluation-exclusion.md**: What to exclude from production backend

