import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

logger = logging.getLogger(__name__)

from app.api.deps import get_current_developer
from app.models.course import SyllabusAnalysisResponse
from app.models.chunk import (
    ChunkPreparationResponse,
    MaterialChunksDetailResponse,
)
from app.models.embedding import (
    MaterialEmbeddingResponse,
)
from app.models.pipeline import (
    IngestionPipelineResponse,
    IngestionStatusResponse,
)
from app.models.extracted_content import MaterialProcessResponse
from app.models.material import (
    MaterialAdminResponse,
    SourceType,
)
from app.models.syllabus_alignment import (
    AlignmentSummaryResponse,
    MaterialAlignmentDetailResponse,
)
from app.models.teaching_question import (
    ExamType,
    QuestionExtractionResponse,
    TeachingQuestionDetailResponse,
)
from app.services.chunk_service import (
    ChunkService,
    ChunkServiceError,
    InvalidMaterialSourceTypeForChunkingError,
    UnalignedMaterialChunkError,
)
from app.services.course_service import CourseNotFoundError
from app.services.document_processing_service import (
    DocumentProcessingError,
    DocumentProcessingService,
    EmptyExtractionError,
    StoredFileNotFoundError,
)
from app.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    EmptyMaterialForEmbeddingError,
    InvalidMaterialSourceTypeForEmbeddingError,
)
from app.services.ingestion_service import (
    IngestionPipelineService,
    InvalidMaterialSourceTypeForPipelineError,
)
from app.services.material_service import (
    InvalidMaterialMetadataError,
    MaterialAlreadyExistsError,
    MaterialNotFoundError,
    MaterialService,
    MaterialServiceError,
    UnsupportedFileTypeError,
)
from app.services.syllabus_alignment_service import (
    AlignmentInvalidSourceTypeError,
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
from app.services.teaching_question_service import (
    EmptyQuestionExtractionError,
    NonExamPaperMaterialError,
    TeachingQuestionService,
    TeachingQuestionServiceError,
    UnprocessedExamPaperError,
)

router = APIRouter(dependencies=[Depends(get_current_developer)])


@router.post(
    "",
    response_model=MaterialAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Course Material (Developer Drop Box)",
    description="Developer endpoint to upload course materials (PDF, PPT, PPTX, DOC, DOCX, PNG, JPG).",
)
async def upload_material(
    file: UploadFile = File(..., description="The document or exam paper to upload"),
    course_code: str = Form(..., description="Target university course code (e.g. BCSE301)"),
    source_type: SourceType = Form(..., description="Category: syllabus, lecture_material, reference_book, exam_paper"),
    exam_type: Optional[ExamType] = Form(None, description="Optional: CAT1, CAT2, FAT (if exam_paper)"),
    year: Optional[int] = Form(None, description="Optional exam year (if exam_paper)"),
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> MaterialAdminResponse:
    """Validate, store file on external storage, and record metadata in MongoDB."""
    try:
        created = await MaterialService.upload_material(
            course_code=course_code,
            upload_file=file,
            source_type=source_type,
            exam_type=exam_type,
            year=year,
        )
        return MaterialAdminResponse(
            id=created.id,
            course_code=created.course_code,
            original_filename=created.original_filename,
            stored_filename=created.stored_filename,
            file_type=created.file_type,
            source_type=created.source_type,
            file_size_bytes=created.file_size_bytes,
            processing_status=created.processing_status,
            exam_type=created.exam_type,
            year=created.year,
            error_message=created.error_message,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except (UnsupportedFileTypeError, InvalidMaterialMetadataError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except MaterialAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except MaterialServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during material upload: {type(e).__name__}",
        )


@router.post(
    "/{material_id}/process",
    response_model=MaterialProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Document & Extract Text (Ingestion Stage 1)",
    description="Trigger text extraction, digital parsing, and OCR on an uploaded material file.",
)
def process_material(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> MaterialProcessResponse:
    """Execute text extraction on uploaded material and persist structured pages in MongoDB."""
    try:
        response = DocumentProcessingService.process_material(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except StoredFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except EmptyExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except DocumentProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing material: {type(e).__name__}",
        )


@router.post(
    "/{material_id}/analyze-syllabus",
    response_model=SyllabusAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Syllabus & Build Course Structure",
    description="Analyze extracted syllabus text to construct structured units, topics, and subtopics hierarchy.",
)
def analyze_syllabus(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> SyllabusAnalysisResponse:
    """Parse extracted syllabus text into units/topics and link hierarchy to the course."""
    try:
        response = SyllabusService.analyze_syllabus(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidMaterialSourceTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ExtractedContentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except SyllabusServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during syllabus analysis: {type(e).__name__}",
        )


@router.post(
    "/{material_id}/align-syllabus",
    response_model=AlignmentSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Align Material Content to Course Syllabus",
    description="Classify lecture material or reference book content against syllabus topics (in_syllabus, out_of_syllabus, ambiguous).",
)
def align_material_to_syllabus(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> AlignmentSummaryResponse:
    """Perform deterministic syllabus alignment and persist classification metadata."""
    try:
        response = SyllabusAlignmentService.align_material(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except AlignmentInvalidSourceTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except (UnprocessedMaterialError, MissingSyllabusStructureError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except SyllabusAlignmentError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during syllabus alignment: {type(e).__name__}",
        )


@router.get(
    "/{material_id}/alignment",
    response_model=MaterialAlignmentDetailResponse,
    summary="Get Material Syllabus Alignment Details",
    description="Retrieve detailed page-by-page alignment and scope classifications for an aligned material.",
)
def get_material_alignment(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> MaterialAlignmentDetailResponse:
    """Retrieve alignment details for a material."""
    try:
        response = SyllabusAlignmentService.get_material_alignment(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching material alignment: {type(e).__name__}",
        )


@router.post(
    "/{material_id}/extract-questions",
    response_model=QuestionExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Exam Questions (Teaching File Ingestion)",
    description="Developer endpoint to parse and structure individual exam questions from a processed exam paper.",
)
def extract_exam_questions(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> QuestionExtractionResponse:
    """Parse and persist individual questions from a processed exam paper."""
    try:
        response = TeachingQuestionService.extract_questions_from_material(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except NonExamPaperMaterialError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except UnprocessedExamPaperError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except EmptyQuestionExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except TeachingQuestionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during exam question extraction: {type(e).__name__}",
        )


@router.get(
    "/{material_id}/questions",
    response_model=TeachingQuestionDetailResponse,
    summary="Inspect Material Exam Questions",
    description="Developer endpoint to inspect structured teaching questions extracted from an exam paper.",
)
def get_exam_questions(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> TeachingQuestionDetailResponse:
    """Retrieve all structured teaching questions for an exam paper."""
    try:
        response = TeachingQuestionService.get_material_questions(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching material questions: {type(e).__name__}",
        )


@router.delete(
    "/{material_id}/questions",
    summary="Delete Material Exam Questions",
    description="Developer endpoint to delete all extracted teaching questions for an exam paper material.",
)
def delete_exam_questions(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> Dict[str, Any]:
    """Delete all extracted questions for an exam paper."""
    try:
        deleted_count = TeachingQuestionService.delete_material_questions(material_id)
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} teaching questions for material '{material_id}'.",
            "deleted_count": deleted_count,
        }
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting material questions: {type(e).__name__}",
        )


@router.post(
    "/{material_id}/chunk",
    response_model=ChunkPreparationResponse,
    status_code=status.HTTP_200_OK,
    summary="Prepare RAG Knowledge Chunks",
    description="Developer endpoint to generate context-preserving chunks from in-syllabus aligned course content.",
)
def chunk_material(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> ChunkPreparationResponse:
    """Generate and persist RAG chunks for an in-syllabus aligned material."""
    try:
        response = ChunkService.chunk_material(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidMaterialSourceTypeForChunkingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except UnalignedMaterialChunkError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ChunkServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during chunk preparation: {type(e).__name__}",
        )


@router.get(
    "/{material_id}/chunks",
    response_model=MaterialChunksDetailResponse,
    summary="Inspect Material Knowledge Chunks",
    description="Developer endpoint to inspect generated RAG chunks for a course material.",
)
def get_material_chunks(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> MaterialChunksDetailResponse:
    """Retrieve all RAG chunks for a material."""
    try:
        response = ChunkService.get_material_chunks(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching material chunks: {type(e).__name__}",
        )


@router.delete(
    "/{material_id}/chunks",
    summary="Delete Material Knowledge Chunks",
    description="Developer endpoint to delete all RAG chunks for a course material.",
)
def delete_material_chunks(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> Dict[str, Any]:
    """Delete all chunks for a material."""
    try:
        deleted_count = ChunkService.delete_material_chunks(material_id)
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} chunks for material '{material_id}'.",
            "deleted_count": deleted_count,
        }
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting material chunks: {type(e).__name__}",
        )


@router.post(
    "/{material_id}/generate-embeddings",
    response_model=MaterialEmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Vector Embeddings for Material",
    description="Developer endpoint to generate and persist dense vector embeddings for chunks or exam questions of a material.",
)
def generate_material_embeddings(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> MaterialEmbeddingResponse:
    """Generate and store embedding vectors for a material's chunks or teaching questions."""
    try:
        response = EmbeddingService.generate_material_embeddings(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except (InvalidMaterialSourceTypeForEmbeddingError, EmptyMaterialForEmbeddingError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except EmbeddingServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in generate_material_embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during embedding generation: {type(e).__name__} - {str(e)}",
        )


@router.post(
    "/{material_id}/ingest",
    response_model=IngestionPipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Ingestion Pipeline (Developer)",
    description="Developer endpoint to trigger the end-to-end multi-stage ingestion pipeline for a material in sequential order.",
)
def run_material_ingestion_pipeline(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> IngestionPipelineResponse:
    """Execute the full end-to-end ingestion pipeline for a material."""
    try:
        response = IngestionPipelineService.run_ingestion_pipeline(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidMaterialSourceTypeForPipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error running ingestion pipeline for material '{material_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during pipeline execution: {type(e).__name__} - {str(e)}",
        )


@router.get(
    "/{material_id}/pipeline-status",
    response_model=IngestionStatusResponse,
    summary="Get Ingestion Pipeline Status (Developer)",
    description="Developer endpoint to inspect the multi-stage ingestion state and artifact metrics for a material.",
)
def get_material_pipeline_status(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> IngestionStatusResponse:
    """Inspect current ingestion status and stage-by-stage progress for a material."""
    try:
        response = IngestionPipelineService.get_pipeline_status(material_id)
        return response
    except MaterialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error getting pipeline status for material '{material_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving pipeline status: {type(e).__name__} - {str(e)}",
        )


@router.get(
    "",
    response_model=List[MaterialAdminResponse],
    summary="List Materials (Developer)",
    description="Developer endpoint to view uploaded course materials with optional course filter.",
)
def list_materials_developer(
    course_code: Optional[str] = Query(None, description="Filter materials by course code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> List[MaterialAdminResponse]:
    """List uploaded materials."""
    materials = MaterialService.list_materials(course_code=course_code, skip=skip, limit=limit)
    return [
        MaterialAdminResponse(
            id=m.id,
            course_code=m.course_code,
            original_filename=m.original_filename,
            stored_filename=m.stored_filename,
            file_type=m.file_type,
            source_type=m.source_type,
            file_size_bytes=m.file_size_bytes,
            processing_status=m.processing_status,
            exam_type=m.exam_type,
            year=m.year,
            error_message=m.error_message,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in materials
    ]


@router.get(
    "/{material_id}",
    response_model=MaterialAdminResponse,
    summary="Get Material Metadata (Developer)",
    description="Developer endpoint to view specific material metadata by ID.",
)
def get_material_developer(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> MaterialAdminResponse:
    """Retrieve material metadata by ID."""
    try:
        material = MaterialService.get_material(material_id)
        return MaterialAdminResponse(
            id=material.id,
            course_code=material.course_code,
            original_filename=material.original_filename,
            stored_filename=material.stored_filename,
            file_type=material.file_type,
            source_type=material.source_type,
            file_size_bytes=material.file_size_bytes,
            processing_status=material.processing_status,
            exam_type=material.exam_type,
            year=material.year,
            error_message=material.error_message,
            created_at=material.created_at,
            updated_at=material.updated_at,
        )
    except MaterialNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID '{material_id}' not found",
        )


@router.delete(
    "/{material_id}",
    summary="Delete Material (Developer)",
    description="Developer endpoint to delete a material record and its stored file.",
)
def delete_material_developer(
    material_id: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> Dict[str, str]:
    """Delete material metadata and remove stored file from external storage."""
    try:
        MaterialService.delete_material(material_id)
        return {
            "status": "success",
            "message": f"Material '{material_id}' deleted successfully",
        }
    except MaterialNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID '{material_id}' not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete material: {str(e)}",
        )
