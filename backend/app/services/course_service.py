"""Course service handling course domain business rules and validation."""

import logging
from typing import List
from app.models.course import CourseCreate, CourseInDB, CourseUpdate
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository

logger = logging.getLogger(__name__)


class CourseServiceError(Exception):
    """Base exception for course service operations."""
    pass


class CourseAlreadyExistsError(CourseServiceError):
    """Raised when attempting to create a course with a code that already exists."""
    pass


class CourseNotFoundError(CourseServiceError):
    """Raised when the requested course does not exist."""
    pass


class CourseService:
    """Service layer orchestrating course business logic."""

    @staticmethod
    def create_course(course_in: CourseCreate) -> CourseInDB:
        """
        Validate and create a new course.
        Normalizes course_code and ensures uniqueness.
        """
        normalized_code = course_in.course_code.strip().upper()

        # Check for duplicate
        existing = CourseRepository.get_course(normalized_code)
        if existing:
            raise CourseAlreadyExistsError(f"Course with code '{normalized_code}' already exists.")

        created = CourseRepository.create_course(course_in)
        if not created:
            raise CourseAlreadyExistsError(f"Course with code '{normalized_code}' could not be created or already exists.")

        logger.info(f"Course '{normalized_code}' created successfully.")
        return created

    @staticmethod
    def get_course(course_code: str) -> CourseInDB:
        """
        Retrieve a course by its normalized course code.
        Raises CourseNotFoundError if not found.
        """
        normalized_code = course_code.strip().upper()
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course with code '{normalized_code}' not found.")
        return course

    @staticmethod
    def list_courses(skip: int = 0, limit: int = 100) -> List[CourseInDB]:
        """
        List all available courses with pagination.
        """
        return CourseRepository.list_courses(skip=skip, limit=limit)

    @staticmethod
    def update_course(course_code: str, course_update: CourseUpdate) -> CourseInDB:
        """
        Update course metadata (course_name, description).
        Disallows altering course_code.
        """
        normalized_code = course_code.strip().upper()
        existing = CourseRepository.get_course(normalized_code)
        if not existing:
            raise CourseNotFoundError(f"Course with code '{normalized_code}' not found.")

        updated = CourseRepository.update_course(normalized_code, course_update)
        if not updated:
            raise CourseNotFoundError(f"Course with code '{normalized_code}' not found.")

        logger.info(f"Course '{normalized_code}' updated successfully.")
        return updated

    @staticmethod
    def delete_course(course_code: str) -> bool:
        """
        Delete a course.
        
        Safe Deletion Policy:
        - Verifies course exists.
        - Checks for associated materials (if any are present in future milestones).
        - Safely executes deletion from courses repository.
        """
        normalized_code = course_code.strip().upper()
        existing = CourseRepository.get_course(normalized_code)
        if not existing:
            raise CourseNotFoundError(f"Course with code '{normalized_code}' not found.")

        # Safe dependency check: check if materials exist
        materials = MaterialRepository.list_materials_by_course(normalized_code)
        if materials:
            logger.warning(
                f"Course '{normalized_code}' has {len(materials)} associated material records. "
                "Proceeding with course removal."
            )

        success = CourseRepository.delete_course(normalized_code)
        if not success:
            raise CourseNotFoundError(f"Failed to delete course '{normalized_code}'.")

        logger.info(f"Course '{normalized_code}' deleted successfully.")
        return True
