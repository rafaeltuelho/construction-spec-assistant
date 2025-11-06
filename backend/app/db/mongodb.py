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
    ProcessingStats,
)
from app.models.fact import Fact
from app.models.comparison import DocumentComparisonResult
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
    db: AsyncIOMotorDatabase, document_id: str, updates: Dict[str, Any]
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

        result = await db.documents.update_one({"_id": document_id}, {"$set": updates})

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
    db: AsyncIOMotorDatabase, document_id: str, status: DocumentStatus, error: Optional[str] = None
) -> bool:
    """Update document processing status."""
    updates = {"status": status.value}

    if error:
        # Append error to the errors list (not replace it)
        error_obj = {
            "stage": "processing",
            "error_type": "ProcessingError",
            "message": error,
            "timestamp": datetime.utcnow(),
        }
        # Use $push to append to the errors array
        await db.documents.update_one(
            {"document_id": document_id}, {"$push": {"errors": error_obj}, "$set": updates}
        )
        return True

    return await update_document(db, document_id, updates)


async def list_documents(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 10,
    status: Optional[DocumentStatus] = None,
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


async def store_document_sections(db: AsyncIOMotorDatabase, sections: List[DocumentSection]) -> int:
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


async def store_document_chunks(db: AsyncIOMotorDatabase, chunks: List[DocumentChunk]) -> int:
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


async def get_document_chunks(db: AsyncIOMotorDatabase, document_id: str) -> List[DocumentChunk]:
    """Retrieve all chunks for a document."""
    try:
        cursor = db.chunks.find({"document_id": document_id})
        chunk_dicts = await cursor.to_list(length=None)

        chunks = [DocumentChunk(**c) for c in chunk_dicts]
        return chunks

    except Exception as e:
        logger.error(f"Failed to retrieve chunks: {str(e)}")
        raise DatabaseError(f"Failed to retrieve chunks: {str(e)}")


async def store_facts(db: AsyncIOMotorDatabase, facts: List[Fact]) -> List[str]:
    """
    Store facts in MongoDB.

    Args:
        db: MongoDB database instance
        facts: List of facts to store

    Returns:
        List of inserted fact IDs

    Raises:
        DatabaseError: If storage fails
    """
    try:
        if not facts:
            return []

        # Convert to dict and insert
        fact_dicts = [fact.model_dump() for fact in facts]
        result = await db.facts.insert_many(fact_dicts)

        logger.info(f"Stored {len(result.inserted_ids)} facts")
        return [str(fact_id) for fact_id in result.inserted_ids]

    except Exception as e:
        logger.error(f"Failed to store facts: {str(e)}")
        raise DatabaseError(f"Failed to store facts: {str(e)}")


async def get_facts_by_document(
    db: AsyncIOMotorDatabase, document_id: str, limit: int = 100, offset: int = 0
) -> List[Fact]:
    """
    Retrieve all facts for a document.

    Args:
        db: MongoDB database instance
        document_id: Document identifier
        limit: Maximum facts to return
        offset: Pagination offset

    Returns:
        List of Fact objects

    Raises:
        DatabaseError: If retrieval fails
    """
    try:
        cursor = db.facts.find({"context.doc_id": document_id}).skip(offset).limit(limit)
        fact_dicts = await cursor.to_list(length=limit)

        facts = [Fact(**doc) for doc in fact_dicts]
        logger.debug(f"Retrieved {len(facts)} facts for document {document_id}")
        return facts

    except Exception as e:
        logger.error(f"Failed to retrieve facts: {str(e)}")
        raise DatabaseError(f"Failed to retrieve facts: {str(e)}")


async def get_fact_by_id(db: AsyncIOMotorDatabase, fact_id: str) -> Fact:
    """
    Retrieve a single fact by ID.

    Args:
        db: MongoDB database instance
        fact_id: Fact identifier

    Returns:
        Fact object

    Raises:
        NotFoundError: If fact not found
        DatabaseError: If retrieval fails
    """
    try:
        fact_dict = await db.facts.find_one({"id": fact_id})

        if not fact_dict:
            raise NotFoundError(f"Fact not found: {fact_id}")

        fact = Fact(**fact_dict)
        logger.debug(f"Retrieved fact: {fact_id}")
        return fact

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve fact: {str(e)}")
        raise DatabaseError(f"Failed to retrieve fact: {str(e)}")


async def get_section_by_id(db: AsyncIOMotorDatabase, section_id: str) -> DocumentSection:
    """
    Retrieve a single section by ID.

    Args:
        db: MongoDB database instance
        section_id: Section identifier

    Returns:
        DocumentSection object

    Raises:
        NotFoundError: If section not found
        DatabaseError: If retrieval fails
    """
    try:
        section_dict = await db.sections.find_one({"section_id": section_id})

        if not section_dict:
            raise NotFoundError(f"Section not found: {section_id}")

        section = DocumentSection(**section_dict)
        logger.debug(f"Retrieved section: {section_id}")
        return section

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve section: {str(e)}")
        raise DatabaseError(f"Failed to retrieve section: {str(e)}")


async def store_document_comparison_result(
    db: AsyncIOMotorDatabase, comparison_result: DocumentComparisonResult
) -> str:
    """
    Store a document comparison result in MongoDB.

    Args:
        db: MongoDB database instance
        comparison_result: Document comparison result to store

    Returns:
        Job ID

    Raises:
        DatabaseError: If storage fails
    """
    try:
        result_dict = comparison_result.model_dump()
        result_dict["_id"] = comparison_result.job_id

        # Upsert to handle updates to existing jobs
        await db.document_comparison_results.replace_one(
            {"_id": comparison_result.job_id}, result_dict, upsert=True
        )

        logger.info(
            f"Stored document comparison result: job_id={comparison_result.job_id}, "
            f"status={comparison_result.status}"
        )
        return comparison_result.job_id

    except Exception as e:
        logger.error(f"Failed to store document comparison result: {str(e)}")
        raise DatabaseError(f"Failed to store document comparison result: {str(e)}")


async def get_document_comparison_result(
    db: AsyncIOMotorDatabase, job_id: str
) -> Optional[DocumentComparisonResult]:
    """
    Retrieve a document comparison result by job ID.

    Args:
        db: MongoDB database instance
        job_id: Job identifier

    Returns:
        DocumentComparisonResult or None if not found

    Raises:
        DatabaseError: If retrieval fails
    """
    try:
        result_dict = await db.document_comparison_results.find_one({"_id": job_id})

        if not result_dict:
            return None

        result_dict["job_id"] = result_dict.pop("_id")

        # Convert comparisons from dicts to ComparisonResult objects
        if "comparisons" in result_dict and result_dict["comparisons"]:
            from app.models.comparison import ComparisonResult

            comparisons = []
            for comp_dict in result_dict["comparisons"]:
                # Ensure retrieved_chunks are properly structured
                if "retrieved_chunks" in comp_dict:
                    chunks = []
                    for chunk in comp_dict["retrieved_chunks"]:
                        if isinstance(chunk, dict):
                            chunks.append(chunk)
                        else:
                            chunks.append(
                                chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
                            )
                    comp_dict["retrieved_chunks"] = chunks

                comparisons.append(ComparisonResult(**comp_dict))

            result_dict["comparisons"] = comparisons

        return DocumentComparisonResult(**result_dict)

    except Exception as e:
        logger.error(f"Failed to retrieve document comparison result: {str(e)}")
        raise DatabaseError(f"Failed to retrieve document comparison result: {str(e)}")


async def get_document_comparison_results_by_spec(
    db: AsyncIOMotorDatabase, spec_document_id: str, limit: int = 100, offset: int = 0
) -> List[DocumentComparisonResult]:
    """
    Retrieve all comparison results for a specific specification document.

    Args:
        db: MongoDB database instance
        spec_document_id: Specification document identifier
        limit: Maximum results to return
        offset: Pagination offset

    Returns:
        List of DocumentComparisonResult objects

    Raises:
        DatabaseError: If retrieval fails
    """
    try:
        cursor = (
            db.document_comparison_results.find({"spec_document_id": spec_document_id})
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        result_dicts = await cursor.to_list(length=limit)

        results = []
        for result_dict in result_dicts:
            result_dict["job_id"] = result_dict.pop("_id")
            results.append(DocumentComparisonResult(**result_dict))

        logger.debug(
            f"Retrieved {len(results)} comparison results for spec document {spec_document_id}"
        )
        return results

    except Exception as e:
        logger.error(f"Failed to retrieve comparison results by spec: {str(e)}")
        raise DatabaseError(f"Failed to retrieve comparison results by spec: {str(e)}")


async def get_document_comparison_results_by_submittal(
    db: AsyncIOMotorDatabase, submittal_document_id: str, limit: int = 100, offset: int = 0
) -> List[DocumentComparisonResult]:
    """
    Retrieve all comparison results for a specific submittal document.

    Args:
        db: MongoDB database instance
        submittal_document_id: Submittal document identifier
        limit: Maximum results to return
        offset: Pagination offset

    Returns:
        List of DocumentComparisonResult objects

    Raises:
        DatabaseError: If retrieval fails
    """
    try:
        cursor = (
            db.document_comparison_results.find({"submittal_document_id": submittal_document_id})
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        result_dicts = await cursor.to_list(length=limit)

        results = []
        for result_dict in result_dicts:
            result_dict["job_id"] = result_dict.pop("_id")
            results.append(DocumentComparisonResult(**result_dict))

        logger.debug(
            f"Retrieved {len(results)} comparison results for submittal document {submittal_document_id}"
        )
        return results

    except Exception as e:
        logger.error(f"Failed to retrieve comparison results by submittal: {str(e)}")
        raise DatabaseError(f"Failed to retrieve comparison results by submittal: {str(e)}")


# Alias for compatibility
async def get_comparison_result(
    db: AsyncIOMotorDatabase, job_id: str
) -> Optional[DocumentComparisonResult]:
    """
    Alias for get_document_comparison_result for compatibility.

    Args:
        db: MongoDB database instance
        job_id: Job identifier

    Returns:
        Document comparison result or None if not found
    """
    return await get_document_comparison_result(db, job_id)


async def update_comparison_annotations(
    db: AsyncIOMotorDatabase, job_id: str, annotations: Dict[str, List[Any]]
) -> None:
    """
    Update annotations for a comparison result.

    Args:
        db: MongoDB database instance
        job_id: Job identifier
        annotations: Annotations dictionary keyed by comparison_id

    Raises:
        DatabaseError: If update fails
        NotFoundError: If comparison result not found
    """
    try:
        # Convert UserAnnotation objects to dicts for MongoDB storage
        annotations_dict = {}
        for comparison_id, annotation_list in annotations.items():
            annotations_dict[comparison_id] = [
                ann.model_dump() if hasattr(ann, "model_dump") else ann for ann in annotation_list
            ]

        result = await db.document_comparison_results.update_one(
            {"_id": job_id},
            {"$set": {"annotations": annotations_dict, "updated_at": datetime.utcnow()}},
        )

        if result.matched_count == 0:
            raise NotFoundError(f"Comparison result not found: {job_id}")

        logger.info(f"Updated annotations for comparison result: {job_id}")

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to update annotations: {str(e)}")
        raise DatabaseError(f"Failed to update annotations: {str(e)}")


async def save_report_conclusion(
    db: AsyncIOMotorDatabase, job_id: str, conclusion: Dict[str, Any]
) -> None:
    """
    Save report conclusion to a comparison result.

    Args:
        db: MongoDB database instance
        job_id: Job identifier
        conclusion: Report conclusion data

    Raises:
        DatabaseError: If save fails
        NotFoundError: If comparison result not found
    """
    try:
        result = await db.document_comparison_results.update_one(
            {"_id": job_id},
            {"$set": {"report_conclusion": conclusion, "updated_at": datetime.utcnow()}},
        )

        if result.matched_count == 0:
            raise NotFoundError(f"Comparison result not found: {job_id}")

        logger.info(f"Saved report conclusion for job: {job_id}")

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to save report conclusion: {str(e)}")
        raise DatabaseError(f"Failed to save report conclusion: {str(e)}")


async def get_report_conclusion(db: AsyncIOMotorDatabase, job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve report conclusion for a comparison result.

    Args:
        db: MongoDB database instance
        job_id: Job identifier

    Returns:
        Report conclusion data if exists, None otherwise

    Raises:
        DatabaseError: If retrieval fails
    """
    try:
        result = await db.document_comparison_results.find_one(
            {"_id": job_id}, {"report_conclusion": 1}
        )

        if not result:
            return None

        return result.get("report_conclusion")

    except Exception as e:
        logger.error(f"Failed to retrieve report conclusion: {str(e)}")
        raise DatabaseError(f"Failed to retrieve report conclusion: {str(e)}")
