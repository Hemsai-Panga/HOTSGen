"""Material document metadata model."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.models.teaching_question import ExamType


class SourceType(str, Enum):
    """Types of course materials uploaded by developer."""
    SYLLABUS = "syllabus"
    LECTURE_MATERIAL = "lecture_material"
    REFERENCE_BOOK = "reference_book"
    EXAM_PAPER = "exam_paper"


class ProcessingStatus(str, Enum):
    """Document ingestion processing lifecycle status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    PENDING = "pending"
    COMPLETED = "completed"


class MaterialCreate(BaseModel):
    """Schema for registering a course material (raw file is stored externally)."""
    course_code: str
    original_filename: str
    stored_filename: str
    source_type: SourceType
    file_type: str = Field(..., description="e.g., pdf, ppt, pptx, doc, docx, png, jpg, jpeg")
    file_size_bytes: int = Field(default=0, ge=0)
    storage_path: str = Field(..., description="External filesystem or object storage path")
    processing_status: ProcessingStatus = ProcessingStatus.UPLOADED
    exam_type: Optional[ExamType] = None
    year: Optional[int] = Field(default=None, ge=2000, le=2100)


class MaterialInDB(BaseModel):
    """Material document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    original_filename: str
    stored_filename: str
    source_type: SourceType
    file_type: str
    file_size_bytes: int = 0
    storage_path: str
    processing_status: ProcessingStatus = ProcessingStatus.UPLOADED
    exam_type: Optional[ExamType] = None
    year: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }


class MaterialAdminResponse(BaseModel):
    """Developer material response schema with administrative metadata."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    original_filename: str
    stored_filename: str
    file_type: str
    source_type: SourceType
    file_size_bytes: int
    processing_status: ProcessingStatus
    exam_type: Optional[ExamType] = None
    year: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
    }
