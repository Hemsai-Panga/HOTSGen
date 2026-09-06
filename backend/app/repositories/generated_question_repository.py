"""Generated question repository managing AI-synthesized HOTS questions."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database import get_generated_questions_collection
from app.models.generated_question import GeneratedQuestionCreate, GeneratedQuestionInDB, ValidationStatus

logger = logging.getLogger(__name__)


def _doc_to_gq(doc: Dict[str, Any]) -> GeneratedQuestionInDB:
    """Convert raw MongoDB document to GeneratedQuestionInDB model, mapping _id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return GeneratedQuestionInDB(**doc_copy)


class GeneratedQuestionRepository:
    """Data access repository for Generated HOTS Questions."""

    @staticmethod
    def save_generated_question(question_in: GeneratedQuestionCreate) -> Optional[GeneratedQuestionInDB]:
        """Persist a generated HOTS question."""
        collection = get_generated_questions_collection()
        if collection is None:
            logger.error("Generated questions collection not available.")
            return None

        doc = question_in.model_dump()
        doc["created_at"] = datetime.now(timezone.utc)

        try:
            result = collection.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if "_id" in doc:
                del doc["_id"]
            return GeneratedQuestionInDB(**doc)
        except Exception as e:
            logger.error(f"Error saving generated question: {type(e).__name__} - {e}")
            return None

    @staticmethod
    def get_generated_question(question_id: str) -> Optional[GeneratedQuestionInDB]:
        """Fetch a generated question by ObjectId."""
        collection = get_generated_questions_collection()
        if collection is None or not ObjectId.is_valid(question_id):
            return None

        doc = collection.find_one({"_id": ObjectId(question_id)})
        return _doc_to_gq(doc) if doc else None

    @staticmethod
    def get_generated_questions_by_course(
        course_code: str,
        limit: int = 50,
    ) -> List[GeneratedQuestionInDB]:
        """Fetch generated questions for a course, sorted newest first."""
        collection = get_generated_questions_collection()
        if collection is None:
            return []

        cursor = (
            collection.find({"course_code": course_code.strip().upper()})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [_doc_to_gq(doc) for doc in cursor]

    @staticmethod
    def update_validation_status(
        question_id: str,
        validation_status: ValidationStatus,
    ) -> bool:
        """Update the validation state of a generated question."""
        collection = get_generated_questions_collection()
        if collection is None or not ObjectId.is_valid(question_id):
            return False

        status_val = (
            validation_status.value
            if isinstance(validation_status, ValidationStatus)
            else validation_status
        )
        result = collection.update_one(
            {"_id": ObjectId(question_id)},
            {"$set": {"validation_status": status_val}},
        )
        return result.modified_count > 0
