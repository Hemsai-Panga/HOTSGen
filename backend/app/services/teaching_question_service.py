"""Service layer managing CAT/FAT exam paper question extraction, structuring, and persistence."""

import logging
from typing import List, Optional

from app.ingestion.exam_question_parser import ExamQuestionParser
from app.models.material import SourceType
from app.models.teaching_question import (
    ExamType,
    QuestionExtractionResponse,
    TeachingQuestionDetailResponse,
    TeachingQuestionInDB,
)
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository
from app.services.course_service import CourseNotFoundError
from app.services.material_service import MaterialNotFoundError

logger = logging.getLogger(__name__)


class TeachingQuestionServiceError(Exception):
    """Base exception for teaching question service errors."""
    pass


class NonExamPaperMaterialError(TeachingQuestionServiceError):
    """Raised when trying to extract exam questions from non-exam_paper material."""
    pass


class UnprocessedExamPaperError(TeachingQuestionServiceError):
    """Raised when an exam paper has not been processed for text extraction."""
    pass


class EmptyQuestionExtractionError(TeachingQuestionServiceError):
    """Raised when no valid exam questions could be extracted from text."""
    pass


class TeachingQuestionService:
    """Service handling past exam question extraction, structuring, and retrieval."""

    @staticmethod
    def extract_questions_from_material(material_id: str) -> QuestionExtractionResponse:
        """
        Extract individual questions from processed CAT1/CAT2/FAT exam paper material and persist them.

        Flow:
        1. Verify material exists.
        2. Validate material source_type is 'exam_paper'.
        3. Verify associated course exists.
        4. Fetch extracted text segments from Phase 5.
        5. Parse individual questions (numbers, subquestions, marks, sections, MCQs).
        6. Deterministically map questions to syllabus hierarchy (if course has analyzed syllabus).
        7. Clear old extracted questions for this material (idempotent re-extraction).
        8. Batch persist structured teaching questions in MongoDB.
        """
        # 1. Fetch material metadata
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        # 2. Validate source_type
        if material.source_type != SourceType.EXAM_PAPER:
            raise NonExamPaperMaterialError(
                f"Material '{material_id}' is of source_type '{material.source_type.value}'. "
                "Only materials of source_type 'exam_paper' can be parsed for exam questions."
            )

        # 3. Validate course
        course = CourseRepository.get_course(material.course_code)
        if not course:
            raise CourseNotFoundError(f"Associated course '{material.course_code}' not found.")

        # 4. Fetch Phase 5 extracted pages
        extracted_pages = ExtractedContentRepository.get_content_by_material(material_id)
        if not extracted_pages:
            raise UnprocessedExamPaperError(
                f"Material '{material_id}' has no extracted content records. "
                "Please process the document (/process) before question extraction."
            )

        # 5. Parse questions from extracted pages
        structured_questions = ExamQuestionParser.parse_pages(
            pages=extracted_pages,
            material=material,
            course=course,
        )

        if not structured_questions:
            raise EmptyQuestionExtractionError(
                f"No questions could be extracted from exam paper material '{material_id}'. "
                "The extracted text may be empty or unparseable."
            )

        # 6. Idempotent cleanup of old records
        TeachingQuestionRepository.delete_questions_by_material(material_id)

        # 7. Batch persist structured questions
        persisted_questions = TeachingQuestionRepository.create_questions_batch(structured_questions)

        exam_type = structured_questions[0].exam_type
        year = structured_questions[0].year
        count = len(persisted_questions)

        logger.info(
            f"Successfully extracted and saved {count} teaching questions for material '{material_id}' "
            f"({material.course_code} {exam_type.value} {year})."
        )

        return QuestionExtractionResponse(
            material_id=material_id,
            course_code=material.course_code,
            exam_type=exam_type,
            year=year,
            questions_extracted=count,
            status="completed",
            message=f"Successfully extracted {count} teaching questions from {exam_type.value} ({year}) exam paper.",
            questions=persisted_questions,
        )

    @staticmethod
    def get_material_questions(material_id: str) -> TeachingQuestionDetailResponse:
        """Retrieve all teaching questions extracted from a specific exam paper material."""
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        questions = TeachingQuestionRepository.get_questions_by_material(material_id)
        exam_type = questions[0].exam_type if questions else material.exam_type
        year = questions[0].year if questions else material.year

        return TeachingQuestionDetailResponse(
            material_id=material_id,
            course_code=material.course_code,
            exam_type=exam_type,
            year=year,
            total_questions=len(questions),
            questions=questions,
        )

    @staticmethod
    def delete_material_questions(material_id: str) -> int:
        """Delete all teaching questions for an exam paper material."""
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        deleted_count = TeachingQuestionRepository.delete_questions_by_material(material_id)
        logger.info(f"Deleted {deleted_count} teaching questions for material '{material_id}'.")
        return deleted_count

    @staticmethod
    def get_questions_by_course(
        course_code: str,
        exam_type: Optional[ExamType] = None,
        topic: Optional[str] = None,
        topic_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[TeachingQuestionInDB]:
        """Retrieve teaching questions for a course with optional filters."""
        normalized_code = course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course '{normalized_code}' not found.")

        return TeachingQuestionRepository.get_questions_by_course(
            course_code=normalized_code,
            exam_type=exam_type,
            topic=topic,
            topic_id=topic_id,
            limit=limit,
        )
