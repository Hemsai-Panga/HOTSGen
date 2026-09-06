"""Document processing service coordinating file parsing, OCR, and extracted text persistence."""

import logging
import os
from typing import List
from pathlib import Path

from app.ingestion.doc_parser import DOCParser, DOCParserError
from app.ingestion.image_parser import ImageParser, ImageParserError
from app.ingestion.ocr_processor import OCRError
from app.ingestion.pdf_parser import PDFParser, PDFParserError
from app.ingestion.ppt_parser import PPTParser, PPTParserError
from app.models.extracted_content import ExtractedPageContent, MaterialProcessResponse
from app.models.material import ProcessingStatus
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository
from app.services.material_service import MaterialNotFoundError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Base exception for document extraction and processing failures."""
    pass


class StoredFileNotFoundError(DocumentProcessingError):
    """Raised when the stored file referenced in MongoDB is missing from disk."""
    pass


class EmptyExtractionError(DocumentProcessingError):
    """Raised when parsing produces no extractable text."""
    pass


class DocumentProcessingService:
    """Service layer orchestrating document ingestion and text extraction."""

    @staticmethod
    def process_material(material_id: str) -> MaterialProcessResponse:
        """
        Process an existing material:
        1. Retrieve metadata from MongoDB.
        2. Verify stored file presence.
        3. Transition status to 'processing'.
        4. Clean up any previous extraction records (idempotent reprocessing).
        5. Invoke appropriate parser / OCR engine.
        6. Persist extracted pages/slides into extracted_content collection.
        7. Transition status to 'processed' (or 'failed' on error).
        """
        # 1. Fetch material metadata
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        # 2. Check physical file presence
        storage_path = material.storage_path
        if not storage_path or not Path(storage_path).exists():
            error_msg = f"Stored file for material '{material_id}' not found on disk."
            logger.error(error_msg)
            MaterialRepository.update_material_status(
                material_id=material_id,
                status=ProcessingStatus.FAILED,
                error_message=error_msg,
            )
            raise StoredFileNotFoundError(error_msg)

        # 3. Transition to 'processing'
        MaterialRepository.update_material_status(
            material_id=material_id,
            status=ProcessingStatus.PROCESSING,
        )

        # 4. Clean up previous extracted content to prevent duplicate records on reprocessing
        ExtractedContentRepository.delete_content_by_material(material_id)

        # 5. Determine parsing strategy based on file extension
        _, ext = os.path.splitext(storage_path)
        ext_lower = ext.lower()

        extracted_pages: List[ExtractedPageContent] = []

        try:
            if ext_lower == ".pdf":
                extracted_pages = PDFParser.extract(
                    material_id=material_id,
                    course_code=material.course_code,
                    file_path=storage_path,
                )
            elif ext_lower in {".ppt", ".pptx"}:
                extracted_pages = PPTParser.extract(
                    material_id=material_id,
                    course_code=material.course_code,
                    file_path=storage_path,
                )
            elif ext_lower in {".doc", ".docx"}:
                extracted_pages = DOCParser.extract(
                    material_id=material_id,
                    course_code=material.course_code,
                    file_path=storage_path,
                )
            elif ext_lower in {".png", ".jpg", ".jpeg"}:
                extracted_pages = ImageParser.extract(
                    material_id=material_id,
                    course_code=material.course_code,
                    file_path=storage_path,
                )
            else:
                raise UnsupportedFileTypeError(f"Unsupported file format '{ext_lower}' for text extraction.")

        except (PDFParserError, PPTParserError, DOCParserError, ImageParserError, OCRError) as err:
            logger.error(f"Parser error for material '{material_id}': {err}")
            MaterialRepository.update_material_status(
                material_id=material_id,
                status=ProcessingStatus.FAILED,
                error_message=str(err),
            )
            raise DocumentProcessingError(str(err))
        except Exception as e:
            logger.error(f"Unexpected error processing material '{material_id}': {type(e).__name__} - {e}")
            MaterialRepository.update_material_status(
                material_id=material_id,
                status=ProcessingStatus.FAILED,
                error_message=f"Extraction failure: {str(e)}",
            )
            raise DocumentProcessingError(f"Extraction failure: {str(e)}")

        # 6. Validate extraction results
        total_chars = sum(p.char_count for p in extracted_pages)
        if not extracted_pages or total_chars == 0:
            error_msg = "Extracted document contained no readable text."
            logger.warning(f"Material '{material_id}': {error_msg}")
            MaterialRepository.update_material_status(
                material_id=material_id,
                status=ProcessingStatus.FAILED,
                error_message=error_msg,
            )
            raise EmptyExtractionError(error_msg)

        # 7. Persist structured extracted pages in MongoDB
        saved_records = ExtractedContentRepository.save_extracted_content_batch(extracted_pages)
        if not saved_records:
            error_msg = "Failed to save extracted text content in database."
            logger.error(error_msg)
            MaterialRepository.update_material_status(
                material_id=material_id,
                status=ProcessingStatus.FAILED,
                error_message=error_msg,
            )
            raise DocumentProcessingError(error_msg)

        # 8. Transition status to 'processed'
        MaterialRepository.update_material_status(
            material_id=material_id,
            status=ProcessingStatus.PROCESSED,
        )

        # Determine dominant extraction method
        methods = [p.extraction_method for p in extracted_pages]
        primary_method = max(set(methods), key=methods.count) if methods else "unknown"

        logger.info(
            f"Material '{material_id}' processed successfully. "
            f"{len(extracted_pages)} pages/slides extracted ({total_chars} chars) using {primary_method}."
        )

        return MaterialProcessResponse(
            material_id=material_id,
            course_code=material.course_code,
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=len(extracted_pages),
            extraction_method=primary_method,
            total_characters=total_chars,
        )
