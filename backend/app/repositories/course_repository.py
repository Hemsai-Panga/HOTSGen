"""Course repository handling CRUD operations on courses collection."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database import get_courses_collection
from app.models.course import CourseCreate, CourseInDB, CourseUpdate

logger = logging.getLogger(__name__)


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
        """Insert a new course. Returns the created course or None if duplicate / unavailable."""
        collection = get_courses_collection()
        if collection is None:
            logger.error("Courses collection not available.")
            return None

        now = datetime.now(timezone.utc)
        doc = course_in.model_dump()
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
            return None

    @staticmethod
    def get_course(course_code: str) -> Optional[CourseInDB]:
        """Fetch a course by unique course code."""
        collection = get_courses_collection()
        if collection is None:
            return None

        doc = collection.find_one({"course_code": course_code.strip().upper()})
        if not doc:
            # Fallback to exact match if not uppercase
            doc = collection.find_one({"course_code": course_code.strip()})
        return _doc_to_course(doc) if doc else None

    @staticmethod
    def get_course_by_id(course_id: str) -> Optional[CourseInDB]:
        """Fetch a course by MongoDB ObjectId string."""
        collection = get_courses_collection()
        if collection is None or not ObjectId.is_valid(course_id):
            return None

        doc = collection.find_one({"_id": ObjectId(course_id)})
        return _doc_to_course(doc) if doc else None

    @staticmethod
    def list_courses(skip: int = 0, limit: int = 100) -> List[CourseInDB]:
        """List all courses with pagination."""
        collection = get_courses_collection()
        if collection is None:
            return []

        cursor = collection.find({}).skip(skip).limit(limit).sort("course_code", 1)
        return [_doc_to_course(doc) for doc in cursor]

    @staticmethod
    def update_course(course_code: str, course_update: CourseUpdate) -> Optional[CourseInDB]:
        """Update an existing course by course code."""
        collection = get_courses_collection()
        if collection is None:
            return None

        update_data = {k: v for k, v in course_update.model_dump().items() if v is not None}
        if not update_data:
            return CourseRepository.get_course(course_code)

        update_data["updated_at"] = datetime.now(timezone.utc)
        result = collection.find_one_and_update(
            {"course_code": course_code},
            {"$set": update_data},
            return_document=True,
        )
        return _doc_to_course(result) if result else None

    @staticmethod
    def delete_course(course_code: str) -> bool:
        """Delete a course by course code."""
        collection = get_courses_collection()
        if collection is None:
            return False

        result = collection.delete_one({"course_code": course_code})
        return result.deleted_count > 0
