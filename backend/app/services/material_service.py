"""Material service managing course material uploads, metadata validation, and lifecycle."""

import logging
import os
from typing import List, Optional
from fastapi import UploadFile

from app.models.material import (
    MaterialCreate,
    MaterialInDB,
    ProcessingStatus,
    SourceType,
)
from app.models.teaching_question import ExamType
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.services.course_service import CourseNotFoundError
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Supported file extensions for course document upload (modern XML-based/digital formats)
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".pptx",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
}


class MaterialServiceError(Exception):
    """Base exception for material service errors."""
    pass


class UnsupportedFileTypeError(MaterialServiceError):
    """Raised when an uploaded file extension is not supported."""
    pass


class MaterialAlreadyExistsError(MaterialServiceError):
    """Raised when a material with the same filename already exists in the course."""
    pass


class MaterialNotFoundError(MaterialServiceError):
    """Raised when the requested material is not found."""
    pass


class InvalidMaterialMetadataError(MaterialServiceError):
    """Raised when provided material metadata is invalid."""
    pass


class MaterialService:
    """Service layer coordinating material file upload, storage, and metadata indexing."""

    @staticmethod
    async def upload_material(
        course_code: str,
        upload_file: UploadFile,
        source_type: SourceType,
        exam_type: Optional[ExamType] = None,
        year: Optional[int] = None,
    ) -> MaterialInDB:
        """
        Validate, store, and record a new course material.
        
        Flow:
        1. Normalize and verify that course_code exists.
        2. Validate supported file extension.
        3. Check for duplicates in course knowledge base.
        4. Write file securely to disk.
        5. Persist metadata in MongoDB with status 'uploaded'.
        6. Clean up file on failure.
        """
        normalized_code = course_code.strip().upper()

        # 1. Course validation
        course = CourseRepository.get_course(normalized_code)
        if not course:
            raise CourseNotFoundError(f"Course with code '{normalized_code}' not found.")

        # 2. File type validation
        original_name = upload_file.filename or "uploaded_file"
        _, ext = os.path.splitext(original_name)
        ext_lower = ext.lower()

        if ext_lower not in ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(ext.lstrip(".") for ext in ALLOWED_EXTENSIONS))
            hint = ""
            if ext_lower in {".ppt", ".doc"}:
                hint = f" Legacy binary '{ext_lower}' files are not supported; please save or convert to '.{ext_lower.lstrip('.')}x' or '.pdf'."
            raise UnsupportedFileTypeError(
                f"File type '{ext_lower}' is not supported. Allowed formats: {allowed_list}.{hint}"
            )

        file_type = ext_lower.lstrip(".")

        # 3. Exam metadata validation
        if source_type == SourceType.EXAM_PAPER:
            if year is not None and not (2000 <= year <= 2100):
                raise InvalidMaterialMetadataError(f"Year must be between 2000 and 2100. Received: {year}")

        # 4. Duplicate check
        existing = MaterialRepository.get_material_by_filename(normalized_code, original_name)
        if existing:
            raise MaterialAlreadyExistsError(
                f"Material with filename '{original_name}' already exists for course '{normalized_code}'."
            )

        # 5. Persist file to external storage
        storage_path = ""
        try:
            _, stored_filename, storage_path, file_size = await StorageService.save_file(
                course_code=normalized_code,
                upload_file=upload_file,
            )
        except Exception as e:
            logger.error(f"File storage failed for {original_name}: {e}")
            raise MaterialServiceError(f"Could not persist uploaded file to storage: {str(e)}")

        # 6. Record metadata in MongoDB
        material_in = MaterialCreate(
            course_code=normalized_code,
            original_filename=original_name,
            stored_filename=stored_filename,
            source_type=source_type,
            file_type=file_type,
            file_size_bytes=file_size,
            storage_path=storage_path,
            processing_status=ProcessingStatus.UPLOADED,
            exam_type=exam_type,
            year=year,
        )

        created_material = MaterialRepository.create_material(material_in)
        if not created_material:
            # Rollback file creation if DB insert fails
            logger.error(f"DB insert failed for material {original_name}. Rolling back stored file.")
            StorageService.delete_file(storage_path)
            raise MaterialServiceError("Failed to persist material record in database.")

        logger.info(f"Material '{original_name}' uploaded successfully for course '{normalized_code}'.")
        return created_material

    @staticmethod
    def get_material(material_id: str) -> MaterialInDB:
        """
        Retrieve material metadata by ID.
        Raises MaterialNotFoundError if missing.
        """
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")
        return material

    @staticmethod
    def list_materials(
        course_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[MaterialInDB]:
        """List materials with optional course filter and pagination."""
        normalized_code = course_code.strip().upper() if course_code else None
        return MaterialRepository.list_materials(course_code=normalized_code, skip=skip, limit=limit)

    @staticmethod
    def delete_material(material_id: str) -> bool:
        """
        Delete a material: removes MongoDB record and removes stored file from external storage.
        """
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        # Delete database record
        deleted_from_db = MaterialRepository.delete_material(material_id)
        if not deleted_from_db:
            raise MaterialServiceError(f"Failed to delete material '{material_id}' from database.")

        # Delete physical file from disk
        if material.storage_path:
            StorageService.delete_file(material.storage_path)

        logger.info(f"Material '{material_id}' ({material.original_filename}) deleted successfully.")
        return True
