"""PDF parser extracting digital text via PyMuPDF with automatic OCR fallback for scanned pages."""

import io
import logging
from typing import List
import pymupdf

from app.ingestion.ocr_processor import OCRError, OCRProcessor
from app.models.extracted_content import ExtractedPageContent

logger = logging.getLogger(__name__)


class PDFParserError(Exception):
    """Raised when PDF parsing fails."""
    pass


class PDFParser:
    """Parser for digital and scanned PDF documents."""

    @staticmethod
    def extract(material_id: str, course_code: str, file_path: str) -> List[ExtractedPageContent]:
        """
        Extract text page-by-page from a PDF document.
        Uses PyMuPDF for digital text and falls back to OCR for image/scanned pages.
        """
        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            logger.error(f"Failed to open PDF file at '{file_path}': {type(e).__name__} - {e}")
            raise PDFParserError(f"Corrupt or unreadable PDF document: {str(e)}")

        pages: List[ExtractedPageContent] = []

        try:
            for page_idx in range(len(doc)):
                page_num = page_idx + 1
                page = doc[page_idx]

                # 1. Attempt digital text extraction via PyMuPDF
                digital_text = page.get_text().strip()

                if len(digital_text) >= 15:
                    # Clean digital text found
                    pages.append(
                        ExtractedPageContent(
                            material_id=material_id,
                            course_code=course_code,
                            page_number=page_num,
                            text=digital_text,
                            extraction_method="pymupdf",
                            char_count=len(digital_text),
                        )
                    )
                else:
                    # 2. Scanned or empty page -> Fallback to OCR
                    logger.info(f"Page {page_num} in '{file_path}' has low digital text. Attempting OCR.")
                    try:
                        pix = page.get_pixmap(dpi=200)
                        img_bytes = pix.tobytes("png")
                        ocr_text = OCRProcessor.extract_text_from_image(img_bytes)

                        final_text = ocr_text if len(ocr_text) > len(digital_text) else digital_text
                        method = "tesseract_ocr" if len(ocr_text) > len(digital_text) else "pymupdf"

                        pages.append(
                            ExtractedPageContent(
                                material_id=material_id,
                                course_code=course_code,
                                page_number=page_num,
                                text=final_text,
                                extraction_method=method,
                                char_count=len(final_text),
                            )
                        )
                    except OCRError as ocr_err:
                        logger.warning(f"OCR fallback failed on page {page_num}: {ocr_err}")
                        # Keep whatever minimal digital text existed
                        pages.append(
                            ExtractedPageContent(
                                material_id=material_id,
                                course_code=course_code,
                                page_number=page_num,
                                text=digital_text,
                                extraction_method="pymupdf",
                                char_count=len(digital_text),
                            )
                        )
        finally:
            doc.close()

        return pages
