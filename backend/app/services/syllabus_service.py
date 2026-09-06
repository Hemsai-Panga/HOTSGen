"""Syllabus analysis service coordinating hierarchy extraction and course model updates."""

import logging
from app.ingestion.syllabus_parser import SyllabusParser, SyllabusParsingError
from app.models.course import CourseUpdate, PublicSyllabusResponse, SyllabusAnalysisResponse
from app.models.material import ProcessingStatus, SourceType
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository
from app.services.course_service import CourseNotFoundError
from app.services.material_service import MaterialNotFoundError

logger = logging.getLogger(__name__)


class SyllabusServiceError(Exception):
    """Base exception for syllabus service errors."""
    pass


class InvalidMaterialSourceTypeError(SyllabusServiceError):
    """Raised when attempting to analyze a material that is not a syllabus."""
    pass


class ExtractedContentNotFoundError(SyllabusServiceError):
    """Raised when a material has no extracted text records."""
    pass


class SyllabusService:
    """Service layer orchestrating syllabus analysis and course hierarchy updates."""

    @staticmethod
    def analyze_syllabus(material_id: str) -> SyllabusAnalysisResponse:
        """
        Analyze extracted syllabus text and populate the structured course hierarchy.
        
        Flow:
        1. Retrieve material metadata from MongoDB.
        2. Validate that source_type is 'syllabus'.
        3. Verify associated course exists.
        4. Retrieve extracted text records from MongoDB.
        5. Parse units, topics, subtopics deterministically.
        6. Persist structured units hierarchy into the Course document.
        """
        # 1. Fetch material metadata
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        # 2. Validate source_type
        source_type_val = material.source_type.value if hasattr(material.source_type, "value") else str(material.source_type)
        if source_type_val != SourceType.SYLLABUS.value:
            raise InvalidMaterialSourceTypeError(
                f"Material '{material_id}' has source_type '{source_type_val}'. "
                "Only materials of type 'syllabus' can be analyzed."
            )

        # 3. Validate course existence
        course = CourseRepository.get_course(material.course_code)
        if not course:
            raise CourseNotFoundError(f"Associated course '{material.course_code}' not found.")

        # 4. Fetch extracted content from MongoDB
        extracted_pages = ExtractedContentRepository.get_content_by_material(material_id)
        if not extracted_pages:
            raise ExtractedContentNotFoundError(
                f"No extracted content found for material '{material_id}'. "
                "Please trigger document processing (/process) first."
            )

        # Combine text across all pages in sequence
        combined_text = "\n\n".join(page.text for page in extracted_pages if page.text.strip())
        if not combined_text.strip():
            raise ExtractedContentNotFoundError(
                f"Extracted content for material '{material_id}' contains no readable text."
            )

        # 5. Parse syllabus hierarchy deterministically
        try:
            units = SyllabusParser.parse_syllabus(
                course_code=material.course_code,
                raw_text=combined_text,
            )
        except SyllabusParsingError as e:
            logger.error(f"Syllabus parsing failed for material '{material_id}': {e}")
            raise SyllabusServiceError(str(e))

        # 6. Update course document in MongoDB (idempotent replacement)
        course_update = CourseUpdate(units=units)
        updated_course = CourseRepository.update_course(material.course_code, course_update)
        if not updated_course:
            raise SyllabusServiceError(f"Failed to update syllabus structure for course '{material.course_code}'.")

        # 7. Update material status
        MaterialRepository.update_material_status(
            material_id=material_id,
            status=ProcessingStatus.PROCESSED,
        )

        units_count = len(units)
        topics_count = sum(len(u.topics) for u in units)
        subtopics_count = sum(len(t.subtopics) for u in units for t in u.topics)

        logger.info(
            f"Syllabus analyzed for '{material.course_code}': "
            f"{units_count} units, {topics_count} topics, {subtopics_count} subtopics."
        )

        return SyllabusAnalysisResponse(
            material_id=material_id,
            course_code=material.course_code,
            units_count=units_count,
            topics_count=topics_count,
            subtopics_count=subtopics_count,
            status="analyzed",
            message=f"Successfully structured syllabus into {units_count} units and {topics_count} topics.",
        )

    @staticmethod
    def get_course_syllabus(course_code: str) -> PublicSyllabusResponse:
        """
        Retrieve structured syllabus hierarchy for public/student view.
        """
        normalized_code = course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course '{normalized_code}' not found.")

        return PublicSyllabusResponse(
            course_code=course.course_code,
            course_name=course.course_name,
            description=course.description,
            units=course.units,
        )
