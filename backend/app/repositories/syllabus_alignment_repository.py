"""Syllabus alignment repository managing content classification records in MongoDB."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database import get_syllabus_alignments_collection
from app.models.syllabus_alignment import AlignedSegment, AlignedSegmentInDB, ScopeStatus

logger = logging.getLogger(__name__)


def _doc_to_aligned_segment(doc: Dict[str, Any]) -> AlignedSegmentInDB:
    """Convert raw MongoDB document to AlignedSegmentInDB model, mapping _id to id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return AlignedSegmentInDB(**doc_copy)


class SyllabusAlignmentRepository:
    """Data access repository for syllabus alignment and content classification segments."""

    @staticmethod
    def save_alignments_batch(items: List[AlignedSegment]) -> List[AlignedSegmentInDB]:
        """Batch insert syllabus alignment documents for a material."""
        collection = get_syllabus_alignments_collection()
        if collection is None or not items:
            return []

        now = datetime.now(timezone.utc)
        docs = []
        for item in items:
            d = item.model_dump()
            d["created_at"] = now
            docs.append(d)

        try:
            result = collection.insert_many(docs)
            persisted = []
            for i, inserted_id in enumerate(result.inserted_ids):
                docs[i]["id"] = str(inserted_id)
                if "_id" in docs[i]:
                    del docs[i]["_id"]
                persisted.append(AlignedSegmentInDB(**docs[i]))
            return persisted
        except Exception as e:
            logger.error(f"Error saving syllabus alignments: {type(e).__name__} - {e}")
            return []

    @staticmethod
    def get_alignments_by_material(material_id: str) -> List[AlignedSegmentInDB]:
        """Retrieve all alignment records for a specific material, ordered by page_number."""
        collection = get_syllabus_alignments_collection()
        if collection is None:
            return []

        cursor = collection.find({"material_id": material_id}).sort("page_number", 1)
        return [_doc_to_aligned_segment(doc) for doc in cursor]

    @staticmethod
    def get_alignments_by_course(
        course_code: str,
        scope_status: Optional[ScopeStatus] = None,
        topic_id: Optional[str] = None,
    ) -> List[AlignedSegmentInDB]:
        """Retrieve alignment records for a course with optional scope or topic filters."""
        collection = get_syllabus_alignments_collection()
        if collection is None:
            return []

        query: Dict[str, Any] = {"course_code": course_code.strip().upper()}
        if scope_status is not None:
            query["scope_status"] = scope_status.value if isinstance(scope_status, ScopeStatus) else scope_status
        if topic_id is not None:
            query["topic_id"] = topic_id

        cursor = collection.find(query).sort("page_number", 1)
        return [_doc_to_aligned_segment(doc) for doc in cursor]

    @staticmethod
    def delete_alignments_by_material(material_id: str) -> int:
        """Delete all alignment records for a material (used during idempotent re-alignment)."""
        collection = get_syllabus_alignments_collection()
        if collection is None:
            return 0

        result = collection.delete_many({"material_id": material_id})
        return result.deleted_count
