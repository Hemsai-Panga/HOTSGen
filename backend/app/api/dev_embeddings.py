import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)

from app.api.deps import get_current_developer
from app.models.embedding import (
    CourseEmbeddingResponse,
    EmbeddingStatusResponse,
    VectorSearchRequest,
    VectorSearchResponse,
)
from app.services.course_service import CourseNotFoundError
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
from app.services.vector_search_service import VectorSearchService

router = APIRouter(dependencies=[Depends(get_current_developer)])


@router.post(
    "/courses/{course_code}/generate-embeddings",
    response_model=CourseEmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk Generate Embeddings for Course",
    description="Developer endpoint to generate and persist dense vector embeddings for all chunks and teaching questions of a course.",
)
def generate_course_embeddings(
    course_code: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> CourseEmbeddingResponse:
    """Bulk generate embeddings for all chunks and past exam questions in a course."""
    try:
        response = EmbeddingService.generate_course_embeddings(course_code)
        return response
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except EmbeddingServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error generating course embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during course embedding generation: {type(e).__name__} - {str(e)}",
        )


@router.get(
    "/embeddings/status",
    response_model=EmbeddingStatusResponse,
    summary="Get Embedding Coverage Status",
    description="Developer endpoint to inspect embedding coverage metrics across knowledge chunks and teaching questions.",
)
def get_embedding_status(
    course_code: Optional[str] = Query(None, description="Optional course code filter"),
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> EmbeddingStatusResponse:
    """Inspect embedding generation status and model configuration."""
    try:
        response = EmbeddingService.get_embedding_status(course_code=course_code)
        return response
    except Exception as e:
        logger.error(f"Error getting embedding status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving embedding status: {type(e).__name__} - {str(e)}",
        )


@router.post(
    "/vector-search",
    response_model=VectorSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Semantic Vector Search Probe",
    description="Developer probe endpoint to test semantic vector retrieval against course knowledge or past exam questions with metadata constraints.",
)
def vector_search(
    request: VectorSearchRequest,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> VectorSearchResponse:
    """Execute metadata-constrained semantic vector search."""
    try:
        response = VectorSearchService.search(request)
        return response
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error executing vector search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during vector search: {type(e).__name__} - {str(e)}",
        )
