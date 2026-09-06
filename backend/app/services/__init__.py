"""Services package providing business logic and orchestration."""

from app.services.course_service import (
    CourseAlreadyExistsError,
    CourseNotFoundError,
    CourseService,
    CourseServiceError,
)
from app.services.document_processing_service import (
    DocumentProcessingError,
    DocumentProcessingService,
    EmptyExtractionError,
    StoredFileNotFoundError,
)
from app.services.material_service import (
    InvalidMaterialMetadataError,
    MaterialAlreadyExistsError,
    MaterialNotFoundError,
    MaterialService,
    MaterialServiceError,
    UnsupportedFileTypeError,
)
from app.services.storage_service import StorageService

__all__ = [
    "CourseService",
    "CourseServiceError",
    "CourseAlreadyExistsError",
    "CourseNotFoundError",
    "MaterialService",
    "MaterialServiceError",
    "UnsupportedFileTypeError",
    "MaterialAlreadyExistsError",
    "MaterialNotFoundError",
    "InvalidMaterialMetadataError",
    "StorageService",
    "DocumentProcessingService",
    "DocumentProcessingError",
    "StoredFileNotFoundError",
    "EmptyExtractionError",
]
