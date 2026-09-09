"""RAG content chunking and metadata enrichment engine for in-syllabus course materials."""

import logging
import re
from typing import List, Optional

from app.models.chunk import ChunkCreate
from app.models.material import MaterialInDB
from app.models.syllabus_alignment import AlignedSegmentInDB, ScopeStatus

logger = logging.getLogger(__name__)

# Splitting thresholds
TARGET_CHUNK_SIZE = 500  # Target character size
MAX_CHUNK_SIZE = 750     # Upper limit before splitting
OVERLAP_SIZE = 80        # Semantic overlap between adjacent chunks in large blocks
MIN_CHUNK_LENGTH = 20    # Discard tiny fragments


class ContentChunker:
    """Chunks in-syllabus lecture notes and reference books with context preservation."""

    @staticmethod
    def split_text_into_chunks(text: str, target_size: int = TARGET_CHUNK_SIZE, max_size: int = MAX_CHUNK_SIZE) -> List[str]:
        """
        Split text into semantically cohesive chunks based on paragraph and sentence boundaries.
        """
        text_clean = text.strip()
        if not text_clean:
            return []

        if len(text_clean) <= max_size:
            return [text_clean]

        # 1. Split into paragraphs
        raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text_clean) if p.strip()]

        # 2. Break down oversized paragraphs by sentence boundaries
        refined_paragraphs: List[str] = []
        for p in raw_paragraphs:
            if len(p) <= max_size:
                refined_paragraphs.append(p)
            else:
                sentences = re.split(r"(?<=[.!?])\s+", p)
                current_sent_buf: List[str] = []
                current_sent_len = 0
                for s in sentences:
                    s_clean = s.strip()
                    if not s_clean:
                        continue
                    if current_sent_len + len(s_clean) + 1 > target_size and current_sent_buf:
                        refined_paragraphs.append(" ".join(current_sent_buf))
                        current_sent_buf = [s_clean]
                        current_sent_len = len(s_clean)
                    else:
                        current_sent_buf.append(s_clean)
                        current_sent_len += len(s_clean) + 1
                if current_sent_buf:
                    refined_paragraphs.append(" ".join(current_sent_buf))

        # 3. Assemble paragraphs into chunks of target size
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in refined_paragraphs:
            para_len = len(para)
            if current_len + para_len + 1 > target_size and current_chunk:
                joined = " ".join(current_chunk).strip()
                if len(joined) >= MIN_CHUNK_LENGTH:
                    chunks.append(joined)
                
                # Retain overlap from previous chunk if available
                last_sentence = current_chunk[-1]
                if len(last_sentence) <= OVERLAP_SIZE:
                    current_chunk = [last_sentence, para]
                    current_len = len(last_sentence) + para_len + 1
                else:
                    current_chunk = [para]
                    current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len + 1

        if current_chunk:
            joined = " ".join(current_chunk).strip()
            if len(joined) >= MIN_CHUNK_LENGTH:
                chunks.append(joined)

        return chunks

    @staticmethod
    def chunk_material(
        material: MaterialInDB,
        aligned_segments: List[AlignedSegmentInDB],
    ) -> List[ChunkCreate]:
        """
        Filter in-syllabus segments and generate context-preserving chunks with complete metadata.
        """
        chunks: List[ChunkCreate] = []
        chunk_idx = 0

        # Sort segments by page number
        sorted_segments = sorted(aligned_segments, key=lambda s: s.page_number)

        for segment in sorted_segments:
            # Strictly chunk only in_syllabus content
            if segment.scope_status != ScopeStatus.IN_SYLLABUS:
                continue

            text_pieces = ContentChunker.split_text_into_chunks(segment.text)
            
            # Derive unit number from unit_id if available
            unit_num: Optional[int] = None
            if segment.unit_id and "_U" in segment.unit_id:
                try:
                    unit_num = int(segment.unit_id.split("_U")[-1])
                except ValueError:
                    unit_num = None

            for piece in text_pieces:
                char_count = len(piece)
                token_count = len(piece.split())

                chunk = ChunkCreate(
                    course_code=segment.course_code,
                    unit=unit_num,
                    unit_id=segment.unit_id,
                    topic=segment.topic_name,
                    topic_id=segment.topic_id,
                    subtopic=segment.subtopic_name if hasattr(segment, "subtopic_name") else None,
                    subtopic_id=segment.subtopic_id,
                    source_type=material.source_type,
                    material_id=material.id,
                    page_number=segment.page_number,
                    scope_status=ScopeStatus.IN_SYLLABUS,
                    chunk_type="course_content",
                    text=piece,
                    char_count=char_count,
                    token_count=token_count,
                    embedding=None,  # Handled in Phase 10
                    chunk_index=chunk_idx,
                )
                chunks.append(chunk)
                chunk_idx += 1

        logger.info(
            f"Chunked material '{material.id}' ({material.course_code}): "
            f"created {len(chunks)} chunks from {len([s for s in aligned_segments if s.scope_status == ScopeStatus.IN_SYLLABUS])} in-syllabus segments."
        )
        return chunks
