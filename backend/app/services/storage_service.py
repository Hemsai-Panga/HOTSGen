"""External file storage service handling secure file persistence and deletion."""

import logging
import os
import re
from pathlib import Path
from typing import Tuple
from uuid import uuid4
from fastapi import UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize an uploaded filename to prevent path traversal and unsafe filesystem characters.
    """
    # Remove directory separators and null bytes
    clean_name = os.path.basename(filename).replace("\x00", "")
    # Remove path traversal tokens
    clean_name = clean_name.replace("..", "")
    # Keep only safe alphanumeric characters, dashes, underscores, and dots
    clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", clean_name)
    # Collapse multiple consecutive underscores
    clean_name = re.sub(r"_+", "_", clean_name).strip("._")
    if not clean_name:
        clean_name = f"file_{uuid4().hex[:8]}"
    return clean_name


class StorageService:
    """Handles secure file persistence in the external storage directory."""

    @staticmethod
    def get_base_storage_dir() -> Path:
        """Resolve and ensure the base storage directory exists."""
        settings = get_settings()
        base_dir = Path(settings.EXTERNAL_STORAGE_PATH).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @staticmethod
    def get_course_storage_dir(course_code: str) -> Path:
        """Resolve and ensure a course-specific storage directory exists."""
        base_dir = StorageService.get_base_storage_dir()
        normalized_code = sanitize_filename(course_code.strip().upper())
        course_dir = (base_dir / normalized_code).resolve()

        # Path traversal guard
        if not str(course_dir).startswith(str(base_dir)):
            raise ValueError(f"Invalid course code causing path traversal: {course_code}")

        course_dir.mkdir(parents=True, exist_ok=True)
        return course_dir

    @staticmethod
    async def save_file(course_code: str, upload_file: UploadFile) -> Tuple[str, str, str, int]:
        """
        Stream an uploaded file to external storage within the course directory.
        
        Returns:
            Tuple of (original_filename, stored_filename, storage_path, file_size_bytes)
        """
        original_name = upload_file.filename or "uploaded_file"
        sanitized_name = sanitize_filename(original_name)
        
        # Split extension
        name_stem, ext = os.path.splitext(sanitized_name)
        ext = ext.lower()
        
        # Generate safe, non-colliding unique stored filename
        unique_prefix = uuid4().hex[:10]
        stored_filename = f"{unique_prefix}_{name_stem}{ext}"

        course_dir = StorageService.get_course_storage_dir(course_code)
        target_path = (course_dir / stored_filename).resolve()

        # Path traversal guard
        if not str(target_path).startswith(str(course_dir)):
            raise ValueError(f"Target file path traverses outside course directory: {stored_filename}")

        file_size_bytes = 0
        try:
            with open(target_path, "wb") as f:
                while chunk := await upload_file.read(1024 * 64):  # 64KB chunks
                    f.write(chunk)
                    file_size_bytes += len(chunk)
            
            logger.info(f"File stored successfully: {target_path} ({file_size_bytes} bytes)")
            return original_name, stored_filename, str(target_path), file_size_bytes
        except Exception as e:
            logger.error(f"Failed to write file to disk: {type(e).__name__} - {e}")
            # Clean up partial file if created
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass
            raise

    @staticmethod
    def delete_file(storage_path: str) -> bool:
        """
        Delete a stored file from the external filesystem.
        Handles already-missing files gracefully.
        """
        if not storage_path:
            return False

        try:
            file_path = Path(storage_path).resolve()
            base_dir = StorageService.get_base_storage_dir()

            # Safety check: ensure path is within base storage directory
            if not str(file_path).startswith(str(base_dir)):
                logger.warning(f"Refusing to delete file outside storage base: {storage_path}")
                return False

            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                logger.info(f"File deleted from storage: {storage_path}")
                return True
            else:
                logger.info(f"File does not exist on disk, skipped: {storage_path}")
                return True
        except Exception as e:
            logger.error(f"Error deleting file '{storage_path}': {type(e).__name__} - {e}")
            return False
