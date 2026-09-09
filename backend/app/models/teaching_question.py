"""Teaching question model extracted from CAT/FAT examination papers."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ExamType(str, Enum):
    """Examination types at university."""
    CAT1 = "CAT1"
    CAT2 = "CAT2"
    FAT = "FAT"


class DifficultyLevel(str, Enum):
    """Question difficulty rating."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TeachingQuestionCreate(BaseModel):
    """Schema for creating a teaching question from past exam papers."""
    course_code: str
    unit: Optional[int] = None
    unit_id: Optional[str] = None
    topic: Optional[str] = None
    topic_id: Optional[str] = None
    subtopic: Optional[str] = None
    subtopic_id: Optional[str] = None
    exam_type: ExamType
    year: int = Field(..., ge=2000, le=2100)
    marks: int = Field(default=10, ge=1, le=100)
    question_text: str
    question_number: Optional[str] = None
    section: Optional[str] = None
    subquestions: Optional[List[str]] = None
    difficulty: Optional[DifficultyLevel] = None
    question_type: Optional[str] = None  # e.g., theoretical, design, numerical, scenario, mcq
    source_material_id: Optional[str] = None
    page_number: Optional[int] = None
    confidence: Optional[float] = None
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding for semantic search")


class TeachingQuestionInDB(BaseModel):
    """Teaching question document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    unit: Optional[int] = None
    unit_id: Optional[str] = None
    topic: Optional[str] = None
    topic_id: Optional[str] = None
    subtopic: Optional[str] = None
    subtopic_id: Optional[str] = None
    exam_type: ExamType
    year: int
    marks: int
    question_text: str
    question_number: Optional[str] = None
    section: Optional[str] = None
    subquestions: Optional[List[str]] = None
    difficulty: Optional[DifficultyLevel] = None
    question_type: Optional[str] = None
    source_material_id: Optional[str] = None
    page_number: Optional[int] = None
    confidence: Optional[float] = None
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }


class QuestionExtractionResponse(BaseModel):
    """Response returned after extracting questions from an exam paper material."""
    material_id: str
    course_code: str
    exam_type: ExamType
    year: int
    questions_extracted: int
    status: str = "completed"
    message: str
    questions: List[TeachingQuestionInDB] = []


class TeachingQuestionDetailResponse(BaseModel):
    """Response schema for listing/inspecting questions of an exam paper."""
    material_id: str
    course_code: str
    exam_type: Optional[ExamType] = None
    year: Optional[int] = None
    total_questions: int
    questions: List[TeachingQuestionInDB] = []
