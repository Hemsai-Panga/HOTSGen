"""Course repository handling CRUD operations on courses collection."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database import get_courses_collection
from app.models.course import CourseCreate, CourseInDB, CourseUpdate

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when the database connection or collection is unavailable."""
    pass


def _doc_to_course(doc: Dict[str, Any]) -> CourseInDB:
    """Convert raw MongoDB document to CourseInDB model, safely mapping _id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return CourseInDB(**doc_copy)


class CourseRepository:
    """Data access repository for Course entities."""

    @staticmethod
    def create_course(course_in: CourseCreate) -> Optional[CourseInDB]:
        """Insert a new course. Returns the created course, None on duplicate, or raises DatabaseConnectionError."""
        collection = get_courses_collection()
        if collection is None:
            logger.error("Courses collection not available.")
            raise DatabaseConnectionError("Database is unavailable. Could not access courses collection.")

        now = datetime.now(timezone.utc)
        doc = course_in.model_dump()
        doc["course_code"] = doc["course_code"].strip().upper()
        doc["created_at"] = now
        doc["updated_at"] = now

        try:
            result = collection.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if "_id" in doc:
                del doc["_id"]
            return CourseInDB(**doc)
        except DuplicateKeyError:
            logger.warning(f"Course with code '{course_in.course_code}' already exists.")
            return None
        except Exception as e:
            logger.error(f"Error creating course: {type(e).__name__} - {e}")
            raise DatabaseConnectionError(f"Database error during course creation: {type(e).__name__} - {e}")

    @staticmethod
    def get_course(course_code: str) -> Optional[CourseInDB]:
        """Fetch a course by unique course code."""
        collection = get_courses_collection()
        if collection is None:
            raise DatabaseConnectionError("Database is unavailable. Could not access courses collection.")

        normalized_code = course_code.strip().upper()
        try:
            doc = collection.find_one({"course_code": normalized_code})
            return _doc_to_course(doc) if doc else None
        except Exception as e:
            logger.error(f"Error fetching course '{normalized_code}': {type(e).__name__} - {e}")
            raise DatabaseConnectionError(f"Database error while fetching course: {type(e).__name__} - {e}")

    @staticmethod
    def get_course_by_id(course_id: str) -> Optional[CourseInDB]:
        """Fetch a course by MongoDB ObjectId string."""
        collection = get_courses_collection()
        if collection is None:
            raise DatabaseConnectionError("Database is unavailable. Could not access courses collection.")
        if not ObjectId.is_valid(course_id):
            return None

        try:
            doc = collection.find_one({"_id": ObjectId(course_id)})
            return _doc_to_course(doc) if doc else None
        except Exception as e:
            logger.error(f"Error fetching course by id '{course_id}': {type(e).__name__} - {e}")
            raise DatabaseConnectionError(f"Database error while fetching course by id: {type(e).__name__} - {e}")

    @staticmethod
    def list_courses(skip: int = 0, limit: int = 100) -> List[CourseInDB]:
        """List all courses with pagination."""
        collection = get_courses_collection()
        if collection is None:
            raise DatabaseConnectionError("Database is unavailable. Could not access courses collection.")

        try:
            cursor = collection.find({}).skip(skip).limit(limit).sort("course_code", 1)
            return [_doc_to_course(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error listing courses: {type(e).__name__} - {e}")
            raise DatabaseConnectionError(f"Database error while listing courses: {type(e).__name__} - {e}")

    @staticmethod
    def update_course(course_code: str, course_update: CourseUpdate) -> Optional[CourseInDB]:
        """Update an existing course by course code."""
        collection = get_courses_collection()
        if collection is None:
            raise DatabaseConnectionError("Database is unavailable. Could not access courses collection.")

        normalized_code = course_code.strip().upper()
        update_data = {k: v for k, v in course_update.model_dump().items() if v is not None}
        if not update_data:
            return CourseRepository.get_course(normalized_code)

        update_data["updated_at"] = datetime.now(timezone.utc)
        try:
            result = collection.find_one_and_update(
                {"course_code": normalized_code},
                {"$set": update_data},
                return_document=True,
            )
            return _doc_to_course(result) if result else None
        except Exception as e:
            logger.error(f"Error updating course '{normalized_code}': {type(e).__name__} - {e}")
            raise DatabaseConnectionError(f"Database error while updating course: {type(e).__name__} - {e}")

    @staticmethod
    def delete_course(course_code: str) -> bool:
        """Delete a course by course code."""
        collection = get_courses_collection()
        if collection is None:
            raise DatabaseConnectionError("Database is unavailable. Could not access courses collection.")

        normalized_code = course_code.strip().upper()
        try:
            result = collection.delete_one({"course_code": normalized_code})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting course '{normalized_code}': {type(e).__name__} - {e}")
            raise DatabaseConnectionError(f"Database error while deleting course: {type(e).__name__} - {e}")
