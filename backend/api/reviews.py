"""Review endpoints for the Construction Spec Assistant API."""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from ..models.api_models import (
    BaseResponse, ReviewRequest, ReviewResponse, ReviewListResponse,
    ReviewStatus, FindingType, Finding, Citation
)
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for demo (replace with proper database in production)
reviews_db: Dict[str, Dict[str, Any]] = {}


def get_services():
    """Get services from app state."""
    from ..main import app_state
    return app_state.get("services")


def get_documents_db():
    """Get documents database from main module."""
    from ..api.documents import documents_db
    return documents_db


@router.post("/reviews", response_model=BaseResponse)
async def create_review(
    review_request: ReviewRequest,
    services = Depends(get_services),
    documents_db = Depends(get_documents_db)
):
    """Create a new document review."""
    try:
        # Validate documents exist
        spec_doc = documents_db.get(review_request.specification_document_id)
        submittal_doc = documents_db.get(review_request.submittal_document_id)
        
        if not spec_doc:
            raise HTTPException(status_code=404, detail="Specification document not found")
        
        if not submittal_doc:
            raise HTTPException(status_code=404, detail="Submittal document not found")
        
        # Check document status
        if spec_doc["status"] != "indexed":
            raise HTTPException(
                status_code=400, 
                detail="Specification document not fully processed"
            )
        
        if submittal_doc["status"] != "indexed":
            raise HTTPException(
                status_code=400, 
                detail="Submittal document not fully processed"
            )
        
        # Generate review ID
        review_id = str(uuid.uuid4())
        
        # Create review record
        review_record = {
            "id": review_id,
            "specification_document_id": review_request.specification_document_id,
            "submittal_document_id": review_request.submittal_document_id,
            "status": ReviewStatus.PENDING,
            "created_at": datetime.utcnow(),
            "review_scope": review_request.review_scope,
            "llm_provider": review_request.llm_provider,
            "llm_model": review_request.llm_model,
            "enable_verification": review_request.enable_verification,
            "findings": [],
            "summary": None,
            "confidence_score": 0.0,
            "processing_time_seconds": None,
            "error_message": None
        }
        
        reviews_db[review_id] = review_record
        
        # Start review process in background
        try:
            await process_review_background(review_id, services, documents_db)
        except Exception as e:
            logger.error(f"Review processing failed: {e}")
            review_record["status"] = ReviewStatus.FAILED
            review_record["error_message"] = str(e)
        
        return BaseResponse(
            success=True,
            message=f"Review created successfully. Review ID: {review_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create review: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create review: {str(e)}")


async def process_review_background(
    review_id: str, 
    services, 
    documents_db: Dict[str, Any]
):
    """Process review in background."""
    try:
        review_record = reviews_db[review_id]
        review_record["status"] = ReviewStatus.IN_PROGRESS
        review_record["started_at"] = datetime.utcnow()
        
        start_time = datetime.utcnow()
        
        # Get specification facts
        spec_doc_id = review_record["specification_document_id"]
        spec_doc = documents_db[spec_doc_id]
        spec_facts = spec_doc.get("extracted_facts", [])
        
        if not spec_facts:
            raise ValueError("No facts extracted from specification document")
        
        # Get submittal collection
        submittal_doc_id = review_record["submittal_document_id"]
        submittal_doc = documents_db[submittal_doc_id]
        collection_name = submittal_doc.get("collection_name")
        
        if not collection_name:
            raise ValueError("Submittal document not indexed in vector store")
        
        # Load catalog
        from ..utils.catalog_loader import load_default_catalog
        catalog = load_default_catalog()
        
        # Create agents
        from ..agents import RetrievalAgent, ComparatorAgent
        retrieval_agent = RetrievalAgent(services.vectorstore_manager)
        comparator_agent = ComparatorAgent(retrieval_agent)
        
        # Compare each spec fact with submittal
        findings = []
        consistent_count = 0
        inconsistent_count = 0
        unclear_count = 0
        
        for fact in spec_facts:
            try:
                comparison_result = comparator_agent.compare(
                    spec_fact=fact,
                    collection_name=collection_name,
                    catalog=catalog,
                    top_k=3
                )
                
                # Create finding
                finding_type = ComparisonVerdict(comparison_result.get("verdict", "unclear"))
                
                finding = Finding(
                    id=str(uuid.uuid4()),
                    finding_type=FindingType(finding_type.value),
                    confidence=comparison_result.get("confidence", 0.0),
                    title=f"Fact: {fact.get('attribute', {}).get('raw', 'Unknown')}",
                    description=f"Specification requires: {fact.get('value', {}).get('raw', 'Unknown')}",
                    recommendation=_generate_recommendation(comparison_result, fact),
                    specification_facts=[str(fact)],
                    submittal_facts=[comparison_result.get("submittal_evidence", "")],
                    supporting_passages=[comparison_result.get("chunk_preview", "")],
                    citations=_create_citations(fact, comparison_result)
                )
                
                findings.append(finding)
                
                # Count results
                if finding_type == ComparisonVerdict.CONSISTENT:
                    consistent_count += 1
                elif finding_type == ComparisonVerdict.INCONSISTENT:
                    inconsistent_count += 1
                else:
                    unclear_count += 1
                
            except Exception as e:
                logger.error(f"Failed to compare fact: {e}")
                continue
        
        # Calculate confidence score
        total_facts = len(spec_facts)
        confidence_score = consistent_count / total_facts if total_facts > 0 else 0.0
        
        # Generate summary
        summary = _generate_summary(
            consistent_count, inconsistent_count, unclear_count, total_facts
        )
        
        # Update review record
        review_record["status"] = ReviewStatus.COMPLETED
        review_record["completed_at"] = datetime.utcnow()
        review_record["findings"] = [finding.dict() for finding in findings]
        review_record["summary"] = summary
        review_record["confidence_score"] = confidence_score
        review_record["processing_time_seconds"] = (
            datetime.utcnow() - start_time
        ).total_seconds()
        
        logger.info(f"Review {review_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Review processing failed: {e}")
        review_record["status"] = ReviewStatus.FAILED
        review_record["error_message"] = str(e)


def _generate_recommendation(comparison_result: Dict[str, Any], fact: Dict[str, Any]) -> str:
    """Generate recommendation based on comparison result."""
    verdict = comparison_result.get("verdict", "unclear")
    
    if verdict == "consistent":
        return "No action required - submittal meets specification requirements."
    elif verdict == "inconsistent":
        return "Review required - submittal does not meet specification requirements."
    else:
        return "Additional information needed - unable to determine compliance."


def _create_citations(fact: Dict[str, Any], comparison_result: Dict[str, Any]) -> List[Citation]:
    """Create citations for the finding."""
    citations = []
    
    # Specification citation
    spec_context = fact.get("context", {})
    citations.append(Citation(
        source="specification",
        page=0,  # Would need to map from section to page
        section=spec_context.get("section_id", ""),
        text=spec_context.get("source_span", "")
    ))
    
    # Submittal citation
    if comparison_result.get("submittal_evidence"):
        citations.append(Citation(
            source="submittal",
            page=0,  # Would need to map from chunk to page
            section=comparison_result.get("chunk_meta", {}).get("chunk_id", ""),
            text=comparison_result.get("submittal_evidence", "")
        ))
    
    return citations


def _generate_summary(
    consistent_count: int, 
    inconsistent_count: int, 
    unclear_count: int, 
    total_facts: int
) -> str:
    """Generate summary of review results."""
    return (
        f"Review completed: {total_facts} facts analyzed. "
        f"{consistent_count} consistent, {inconsistent_count} inconsistent, "
        f"{unclear_count} unclear. "
        f"Overall confidence: {(consistent_count / total_facts * 100):.1f}%"
    )


@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[ReviewStatus] = Query(None),
    specification_document_id: Optional[str] = Query(None),
    submittal_document_id: Optional[str] = Query(None)
):
    """List reviews with pagination and filtering."""
    try:
        # Filter reviews
        filtered_reviews = list(reviews_db.values())
        
        if status:
            filtered_reviews = [r for r in filtered_reviews if r["status"] == status]
        
        if specification_document_id:
            filtered_reviews = [
                r for r in filtered_reviews 
                if r["specification_document_id"] == specification_document_id
            ]
        
        if submittal_document_id:
            filtered_reviews = [
                r for r in filtered_reviews 
                if r["submittal_document_id"] == submittal_document_id
            ]
        
        # Paginate
        total = len(filtered_reviews)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_reviews = filtered_reviews[start_idx:end_idx]
        
        # Convert to response format
        review_responses = []
        for review in paginated_reviews:
            review_response = ReviewResponse(
                review_id=review["id"],
                specification_document_id=review["specification_document_id"],
                submittal_document_id=review["submittal_document_id"],
                status=review["status"],
                created_at=review["created_at"],
                started_at=review.get("started_at"),
                completed_at=review.get("completed_at"),
                findings=[Finding(**f) for f in review["findings"]],
                summary=review["summary"],
                confidence_score=review["confidence_score"],
                processing_time_seconds=review["processing_time_seconds"],
                review_scope=review["review_scope"],
                llm_provider=review["llm_provider"],
                llm_model=review["llm_model"],
                error_message=review.get("error_message")
            )
            review_responses.append(review_response)
        
        return ReviewListResponse(
            items=review_responses,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
            has_previous=page > 1
        )
        
    except Exception as e:
        logger.error(f"Failed to list reviews: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list reviews: {str(e)}")


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """Get review details."""
    try:
        if review_id not in reviews_db:
            raise HTTPException(status_code=404, detail="Review not found")
        
        review = reviews_db[review_id]
        
        return ReviewResponse(
            review_id=review["id"],
            specification_document_id=review["specification_document_id"],
            submittal_document_id=review["submittal_document_id"],
            status=review["status"],
            created_at=review["created_at"],
            started_at=review.get("started_at"),
            completed_at=review.get("completed_at"),
            findings=[Finding(**f) for f in review["findings"]],
            summary=review["summary"],
            confidence_score=review["confidence_score"],
            processing_time_seconds=review["processing_time_seconds"],
            review_scope=review["review_scope"],
            llm_provider=review["llm_provider"],
            llm_model=review["llm_model"],
            error_message=review.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get review: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get review: {str(e)}")


@router.get("/reviews/{review_id}/findings")
async def get_review_findings(
    review_id: str,
    finding_type: Optional[FindingType] = Query(None)
):
    """Get findings from a review with optional filtering."""
    try:
        if review_id not in reviews_db:
            raise HTTPException(status_code=404, detail="Review not found")
        
        review = reviews_db[review_id]
        findings = [Finding(**f) for f in review["findings"]]
        
        if finding_type:
            findings = [f for f in findings if f.finding_type == finding_type]
        
        return {
            "review_id": review_id,
            "findings_count": len(findings),
            "findings": [f.dict() for f in findings]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get review findings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get review findings: {str(e)}")


@router.delete("/reviews/{review_id}")
async def delete_review(review_id: str):
    """Delete a review."""
    try:
        if review_id not in reviews_db:
            raise HTTPException(status_code=404, detail="Review not found")
        
        del reviews_db[review_id]
        
        return BaseResponse(
            success=True,
            message=f"Review {review_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete review: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete review: {str(e)}")
