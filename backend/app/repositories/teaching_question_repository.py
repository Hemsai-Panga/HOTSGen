"""Teaching question repository handling past exam questions used as teaching examples."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo import UpdateOne
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.core.embeddings import cosine_similarity
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
    def get_questions_by_material(material_id: str) -> List[TeachingQuestionInDB]:
        """Retrieve all teaching questions extracted from a specific material."""
        collection = get_teaching_questions_collection()
        if collection is None:
            return []

        cursor = collection.find({"source_material_id": material_id}).sort("page_number", 1)
        return [_doc_to_tq(doc) for doc in cursor]

    @staticmethod
    def get_questions_by_course(
        course_code: str,
        exam_type: Optional[ExamType] = None,
        topic: Optional[str] = None,
        topic_id: Optional[str] = None,
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
        if topic_id is not None:
            query["topic_id"] = topic_id

        cursor = collection.find(query).sort("year", -1).limit(limit)
        return [_doc_to_tq(doc) for doc in cursor]

    @staticmethod
    def update_question_embedding(question_id: str, embedding: List[float]) -> bool:
        """Update the embedding vector for a single teaching question."""
        collection = get_teaching_questions_collection()
        if collection is None or not ObjectId.is_valid(question_id):
            return False

        try:
            res = collection.update_one(
                {"_id": ObjectId(question_id)},
                {"$set": {"embedding": embedding}},
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating question embedding: {e}")
            return False

    @staticmethod
    def update_questions_embeddings_batch(updates: List[Tuple[str, List[float]]]) -> int:
        """Bulk update embedding vectors for multiple teaching questions."""
        collection = get_teaching_questions_collection()
        if collection is None or not updates:
            return 0

        operations = []
        for q_id, embedding in updates:
            if ObjectId.is_valid(q_id):
                operations.append(
                    UpdateOne(
                        {"_id": ObjectId(q_id)},
                        {"$set": {"embedding": embedding}},
                    )
                )

        if not operations:
            return 0

        try:
            result = collection.bulk_write(operations, ordered=False)
            return result.modified_count
        except Exception as e:
            logger.error(f"Error bulk updating question embeddings: {e}")
            return 0

    @staticmethod
    def count_questions(course_code: Optional[str] = None, with_embeddings_only: bool = False) -> int:
        """Count teaching questions with optional course and embedding filters."""
        collection = get_teaching_questions_collection()
        if collection is None:
            return 0

        query: Dict[str, Any] = {}
        if course_code:
            query["course_code"] = course_code.strip().upper()
        if with_embeddings_only:
            query["embedding"] = {"$ne": None}

        return collection.count_documents(query) if hasattr(collection, "count_documents") else len(list(collection.find(query)))

    @staticmethod
    def vector_search_questions(
        query_vector: List[float],
        course_code: str,
        unit_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        exam_type: Optional[ExamType] = None,
        limit: int = 5,
    ) -> List[Tuple[TeachingQuestionInDB, float]]:
        """
        Execute vector similarity search on past exam teaching questions with metadata filtering.
        Attempts MongoDB Atlas $vectorSearch pipeline first, falling back to in-memory cosine ranking.
        """
        collection = get_teaching_questions_collection()
        if collection is None:
            return []

        normalized_code = course_code.strip().upper()
        filter_doc: Dict[str, Any] = {
            "course_code": normalized_code,
        }
        if unit_id:
            filter_doc["unit_id"] = unit_id
        if topic_id:
            filter_doc["topic_id"] = topic_id
        if exam_type:
            filter_doc["exam_type"] = exam_type.value if isinstance(exam_type, ExamType) else exam_type

        settings = get_settings()
        pipeline = [
            {
                "$vectorSearch": {
                    "index": settings.VECTOR_SEARCH_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": max(limit * 10, 20),
                    "limit": limit,
                    "filter": filter_doc,
                }
            },
            {
                "$project": {
                    "_id": 1, "course_code": 1, "unit": 1, "unit_id": 1,
                    "topic": 1, "topic_id": 1, "subtopic": 1, "subtopic_id": 1,
                    "exam_type": 1, "year": 1, "marks": 1, "question_text": 1,
                    "question_number": 1, "section": 1, "subquestions": 1,
                    "difficulty": 1, "question_type": 1, "source_material_id": 1,
                    "page_number": 1, "confidence": 1, "embedding": 1,
                    "created_at": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        try:
            cursor = collection.aggregate(pipeline)
            results = []
            for doc in cursor:
                score = float(doc.get("score", 0.0))
                q = _doc_to_tq(doc)
                results.append((q, score))
            if results:
                return results
        except Exception as e:
            logger.debug(f"Atlas $vectorSearch not supported on connection ({type(e).__name__}); using cosine fallback.")

        # In-memory / local fallback ranking for testing & local development
        cursor = collection.find(filter_doc)
        scored_questions: List[Tuple[TeachingQuestionInDB, float]] = []
        for doc in cursor:
            emb = doc.get("embedding")
            if emb and isinstance(emb, list) and len(emb) == len(query_vector):
                score = cosine_similarity(query_vector, emb)
                q = _doc_to_tq(doc)
                scored_questions.append((q, score))

        scored_questions.sort(key=lambda x: x[1], reverse=True)
        return scored_questions[:limit]

    @staticmethod
    def delete_question(question_id: str) -> bool:
        """Delete teaching question by ObjectId."""
        collection = get_teaching_questions_collection()
        if collection is None or not ObjectId.is_valid(question_id):
            return False

        result = collection.delete_one({"_id": ObjectId(question_id)})
        return result.deleted_count > 0

    @staticmethod
    def delete_questions_by_material(material_id: str) -> int:
        """Delete all teaching questions associated with a given source material."""
        collection = get_teaching_questions_collection()
        if collection is None:
            return 0

        try:
            result = collection.delete_many({"source_material_id": material_id})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting teaching questions for material '{material_id}': {e}")
            return 0

    @staticmethod
    def delete_questions_by_course(course_code: str) -> int:
        """Delete all teaching questions for a course."""
        collection = get_teaching_questions_collection()
        if collection is None:
            return 0

        try:
            result = collection.delete_many({"course_code": course_code.strip().upper()})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting teaching questions for course '{course_code}': {e}")
            return 0
