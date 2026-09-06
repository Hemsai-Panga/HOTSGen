"""Image parser for scanned notes and exam pictures using OCRProcessor."""

import logging
from typing import List

from app.ingestion.ocr_processor import OCRError, OCRProcessor
from app.models.extracted_content import ExtractedPageContent

logger = logging.getLogger(__name__)


class ImageParserError(Exception):
    """Raised when image parsing fails."""
    pass


class ImageParser:
    """Parser for image formats (.png, .jpg, .jpeg) using OCR."""

    @staticmethod
    def extract(material_id: str, course_code: str, file_path: str) -> List[ExtractedPageContent]:
        """
        Extract text from an image using the OCR pipeline (grayscale -> contrast enhancement -> OCR).
        """
        try:
            text = OCRProcessor.extract_text_from_image(file_path)
        except OCRError as e:
            logger.error(f"OCR failed for image '{file_path}': {e}")
            raise ImageParserError(str(e))
        except Exception as e:
            logger.error(f"Image processing error for '{file_path}': {type(e).__name__} - {e}")
            raise ImageParserError(f"Image OCR processing failed: {str(e)}")

        return [
            ExtractedPageContent(
                material_id=material_id,
                course_code=course_code,
                page_number=1,
                text=text,
                extraction_method="tesseract_ocr",
                char_count=len(text),
            )
        ]
