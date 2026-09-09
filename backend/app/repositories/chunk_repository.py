"""Chunk repository managing RAG text chunks and their embeddings."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo import UpdateOne
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.core.embeddings import cosine_similarity
from app.database import get_chunks_collection
from app.models.chunk import ChunkCreate, ChunkInDB
from app.models.syllabus_alignment import ScopeStatus

logger = logging.getLogger(__name__)


def _doc_to_chunk(doc: Dict[str, Any]) -> ChunkInDB:
    """Convert raw MongoDB document to ChunkInDB model, mapping _id to id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return ChunkInDB(**doc_copy)


class ChunkRepository:
    """Data access repository for RAG Chunks."""

    @staticmethod
    def create_chunk(chunk_in: ChunkCreate) -> Optional[ChunkInDB]:
        """Insert a single text chunk with metadata."""
        collection = get_chunks_collection()
        if collection is None:
            logger.error("Chunks collection not available.")
            return None

        doc = chunk_in.model_dump()
        doc["created_at"] = datetime.now(timezone.utc)

        try:
            result = collection.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if "_id" in doc:
                del doc["_id"]
            return ChunkInDB(**doc)
        except Exception as e:
            logger.error(f"Error creating chunk: {type(e).__name__} - {e}")
            return None

    @staticmethod
    def create_chunks_batch(chunks_in: List[ChunkCreate]) -> List[ChunkInDB]:
        """Batch insert multiple text chunks."""
        collection = get_chunks_collection()
        if collection is None or not chunks_in:
            return []

        now = datetime.now(timezone.utc)
        docs = []
        for c in chunks_in:
            d = c.model_dump()
            d["created_at"] = now
            docs.append(d)

        try:
            result = collection.insert_many(docs)
            created = []
            for i, inserted_id in enumerate(result.inserted_ids):
                docs[i]["id"] = str(inserted_id)
                if "_id" in docs[i]:
                    del docs[i]["_id"]
                created.append(ChunkInDB(**docs[i]))
            return created
        except Exception as e:
            logger.error(f"Error batch inserting chunks: {type(e).__name__} - {e}")
            return []

    @staticmethod
    def get_chunk(chunk_id: str) -> Optional[ChunkInDB]:
        """Retrieve chunk by ObjectId."""
        collection = get_chunks_collection()
        if collection is None or not ObjectId.is_valid(chunk_id):
            return None

        doc = collection.find_one({"_id": ObjectId(chunk_id)})
        return _doc_to_chunk(doc) if doc else None

    @staticmethod
    def get_chunks_by_material(material_id: str) -> List[ChunkInDB]:
        """Retrieve all chunks created from a specific material."""
        collection = get_chunks_collection()
        if collection is None:
            return []

        cursor = collection.find({"material_id": material_id}).sort("chunk_index", 1)
        return [_doc_to_chunk(doc) for doc in cursor]

    @staticmethod
    def get_chunks_by_course(
        course_code: str,
        unit_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        topic: Optional[str] = None,
        scope_status: Optional[ScopeStatus] = ScopeStatus.IN_SYLLABUS,
        limit: int = 100,
    ) -> List[ChunkInDB]:
        """Retrieve chunks filtered by course and optionally topic/unit."""
        collection = get_chunks_collection()
        if collection is None:
            return []

        query: Dict[str, Any] = {"course_code": course_code.strip().upper()}
        if unit_id is not None:
            query["unit_id"] = unit_id
        if topic_id is not None:
            query["topic_id"] = topic_id
        if topic is not None:
            query["topic"] = topic
        if scope_status is not None:
            query["scope_status"] = scope_status.value if isinstance(scope_status, ScopeStatus) else scope_status

        cursor = collection.find(query).sort("chunk_index", 1).limit(limit)
        return [_doc_to_chunk(doc) for doc in cursor]

    @staticmethod
    def update_chunk_embedding(chunk_id: str, embedding: List[float]) -> bool:
        """Update the embedding vector for a single chunk."""
        collection = get_chunks_collection()
        if collection is None or not ObjectId.is_valid(chunk_id):
            return False

        try:
            res = collection.update_one(
                {"_id": ObjectId(chunk_id)},
                {"$set": {"embedding": embedding}},
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating chunk embedding: {e}")
            return False

    @staticmethod
    def update_chunks_embeddings_batch(updates: List[Tuple[str, List[float]]]) -> int:
        """Bulk update embedding vectors for multiple chunks."""
        collection = get_chunks_collection()
        if collection is None or not updates:
            return 0

        operations = []
        for chunk_id, embedding in updates:
            if ObjectId.is_valid(chunk_id):
                operations.append(
                    UpdateOne(
                        {"_id": ObjectId(chunk_id)},
                        {"$set": {"embedding": embedding}},
                    )
                )

        if not operations:
            return 0

        try:
            result = collection.bulk_write(operations, ordered=False)
            return result.modified_count
        except Exception as e:
            logger.error(f"Error bulk updating chunk embeddings: {e}")
            return 0

    @staticmethod
    def count_chunks(course_code: Optional[str] = None, with_embeddings_only: bool = False) -> int:
        """Count chunks with optional course filter and embedding filter."""
        collection = get_chunks_collection()
        if collection is None:
            return 0

        query: Dict[str, Any] = {}
        if course_code:
            query["course_code"] = course_code.strip().upper()
        if with_embeddings_only:
            query["embedding"] = {"$ne": None}

        return collection.count_documents(query) if hasattr(collection, "count_documents") else len(list(collection.find(query)))

    @staticmethod
    def vector_search_chunks(
        query_vector: List[float],
        course_code: str,
        unit_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        subtopic_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Tuple[ChunkInDB, float]]:
        """
        Execute vector similarity search on course chunks with metadata filtering.
        Attempts MongoDB Atlas $vectorSearch pipeline first, falling back to in-memory cosine ranking.
        """
        collection = get_chunks_collection()
        if collection is None:
            return []

        normalized_code = course_code.strip().upper()
        filter_doc: Dict[str, Any] = {
            "course_code": normalized_code,
            "scope_status": "in_syllabus",
        }
        if unit_id:
            filter_doc["unit_id"] = unit_id
        if topic_id:
            filter_doc["topic_id"] = topic_id
        if subtopic_id:
            filter_doc["subtopic_id"] = subtopic_id

        # 1. Attempt Atlas $vectorSearch aggregation
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
                    "source_type": 1, "material_id": 1, "page_number": 1,
                    "scope_status": 1, "chunk_type": 1, "text": 1,
                    "char_count": 1, "token_count": 1, "embedding": 1,
                    "chunk_index": 1, "created_at": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        try:
            cursor = collection.aggregate(pipeline)
            results = []
            for doc in cursor:
                score = float(doc.get("score", 0.0))
                chunk = _doc_to_chunk(doc)
                results.append((chunk, score))
            if results:
                return results
        except Exception as e:
            logger.debug(f"Atlas $vectorSearch not supported on connection ({type(e).__name__}); using cosine fallback.")

        # 2. In-memory / local fallback ranking for testing & local development
        cursor = collection.find(filter_doc)
        scored_chunks: List[Tuple[ChunkInDB, float]] = []
        for doc in cursor:
            emb = doc.get("embedding")
            if emb and isinstance(emb, list) and len(emb) == len(query_vector):
                score = cosine_similarity(query_vector, emb)
                chunk = _doc_to_chunk(doc)
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:limit]

    @staticmethod
    def delete_chunks_by_material(material_id: str) -> int:
        """Delete all chunks associated with a specific material (e.g. on re-ingestion)."""
        collection = get_chunks_collection()
        if collection is None:
            return 0

        try:
            result = collection.delete_many({"material_id": material_id})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting chunks for material '{material_id}': {e}")
            return 0

    @staticmethod
    def delete_chunks_by_course(course_code: str) -> int:
        """Delete all chunks for a given course."""
        collection = get_chunks_collection()
        if collection is None:
            return 0

        try:
            result = collection.delete_many({"course_code": course_code.strip().upper()})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting chunks for course '{course_code}': {e}")
            return 0
