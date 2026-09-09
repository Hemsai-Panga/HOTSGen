"""Service layer providing metadata-filtered semantic vector search across course knowledge and teaching questions."""

import logging
from typing import List

from app.core.embeddings import EmbeddingGenerator
from app.models.embedding import (
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
    VectorSearchTarget,
)
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository
from app.services.course_service import CourseNotFoundError

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service providing semantic similarity search with strict course and syllabus metadata filtering."""

    @staticmethod
    def search(request: VectorSearchRequest) -> VectorSearchResponse:
        """
        Execute semantic similarity search against either course content chunks or past exam teaching questions.
        """
        normalized_code = request.course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course '{normalized_code}' not found.")

        # 1. Generate query embedding vector
        generator = EmbeddingGenerator.get_instance()
        query_vector = generator.generate_embedding(request.query)

        results: List[VectorSearchResult] = []

        # 2. Search target collection with metadata constraints
        if request.target == VectorSearchTarget.COURSE_CONTENT:
            chunk_matches = ChunkRepository.vector_search_chunks(
                query_vector=query_vector,
                course_code=normalized_code,
                unit_id=request.unit_id,
                topic_id=request.topic_id,
                subtopic_id=request.subtopic_id,
                limit=request.limit,
            )

            for chunk, score in chunk_matches:
                results.append(
                    VectorSearchResult(
                        id=chunk.id or "",
                        text=chunk.text,
                        score=round(score, 4),
                        course_code=chunk.course_code,
                        unit_id=chunk.unit_id,
                        topic_id=chunk.topic_id,
                        subtopic_id=chunk.subtopic_id,
                        source_type=chunk.source_type.value if hasattr(chunk.source_type, "value") else chunk.source_type,
                        source_material_id=chunk.material_id,
                        page_number=chunk.page_number,
                    )
                )

        elif request.target == VectorSearchTarget.TEACHING_QUESTIONS:
            question_matches = TeachingQuestionRepository.vector_search_questions(
                query_vector=query_vector,
                course_code=normalized_code,
                unit_id=request.unit_id,
                topic_id=request.topic_id,
                exam_type=request.exam_type,
                limit=request.limit,
            )

            for q, score in question_matches:
                results.append(
                    VectorSearchResult(
                        id=q.id or "",
                        text=q.question_text,
                        score=round(score, 4),
                        course_code=q.course_code,
                        unit_id=q.unit_id,
                        topic_id=q.topic_id,
                        subtopic_id=q.subtopic_id,
                        source_material_id=q.source_material_id,
                        page_number=q.page_number,
                        question_number=q.question_number,
                        section=q.section,
                        exam_type=q.exam_type.value if hasattr(q.exam_type, "value") else str(q.exam_type),
                        year=q.year,
                        marks=q.marks,
                        question_type=q.question_type,
                        difficulty=q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty) if q.difficulty else None,
                    )
                )

        logger.info(
            f"Vector search for '{request.query[:30]}...' on {request.target.value} ({normalized_code}): "
            f"returned {len(results)} results."
        )

        return VectorSearchResponse(
            query=request.query,
            target=request.target,
            course_code=normalized_code,
            total_results=len(results),
            results=results,
        )
