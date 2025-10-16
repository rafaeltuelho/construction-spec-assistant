# Retrieval System Specification

## Overview

This specification defines the hybrid retrieval system that combines semantic vector search with keyword-based BM25 search to efficiently find relevant content for document comparison tasks.

## Qdrant Vector Database Setup

### Installation and Configuration

```python
# requirements.txt
qdrant-client==1.7.0
sentence-transformers==2.2.2
numpy>=1.24.0
```

### Qdrant Client Configuration

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http import models
from typing import List, Dict, Any, Optional
import numpy as np

class QdrantConfig:
    """Configuration for Qdrant vector database"""
    
    def __init__(self):
        self.host = "localhost"
        self.port = 6333
        self.collection_name = "construction_passages"
        self.vector_size = 384  # all-MiniLM-L6-v2 embedding size
        self.distance_metric = Distance.COSINE
        self.on_disk_payload = True
        self.quantization_config = None

class QdrantManager:
    """Manage Qdrant vector database operations"""
    
    def __init__(self, config: QdrantConfig):
        self.config = config
        self.client = QdrantClient(host=config.host, port=config.port)
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.get_collection(self.config.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(
                    size=self.config.vector_size,
                    distance=self.config.distance_metric,
                    on_disk=self.config.on_disk_payload,
                ),
                quantization_config=self.config.quantization_config
            )
    
    async def upsert_passages(
        self, 
        passages: List[Dict[str, Any]], 
        embeddings: List[List[float]]
    ) -> bool:
        """
        Insert or update passages with embeddings
        
        Args:
            passages: List of passage dictionaries
            embeddings: List of embedding vectors
            
        Returns:
            Success status
        """
        try:
            points = []
            for passage, embedding in zip(passages, embeddings):
                point = PointStruct(
                    id=passage["id"],
                    vector=embedding,
                    payload={
                        "document_id": passage["document_id"],
                        "text": passage["text"],
                        "passage_type": passage["passage_type"],
                        "page_number": passage["page_number"],
                        "section_id": passage.get("section_id"),
                        "csi_division": passage.get("csi_division"),
                        "title": passage.get("title"),
                        "token_count": passage.get("token_count", 0)
                    }
                )
                points.append(point)
            
            self.client.upsert(
                collection_name=self.config.collection_name,
                points=points
            )
            
            return True
            
        except Exception as e:
            print(f"Error upserting passages: {e}")
            return False
    
    async def search_similar(
        self, 
        query_embedding: List[float], 
        limit: int = 10,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar passages using vector similarity
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filters: Optional metadata filters
            
        Returns:
            List of similar passages with scores
        """
        try:
            query_filter = None
            if filters:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                        for key, value in filters.items()
                    ]
                )
            
            search_result = self.client.search(
                collection_name=self.config.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter
            )
            
            results = []
            for hit in search_result:
                results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.payload["text"],
                    "document_id": hit.payload["document_id"],
                    "passage_type": hit.payload["passage_type"],
                    "page_number": hit.payload["page_number"],
                    "section_id": hit.payload.get("section_id"),
                    "csi_division": hit.payload.get("csi_division"),
                    "title": hit.payload.get("title")
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching similar passages: {e}")
            return []
    
    async def delete_document_passages(self, document_id: str) -> bool:
        """Delete all passages for a specific document"""
        try:
            self.client.delete(
                collection_name=self.config.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
            return True
        except Exception as e:
            print(f"Error deleting document passages: {e}")
            return False
```

## Embedding Generation

### Sentence Transformer Setup

```python
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import torch

class EmbeddingGenerator:
    """Generate embeddings for text passages"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
    
    async def generate_embeddings(
        self, 
        texts: List[str], 
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts
        
        Args:
            texts: List of text strings
            batch_size: Batch size for processing
            
        Returns:
            List of embedding vectors
        """
        try:
            # Process in batches to avoid memory issues
            embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_embeddings = self.model.encode(
                    batch_texts,
                    convert_to_tensor=False,
                    show_progress_bar=True
                )
                embeddings.extend(batch_embeddings.tolist())
            
            return embeddings
            
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return []
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a single query"""
        try:
            embedding = self.model.encode([query], convert_to_tensor=False)
            return embedding[0].tolist()
        except Exception as e:
            print(f"Error generating query embedding: {e}")
            return []
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model"""
        return self.model.get_sentence_embedding_dimension()
```

## BM25 Keyword Search

### BM25 Implementation

```python
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Set
import re
from collections import Counter

class BM25SearchEngine:
    """BM25-based keyword search engine"""
    
    def __init__(self):
        self.bm25 = None
        self.passages = []
        self.passage_metadata = []
        self.vocabulary = set()
    
    async def index_passages(self, passages: List[Dict[str, Any]]):
        """
        Index passages for BM25 search
        
        Args:
            passages: List of passage dictionaries
        """
        self.passages = passages
        
        # Tokenize passages
        tokenized_passages = []
        for passage in passages:
            tokens = self._tokenize_text(passage["text"])
            tokenized_passages.append(tokens)
            self.vocabulary.update(tokens)
            
            # Store metadata
            self.passage_metadata.append({
                "id": passage["id"],
                "document_id": passage["document_id"],
                "passage_type": passage["passage_type"],
                "page_number": passage["page_number"],
                "section_id": passage.get("section_id"),
                "csi_division": passage.get("csi_division"),
                "title": passage.get("title")
            })
        
        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_passages)
    
    def _tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # Convert to lowercase and split on whitespace
        tokens = re.findall(r'\b\w+\b', text.lower())
        
        # Remove stop words and short tokens
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with'
        }
        
        filtered_tokens = [
            token for token in tokens 
            if len(token) > 2 and token not in stop_words
        ]
        
        return filtered_tokens
    
    async def search(
        self, 
        query: str, 
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search passages using BM25
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional metadata filters
            
        Returns:
            List of matching passages with scores
        """
        if self.bm25 is None:
            return []
        
        try:
            # Tokenize query
            query_tokens = self._tokenize_text(query)
            
            if not query_tokens:
                return []
            
            # Get BM25 scores
            scores = self.bm25.get_scores(query_tokens)
            
            # Create results with scores
            results = []
            for i, score in enumerate(scores):
                if score > 0:  # Only include passages with positive scores
                    result = {
                        "id": self.passage_metadata[i]["id"],
                        "score": float(score),
                        "text": self.passages[i]["text"],
                        **self.passage_metadata[i]
                    }
                    results.append(result)
            
            # Apply filters if provided
            if filters:
                results = self._apply_filters(results, filters)
            
            # Sort by score and limit results
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
            
        except Exception as e:
            print(f"Error in BM25 search: {e}")
            return []
    
    def _apply_filters(
        self, 
        results: List[Dict[str, Any]], 
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply metadata filters to search results"""
        filtered_results = []
        
        for result in results:
            include = True
            
            for key, value in filters.items():
                if key in result and result[key] != value:
                    include = False
                    break
            
            if include:
                filtered_results.append(result)
        
        return filtered_results
    
    async def search_exact_terms(
        self, 
        terms: List[str], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for exact terms (useful for codes, product names, ASTM standards)
        
        Args:
            terms: List of exact terms to search for
            limit: Maximum number of results
            
        Returns:
            List of matching passages
        """
        results = []
        term_set = set(term.lower() for term in terms)
        
        for i, passage in enumerate(self.passages):
            passage_text_lower = passage["text"].lower()
            
            # Check if any term appears in the passage
            matches = []
            for term in term_set:
                if term in passage_text_lower:
                    matches.append(term)
            
            if matches:
                # Calculate score based on term frequency
                score = len(matches) / len(term_set)
                
                result = {
                    "id": self.passage_metadata[i]["id"],
                    "score": score,
                    "text": passage["text"],
                    "matched_terms": matches,
                    **self.passage_metadata[i]
                }
                results.append(result)
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    async def search_csi_divisions(
        self, 
        csi_codes: List[str], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for CSI division codes (e.g., "14 24 00", "07 21 00")
        
        Args:
            csi_codes: List of CSI division codes
            limit: Maximum number of results
            
        Returns:
            List of matching passages
        """
        results = []
        
        for i, passage in enumerate(self.passages):
            passage_text = passage["text"]
            
            # Check for CSI codes in passage
            matches = []
            for csi_code in csi_codes:
                # Look for various CSI code formats
                patterns = [
                    csi_code,  # "14 24 00"
                    csi_code.replace(" ", ""),  # "142400"
                    csi_code.replace(" ", "-"),  # "14-24-00"
                ]
                
                for pattern in patterns:
                    if pattern in passage_text:
                        matches.append(csi_code)
                        break
            
            if matches:
                result = {
                    "id": self.passage_metadata[i]["id"],
                    "score": 1.0,  # High score for exact CSI matches
                    "text": passage["text"],
                    "matched_csi_codes": matches,
                    **self.passage_metadata[i]
                }
                results.append(result)
        
        return results[:limit]
    
    async def search_manufacturer_products(
        self, 
        manufacturers: List[str], 
        product_codes: List[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for manufacturer names and product codes
        
        Args:
            manufacturers: List of manufacturer names
            product_codes: Optional list of product codes
            limit: Maximum number of results
            
        Returns:
            List of matching passages
        """
        results = []
        search_terms = set(manufacturer.lower() for manufacturer in manufacturers)
        
        if product_codes:
            search_terms.update(product_code.lower() for product_code in product_codes)
        
        for i, passage in enumerate(self.passages):
            passage_text_lower = passage["text"].lower()
            
            # Check for manufacturer/product matches
            matches = []
            for term in search_terms:
                if term in passage_text_lower:
                    matches.append(term)
            
            if matches:
                # Boost score for manufacturer matches
                score = len(matches) / len(search_terms)
                if any(match in [m.lower() for m in manufacturers] for match in matches):
                    score += 0.3  # Boost for manufacturer names
                
                result = {
                    "id": self.passage_metadata[i]["id"],
                    "score": min(score, 1.0),
                    "text": passage["text"],
                    "matched_terms": matches,
                    **self.passage_metadata[i]
                }
                results.append(result)
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
```

## Hybrid Retrieval System

### Combined Search Engine

```python
from typing import List, Dict, Any, Optional, Tuple
import asyncio

class HybridRetrievalEngine:
    """Combined vector and BM25 search engine"""
    
    def __init__(
        self, 
        qdrant_manager: QdrantManager,
        bm25_engine: BM25SearchEngine,
        embedding_generator: EmbeddingGenerator
    ):
        self.qdrant_manager = qdrant_manager
        self.bm25_engine = bm25_engine
        self.embedding_generator = embedding_generator
        
        # Search configuration
        self.vector_weight = 0.6
        self.bm25_weight = 0.4
        self.max_results = 20
        self.rerank_top_k = 10
    
    async def search(
        self, 
        query: str,
        document_types: Optional[List[str]] = None,
        csi_divisions: Optional[List[str]] = None,
        limit: int = 10,
        exact_terms: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and BM25
        
        Args:
            query: Search query
            document_types: Filter by document types (specification, submittal, drawing)
            csi_divisions: Filter by CSI division codes
            limit: Maximum number of results
            exact_terms: List of exact terms for precise matching
            
        Returns:
            List of relevant passages with combined scores
        """
        # Prepare filters
        filters = {}
        if document_types:
            filters["document_type"] = {"$in": document_types}
        if csi_divisions:
            filters["csi_division"] = {"$in": csi_divisions}
        
        # Perform parallel searches
        tasks = []
        
        # Vector search
        query_embedding = await self.embedding_generator.generate_query_embedding(query)
        vector_task = self.qdrant_manager.search_similar(
            query_embedding, 
            limit=self.max_results,
            filters=filters
        )
        tasks.append(vector_task)
        
        # BM25 search
        bm25_task = self.bm25_engine.search(
            query, 
            limit=self.max_results,
            filters=filters
        )
        tasks.append(bm25_task)
        
        # Exact term search (if provided)
        if exact_terms:
            exact_task = self.bm25_engine.search_exact_terms(exact_terms, self.max_results)
            tasks.append(exact_task)
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))  # Dummy task
        
        # Wait for all searches to complete
        vector_results, bm25_results, exact_results = await asyncio.gather(*tasks)
        
        # Combine and rerank results
        combined_results = await self._combine_results(
            vector_results, 
            bm25_results, 
            exact_results,
            query
        )
        
        return combined_results[:limit]
    
    async def _combine_results(
        self, 
        vector_results: List[Dict[str, Any]], 
        bm25_results: List[Dict[str, Any]], 
        exact_results: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Combine and rerank search results from different methods
        
        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            exact_results: Results from exact term search
            query: Original search query
            
        Returns:
            Combined and reranked results
        """
        # Create passage ID to result mapping
        passage_scores = {}
        
        # Add vector search results
        for result in vector_results:
            passage_id = result["id"]
            passage_scores[passage_id] = {
                "passage": result,
                "vector_score": result["score"],
                "bm25_score": 0.0,
                "exact_score": 0.0,
                "combined_score": 0.0
            }
        
        # Add BM25 search results
        for result in bm25_results:
            passage_id = result["id"]
            if passage_id in passage_scores:
                passage_scores[passage_id]["bm25_score"] = result["score"]
            else:
                passage_scores[passage_id] = {
                    "passage": result,
                    "vector_score": 0.0,
                    "bm25_score": result["score"],
                    "exact_score": 0.0,
                    "combined_score": 0.0
                }
        
        # Add exact term search results (boost score)
        for result in exact_results:
            passage_id = result["id"]
            if passage_id in passage_scores:
                passage_scores[passage_id]["exact_score"] = result["score"]
            else:
                passage_scores[passage_id] = {
                    "passage": result,
                    "vector_score": 0.0,
                    "bm25_score": 0.0,
                    "exact_score": result["score"],
                    "combined_score": 0.0
                }
        
        # Calculate combined scores
        for passage_id, scores in passage_scores.items():
            combined_score = (
                self.vector_weight * scores["vector_score"] +
                self.bm25_weight * scores["bm25_score"] +
                0.2 * scores["exact_score"]  # Boost for exact matches
            )
            scores["combined_score"] = combined_score
        
        # Sort by combined score
        sorted_results = sorted(
            passage_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        # Return top results with metadata
        final_results = []
        for result_data in sorted_results:
            passage = result_data["passage"].copy()
            passage["vector_score"] = result_data["vector_score"]
            passage["bm25_score"] = result_data["bm25_score"]
            passage["exact_score"] = result_data["exact_score"]
            passage["combined_score"] = result_data["combined_score"]
            final_results.append(passage)
        
        return final_results
    
    async def search_for_comparison(
        self, 
        specification_query: str,
        submittal_query: str,
        csi_divisions: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Search for passages to compare between specification and submittal
        
        Args:
            specification_query: Query for specification passages
            submittal_query: Query for submittal passages
            csi_divisions: Filter by CSI division codes
            
        Returns:
            Tuple of (specification_results, submittal_results)
        """
        # Search specification documents
        spec_filters = {"document_type": "specification"}
        if csi_divisions:
            spec_filters["csi_division"] = {"$in": csi_divisions}
        
        spec_results = await self.search(
            specification_query,
            filters=spec_filters,
            limit=8
        )
        
        # Search submittal documents
        submittal_filters = {"document_type": "submittal"}
        if csi_divisions:
            submittal_filters["csi_division"] = {"$in": csi_divisions}
        
        submittal_results = await self.search(
            submittal_query,
            filters=submittal_filters,
            limit=8
        )
        
        return spec_results, submittal_results
    
    async def search_elevator_specifications(
        self, 
        capacity_lbs: Optional[int] = None,
        speed_fpm: Optional[int] = None,
        csi_code: str = "14 24 00"
    ) -> List[Dict[str, Any]]:
        """
        Search for elevator specifications based on real-world parameters
        
        Args:
            capacity_lbs: Elevator capacity in pounds
            speed_fpm: Travel speed in feet per minute
            csi_code: CSI division code (default: 14 24 00 for hydraulic elevators)
            
        Returns:
            List of matching specification passages
        """
        # Build search query based on parameters
        search_terms = []
        
        if capacity_lbs:
            search_terms.append(f"{capacity_lbs} pounds")
            search_terms.append(f"{capacity_lbs:,} lbs")
        
        if speed_fpm:
            search_terms.append(f"{speed_fpm} fpm")
            search_terms.append(f"{speed_fpm} feet per minute")
        
        # Add CSI-specific terms
        search_terms.extend([
            "hydraulic elevator",
            "elevator capacity",
            "rated load",
            "travel speed"
        ])
        
        # Combine terms into search query
        query = " ".join(search_terms)
        
        # Search with CSI filter
        results = await self.search(
            query=query,
            csi_divisions=[csi_code],
            limit=10
        )
        
        return results
```

## Context Pack Assembly

### Context Pack Builder

```python
from typing import List, Dict, Any, Optional
import json

class ContextPackBuilder:
    """Build context packs for LLM processing"""
    
    def __init__(self, max_tokens: int = 6000):
        self.max_tokens = max_tokens
        self.token_overhead = 500  # Reserve tokens for prompt and response
    
    async def build_context_pack(
        self,
        specification_passages: List[Dict[str, Any]],
        submittal_passages: List[Dict[str, Any]],
        facts: List[Dict[str, Any]],
        query: str
    ) -> Dict[str, Any]:
        """
        Build a context pack for document comparison
        
        Args:
            specification_passages: Relevant specification passages
            submittal_passages: Relevant submittal passages
            facts: Related facts from both documents
            query: Comparison query
            
        Returns:
            Context pack dictionary
        """
        context_pack = {
            "id": self._generate_context_pack_id(),
            "query": query,
            "specification_content": [],
            "submittal_content": [],
            "facts": [],
            "metadata": {
                "total_tokens": 0,
                "passage_count": 0,
                "fact_count": 0
            }
        }
        
        current_tokens = 0
        max_content_tokens = self.max_tokens - self.token_overhead
        
        # Add specification passages
        for passage in specification_passages:
            passage_tokens = self._estimate_tokens(passage["text"])
            if current_tokens + passage_tokens <= max_content_tokens:
                context_pack["specification_content"].append({
                    "id": passage["id"],
                    "text": passage["text"],
                    "page_number": passage["page_number"],
                    "section_id": passage.get("section_id"),
                    "csi_division": passage.get("csi_division"),
                    "title": passage.get("title"),
                    "passage_type": passage.get("passage_type"),
                    "score": passage.get("combined_score", 0.0)
                })
                current_tokens += passage_tokens
                context_pack["metadata"]["passage_count"] += 1
            else:
                break
        
        # Add submittal passages
        for passage in submittal_passages:
            passage_tokens = self._estimate_tokens(passage["text"])
            if current_tokens + passage_tokens <= max_content_tokens:
                context_pack["submittal_content"].append({
                    "id": passage["id"],
                    "text": passage["text"],
                    "page_number": passage["page_number"],
                    "section_id": passage.get("section_id"),
                    "csi_division": passage.get("csi_division"),
                    "title": passage.get("title"),
                    "passage_type": passage.get("passage_type"),
                    "score": passage.get("combined_score", 0.0)
                })
                current_tokens += passage_tokens
                context_pack["metadata"]["passage_count"] += 1
            else:
                break
        
        # Add relevant facts
        for fact in facts:
            fact_tokens = self._estimate_tokens(json.dumps(fact))
            if current_tokens + fact_tokens <= max_content_tokens:
                context_pack["facts"].append({
                    "id": fact["id"],
                    "topic": fact["topic"],
                    "attribute": fact["attribute"],
                    "operator": fact["operator"],
                    "value": fact["value"],
                    "unit": fact.get("unit"),
                    "source": fact["source"],
                    "confidence": fact["confidence_score"]
                })
                current_tokens += fact_tokens
                context_pack["metadata"]["fact_count"] += 1
            else:
                break
        
        context_pack["metadata"]["total_tokens"] = current_tokens
        
        return context_pack
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)"""
        # Simple estimation: ~4 characters per token
        return len(text) // 4
    
    def _generate_context_pack_id(self) -> str:
        """Generate unique context pack ID"""
        import uuid
        return f"cp_{uuid.uuid4().hex[:8]}"
    
    async def format_context_pack_for_llm(
        self, 
        context_pack: Dict[str, Any]
    ) -> str:
        """
        Format context pack as text for LLM processing
        
        Args:
            context_pack: Context pack dictionary
            
        Returns:
            Formatted text for LLM
        """
        formatted_text = f"# Document Comparison Query\n{context_pack['query']}\n\n"
        
        # Add specification content
        formatted_text += "## Specification Content\n"
        for i, passage in enumerate(context_pack["specification_content"], 1):
            formatted_text += f"### Specification {i} [Page {passage['page_number']}]\n"
            if passage.get("title"):
                formatted_text += f"**Title:** {passage['title']}\n"
            if passage.get("section_id"):
                formatted_text += f"**Section:** {passage['section_id']}\n"
            if passage.get("csi_division"):
                formatted_text += f"**CSI Division:** {passage['csi_division']}\n"
            formatted_text += f"{passage['text']}\n\n"
        
        # Add submittal content
        formatted_text += "## Submittal Content\n"
        for i, passage in enumerate(context_pack["submittal_content"], 1):
            formatted_text += f"### Submittal {i} [Page {passage['page_number']}]\n"
            if passage.get("title"):
                formatted_text += f"**Title:** {passage['title']}\n"
            if passage.get("section_id"):
                formatted_text += f"**Section:** {passage['section_id']}\n"
            if passage.get("csi_division"):
                formatted_text += f"**CSI Division:** {passage['csi_division']}\n"
            formatted_text += f"{passage['text']}\n\n"
        
        # Add facts
        if context_pack["facts"]:
            formatted_text += "## Extracted Facts\n"
            for fact in context_pack["facts"]:
                formatted_text += f"- **{fact['topic']}** ({fact['attribute']}): {fact['operator']} {fact['value']}"
                if fact.get("unit"):
                    formatted_text += f" {fact['unit']}"
                formatted_text += f" [Confidence: {fact['confidence']:.2f}]\n"
            formatted_text += "\n"
        
        return formatted_text
```

## Performance Optimization

### Caching and Indexing

```python
from functools import lru_cache
import hashlib
from typing import Dict, Any

class RetrievalCache:
    """Cache for retrieval results and embeddings"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}
    
    def _generate_cache_key(self, query: str, filters: Dict[str, Any]) -> str:
        """Generate cache key for query and filters"""
        key_data = {
            "query": query,
            "filters": filters
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_cached_result(
        self, 
        query: str, 
        filters: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search result"""
        cache_key = self._generate_cache_key(query, filters)
        if cache_key in self.cache:
            self.access_times[cache_key] = time.time()
            return self.cache[cache_key]
        return None
    
    def cache_result(
        self, 
        query: str, 
        filters: Dict[str, Any], 
        result: List[Dict[str, Any]]
    ):
        """Cache search result"""
        cache_key = self._generate_cache_key(query, filters)
        
        # Remove oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[cache_key] = result
        self.access_times[cache_key] = time.time()
    
    def clear_cache(self):
        """Clear all cached results"""
        self.cache.clear()
        self.access_times.clear()

class OptimizedRetrievalEngine(HybridRetrievalEngine):
    """Optimized retrieval engine with caching"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = RetrievalCache()
    
    async def search(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """Search with caching"""
        # Generate cache key
        filters = kwargs.get("filters", {})
        query = args[0] if args else ""
        
        # Check cache first
        cached_result = self.cache.get_cached_result(query, filters)
        if cached_result is not None:
            return cached_result
        
        # Perform search
        result = await super().search(*args, **kwargs)
        
        # Cache result
        self.cache.cache_result(query, filters, result)
        
        return result
```

This retrieval system specification provides a comprehensive hybrid search solution that efficiently combines semantic vector search with keyword-based BM25 search, optimized for construction document comparison tasks.
