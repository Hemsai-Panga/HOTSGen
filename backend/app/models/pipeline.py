"""Ingestion pipeline models and schemas for tracking end-to-end processing states."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StageName(str, Enum):
    """Names of discrete processing stages in the ingestion pipeline."""
    EXTRACTION = "extraction"
    SYLLABUS_ANALYSIS = "syllabus_analysis"
    SYLLABUS_ALIGNMENT = "syllabus_alignment"
    CHUNKING = "chunking"
    QUESTION_STRUCTURING = "question_structuring"
    EMBEDDINGS = "embeddings"


class StageStatus(str, Enum):
    """Execution status for an individual pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStageResult(BaseModel):
    """Result and metadata of a single pipeline stage execution."""
    stage: StageName
    status: StageStatus
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class IngestionPipelineResponse(BaseModel):
    """Response payload returned when triggering an end-to-end ingestion pipeline."""
    material_id: str
    course_code: str
    source_type: str
    overall_status: str  # e.g., "completed", "failed", "processing"
    current_stage: Optional[StageName] = None
    stages: List[PipelineStageResult] = []
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class IngestionStatusResponse(BaseModel):
    """Detailed response schema for inspecting the current multi-stage status of a material."""
    material_id: str
    course_code: str
    source_type: str
    processing_status: str
    stages: List[PipelineStageResult] = []
    extracted_page_count: int = 0
    alignment_segment_count: int = 0
    chunk_count: int = 0
    question_count: int = 0
    embeddings_count: int = 0
    is_fully_ingested: bool = False
    last_error: Optional[str] = None
    updated_at: Optional[datetime] = None
