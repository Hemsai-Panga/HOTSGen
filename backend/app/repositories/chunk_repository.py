"""Chunk repository managing RAG text chunks and their embeddings."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database import get_chunks_collection
from app.models.chunk import ChunkCreate, ChunkInDB

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
    def get_chunks_by_course(
        course_code: str,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChunkInDB]:
        """Retrieve chunks filtered by course and optionally topic."""
        collection = get_chunks_collection()
        if collection is None:
            return []

        query: Dict[str, Any] = {"course_code": course_code.strip().upper()}
        if topic is not None:
            query["topic"] = topic

        cursor = collection.find(query).sort("chunk_index", 1).limit(limit)
        return [_doc_to_chunk(doc) for doc in cursor]

    @staticmethod
    def delete_chunks_by_material(material_id: str) -> int:
        """Delete all chunks associated with a specific material (e.g. on re-ingestion)."""
        collection = get_chunks_collection()
        if collection is None:
            return 0

        result = collection.delete_many({"material_id": material_id})
        return result.deleted_count
