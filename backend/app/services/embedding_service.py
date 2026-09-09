"""Service layer orchestrating embedding generation and vector storage persistence."""

import logging
from typing import List, Optional, Tuple

from app.config import get_settings
from app.core.embeddings import EmbeddingGenerator, EmbeddingModelError
from app.models.embedding import (
    CourseEmbeddingResponse,
    EmbeddingStatusResponse,
    MaterialEmbeddingResponse,
)
from app.models.material import SourceType
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository
from app.services.course_service import CourseNotFoundError
from app.services.material_service import MaterialNotFoundError

logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    """Base exception for embedding service operations."""
    pass


class InvalidMaterialSourceTypeForEmbeddingError(EmbeddingServiceError):
    """Raised when trying to embed a material type that is not supported."""
    pass


class EmptyMaterialForEmbeddingError(EmbeddingServiceError):
    """Raised when a material has no chunks or questions to embed."""
    pass


class EmbeddingService:
    """Service managing embedding generation and persistence for chunks and teaching questions."""

    @staticmethod
    def generate_material_embeddings(material_id: str) -> MaterialEmbeddingResponse:
        """
        Generate and persist dense vector embeddings for all chunks or questions of a material.
        """
        # 1. Fetch material metadata
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        generator = EmbeddingGenerator.get_instance()
        settings = get_settings()

        # 2. Embed based on material source_type
        if material.source_type in (SourceType.LECTURE_MATERIAL, SourceType.REFERENCE_BOOK):
            chunks = ChunkRepository.get_chunks_by_material(material_id)
            if not chunks:
                raise EmptyMaterialForEmbeddingError(
                    f"Material '{material_id}' has no prepared chunks. "
                    "Please run chunk preparation (/chunk) before generating embeddings."
                )

            texts = [c.text for c in chunks]
            vectors = generator.generate_embeddings_batch(texts)
            updates: List[Tuple[str, List[float]]] = [(c.id, v) for c, v in zip(chunks, vectors) if c.id is not None]
            persisted_count = ChunkRepository.update_chunks_embeddings_batch(updates)

            logger.info(f"Generated and saved embeddings for {persisted_count} chunks of material '{material_id}'.")
            return MaterialEmbeddingResponse(
                material_id=material_id,
                course_code=material.course_code,
                source_type=material.source_type.value,
                embedded_count=persisted_count,
                dimension=generator.dimension,
                status="completed",
                message=f"Successfully generated {persisted_count} embeddings for course content chunks.",
            )

        elif material.source_type == SourceType.EXAM_PAPER:
            questions = TeachingQuestionRepository.get_questions_by_material(material_id)
            if not questions:
                raise EmptyMaterialForEmbeddingError(
                    f"Exam paper '{material_id}' has no extracted questions. "
                    "Please run question extraction (/extract-questions) before generating embeddings."
                )

            texts = [q.question_text for q in questions]
            vectors = generator.generate_embeddings_batch(texts)
            updates = [(q.id, v) for q, v in zip(questions, vectors) if q.id is not None]
            persisted_count = TeachingQuestionRepository.update_questions_embeddings_batch(updates)

            logger.info(f"Generated and saved embeddings for {persisted_count} teaching questions of material '{material_id}'.")
            return MaterialEmbeddingResponse(
                material_id=material_id,
                course_code=material.course_code,
                source_type=material.source_type.value,
                embedded_count=persisted_count,
                dimension=generator.dimension,
                status="completed",
                message=f"Successfully generated {persisted_count} embeddings for past exam teaching questions.",
            )

        else:
            raise InvalidMaterialSourceTypeForEmbeddingError(
                f"Material '{material_id}' is of source_type '{material.source_type.value}'. "
                "Syllabus materials are structural definitions and do not have embedding vectors."
            )

    @staticmethod
    def generate_course_embeddings(course_code: str) -> CourseEmbeddingResponse:
        """
        Bulk generate embeddings for all chunks and teaching questions associated with a course.
        """
        normalized_code = course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course '{normalized_code}' not found.")

        generator = EmbeddingGenerator.get_instance()

        # 1. Embed course chunks
        chunks = ChunkRepository.get_chunks_by_course(normalized_code, limit=10000)
        chunks_embedded = 0
        if chunks:
            chunk_texts = [c.text for c in chunks]
            chunk_vectors = generator.generate_embeddings_batch(chunk_texts)
            chunk_updates = [(c.id, v) for c, v in zip(chunks, chunk_vectors) if c.id is not None]
            chunks_embedded = ChunkRepository.update_chunks_embeddings_batch(chunk_updates)

        # 2. Embed teaching questions
        questions = TeachingQuestionRepository.get_questions_by_course(normalized_code, limit=10000)
        questions_embedded = 0
        if questions:
            q_texts = [q.question_text for q in questions]
            q_vectors = generator.generate_embeddings_batch(q_texts)
            q_updates = [(q.id, v) for q, v in zip(questions, q_vectors) if q.id is not None]
            questions_embedded = TeachingQuestionRepository.update_questions_embeddings_batch(q_updates)

        total = chunks_embedded + questions_embedded
        logger.info(
            f"Bulk embedded course '{normalized_code}': {chunks_embedded} chunks, "
            f"{questions_embedded} questions (total {total})."
        )

        return CourseEmbeddingResponse(
            course_code=normalized_code,
            chunks_embedded=chunks_embedded,
            questions_embedded=questions_embedded,
            total_embedded=total,
            dimension=generator.dimension,
            status="completed",
            message=f"Successfully generated embeddings for {chunks_embedded} chunks and {questions_embedded} teaching questions.",
        )

    @staticmethod
    def get_embedding_status(course_code: Optional[str] = None) -> EmbeddingStatusResponse:
        """
        Retrieve embedding coverage metrics across chunks and teaching questions.
        """
        normalized_code = course_code.strip().upper() if course_code else None

        total_chunks = ChunkRepository.count_chunks(course_code=normalized_code)
        chunks_with_emb = ChunkRepository.count_chunks(course_code=normalized_code, with_embeddings_only=True)

        total_questions = TeachingQuestionRepository.count_questions(course_code=normalized_code)
        questions_with_emb = TeachingQuestionRepository.count_questions(course_code=normalized_code, with_embeddings_only=True)

        total_items = total_chunks + total_questions
        embedded_items = chunks_with_emb + questions_with_emb
        is_fully_embedded = (total_items > 0) and (total_items == embedded_items)

        settings = get_settings()

        return EmbeddingStatusResponse(
            course_code=normalized_code,
            total_chunks=total_chunks,
            chunks_with_embeddings=chunks_with_emb,
            total_questions=total_questions,
            questions_with_embeddings=questions_with_emb,
            is_fully_embedded=is_fully_embedded,
            model_name=settings.EMBEDDING_MODEL_NAME,
            dimension=settings.EMBEDDING_DIMENSION,
        )
