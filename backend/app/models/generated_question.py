"""Generated HOTS question data model."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class BloomLevel(str, Enum):
    """Bloom's Taxonomy Higher Order Thinking Skills levels."""
    APPLY = "Apply"
    ANALYZE = "Analyze"
    EVALUATE = "Evaluate"
    CREATE = "Create"


class ValidationStatus(str, Enum):
    """Quality and syllabus validation status."""
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


class GeneratedQuestionCreate(BaseModel):
    """Schema for persisting a generated HOTS question."""
    course_code: str
    topics: List[str] = Field(default_factory=list)
    cat_designation: Optional[str] = None  # e.g., 'CAT1', 'CAT2', 'FAT'
    bloom_level: BloomLevel
    difficulty: Optional[str] = None
    marks: int = Field(..., ge=1, le=100)
    question_text: str
    retrieved_context_ids: List[str] = Field(default_factory=list, description="IDs of chunks used as RAG context")
    validation_status: ValidationStatus = ValidationStatus.PENDING


class GeneratedQuestionInDB(BaseModel):
    """Generated question document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    topics: List[str] = Field(default_factory=list)
    cat_designation: Optional[str] = None
    bloom_level: BloomLevel
    difficulty: Optional[str] = None
    marks: int
    question_text: str
    retrieved_context_ids: List[str] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }
