"""Word (.doc, .docx) document parser using python-docx."""

import logging
import os
from typing import List
import docx

from app.models.extracted_content import ExtractedPageContent

logger = logging.getLogger(__name__)


class DOCParserError(Exception):
    """Raised when Word document parsing fails."""
    pass


class DOCParser:
    """Parser for Microsoft Word (.docx, .doc) documents."""

    @staticmethod
    def extract(material_id: str, course_code: str, file_path: str) -> List[ExtractedPageContent]:
        """
        Extract text from a Word document.
        Extracts paragraphs, headings, and table cells.
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".doc":
            # Handle legacy binary doc format
            logger.warning(f"Legacy .doc binary format encountered: {file_path}")
            raise DOCParserError(
                "Legacy binary '.doc' files must be saved or converted to '.docx' or 'PDF' for parsing."
            )

        try:
            doc = docx.Document(file_path)
        except Exception as e:
            logger.error(f"Failed to open DOCX file at '{file_path}': {type(e).__name__} - {e}")
            raise DOCParserError(f"Corrupt or unreadable Word document: {str(e)}")

        text_lines: List[str] = []

        # 1. Extract paragraphs
        for para in doc.paragraphs:
            para_text = para.text.strip()
            if para_text:
                text_lines.append(para_text)

        # 2. Extract tables
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    text_lines.append(" | ".join(row_cells))

        combined_text = "\n".join(text_lines).strip()

        return [
            ExtractedPageContent(
                material_id=material_id,
                course_code=course_code,
                page_number=1,
                text=combined_text,
                extraction_method="python-docx",
                char_count=len(combined_text),
            )
        ]
