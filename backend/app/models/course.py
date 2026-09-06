"""Course, Unit, Topic, and Subtopic data models."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Subtopic(BaseModel):
    """Subtopic within a syllabus topic."""
    title: str
    description: Optional[str] = None


class Topic(BaseModel):
    """Syllabus topic containing optional subtopics and exam designation."""
    topic_name: str
    subtopics: List[Subtopic] = Field(default_factory=list)
    cat_designation: Optional[str] = None  # e.g., 'CAT1', 'CAT2', or None


class Unit(BaseModel):
    """Syllabus unit containing topics."""
    unit_number: int
    unit_name: str
    topics: List[Topic] = Field(default_factory=list)


class CourseCreate(BaseModel):
    """Schema for creating a course."""
    course_code: str = Field(..., min_length=2, max_length=20, description="e.g., BCSE301")
    course_name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None
    units: List[Unit] = Field(default_factory=list)

    @field_validator("course_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Strip and uppercase course code."""
        return v.strip().upper()

    @field_validator("course_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip course name whitespace."""
        return v.strip()


class CourseUpdate(BaseModel):
    """Schema for updating an existing course (course_code cannot be changed)."""
    course_name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = None
    units: Optional[List[Unit]] = None

    @field_validator("course_name")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class CoursePublicResponse(BaseModel):
    """Public course information returned to students without internal metadata."""
    course_code: str
    course_name: str
    description: Optional[str] = None
    units: List[Unit] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
    }


class CourseAdminResponse(BaseModel):
    """Developer course information with administrative metadata."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId string")
    course_code: str
    course_name: str
    description: Optional[str] = None
    units: List[Unit] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
    }


class CourseInDB(BaseModel):
    """Course document representation in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId as string")
    course_code: str
    course_name: str
    description: Optional[str] = None
    units: List[Unit] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }
