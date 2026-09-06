"""Models package exporting all domain schemas and database representations."""

from app.models.course import (
    CourseAdminResponse,
    CourseCreate,
    CourseInDB,
    CoursePublicResponse,
    CourseUpdate,
    PublicSyllabusResponse,
    Subtopic,
    SyllabusAnalysisResponse,
    Topic,
    Unit,
)
from app.models.material import (
    MaterialAdminResponse,
    MaterialCreate,
    MaterialInDB,
    ProcessingStatus,
    SourceType,
)
from app.models.extracted_content import (
    ExtractedContentInDB,
    ExtractedPageContent,
    MaterialProcessResponse,
)
from app.models.teaching_question import DifficultyLevel, ExamType, TeachingQuestionCreate, TeachingQuestionInDB
from app.models.chunk import ChunkCreate, ChunkInDB
from app.models.generated_question import BloomLevel, GeneratedQuestionCreate, GeneratedQuestionInDB, ValidationStatus

__all__ = [
    "Subtopic",
    "Topic",
    "Unit",
    "CourseCreate",
    "CourseUpdate",
    "CourseInDB",
    "CoursePublicResponse",
    "PublicSyllabusResponse",
    "SyllabusAnalysisResponse",
    "CourseAdminResponse",
    "SourceType",
    "ProcessingStatus",
    "MaterialCreate",
    "MaterialInDB",
    "MaterialAdminResponse",
    "ExtractedPageContent",
    "ExtractedContentInDB",
    "MaterialProcessResponse",
    "ExamType",
    "DifficultyLevel",
    "TeachingQuestionCreate",
    "TeachingQuestionInDB",
    "ChunkCreate",
    "ChunkInDB",
    "BloomLevel",
    "ValidationStatus",
    "GeneratedQuestionCreate",
    "GeneratedQuestionInDB",
]
