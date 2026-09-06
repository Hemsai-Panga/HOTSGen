"""Teaching question repository handling past exam questions used as teaching examples."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database import get_teaching_questions_collection
from app.models.teaching_question import ExamType, TeachingQuestionCreate, TeachingQuestionInDB

logger = logging.getLogger(__name__)


def _doc_to_tq(doc: Dict[str, Any]) -> TeachingQuestionInDB:
    """Convert raw MongoDB document to TeachingQuestionInDB model, mapping _id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return TeachingQuestionInDB(**doc_copy)


class TeachingQuestionRepository:
    """Data access repository for Teaching Questions."""

    @staticmethod
    def create_question(question_in: TeachingQuestionCreate) -> Optional[TeachingQuestionInDB]:
        """Insert a single teaching question."""
        collection = get_teaching_questions_collection()
        if collection is None:
            logger.error("Teaching questions collection not available.")
            return None

        doc = question_in.model_dump()
        doc["created_at"] = datetime.now(timezone.utc)

        try:
            result = collection.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if "_id" in doc:
                del doc["_id"]
            return TeachingQuestionInDB(**doc)
        except Exception as e:
            logger.error(f"Error creating teaching question: {type(e).__name__} - {e}")
            return None

    @staticmethod
    def create_questions_batch(questions_in: List[TeachingQuestionCreate]) -> List[TeachingQuestionInDB]:
        """Insert multiple teaching questions in batch."""
        collection = get_teaching_questions_collection()
        if collection is None or not questions_in:
            return []

        now = datetime.now(timezone.utc)
        docs = []
        for q in questions_in:
            d = q.model_dump()
            d["created_at"] = now
            docs.append(d)

        try:
            result = collection.insert_many(docs)
            created = []
            for i, inserted_id in enumerate(result.inserted_ids):
                docs[i]["id"] = str(inserted_id)
                if "_id" in docs[i]:
                    del docs[i]["_id"]
                created.append(TeachingQuestionInDB(**docs[i]))
            return created
        except Exception as e:
            logger.error(f"Error batch inserting teaching questions: {type(e).__name__} - {e}")
            return []

    @staticmethod
    def get_question(question_id: str) -> Optional[TeachingQuestionInDB]:
        """Retrieve teaching question by ObjectId string."""
        collection = get_teaching_questions_collection()
        if collection is None or not ObjectId.is_valid(question_id):
            return None

        doc = collection.find_one({"_id": ObjectId(question_id)})
        return _doc_to_tq(doc) if doc else None

    @staticmethod
    def get_questions_by_course(
        course_code: str,
        exam_type: Optional[ExamType] = None,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[TeachingQuestionInDB]:
        """Retrieve teaching questions filtered by course, and optionally exam type and topic."""
        collection = get_teaching_questions_collection()
        if collection is None:
            return []

        query: Dict[str, Any] = {"course_code": course_code.strip().upper()}
        if exam_type is not None:
            query["exam_type"] = exam_type.value if isinstance(exam_type, ExamType) else exam_type
        if topic is not None:
            query["topic"] = topic

        cursor = collection.find(query).sort("year", -1).limit(limit)
        return [_doc_to_tq(doc) for doc in cursor]

    @staticmethod
    def delete_question(question_id: str) -> bool:
        """Delete teaching question by ObjectId."""
        collection = get_teaching_questions_collection()
        if collection is None or not ObjectId.is_valid(question_id):
            return False

        result = collection.delete_one({"_id": ObjectId(question_id)})
        return result.deleted_count > 0
