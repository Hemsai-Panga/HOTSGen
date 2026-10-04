"""PPT and PPTX presentation parser using python-pptx."""

import logging
import os
from typing import List
from pptx import Presentation

from app.models.extracted_content import ExtractedPageContent

logger = logging.getLogger(__name__)


class PPTParserError(Exception):
    """Raised when presentation parsing fails."""
    pass


class PPTParser:
    """Parser for PowerPoint (.pptx) presentations."""

    @staticmethod
    def extract(material_id: str, course_code: str, file_path: str) -> List[ExtractedPageContent]:
        """
        Extract text slide-by-slide from a PowerPoint presentation.
        Extracts titles, text frames, tables, and slide notes.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".ppt":
            logger.warning(f"Legacy .ppt binary format encountered: {file_path}")
            raise PPTParserError(
                "Legacy binary '.ppt' files are not supported. Please save or convert to '.pptx' or 'PDF' for parsing."
            )

        try:
            prs = Presentation(file_path)
        except Exception as e:
            logger.error(f"Failed to open PowerPoint file at '{file_path}': {type(e).__name__} - {e}")
            raise PPTParserError(f"Corrupt or unreadable presentation file: {str(e)}")

        slides: List[ExtractedPageContent] = []

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1
            text_fragments: List[str] = []

            # 1. Extract shapes and tables
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        para_text = paragraph.text.strip()
                        if para_text:
                            text_fragments.append(para_text)

                if shape.has_table:
                    for row in shape.table.rows:
                        row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_cells:
                            text_fragments.append(" | ".join(row_cells))

            # 2. Extract notes slide if present
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    text_fragments.append(f"[Notes: {notes_text}]")

            slide_text = "\n".join(text_fragments).strip()

            slides.append(
                ExtractedPageContent(
                    material_id=material_id,
                    course_code=course_code,
                    page_number=slide_num,
                    text=slide_text,
                    extraction_method="python-pptx",
                    char_count=len(slide_text),
                )
            )

        return slides
