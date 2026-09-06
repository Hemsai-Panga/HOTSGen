"""Extracted content repository managing page/slide text records in MongoDB."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database import get_extracted_content_collection
from app.models.extracted_content import ExtractedContentInDB, ExtractedPageContent

logger = logging.getLogger(__name__)


def _doc_to_extracted_content(doc: Dict[str, Any]) -> ExtractedContentInDB:
    """Convert raw MongoDB document to ExtractedContentInDB model, mapping _id to id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return ExtractedContentInDB(**doc_copy)


class ExtractedContentRepository:
    """Data access repository for document extracted page/slide content."""

    @staticmethod
    def save_extracted_content_batch(items: List[ExtractedPageContent]) -> List[ExtractedContentInDB]:
        """Batch insert extracted content documents for a material."""
        collection = get_extracted_content_collection()
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
                persisted.append(ExtractedContentInDB(**docs[i]))
            return persisted
        except Exception as e:
            logger.error(f"Error batch saving extracted content: {type(e).__name__} - {e}")
            return []

    @staticmethod
    def get_content_by_material(material_id: str) -> List[ExtractedContentInDB]:
        """Retrieve all extracted content chunks/pages for a material, ordered by page_number."""
        collection = get_extracted_content_collection()
        if collection is None:
            return []

        cursor = collection.find({"material_id": material_id}).sort("page_number", 1)
        return [_doc_to_extracted_content(doc) for doc in cursor]

    @staticmethod
    def delete_content_by_material(material_id: str) -> int:
        """Delete all extracted content for a material (used during reprocessing)."""
        collection = get_extracted_content_collection()
        if collection is None:
            return 0

        result = collection.delete_many({"material_id": material_id})
        return result.deleted_count
