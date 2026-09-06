"""OCR processor handling image preprocessing (grayscale -> contrast enhancement) and Tesseract extraction."""

import io
import logging
import os
import shutil
from typing import Union
from PIL import Image, ImageEnhance
import pytesseract

from app.config import get_settings

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Raised when optical character recognition fails or Tesseract is misconfigured."""
    pass


class OCRProcessor:
    """Handles optical character recognition with standardized preprocessing."""

    @staticmethod
    def _configure_tesseract() -> None:
        """Configure the pytesseract binary path from settings if available."""
        settings = get_settings()
        custom_cmd = settings.TESSERACT_CMD_PATH

        if custom_cmd and os.path.exists(custom_cmd):
            pytesseract.pytesseract.tesseract_cmd = custom_cmd
        else:
            # Fallback to PATH lookup
            which_tesseract = shutil.which("tesseract")
            if which_tesseract:
                pytesseract.pytesseract.tesseract_cmd = which_tesseract

    @staticmethod
    def is_available() -> bool:
        """Check whether Tesseract binary is accessible on the system."""
        OCRProcessor._configure_tesseract()
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @staticmethod
    def preprocess_image(image: Image.Image) -> Image.Image:
        """
        Standardized OCR Preprocessing:
        Grayscale -> Contrast Enhancement (1.8x).
        Avoids aggressive binarization/thresholding unless needed.
        """
        # 1. Convert to grayscale
        gray_image = image.convert("L")

        # 2. Contrast enhancement
        enhancer = ImageEnhance.Contrast(gray_image)
        enhanced_image = enhancer.enhance(1.8)

        return enhanced_image

    @staticmethod
    def extract_text_from_image(image_input: Union[Image.Image, bytes, str]) -> str:
        """
        Preprocess image and extract text using Tesseract OCR.
        
        Args:
            image_input: PIL Image, raw image bytes, or filesystem path.
            
        Returns:
            Extracted text string.
            
        Raises:
            OCRError: If Tesseract is unavailable, misconfigured, or OCR execution fails.
        """
        OCRProcessor._configure_tesseract()

        try:
            if isinstance(image_input, bytes):
                image = Image.open(io.BytesIO(image_input))
            elif isinstance(image_input, str):
                image = Image.open(image_input)
            elif isinstance(image_input, Image.Image):
                image = image_input
            else:
                raise ValueError("Unsupported image input type for OCR.")

            # Apply agreed preprocessing: Grayscale -> Contrast Enhancement
            processed_image = OCRProcessor.preprocess_image(image)

            # Perform OCR
            text = pytesseract.image_to_string(processed_image, lang="eng")
            return text.strip()
        except pytesseract.TesseractNotFoundError as e:
            settings = get_settings()
            logger.error(f"Tesseract OCR executable not found at '{settings.TESSERACT_CMD_PATH}': {e}")
            raise OCRError(
                f"Tesseract OCR is not installed or not found at path '{settings.TESSERACT_CMD_PATH}'."
            )
        except pytesseract.TesseractError as e:
            logger.error(f"Tesseract OCR processing error: {e}")
            raise OCRError(f"OCR execution failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during OCR processing: {type(e).__name__} - {e}")
            raise OCRError(f"OCR processing failed: {str(e)}")
