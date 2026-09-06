"""Chunk data model for Retrieval-Augmented Generation (RAG)."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class ChunkCreate(BaseModel):
    """Schema for storing a chunk of text with its metadata and embedding vector."""
    course_code: str
    unit: Optional[int] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    source_type: Optional[str] = None
    material_id: Optional[str] = None
    text: str = Field(..., description="Actual text content used for LLM prompt augmentation")
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding for semantic search")
    chunk_index: int = 0


class ChunkInDB(BaseModel):
    """Chunk document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    unit: Optional[int] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    source_type: Optional[str] = None
    material_id: Optional[str] = None
    text: str
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }
