"""Material document metadata model."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Types of course materials uploaded by developer."""
    SYLLABUS = "syllabus"
    LECTURE_MATERIAL = "lecture_material"
    REFERENCE_BOOK = "reference_book"
    EXAM_PAPER = "exam_paper"


class ProcessingStatus(str, Enum):
    """Document ingestion processing lifecycle status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MaterialCreate(BaseModel):
    """Schema for registering a course material (raw file is stored externally)."""
    course_code: str
    file_name: str
    source_type: SourceType
    file_type: str = Field(..., description="e.g., pdf, pptx, docx, png, jpg")
    storage_path: str = Field(..., description="External filesystem or object storage path")
    processing_status: ProcessingStatus = ProcessingStatus.PENDING


class MaterialInDB(BaseModel):
    """Material document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    file_name: str
    source_type: SourceType
    file_type: str
    storage_path: str
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }
