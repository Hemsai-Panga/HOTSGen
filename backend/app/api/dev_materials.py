"""Developer material management, Drop Box, Document Processing, and Syllabus Analysis API routes."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import get_current_developer
from app.models.course import SyllabusAnalysisResponse
from app.models.extracted_content import MaterialProcessResponse
from app.models.material import (
    MaterialAdminResponse,
    SourceType,
)
from app.models.teaching_question import ExamType
from app.services.course_service import CourseNotFoundError
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
from app.services.syllabus_service import (
    ExtractedContentNotFoundError,
    InvalidMaterialSourceTypeError,
    SyllabusService,
    SyllabusServiceError,
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
