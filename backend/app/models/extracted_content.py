"""Extracted document content data models."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from app.models.material import ProcessingStatus


class ExtractedPageContent(BaseModel):
    """Extracted text content from a single page or slide of an ingested material."""
    material_id: str
    course_code: str
    page_number: int = Field(..., ge=1, description="1-indexed page or slide number")
    text: str = Field(..., description="Extracted text content from the page/slide")
    extraction_method: str = Field(..., description="e.g. pymupdf, python-pptx, python-docx, tesseract_ocr")
    char_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractedContentInDB(BaseModel):
    """Extracted document content persisted in MongoDB."""
    id: Optional[str] = Field(None, description="MongoDB ObjectId string")
    material_id: str
    course_code: str
    page_number: int
    text: str
    extraction_method: str
    char_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
    }


class MaterialProcessResponse(BaseModel):
    """Concise response model returned upon completion of document text extraction."""
    material_id: str
    course_code: str
    processing_status: ProcessingStatus
    pages_processed: int
    extraction_method: str
    total_characters: int
    message: str = "Document processed and text extracted successfully"

    model_config = {
        "populate_by_name": True,
    }
