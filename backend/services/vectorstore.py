"""Vector store service using Qdrant for document storage and retrieval."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from langchain_core.documents import Document
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams, Modifier, PointStruct, SparseVector
from fastembed import SparseTextEmbedding

from .metadata_tagger import MetadataTagger

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manager for Qdrant vector store operations."""
    
    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        embedding_dim: int = 1024,
        catalog_path: Optional[str] = None
    ):
        """
        Initialize the vector store manager.
        
        Args:
            embedding_model: OpenAI embedding model to use
            embedding_dim: Embedding dimensions
            catalog_path: Path to attribute catalog for metadata tagging
        """
        self.embedding_model_name = embedding_model
        self.embedding_dim = embedding_dim
        self.embedding_model = OpenAIEmbeddings(model=embedding_model, dimensions=embedding_dim)
        self.bm25_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        
        # Initialize in-memory Qdrant client
        self.client = QdrantClient(":memory:")
        self.collections = {}
        
        # Initialize metadata tagger
        self.metadata_tagger = MetadataTagger(catalog_path)
    
    def create_collection(
        self,
        collection_name: str,
        hybrid: bool = True,
        recreate: bool = False
    ) -> str:
        """
        Create a Qdrant collection with optional hybrid support.
        
        Args:
            collection_name: Name of the collection
            hybrid: Whether to enable hybrid search (dense + sparse)
            recreate: Whether to recreate if collection exists
            
        Returns:
            Name of the created collection
        """
        if recreate and collection_name in self.collections:
            self.client.delete_collection(collection_name)
        
        try:
            if hybrid:
                # Create collection with hybrid support
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": VectorParams(size=self.embedding_dim, distance="Cosine"),
                    },
                    sparse_vectors_config={
                        "bm25": SparseVectorParams(modifier=Modifier.IDF),
                    }
                )
                logger.info(f"Created hybrid collection: {collection_name}")
            else:
                # Create collection with dense vectors only
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE),
                )
                logger.info(f"Created dense collection: {collection_name}")
            
            # Create LangChain vector store
            self.collections[collection_name] = QdrantVectorStore(
                client=self.client,
                collection_name=collection_name,
                embedding=self.embedding_model,
            )
            
            return collection_name
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise
    
    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        add_metadata_tags: bool = True
    ) -> bool:
        """
        Add documents to the collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: Optional metadata for each document
            add_metadata_tags: Whether to add automatic metadata tags
            
        Returns:
            True if successful
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection {collection_name} not found. Create it first.")
        
        try:
            vectorstore = self.collections[collection_name]
            
            # Prepare documents with metadata
            docs = []
            for i, text in enumerate(documents):
                metadata = (metadatas[i] if metadatas and i < len(metadatas) else {}) or {}
                metadata["chunk_id"] = i
                
                # Add automatic metadata tags
                if add_metadata_tags:
                    auto_tags = self.metadata_tagger.tag_payload_generic(text)
                    metadata.update(auto_tags)
                
                docs.append(Document(page_content=text, metadata=metadata))
            
            # Add documents to vectorstore
            vectorstore.add_documents(docs)
            
            # If collection supports hybrid search, add BM25 vectors
            if self._collection_supports_hybrid(collection_name):
                self._add_bm25_vectors(collection_name, documents)
            
            logger.info(f"Added {len(documents)} documents to collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add documents to {collection_name}: {e}")
            return False
    
    def _collection_supports_hybrid(self, collection_name: str) -> bool:
        """Check if collection supports hybrid search."""
        try:
            collection_info = self.client.get_collection(collection_name)
            return "sparse_vectors" in collection_info.config.params
        except Exception:
            return False
    
    def _add_bm25_vectors(self, collection_name: str, documents: List[str]):
        """Add BM25 sparse vectors to collection."""
        try:
            # Generate BM25 embeddings
            bm25_embeddings = list(self.bm25_model.embed(documents))
            
            # Get existing points
            all_points = self.client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=True
            )[0]
            
            # Update points with BM25 vectors
            updated_points = []
            for point, bm25_emb in zip(all_points, bm25_embeddings):
                existing_vector = point.vector
                if isinstance(existing_vector, dict):
                    dense_vector = existing_vector.get("dense", existing_vector)
                else:
                    dense_vector = existing_vector
                
                updated_points.append(
                    PointStruct(
                        id=point.id,
                        vector={
                            "dense": dense_vector,
                            "bm25": bm25_emb.as_object()
                        },
                        payload=point.payload
                    )
                )
            
            # Upsert updated points
            self.client.upsert(collection_name=collection_name, points=updated_points)
            logger.info(f"Added BM25 vectors to {len(updated_points)} documents")
            
        except Exception as e:
            logger.error(f"Failed to add BM25 vectors: {e}")
    
    def dense_search(
        self,
        collection_name: str,
        query: str,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Perform dense vector search.
        
        Args:
            collection_name: Name of the collection
            query: Search query
            limit: Number of results to return
            filter_conditions: Optional filter conditions
            
        Returns:
            List of (document, score) tuples
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection {collection_name} not found")
        
        try:
            vectorstore = self.collections[collection_name]
            return vectorstore.similarity_search_with_score(query=query, k=limit)
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []
    
    def bm25_search(
        self,
        collection_name: str,
        query: str,
        limit: int = 5
    ) -> List[Tuple[Document, float]]:
        """
        Perform BM25 sparse vector search.
        
        Args:
            collection_name: Name of the collection
            query: Search query
            limit: Number of results to return
            
        Returns:
            List of (document, score) tuples
        """
        try:
            # Generate BM25 embedding for query
            query_embedding = next(self.bm25_model.query_embed(query))
            
            # Create SparseVector object
            sparse_vector = SparseVector(
                indices=query_embedding.indices.tolist(),
                values=query_embedding.values.tolist()
            )
            
            # Perform search
            search_results = self.client.query_points(
                collection_name=collection_name,
                query=sparse_vector,
                using="bm25",
                query_filter=None,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            # Convert to Document objects
            results = []
            for result in search_results.points:
                doc = Document(
                    page_content=result.payload.get('page_content', ''),
                    metadata=result.payload
                )
                results.append((doc, result.score))
            
            return results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def hybrid_search(
        self,
        collection_name: str,
        query: str,
        limit: int = 5,
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining dense and sparse vectors.
        
        Args:
            collection_name: Name of the collection
            query: Search query
            limit: Number of results to return
            alpha: Weight for dense vs sparse (0.0 = sparse only, 1.0 = dense only)
            
        Returns:
            List of combined results with scores
        """
        try:
            # Perform both searches
            dense_results = self.dense_search(collection_name, query, limit * 2)
            sparse_results = self.bm25_search(collection_name, query, limit * 2)
            
            # Combine results
            combined_results = self._combine_search_results(
                dense_results, sparse_results, alpha, limit
            )
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    def _combine_search_results(
        self,
        dense_results: List[Tuple[Document, float]],
        sparse_results: List[Tuple[Document, float]],
        alpha: float,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Combine dense and sparse search results with weighted scoring."""
        # Create document ID to scores mapping
        doc_scores = {}
        
        # Add dense vector scores
        for doc, score in dense_results:
            doc_id = id(doc.page_content)  # Use content hash as ID
            doc_scores[doc_id] = {
                'dense_score': score,
                'sparse_score': 0.0,
                'payload': doc.metadata,
                'content': doc.page_content,
                'doc_id': doc_id
            }
        
        # Add sparse vector scores
        for doc, score in sparse_results:
            doc_id = id(doc.page_content)
            if doc_id in doc_scores:
                doc_scores[doc_id]['sparse_score'] = score
            else:
                doc_scores[doc_id] = {
                    'dense_score': 0.0,
                    'sparse_score': score,
                    'payload': doc.metadata,
                    'content': doc.page_content,
                    'doc_id': doc_id
                }
        
        # Calculate combined scores
        for doc_id, scores in doc_scores.items():
            combined_score = (alpha * scores['dense_score'] + (1 - alpha) * scores['sparse_score'])
            scores['combined_score'] = combined_score
        
        # Sort by combined score and return top results
        sorted_results = sorted(
            doc_scores.values(),
            key=lambda x: x['combined_score'],
            reverse=True
        )
        
        return sorted_results[:max_results]
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection."""
        try:
            collection_info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": collection_info.vectors_count,
                "status": collection_info.status,
                "supports_hybrid": self._collection_supports_hybrid(collection_name)
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
    
    def list_collections(self) -> List[str]:
        """List all collections."""
        try:
            collections = self.client.get_collections()
            return [col.name for col in collections.collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
