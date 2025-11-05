"""
Parent document retriever using small-to-big strategy.

This module implements a retriever that searches on small child chunks but returns
larger parent documents for better context in comparison tasks.
"""

from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.stores import InMemoryStore
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
import logging
import uuid

from app.retrievers.base import BaseRetriever

logger = logging.getLogger(__name__)


class ParentDocumentRetriever(BaseRetriever):
    """
    Parent document retriever using small-to-big strategy.

    Searches on small child chunks for better precision, but returns larger parent
    documents for better context. This approach combines the benefits of:
    - Fine-grained search (small chunks)
    - Rich context (large parent documents)
    """

    def __init__(
        self,
        qdrant_client: QdrantClient,
        parent_documents: List[Document],
        collection_name: str = "construction_docs_parent",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        child_chunk_size: int = 750,
        child_chunk_overlap: int = 75,
    ):
        """
        Initialize parent document retriever.

        Args:
            qdrant_client: Qdrant client instance
            parent_documents: List of parent documents to index
            collection_name: Name of the Qdrant collection for child chunks
            embedding_model: FastEmbed model name
            child_chunk_size: Size of child chunks in characters
            child_chunk_overlap: Overlap between child chunks
        """
        self.client = qdrant_client
        self.collection_name = collection_name
        self.embedding_model = TextEmbedding(model_name=embedding_model)

        # Store parent documents in memory
        self.docstore = InMemoryStore()

        # Create child splitter
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
        )

        # Index documents
        self._index_documents(parent_documents)

        logger.info(
            f"Initialized ParentDocumentRetriever with {len(parent_documents)} parent documents, "
            f"child_chunk_size={child_chunk_size}"
        )

    def _index_documents(self, parent_documents: List[Document]):
        """
        Index parent documents by splitting into child chunks.

        Args:
            parent_documents: List of parent documents to index
        """
        from qdrant_client.models import Distance, VectorParams, PointStruct

        # Create collection if it doesn't exist
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection {self.collection_name} already exists")
        except Exception:
            # Get embedding dimension from model
            sample_embedding = list(self.embedding_model.embed(["test"]))[0]
            embedding_dim = len(sample_embedding)

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )
            logger.info(f"Created collection {self.collection_name} with dimension {embedding_dim}")

        # Process each parent document
        points = []
        for parent_doc in parent_documents:
            # Generate parent ID
            parent_id = parent_doc.metadata.get("chunk_id") or str(uuid.uuid4())

            # Store parent document in docstore
            self.docstore.mset([(parent_id, parent_doc)])

            # Split into child chunks
            child_docs = self.child_splitter.split_documents([parent_doc])

            # Create embeddings and points for child chunks
            for i, child_doc in enumerate(child_docs):
                child_id = f"{parent_id}_child_{i}"

                # Generate embedding
                embedding = list(self.embedding_model.embed([child_doc.page_content]))[0]

                # Create point with parent_id in metadata
                point = PointStruct(
                    id=child_id,
                    vector=embedding.tolist(),
                    payload={
                        "content": child_doc.page_content,
                        "parent_id": parent_id,
                        "child_index": i,
                        **child_doc.metadata,
                    },
                )
                points.append(point)

        # Upsert all points
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(
                f"Indexed {len(points)} child chunks from {len(parent_documents)} parent documents"
            )

    async def retrieve(
        self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve parent documents by searching on child chunks.

        Args:
            query: Query string
            top_k: Number of parent documents to retrieve
            filters: Optional filters (e.g., {"document_id": "doc_123"})

        Returns:
            List of parent Document objects with relevance scores
        """
        try:
            self._validate_query(query)
            self._validate_top_k(top_k)

            logger.debug(f"Parent document retrieval: query='{query[:50]}...', top_k={top_k}")

            # Generate query embedding
            query_embedding = list(self.embedding_model.embed([query]))[0]

            # Build Qdrant filter
            qdrant_filter = None
            if filters and "document_id" in filters:
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                qdrant_filter = Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=filters["document_id"]),
                        )
                    ]
                )

            # Search child chunks (get more initially to ensure we have enough unique parents)
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                limit=top_k * 3,  # Get more child chunks to find unique parents
                query_filter=qdrant_filter,
            )

            # Collect unique parent documents with their best child scores
            parent_scores: Dict[str, float] = {}
            parent_ids_seen = set()

            for result in search_results:
                parent_id = result.payload.get("parent_id")
                if not parent_id:
                    continue

                # Keep the best score for each parent
                if parent_id not in parent_scores or result.score > parent_scores[parent_id]:
                    parent_scores[parent_id] = result.score
                    parent_ids_seen.add(parent_id)

            # Sort parents by score and take top_k
            sorted_parents = sorted(parent_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

            # Retrieve parent documents from docstore
            documents = []
            for parent_id, score in sorted_parents:
                parent_docs = self.docstore.mget([parent_id])
                parent_doc = parent_docs[0] if parent_docs else None

                if parent_doc:
                    # Create result document with updated metadata
                    result_doc = Document(
                        page_content=parent_doc.page_content,
                        metadata={
                            **parent_doc.metadata,
                            "relevance_score": float(score),
                            "retrieval_method": "parent_document",
                        },
                    )
                    documents.append(result_doc)

            logger.info(
                f"Parent document retrieval: retrieved {len(documents)} parent documents "
                f"from {len(search_results)} child chunks"
            )
            return documents

        except Exception as e:
            logger.error(f"Parent document retrieval failed: {e}", exc_info=True)
            return []
