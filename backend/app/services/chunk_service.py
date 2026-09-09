"""Service layer managing RAG content chunking and metadata preparation."""

import logging
from typing import List, Optional

from app.ingestion.content_chunker import ContentChunker
from app.models.chunk import (
    ChunkInDB,
    ChunkPreparationResponse,
    MaterialChunksDetailResponse,
)
from app.models.material import SourceType
from app.models.syllabus_alignment import ScopeStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.syllabus_alignment_repository import SyllabusAlignmentRepository
from app.services.course_service import CourseNotFoundError
from app.services.material_service import MaterialNotFoundError

logger = logging.getLogger(__name__)

CHUNKABLE_SOURCE_TYPES = {
    SourceType.LECTURE_MATERIAL,
    SourceType.REFERENCE_BOOK,
}


class ChunkServiceError(Exception):
    """Base exception for chunking service errors."""
    pass


class InvalidMaterialSourceTypeForChunkingError(ChunkServiceError):
    """Raised when trying to chunk a material that is not lecture_material or reference_book."""
    pass


class UnalignedMaterialChunkError(ChunkServiceError):
    """Raised when trying to chunk a material that has not completed syllabus alignment."""
    pass


class ChunkService:
    """Service orchestrating context-preserving chunking for syllabus-aligned course content."""

    @staticmethod
    def chunk_material(material_id: str) -> ChunkPreparationResponse:
        """
        Prepare RAG chunks from in-syllabus aligned content segments of a material.

        Flow:
        1. Fetch material metadata and validate source_type (lecture_material or reference_book).
        2. Retrieve syllabus alignment records from Phase 7.
        3. Filter only in_syllabus segments.
        4. Execute context-preserving chunking and metadata attachment.
        5. Clear previous chunks for this material (idempotent re-chunking).
        6. Batch persist chunks in MongoDB.
        """
        # 1. Fetch material metadata
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        # 2. Validate source type
        if material.source_type not in CHUNKABLE_SOURCE_TYPES:
            allowed = ", ".join(t.value for t in CHUNKABLE_SOURCE_TYPES)
            raise InvalidMaterialSourceTypeForChunkingError(
                f"Material '{material_id}' is of source_type '{material.source_type.value}'. "
                f"Only [{allowed}] materials can be chunked for course content knowledge base."
            )

        # 3. Retrieve aligned segments
        aligned_segments = SyllabusAlignmentRepository.get_alignments_by_material(material_id)
        if not aligned_segments:
            raise UnalignedMaterialChunkError(
                f"Material '{material_id}' has no syllabus alignment records. "
                "Please run syllabus alignment (/align-syllabus) before generating knowledge chunks."
            )

        total_pages = len(aligned_segments)
        in_syllabus_segments = [s for s in aligned_segments if s.scope_status == ScopeStatus.IN_SYLLABUS]
        in_syllabus_count = len(in_syllabus_segments)

        # 4. Handle 0 in-syllabus content
        if in_syllabus_count == 0:
            ChunkRepository.delete_chunks_by_material(material_id)
            return ChunkPreparationResponse(
                material_id=material_id,
                course_code=material.course_code,
                source_type=material.source_type.value,
                total_aligned_pages=total_pages,
                in_syllabus_pages=0,
                chunks_created=0,
                status="completed",
                message=f"Material '{material_id}' contains 0 in-syllabus segments. No knowledge chunks generated.",
                chunks=[],
            )

        # 5. Generate chunks with metadata
        chunks_to_create = ContentChunker.chunk_material(
            material=material,
            aligned_segments=aligned_segments,
        )

        # 6. Idempotent cleanup of old chunks
        ChunkRepository.delete_chunks_by_material(material_id)

        # 7. Batch insert in MongoDB
        persisted_chunks = ChunkRepository.create_chunks_batch(chunks_to_create)

        logger.info(
            f"Successfully prepared {len(persisted_chunks)} chunks for material '{material_id}' "
            f"({material.course_code} - {in_syllabus_count}/{total_pages} in-syllabus pages)."
        )

        return ChunkPreparationResponse(
            material_id=material_id,
            course_code=material.course_code,
            source_type=material.source_type.value,
            total_aligned_pages=total_pages,
            in_syllabus_pages=in_syllabus_count,
            chunks_created=len(persisted_chunks),
            status="completed",
            message=f"Successfully generated {len(persisted_chunks)} knowledge chunks from {in_syllabus_count} in-syllabus segments.",
            chunks=persisted_chunks,
        )

    @staticmethod
    def get_material_chunks(material_id: str) -> MaterialChunksDetailResponse:
        """Retrieve all knowledge chunks for a material."""
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        chunks = ChunkRepository.get_chunks_by_material(material_id)

        return MaterialChunksDetailResponse(
            material_id=material_id,
            course_code=material.course_code,
            source_type=material.source_type.value,
            total_chunks=len(chunks),
            chunks=chunks,
        )

    @staticmethod
    def delete_material_chunks(material_id: str) -> int:
        """Delete all knowledge chunks for a material."""
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        deleted_count = ChunkRepository.delete_chunks_by_material(material_id)
        logger.info(f"Deleted {deleted_count} chunks for material '{material_id}'.")
        return deleted_count

    @staticmethod
    def get_chunks_by_course(
        course_code: str,
        unit_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChunkInDB]:
        """Retrieve knowledge chunks for a course filtered by syllabus hierarchy."""
        normalized_code = course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course '{normalized_code}' not found.")

        return ChunkRepository.get_chunks_by_course(
            course_code=normalized_code,
            unit_id=unit_id,
            topic_id=topic_id,
            limit=limit,
        )
