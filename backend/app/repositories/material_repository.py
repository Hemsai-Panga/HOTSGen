"""Material repository handling document metadata storage and processing states."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database import get_materials_collection
from app.models.material import MaterialCreate, MaterialInDB, ProcessingStatus

logger = logging.getLogger(__name__)


def _doc_to_material(doc: Dict[str, Any]) -> MaterialInDB:
    """Convert raw MongoDB document to MaterialInDB model, mapping _id to id."""
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    return MaterialInDB(**doc_copy)


class MaterialRepository:
    """Data access repository for Material metadata."""

    @staticmethod
    def create_material(material_in: MaterialCreate) -> Optional[MaterialInDB]:
        """Register a new material metadata record."""
        collection = get_materials_collection()
        if collection is None:
            logger.error("Materials collection not available.")
            return None

        now = datetime.now(timezone.utc)
        doc = material_in.model_dump()
        doc["course_code"] = doc["course_code"].strip().upper()
        doc["created_at"] = now
        doc["updated_at"] = now

        try:
            result = collection.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if "_id" in doc:
                del doc["_id"]
            return MaterialInDB(**doc)
        except Exception as e:
            logger.error(f"Error registering material: {type(e).__name__} - {e}")
            return None

    @staticmethod
    def get_material(material_id: str) -> Optional[MaterialInDB]:
        """Fetch material by ObjectId string."""
        collection = get_materials_collection()
        if collection is None or not ObjectId.is_valid(material_id):
            return None

        doc = collection.find_one({"_id": ObjectId(material_id)})
        return _doc_to_material(doc) if doc else None

    @staticmethod
    def get_material_by_filename(course_code: str, original_filename: str) -> Optional[MaterialInDB]:
        """Check for existing material with the same filename in a course to prevent duplicates."""
        collection = get_materials_collection()
        if collection is None:
            return None

        doc = collection.find_one({
            "course_code": course_code.strip().upper(),
            "original_filename": original_filename.strip(),
        })
        return _doc_to_material(doc) if doc else None

    @staticmethod
    def list_materials(
        course_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[MaterialInDB]:
        """List materials with optional course filter and pagination."""
        collection = get_materials_collection()
        if collection is None:
            return []

        query: Dict[str, Any] = {}
        if course_code:
            query["course_code"] = course_code.strip().upper()

        cursor = collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        return [_doc_to_material(doc) for doc in cursor]

    @staticmethod
    def list_materials_by_course(course_code: str) -> List[MaterialInDB]:
        """List all materials associated with a specific course."""
        return MaterialRepository.list_materials(course_code=course_code)

    @staticmethod
    def update_material_status(
        material_id: str,
        status: ProcessingStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update the ingestion processing status of a material."""
        collection = get_materials_collection()
        if collection is None or not ObjectId.is_valid(material_id):
            return False

        update_fields: Dict[str, Any] = {
            "processing_status": status.value if isinstance(status, ProcessingStatus) else status,
            "updated_at": datetime.now(timezone.utc),
        }
        if error_message is not None:
            update_fields["error_message"] = error_message

        result = collection.update_one(
            {"_id": ObjectId(material_id)},
            {"$set": update_fields},
        )
        return result.modified_count > 0

    @staticmethod
    def delete_material(material_id: str) -> bool:
        """Delete material metadata record."""
        collection = get_materials_collection()
        if collection is None or not ObjectId.is_valid(material_id):
            return False

        result = collection.delete_one({"_id": ObjectId(material_id)})
        return result.deleted_count > 0
