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
from app.services.syllabus_alignment_service import (
    InvalidMaterialSourceTypeError as AlignmentInvalidSourceTypeError,
    MissingSyllabusStructureError,
    SyllabusAlignmentError,
    SyllabusAlignmentService,
    UnprocessedMaterialError,
)
from app.services.syllabus_service import (
    ExtractedContentNotFoundError,
    InvalidMaterialSourceTypeError,
    SyllabusService,
    SyllabusServiceError,
)
from app.services.chunk_service import (
    ChunkService,
    ChunkServiceError,
    InvalidMaterialSourceTypeForChunkingError,
    UnalignedMaterialChunkError,
)
from app.services.teaching_question_service import (
    EmptyQuestionExtractionError,
    NonExamPaperMaterialError,
    TeachingQuestionService,
    TeachingQuestionServiceError,
    UnprocessedExamPaperError,
)
from app.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    EmptyMaterialForEmbeddingError,
    InvalidMaterialSourceTypeForEmbeddingError,
)
from app.services.ingestion_service import (
    IngestionPipelineError,
    IngestionPipelineService,
    InvalidMaterialSourceTypeForPipelineError,
)
from app.services.vector_search_service import VectorSearchService

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
    "SyllabusService",
    "SyllabusServiceError",
    "InvalidMaterialSourceTypeError",
    "ExtractedContentNotFoundError",
    "SyllabusAlignmentService",
    "SyllabusAlignmentError",
    "AlignmentInvalidSourceTypeError",
    "UnprocessedMaterialError",
    "MissingSyllabusStructureError",
    "TeachingQuestionService",
    "TeachingQuestionServiceError",
    "NonExamPaperMaterialError",
    "UnprocessedExamPaperError",
    "EmptyQuestionExtractionError",
    "ChunkService",
    "ChunkServiceError",
    "InvalidMaterialSourceTypeForChunkingError",
    "UnalignedMaterialChunkError",
    "EmbeddingService",
    "EmbeddingServiceError",
    "InvalidMaterialSourceTypeForEmbeddingError",
    "EmptyMaterialForEmbeddingError",
    "IngestionPipelineService",
    "IngestionPipelineError",
    "InvalidMaterialSourceTypeForPipelineError",
    "VectorSearchService",
]
