"""Service layer managing syllabus alignment and content classification for lecture materials and reference books."""

import logging
from typing import List, Optional

from app.ingestion.syllabus_aligner import SyllabusAligner
from app.models.material import SourceType
from app.models.syllabus_alignment import (
    AlignedSegmentInDB,
    AlignmentSummaryResponse,
    MaterialAlignmentDetailResponse,
    ScopeStatus,
)
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.syllabus_alignment_repository import SyllabusAlignmentRepository
from app.services.course_service import CourseNotFoundError
from app.services.material_service import MaterialNotFoundError

logger = logging.getLogger(__name__)

# Supported material categories for syllabus alignment
ALIGNABLE_SOURCE_TYPES = {
    SourceType.LECTURE_MATERIAL,
    SourceType.REFERENCE_BOOK,
}


class SyllabusAlignmentError(Exception):
    """Base exception for syllabus alignment operations."""
    pass


class InvalidMaterialSourceTypeError(SyllabusAlignmentError):
    """Raised when attempting to align a material with an unsupported source type."""
    pass


AlignmentInvalidSourceTypeError = InvalidMaterialSourceTypeError


class UnprocessedMaterialError(SyllabusAlignmentError):
    """Raised when a material has not been processed for text extraction."""
    pass


class MissingSyllabusStructureError(SyllabusAlignmentError):
    """Raised when the associated course does not have an analyzed syllabus."""
    pass


class SyllabusAlignmentService:
    """Service layer coordinating syllabus alignment and content classification."""

    @staticmethod
    def align_material(material_id: str) -> AlignmentSummaryResponse:
        """
        Align extracted content of a lecture material or reference book against course syllabus.
        
        Flow:
        1. Fetch material metadata and validate source_type is lecture_material or reference_book.
        2. Verify associated course exists and possesses structured syllabus units.
        3. Retrieve extracted text segments from MongoDB.
        4. Clear existing alignment records for this material (idempotent re-alignment).
        5. Execute lexical syllabus matching and assign scope_status (in_syllabus, out_of_syllabus, ambiguous).
        6. Persist alignment records in MongoDB.
        """
        # 1. Fetch material metadata
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        # 2. Validate source type
        if material.source_type not in ALIGNABLE_SOURCE_TYPES:
            allowed = ", ".join(t.value for t in ALIGNABLE_SOURCE_TYPES)
            raise InvalidMaterialSourceTypeError(
                f"Material '{material_id}' has source_type '{material.source_type.value}'. "
                f"Only [{allowed}] materials can be aligned against the syllabus."
            )

        # 3. Validate course and syllabus hierarchy presence
        course = CourseRepository.get_course(material.course_code)
        if not course:
            raise CourseNotFoundError(f"Associated course '{material.course_code}' not found.")

        if not course.units:
            raise MissingSyllabusStructureError(
                f"Course '{material.course_code}' does not have an analyzed syllabus hierarchy. "
                "Please upload and analyze the course syllabus first."
            )

        # 4. Fetch extracted text segments from Phase 5
        extracted_pages = ExtractedContentRepository.get_content_by_material(material_id)
        if not extracted_pages:
            raise UnprocessedMaterialError(
                f"Material '{material_id}' has no extracted content records. "
                "Please process the material (/process) before alignment."
            )

        # 5. Idempotent cleanup of old alignment records
        SyllabusAlignmentRepository.delete_alignments_by_material(material_id)

        # 6. Execute alignment against syllabus topic catalog
        aligned_segments = SyllabusAligner.align_content(
            course=course,
            material_id=material_id,
            pages=extracted_pages,
        )

        # 7. Persist aligned segments in MongoDB
        persisted = SyllabusAlignmentRepository.save_alignments_batch(aligned_segments)
        if not persisted:
            raise SyllabusAlignmentError(f"Failed to persist alignment records for material '{material_id}'.")

        # 8. Compute alignment metrics
        total_pages = len(aligned_segments)
        in_syllabus_count = sum(1 for s in aligned_segments if s.scope_status == ScopeStatus.IN_SYLLABUS)
        out_of_syllabus_count = sum(1 for s in aligned_segments if s.scope_status == ScopeStatus.OUT_OF_SYLLABUS)
        ambiguous_count = sum(1 for s in aligned_segments if s.scope_status == ScopeStatus.AMBIGUOUS)

        logger.info(
            f"Aligned material '{material_id}' ({material.course_code}): "
            f"{in_syllabus_count} in-syllabus, {out_of_syllabus_count} out-of-syllabus, {ambiguous_count} ambiguous."
        )

        return AlignmentSummaryResponse(
            material_id=material_id,
            course_code=material.course_code,
            total_pages_aligned=total_pages,
            in_syllabus_count=in_syllabus_count,
            out_of_syllabus_count=out_of_syllabus_count,
            ambiguous_count=ambiguous_count,
            alignment_status="completed",
            message=f"Successfully aligned {total_pages} segments ({in_syllabus_count} in-syllabus, {out_of_syllabus_count} out-of-syllabus, {ambiguous_count} ambiguous).",
        )

    @staticmethod
    def get_material_alignment(material_id: str) -> MaterialAlignmentDetailResponse:
        """Retrieve detailed page-by-page alignment classifications for a material."""
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        segments = SyllabusAlignmentRepository.get_alignments_by_material(material_id)

        in_syllabus_count = sum(1 for s in segments if s.scope_status == ScopeStatus.IN_SYLLABUS)
        out_of_syllabus_count = sum(1 for s in segments if s.scope_status == ScopeStatus.OUT_OF_SYLLABUS)
        ambiguous_count = sum(1 for s in segments if s.scope_status == ScopeStatus.AMBIGUOUS)

        return MaterialAlignmentDetailResponse(
            material_id=material_id,
            course_code=material.course_code,
            total_pages=len(segments),
            in_syllabus_count=in_syllabus_count,
            out_of_syllabus_count=out_of_syllabus_count,
            ambiguous_count=ambiguous_count,
            segments=segments,
        )

    @staticmethod
    def get_course_aligned_content(
        course_code: str,
        scope_status: Optional[ScopeStatus] = None,
        topic_id: Optional[str] = None,
    ) -> List[AlignedSegmentInDB]:
        """Retrieve aligned content segments for a course with optional filters."""
        normalized_code = course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course '{normalized_code}' not found.")

        return SyllabusAlignmentRepository.get_alignments_by_course(
            course_code=normalized_code,
            scope_status=scope_status,
            topic_id=topic_id,
        )
