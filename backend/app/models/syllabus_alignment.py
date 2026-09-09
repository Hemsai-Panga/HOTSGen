"""Syllabus alignment and content classification data models."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ScopeStatus(str, Enum):
    """Scope determination of material content relative to course syllabus."""
    IN_SYLLABUS = "in_syllabus"
    OUT_OF_SYLLABUS = "out_of_syllabus"
    AMBIGUOUS = "ambiguous"


class AlignedSegment(BaseModel):
    """Alignment data for a single page or slide of course content."""
    material_id: str
    course_code: str
    page_number: int = Field(..., ge=1, description="1-indexed source page or slide number")
    text: str = Field(..., description="Original extracted text content")
    scope_status: ScopeStatus
    unit_id: Optional[str] = Field(None, description="Matched stable unit ID (e.g. BCSE301_U1)")
    topic_id: Optional[str] = Field(None, description="Matched stable topic ID (e.g. BCSE301_U1_T1)")
    subtopic_id: Optional[str] = Field(None, description="Matched stable subtopic ID (e.g. BCSE301_U1_T1_S1)")
    unit_name: Optional[str] = None
    topic_name: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_keywords: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlignedSegmentInDB(BaseModel):
    """Aligned document segment persisted in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId string")
    material_id: str
    course_code: str
    page_number: int
    text: str
    scope_status: ScopeStatus
    unit_id: Optional[str] = None
    topic_id: Optional[str] = None
    subtopic_id: Optional[str] = None
    unit_name: Optional[str] = None
    topic_name: Optional[str] = None
    confidence: float = 0.0
    matched_keywords: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }


class AlignmentSummaryResponse(BaseModel):
    """Concise response model returned upon triggering syllabus alignment."""
    material_id: str
    course_code: str
    total_pages_aligned: int
    in_syllabus_count: int
    out_of_syllabus_count: int
    ambiguous_count: int
    alignment_status: str = "completed"
    message: str = "Material content aligned against course syllabus hierarchy successfully."

    model_config = {
        "populate_by_name": True,
    }


class MaterialAlignmentDetailResponse(BaseModel):
    """Detailed response containing page-by-page alignment classifications."""
    material_id: str
    course_code: str
    total_pages: int
    in_syllabus_count: int
    out_of_syllabus_count: int
    ambiguous_count: int
    segments: List[AlignedSegmentInDB] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
    }
