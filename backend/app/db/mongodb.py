"""
MongoDB database operations for document storage.

This module provides async functions for storing and retrieving
documents, sections, and chunks in MongoDB.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.models.document import (
    Document,
    DocumentSection,
    DocumentChunk,
    DocumentStatus,
    ProcessingStats
)
from app.utils.logging import get_logger
from app.utils.exceptions import DatabaseError, NotFoundError

logger = get_logger(__name__)


async def store_document(db: AsyncIOMotorDatabase, document: Document) -> str:
    """
    Store a document in MongoDB.
    
    Args:
        db: MongoDB database instance
        document: Document to store
    
    Returns:
        Document ID
    
    Raises:
        DatabaseError: If storage fails
    """
    try:
        doc_dict = document.model_dump()
        doc_dict["_id"] = document.document_id
        
        result = await db.documents.insert_one(doc_dict)
        logger.info(f"Stored document: {document.document_id}")
        return str(result.inserted_id)
        
    except Exception as e:
        logger.error(f"Failed to store document: {str(e)}")
        raise DatabaseError(f"Failed to store document: {str(e)}")


async def get_document(db: AsyncIOMotorDatabase, document_id: str) -> Document:
    """
    Retrieve a document by ID.
    
    Args:
        db: MongoDB database instance
        document_id: Document ID
    
    Returns:
        Document
    
    Raises:
        NotFoundError: If document not found
        DatabaseError: If retrieval fails
    """
    try:
        doc_dict = await db.documents.find_one({"_id": document_id})
        
        if not doc_dict:
            raise NotFoundError(f"Document not found: {document_id}")
        
        doc_dict["document_id"] = doc_dict.pop("_id")
        return Document(**doc_dict)
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve document: {str(e)}")
        raise DatabaseError(f"Failed to retrieve document: {str(e)}")


async def update_document(
    db: AsyncIOMotorDatabase,
    document_id: str,
    updates: Dict[str, Any]
) -> bool:
    """
    Update document fields.
    
    Args:
        db: MongoDB database instance
        document_id: Document ID
        updates: Fields to update
    
    Returns:
        True if updated
    
    Raises:
        DatabaseError: If update fails
    """
    try:
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.documents.update_one(
            {"_id": document_id},
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            raise NotFoundError(f"Document not found: {document_id}")
        
        logger.info(f"Updated document: {document_id}")
        return True
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to update document: {str(e)}")
        raise DatabaseError(f"Failed to update document: {str(e)}")


async def update_document_status(
    db: AsyncIOMotorDatabase,
    document_id: str,
    status: DocumentStatus,
    error: Optional[str] = None
) -> bool:
    """Update document processing status."""
    updates = {"status": status.value}
    
    if error:
        updates["errors"] = {
            "stage": "processing",
            "error_type": "ProcessingError",
            "message": error,
            "timestamp": datetime.utcnow()
        }
    
    return await update_document(db, document_id, updates)


async def list_documents(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 10,
    status: Optional[DocumentStatus] = None
) -> tuple[List[Document], int]:
    """
    List documents with pagination.
    
    Args:
        db: MongoDB database instance
        skip: Number of documents to skip
        limit: Maximum documents to return
        status: Filter by status
    
    Returns:
        Tuple of (documents, total_count)
    """
    try:
        query = {}
        if status:
            query["status"] = status.value
        
        cursor = db.documents.find(query).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        total = await db.documents.count_documents(query)
        
        documents = []
        for doc_dict in docs:
            doc_dict["document_id"] = doc_dict.pop("_id")
            documents.append(Document(**doc_dict))
        
        return documents, total
        
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise DatabaseError(f"Failed to list documents: {str(e)}")


async def delete_document(db: AsyncIOMotorDatabase, document_id: str) -> bool:
    """Delete a document and all related data."""
    try:
        # Delete document
        result = await db.documents.delete_one({"_id": document_id})
        
        if result.deleted_count == 0:
            raise NotFoundError(f"Document not found: {document_id}")
        
        # Delete sections
        await db.sections.delete_many({"document_id": document_id})
        
        # Delete chunks
        await db.chunks.delete_many({"document_id": document_id})
        
        logger.info(f"Deleted document and related data: {document_id}")
        return True
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {str(e)}")
        raise DatabaseError(f"Failed to delete document: {str(e)}")


async def store_document_sections(
    db: AsyncIOMotorDatabase,
    sections: List[DocumentSection]
) -> int:
    """Store document sections."""
    try:
        if not sections:
            return 0
        
        section_dicts = [s.model_dump() for s in sections]
        result = await db.sections.insert_many(section_dicts)
        
        logger.info(f"Stored {len(result.inserted_ids)} sections")
        return len(result.inserted_ids)
        
    except Exception as e:
        logger.error(f"Failed to store sections: {str(e)}")
        raise DatabaseError(f"Failed to store sections: {str(e)}")


async def store_document_chunks(
    db: AsyncIOMotorDatabase,
    chunks: List[DocumentChunk]
) -> int:
    """Store document chunks."""
    try:
        if not chunks:
            return 0
        
        chunk_dicts = [c.model_dump() for c in chunks]
        result = await db.chunks.insert_many(chunk_dicts)
        
        logger.info(f"Stored {len(result.inserted_ids)} chunks")
        return len(result.inserted_ids)
        
    except Exception as e:
        logger.error(f"Failed to store chunks: {str(e)}")
        raise DatabaseError(f"Failed to store chunks: {str(e)}")


async def get_document_chunks(
    db: AsyncIOMotorDatabase,
    document_id: str
) -> List[DocumentChunk]:
    """Retrieve all chunks for a document."""
    try:
        cursor = db.chunks.find({"document_id": document_id})
        chunk_dicts = await cursor.to_list(length=None)
        
        chunks = [DocumentChunk(**c) for c in chunk_dicts]
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to retrieve chunks: {str(e)}")
        raise DatabaseError(f"Failed to retrieve chunks: {str(e)}")

