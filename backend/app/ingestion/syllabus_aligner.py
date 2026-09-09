"""Deterministic syllabus alignment and content classification engine."""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from app.models.course import CourseInDB, Unit
from app.models.extracted_content import ExtractedPageContent
from app.models.syllabus_alignment import AlignedSegment, ScopeStatus

logger = logging.getLogger(__name__)

# Basic stopwords to avoid false-positive keyword matches
STOPWORDS = {
    "the", "a", "an", "is", "and", "or", "in", "on", "of", "to", "with",
    "for", "by", "at", "from", "that", "this", "these", "those", "as",
    "are", "be", "it", "its", "into", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such", "than", "too", "very",
    "can", "will", "just", "should", "now", "d", "ll", "m", "o", "re",
    "ve", "y", "ain", "aren", "couldn", "didn", "doesn", "hadn", "hasn",
    "haven", "isn", "ma", "mightn", "mustn", "needn", "shan", "shouldn",
    "wasn", "weren", "won", "wouldn", "about", "after", "again", "also",
    "between", "during", "out", "over", "through", "under", "unit", "module",
    "lecture", "chapter", "section", "topic", "study", "page", "slide",
}


def tokenize_words(text: str) -> Set[str]:
    """Extract unique meaningful lowercase word tokens (length >= 3, not in stopwords)."""
    words = re.findall(r"\b[a-zA-Z0-9_\-\+\#]{3,}\b", text.lower())
    return {w for w in words if w not in STOPWORDS}


class TopicCatalogEntry:
    """Indexed representation of a syllabus topic and its subtopics for fast lexical matching."""

    def __init__(
        self,
        unit_id: str,
        unit_number: int,
        unit_name: str,
        topic_id: str,
        topic_name: str,
        subtopics: List[Tuple[str, str]],  # List of (subtopic_id, subtopic_title)
    ):
        self.unit_id = unit_id
        self.unit_number = unit_number
        self.unit_name = unit_name
        self.topic_id = topic_id
        self.topic_name = topic_name
        self.subtopics = subtopics

        # Phrases (exact multi-word strings)
        self.topic_phrase = topic_name.lower().strip()
        self.subtopic_phrases = [(s_id, s_title.lower().strip()) for s_id, s_title in subtopics]

        # Word sets
        self.unit_keywords = tokenize_words(unit_name)
        self.topic_keywords = tokenize_words(topic_name)
        self.subtopic_keywords = {
            s_id: tokenize_words(s_title) for s_id, s_title in subtopics
        }


class SyllabusAligner:
    """Aligns extracted content against course syllabus hierarchy using deterministic lexical scoring."""

    @staticmethod
    def build_catalog(units: List[Unit]) -> List[TopicCatalogEntry]:
        """Index all topics and subtopics from syllabus units."""
        catalog: List[TopicCatalogEntry] = []
        for unit in units:
            unit_id = unit.id or f"U{unit.unit_number}"
            for topic in unit.topics:
                topic_id = topic.id or f"{unit_id}_T1"
                subtopics_list = [
                    (sub.id or f"{topic_id}_S{idx+1}", sub.title)
                    for idx, sub in enumerate(topic.subtopics)
                ]
                entry = TopicCatalogEntry(
                    unit_id=unit_id,
                    unit_number=unit.unit_number,
                    unit_name=unit.unit_name,
                    topic_id=topic_id,
                    topic_name=topic.topic_name,
                    subtopics=subtopics_list,
                )
                catalog.append(entry)
        return catalog

    @staticmethod
    def align_single_segment(
        catalog: List[TopicCatalogEntry],
        material_id: str,
        course_code: str,
        page_number: int,
        text: str,
    ) -> AlignedSegment:
        """
        Score a single page/slide against the topic catalog and assign scope status.
        """
        text_clean = text.strip()
        if not text_clean or len(text_clean) < 15:
            return AlignedSegment(
                material_id=material_id,
                course_code=course_code,
                page_number=page_number,
                text=text_clean,
                scope_status=ScopeStatus.OUT_OF_SYLLABUS,
                confidence=0.0,
                matched_keywords=[],
            )

        text_lower = text_clean.lower()
        page_words = tokenize_words(text_clean)

        best_score = 0.0
        best_entry: Optional[TopicCatalogEntry] = None
        best_subtopic_id: Optional[str] = None
        best_matched_keywords: List[str] = []

        for entry in catalog:
            score = 0.0
            matched_terms: List[str] = []

            # 1. Exact topic phrase match (e.g. "relational algebra", "functional dependencies")
            if len(entry.topic_phrase) >= 4 and entry.topic_phrase in text_lower:
                score += 0.50
                matched_terms.append(entry.topic_name)

            # 2. Topic keyword matches
            common_topic_words = entry.topic_keywords.intersection(page_words)
            if common_topic_words:
                kw_ratio = len(common_topic_words) / max(len(entry.topic_keywords), 1)
                score += min(0.35, len(common_topic_words) * 0.12)
                matched_terms.extend(list(common_topic_words))

            # 3. Subtopic phrase and keyword matches
            matched_sub_id: Optional[str] = None
            for s_id, s_phrase in entry.subtopic_phrases:
                if len(s_phrase) >= 3 and s_phrase in text_lower:
                    score += 0.35
                    matched_sub_id = s_id
                    matched_terms.append(s_phrase)
                else:
                    sub_words = entry.subtopic_keywords.get(s_id, set())
                    common_sub = sub_words.intersection(page_words)
                    if len(common_sub) >= 2 or (len(sub_words) == 1 and len(common_sub) == 1):
                        score += 0.20
                        matched_sub_id = s_id
                        matched_terms.extend(list(common_sub))

            # 4. Unit keyword matches (supporting context)
            common_unit_words = entry.unit_keywords.intersection(page_words)
            if common_unit_words:
                score += min(0.15, len(common_unit_words) * 0.05)

            # Normalize score
            score = min(1.0, score)

            if score > best_score:
                best_score = score
                best_entry = entry
                best_subtopic_id = matched_sub_id
                best_matched_keywords = list(dict.fromkeys(matched_terms))  # unique preserving order

        # Thresholds for classification
        # In-Syllabus: strong confidence (>= 0.40)
        # Ambiguous: borderline match (0.20 <= score < 0.40)
        # Out-of-Syllabus: weak or no match (< 0.20)
        if best_score >= 0.40 and best_entry is not None:
            scope_status = ScopeStatus.IN_SYLLABUS
            confidence = round(best_score, 2)
            unit_id = best_entry.unit_id
            topic_id = best_entry.topic_id
            unit_name = best_entry.unit_name
            topic_name = best_entry.topic_name
            subtopic_id = best_subtopic_id
        elif best_score >= 0.20 and best_entry is not None:
            scope_status = ScopeStatus.AMBIGUOUS
            confidence = round(best_score, 2)
            unit_id = best_entry.unit_id
            topic_id = best_entry.topic_id
            unit_name = best_entry.unit_name
            topic_name = best_entry.topic_name
            subtopic_id = best_subtopic_id
        else:
            scope_status = ScopeStatus.OUT_OF_SYLLABUS
            confidence = 0.0
            unit_id = None
            topic_id = None
            subtopic_id = None
            unit_name = None
            topic_name = None
            best_matched_keywords = []

        return AlignedSegment(
            material_id=material_id,
            course_code=course_code,
            page_number=page_number,
            text=text_clean,
            scope_status=scope_status,
            unit_id=unit_id,
            topic_id=topic_id,
            subtopic_id=subtopic_id,
            unit_name=unit_name,
            topic_name=topic_name,
            confidence=confidence,
            matched_keywords=best_matched_keywords[:10],
        )

    @staticmethod
    def align_content(
        course: CourseInDB,
        material_id: str,
        pages: List[ExtractedPageContent],
    ) -> List[AlignedSegment]:
        """
        Align a batch of extracted pages/slides against the course's syllabus units.
        """
        if not course.units:
            raise ValueError(f"Course '{course.course_code}' has no syllabus units for alignment.")

        catalog = SyllabusAligner.build_catalog(course.units)
        aligned_segments: List[AlignedSegment] = []

        for page in pages:
            segment = SyllabusAligner.align_single_segment(
                catalog=catalog,
                material_id=material_id,
                course_code=course.course_code,
                page_number=page.page_number,
                text=page.text,
            )
            aligned_segments.append(segment)

        return aligned_segments
