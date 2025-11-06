"""
Test duplicate document detection.

This module tests the content-based deduplication feature for document uploads.
"""

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile
from io import BytesIO

from app.models.document import DocumentType, DocumentStatus


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"%PDF-1.4\n%Test PDF content\nSample submittal document\n%%EOF"


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB database."""
    mock_db = MagicMock()
    mock_db.documents = MagicMock()
    return mock_db


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client."""
    return MagicMock()


@pytest.mark.asyncio
async def test_duplicate_detection_returns_existing_document(
    sample_pdf_content, mock_mongodb, mock_qdrant
):
    """Test that uploading a duplicate file returns the existing document."""
    from app.api.v1.documents import upload_document
    from fastapi import BackgroundTasks

    # Calculate content hash
    content_hash = hashlib.sha256(sample_pdf_content).hexdigest()

    # Mock existing document in database
    existing_doc = {
        "document_id": "existing-doc-123",
        "title": "Existing Submittal.pdf",
        "status": DocumentStatus.COMPLETED.value,
        "metadata": {
            "document_type": DocumentType.SUBMITTAL.value,
            "filename": "Existing Submittal.pdf",
            "file_size": len(sample_pdf_content),
            "mime_type": "application/pdf",
            "content_hash": content_hash,
            "upload_timestamp": "2025-11-06T10:00:00",
            "processing_timestamp": "2025-11-06T10:01:00",
            "used_ocr": True,
            "ocr_engine": None,
            "parse_time": 5.2,
        },
        "markdown_content": None,
        "processing_stats": {
            "total_sections": 0,
            "sections_by_level": {},
            "total_chunks": 50,
            "total_tokens": 5000,
        },
        "progress": None,
        "errors": [],
        "created_at": "2025-11-06T10:00:00",
        "updated_at": "2025-11-06T10:01:00",
    }

    # Mock MongoDB find_one to return existing document
    mock_mongodb.documents.find_one = AsyncMock(return_value=existing_doc)

    # Create upload file
    file = UploadFile(
        filename="Duplicate Submittal.pdf",
        file=BytesIO(sample_pdf_content),
        content_type="application/pdf",
    )

    # Mock file.read()
    async def mock_read():
        return sample_pdf_content

    file.read = mock_read

    # Create background tasks
    background_tasks = BackgroundTasks()

    # Call upload endpoint
    response = await upload_document(
        background_tasks=background_tasks,
        file=file,
        document_type="submittal",
        title=None,
        use_ocr=True,
        project_id=None,
        max_chunk_tokens=500,
        chunk_overlap_tokens=50,
        force_reupload=False,
        mongodb=mock_mongodb,
        qdrant=mock_qdrant,
    )

    # Verify response
    assert response.status_code == 200
    response_data = response.body.decode()
    assert "existing-doc-123" in response_data
    assert "duplicate_detected" in response_data
    assert "Document already exists" in response_data

    # Verify MongoDB was queried for duplicate
    mock_mongodb.documents.find_one.assert_called_once()
    call_args = mock_mongodb.documents.find_one.call_args[0][0]
    assert call_args["metadata.content_hash"] == content_hash
    assert call_args["metadata.document_type"] == DocumentType.SUBMITTAL.value


@pytest.mark.asyncio
async def test_force_reupload_bypasses_duplicate_detection(
    sample_pdf_content, mock_mongodb, mock_qdrant
):
    """Test that force_reupload=True bypasses duplicate detection."""
    from app.api.v1.documents import upload_document
    from fastapi import BackgroundTasks

    # Calculate content hash
    content_hash = hashlib.sha256(sample_pdf_content).hexdigest()

    # Mock existing document in database
    existing_doc = {
        "document_id": "existing-doc-123",
        "title": "Existing Submittal.pdf",
        "status": DocumentStatus.COMPLETED.value,
        "metadata": {
            "document_type": DocumentType.SUBMITTAL.value,
            "filename": "Existing Submittal.pdf",
            "file_size": len(sample_pdf_content),
            "mime_type": "application/pdf",
            "content_hash": content_hash,
        },
        "created_at": "2025-11-06T10:00:00",
        "updated_at": "2025-11-06T10:01:00",
    }

    # Mock MongoDB operations
    mock_mongodb.documents.find_one = AsyncMock(return_value=existing_doc)
    mock_mongodb.documents.insert_one = AsyncMock()

    # Create upload file
    file = UploadFile(
        filename="Duplicate Submittal.pdf",
        file=BytesIO(sample_pdf_content),
        content_type="application/pdf",
    )

    # Mock file.read()
    async def mock_read():
        return sample_pdf_content

    file.read = mock_read

    # Create background tasks
    background_tasks = BackgroundTasks()

    # Mock store_document
    with patch("app.api.v1.documents.store_document", new_callable=AsyncMock):
        # Call upload endpoint with force_reupload=True
        response = await upload_document(
            background_tasks=background_tasks,
            file=file,
            document_type="submittal",
            title=None,
            use_ocr=True,
            project_id=None,
            max_chunk_tokens=500,
            chunk_overlap_tokens=50,
            force_reupload=True,  # ← Force reupload
            mongodb=mock_mongodb,
            qdrant=mock_qdrant,
        )

    # Verify response is 202 (new document created)
    assert response.status_code == 202

    # Verify MongoDB was NOT queried for duplicate
    mock_mongodb.documents.find_one.assert_not_called()


@pytest.mark.asyncio
async def test_different_document_types_not_considered_duplicates(
    sample_pdf_content, mock_mongodb, mock_qdrant
):
    """Test that same file with different document_type is not considered duplicate."""
    from app.api.v1.documents import upload_document
    from fastapi import BackgroundTasks

    # Calculate content hash
    content_hash = hashlib.sha256(sample_pdf_content).hexdigest()

    # Mock existing SPECIFICATION document in database
    existing_doc = {
        "document_id": "existing-spec-123",
        "title": "Existing Specification.pdf",
        "status": DocumentStatus.COMPLETED.value,
        "metadata": {
            "document_type": DocumentType.SPECIFICATION.value,  # ← SPECIFICATION
            "filename": "Existing Specification.pdf",
            "file_size": len(sample_pdf_content),
            "mime_type": "application/pdf",
            "content_hash": content_hash,
        },
        "created_at": "2025-11-06T10:00:00",
        "updated_at": "2025-11-06T10:01:00",
    }

    # Mock MongoDB find_one to return None (no duplicate SUBMITTAL found)
    mock_mongodb.documents.find_one = AsyncMock(return_value=None)
    mock_mongodb.documents.insert_one = AsyncMock()

    # Create upload file
    file = UploadFile(
        filename="Same File as Submittal.pdf",
        file=BytesIO(sample_pdf_content),
        content_type="application/pdf",
    )

    # Mock file.read()
    async def mock_read():
        return sample_pdf_content

    file.read = mock_read

    # Create background tasks
    background_tasks = BackgroundTasks()

    # Mock store_document
    with patch("app.api.v1.documents.store_document", new_callable=AsyncMock):
        # Call upload endpoint with document_type=submittal
        response = await upload_document(
            background_tasks=background_tasks,
            file=file,
            document_type="submittal",  # ← SUBMITTAL (different from existing SPECIFICATION)
            title=None,
            use_ocr=True,
            project_id=None,
            max_chunk_tokens=500,
            chunk_overlap_tokens=50,
            force_reupload=False,
            mongodb=mock_mongodb,
            qdrant=mock_qdrant,
        )

    # Verify response is 202 (new document created, not duplicate)
    assert response.status_code == 202

    # Verify MongoDB was queried with correct document_type filter
    mock_mongodb.documents.find_one.assert_called_once()
    call_args = mock_mongodb.documents.find_one.call_args[0][0]
    assert call_args["metadata.content_hash"] == content_hash
    assert call_args["metadata.document_type"] == DocumentType.SUBMITTAL.value
