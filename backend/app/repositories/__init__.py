"""Repositories package providing database access methods for core domain entities."""

from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.generated_question_repository import GeneratedQuestionRepository

__all__ = [
    "CourseRepository",
    "MaterialRepository",
    "ExtractedContentRepository",
    "TeachingQuestionRepository",
    "ChunkRepository",
    "GeneratedQuestionRepository",
]
