"""Chunk data model for Retrieval-Augmented Generation (RAG)."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.material import SourceType
from app.models.syllabus_alignment import ScopeStatus


class ChunkCreate(BaseModel):
    """Schema for storing a chunk of text with its metadata and embedding vector."""
    course_code: str
    unit: Optional[int] = None
    unit_id: Optional[str] = None
    topic: Optional[str] = None
    topic_id: Optional[str] = None
    subtopic: Optional[str] = None
    subtopic_id: Optional[str] = None
    source_type: Optional[SourceType] = None
    material_id: Optional[str] = None
    page_number: Optional[int] = None
    scope_status: ScopeStatus = ScopeStatus.IN_SYLLABUS
    chunk_type: str = "course_content"
    text: str = Field(..., description="Actual text content used for LLM prompt augmentation")
    char_count: int = 0
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding for semantic search (prepared in future phase)")
    chunk_index: int = 0


class ChunkInDB(BaseModel):
    """Chunk document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    unit: Optional[int] = None
    unit_id: Optional[str] = None
    topic: Optional[str] = None
    topic_id: Optional[str] = None
    subtopic: Optional[str] = None
    subtopic_id: Optional[str] = None
    source_type: Optional[SourceType] = None
    material_id: Optional[str] = None
    page_number: Optional[int] = None
    scope_status: ScopeStatus = ScopeStatus.IN_SYLLABUS
    chunk_type: str = "course_content"
    text: str
    char_count: int = 0
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }


class ChunkPreparationResponse(BaseModel):
    """Response returned after preparing RAG chunks from an aligned material."""
    material_id: str
    course_code: str
    source_type: str
    total_aligned_pages: int
    in_syllabus_pages: int
    chunks_created: int
    status: str = "completed"
    message: str
    chunks: List[ChunkInDB] = []


class MaterialChunksDetailResponse(BaseModel):
    """Response schema for listing/inspecting chunks of a course material."""
    material_id: str
    course_code: str
    source_type: Optional[str] = None
    total_chunks: int
    chunks: List[ChunkInDB] = []
