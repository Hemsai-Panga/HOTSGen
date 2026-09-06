"""Course, Unit, Topic, and Subtopic data models."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


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


class CourseUpdate(BaseModel):
    """Schema for updating an existing course."""
    course_name: Optional[str] = None
    description: Optional[str] = None
    units: Optional[List[Unit]] = None


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
        "json_schema_extra": {
            "example": {
                "course_code": "BCSE301",
                "course_name": "Database Management Systems",
                "description": "Core course covering relational models, SQL, and indexing.",
                "units": [
                    {
                        "unit_number": 1,
                        "unit_name": "Introduction to DBMS & Relational Model",
                        "topics": [
                            {
                                "topic_name": "ER Modeling",
                                "subtopics": [{"title": "Entities and Relationships"}],
                                "cat_designation": "CAT1",
                            }
                        ],
                    }
                ],
            }
        },
    }
