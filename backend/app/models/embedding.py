"""Embedding and Vector Search domain models and request/response schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.teaching_question import DifficultyLevel, ExamType


class VectorSearchTarget(str, Enum):
    """Target collection for vector similarity search."""
    COURSE_CONTENT = "course_content"
    TEACHING_QUESTIONS = "teaching_questions"


class VectorSearchRequest(BaseModel):
    """Request payload for semantic vector search query."""
    query: str = Field(..., min_length=2, description="Semantic text query to search for")
    target: VectorSearchTarget = Field(
        default=VectorSearchTarget.COURSE_CONTENT,
        description="Search either 'course_content' (knowledge chunks) or 'teaching_questions' (exam exemplars)",
    )
    course_code: str = Field(..., description="Target course code filter (e.g. BCSE301)")
    unit_id: Optional[str] = Field(None, description="Optional unit constraint (e.g. BCSE301_U1)")
    topic_id: Optional[str] = Field(None, description="Optional topic constraint (e.g. BCSE301_U1_T1)")
    subtopic_id: Optional[str] = Field(None, description="Optional subtopic constraint")
    exam_type: Optional[ExamType] = Field(None, description="Optional exam type filter for teaching questions")
    limit: int = Field(default=5, ge=1, le=50, description="Max number of ranked results to return")


class VectorSearchResult(BaseModel):
    """A single matched record with similarity score and associated metadata."""
    id: str
    text: str
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    course_code: str
    unit_id: Optional[str] = None
    topic_id: Optional[str] = None
    subtopic_id: Optional[str] = None
    source_type: Optional[str] = None
    source_material_id: Optional[str] = None
    page_number: Optional[int] = None
    # Exam question specific fields
    question_number: Optional[str] = None
    section: Optional[str] = None
    exam_type: Optional[str] = None
    year: Optional[int] = None
    marks: Optional[int] = None
    question_type: Optional[str] = None
    difficulty: Optional[str] = None


class VectorSearchResponse(BaseModel):
    """Response containing ranked semantic search results."""
    query: str
    target: VectorSearchTarget
    course_code: str
    total_results: int
    results: List[VectorSearchResult] = []


class MaterialEmbeddingResponse(BaseModel):
    """Response schema for generating embeddings for a specific material."""
    material_id: str
    course_code: str
    source_type: str
    embedded_count: int
    dimension: int
    status: str = "completed"
    message: str


class CourseEmbeddingResponse(BaseModel):
    """Response schema for bulk embedding all course chunks and exam questions."""
    course_code: str
    chunks_embedded: int
    questions_embedded: int
    total_embedded: int
    dimension: int
    status: str = "completed"
    message: str


class EmbeddingStatusResponse(BaseModel):
    """Response schema for embedding coverage and vector index health."""
    course_code: Optional[str] = None
    total_chunks: int
    chunks_with_embeddings: int
    total_questions: int
    questions_with_embeddings: int
    is_fully_embedded: bool
    model_name: str
    dimension: int
