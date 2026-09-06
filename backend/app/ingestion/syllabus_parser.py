"""Deterministic rule-based syllabus parser transforming raw extracted syllabus text into a course hierarchy."""

import logging
import re
from typing import List, Optional, Tuple
from app.models.course import Subtopic, Topic, Unit

logger = logging.getLogger(__name__)

ROMAN_MAP = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
}

# Boilerplate patterns to ignore during topic parsing
IGNORE_LINE_PATTERNS = [
    re.compile(r"^(?:text\s*books?|reference\s*books?|references?|mode\s*of\s*evaluation|hours?|total\s*hours?|lecture\s*hours?|course\s*objectives?|course\s*outcomes?|prerequisites?):?.*$", re.IGNORECASE),
    re.compile(r"^\(?\s*(?:[0-9]+\s*(?:hours?|hrs?))\s*\)?$", re.IGNORECASE),
    re.compile(r"^(?:page\s*[0-9]+|\b\d+\s*/\s*\d+\b)", re.IGNORECASE),
]


class SyllabusParsingError(Exception):
    """Raised when syllabus parsing fails or extracted text cannot produce a valid hierarchy."""
    pass


def parse_roman_or_int(value_str: str) -> int:
    """Parse integer or Roman numeral into an integer."""
    val = value_str.strip().upper()
    if val.isdigit():
        return int(val)
    if val in ROMAN_MAP:
        return ROMAN_MAP[val]
    # Fallback attempt
    digits = re.findall(r"\d+", val)
    if digits:
        return int(digits[0])
    return 1


def is_boilerplate(line: str) -> bool:
    """Check if a line contains metadata or boilerplate rather than syllabus topic content."""
    clean = line.strip()
    if not clean or len(clean) < 3:
        return True
    for pat in IGNORE_LINE_PATTERNS:
        if pat.match(clean):
            return True
    return False


def clean_topic_title(text: str) -> str:
    """Clean topic title removing leading bullets, numbering, and trailing punctuation."""
    # Remove leading numbering/bullets like "1.", "1.1", "-", "*", "•", "a)"
    cleaned = re.sub(r"^(?:[0-9]+(?:\.[0-9]+)*[\.\)]|\s*[-*•–—]\s*|[a-zA-Z]\))\s*", "", text).strip()
    # Remove trailing hours like "(6 hours)" or "[4 hrs]"
    cleaned = re.sub(r"\s*[\(\[]\s*\d+\s*(?:hours?|hrs?)\s*[\)\]]$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.strip(" .,-:")


class SyllabusParser:
    """Deterministic parser extracting units, topics, and subtopics from syllabus text."""

    @staticmethod
    def parse_syllabus(course_code: str, raw_text: str) -> List[Unit]:
        """
        Parse raw syllabus text into a list of structured Unit domain objects.
        
        Args:
            course_code: Normalized course code (e.g. BCSE301) for stable IDs.
            raw_text: Full extracted text from syllabus document.
            
        Returns:
            List[Unit] with stable IDs, unit numbers, names, topics, and subtopics.
            
        Raises:
            SyllabusParsingError: If no valid units or topics can be extracted.
        """
        if not raw_text or not raw_text.strip():
            raise SyllabusParsingError("Syllabus text is empty.")

        normalized_code = course_code.strip().upper()

        # Match common unit header patterns
        # Pattern 1: UNIT 1 / MODULE I / Unit 1: ...
        unit_pattern = re.compile(
            r"(?:UNIT|MODULE)\s*[-:]?\s*([0-9]+|[IVXLCDM]+)[\s:-]*([^\n\r]*)(.*?)(?=(?:(?:UNIT|MODULE)\s*[-:]?\s*(?:[0-9]+|[IVXLCDM]+))|\Z)",
            re.IGNORECASE | re.DOTALL,
        )

        matches = list(unit_pattern.finditer(raw_text))

        # Fallback Pattern 2: Numbered Sections (e.g. "1. Introduction to ...") if no UNIT/MODULE keywords
        if not matches:
            fallback_pattern = re.compile(
                r"^([1-9])\.\s+([A-Z][^\n\r]*)(.*?)(?=^[1-9]\.|\Z)",
                re.MULTILINE | re.DOTALL,
            )
            matches = list(fallback_pattern.finditer(raw_text))

        if not matches:
            raise SyllabusParsingError(
                "Could not identify structured units or modules in the syllabus. "
                "Ensure the document contains recognizable unit markers (e.g. 'UNIT 1', 'Module I')."
            )

        units: List[Unit] = []
        seen_unit_numbers = set()

        for unit_idx, match in enumerate(matches):
            raw_num = match.group(1)
            raw_title = match.group(2).strip()
            unit_body = match.group(3).strip()

            unit_number = parse_roman_or_int(raw_num)
            if unit_number in seen_unit_numbers:
                unit_number = len(seen_unit_numbers) + 1
            seen_unit_numbers.add(unit_number)

            unit_id = f"{normalized_code}_U{unit_number}"

            # Clean up unit title
            unit_name = clean_topic_title(raw_title)
            if not unit_name or len(unit_name) < 3:
                # Check first line of body if title was on the next line
                lines = [l.strip() for l in unit_body.splitlines() if l.strip()]
                if lines and not is_boilerplate(lines[0]):
                    unit_name = clean_topic_title(lines[0])
                    unit_body = "\n".join(lines[1:])
                else:
                    unit_name = f"Unit {unit_number}"

            # Heuristic exam designation
            cat_designation: Optional[str] = None
            if unit_number in (1, 2):
                cat_designation = "CAT1"
            elif unit_number in (3, 4):
                cat_designation = "CAT2"
            else:
                cat_designation = "FAT"

            # Parse topics from unit body
            topics = SyllabusParser._parse_unit_topics(
                unit_id=unit_id,
                unit_body=unit_body,
                cat_designation=cat_designation,
            )

            if not topics:
                # If body had no sub-bullets, use the unit name itself as the topic
                topic_id = f"{unit_id}_T1"
                topics = [
                    Topic(
                        id=topic_id,
                        topic_name=unit_name,
                        subtopics=[],
                        cat_designation=cat_designation,
                    )
                ]

            units.append(
                Unit(
                    id=unit_id,
                    unit_number=unit_number,
                    unit_name=unit_name,
                    topics=topics,
                )
            )

        if not units:
            raise SyllabusParsingError("Failed to extract any valid units from the syllabus.")

        # Ensure unit ordering is preserved
        units.sort(key=lambda u: u.unit_number)
        logger.info(f"Successfully parsed {len(units)} units for course '{normalized_code}'.")
        return units

    @staticmethod
    def _parse_unit_topics(
        unit_id: str,
        unit_body: str,
        cat_designation: Optional[str],
    ) -> List[Topic]:
        """Parse structured topics and subtopics from a unit's text body."""
        topics: List[Topic] = []
        lines = [l.strip() for l in unit_body.splitlines() if l.strip() and not is_boilerplate(l)]

        raw_topic_chunks: List[str] = []

        # Check if lines have bullets or semicolons
        for line in lines:
            # Check for semicolon separation on the same line
            if ";" in line:
                clauses = [c.strip() for c in line.split(";") if c.strip() and not is_boilerplate(c)]
                raw_topic_chunks.extend(clauses)
            else:
                raw_topic_chunks.append(line)

        topic_counter = 1
        seen_topic_names = set()

        for chunk in raw_topic_chunks:
            # 1. Check for colon structure: "Topic Name: Subtopic 1, Subtopic 2, Subtopic 3"
            if ":" in chunk:
                parts = chunk.split(":", 1)
                t_name = clean_topic_title(parts[0])
                sub_text = parts[1].strip()

                if not t_name or len(t_name) < 2 or t_name.lower() in seen_topic_names:
                    continue

                seen_topic_names.add(t_name.lower())
                topic_id = f"{unit_id}_T{topic_counter}"

                # Parse subtopics from comma/semicolon list
                subtopics: List[Subtopic] = []
                sub_items = [s.strip() for s in re.split(r"[,;]", sub_text) if s.strip() and not is_boilerplate(s)]
                for sub_idx, sub_item in enumerate(sub_items):
                    clean_sub = clean_topic_title(sub_item)
                    if clean_sub and len(clean_sub) >= 2:
                        sub_id = f"{topic_id}_S{sub_idx + 1}"
                        subtopics.append(Subtopic(id=sub_id, title=clean_sub))

                topics.append(
                    Topic(
                        id=topic_id,
                        topic_name=t_name,
                        subtopics=subtopics,
                        cat_designation=cat_designation,
                    )
                )
                topic_counter += 1

            else:
                # Direct topic line
                t_name = clean_topic_title(chunk)
                if not t_name or len(t_name) < 2 or t_name.lower() in seen_topic_names:
                    continue

                seen_topic_names.add(t_name.lower())
                topic_id = f"{unit_id}_T{topic_counter}"
                topics.append(
                    Topic(
                        id=topic_id,
                        topic_name=t_name,
                        subtopics=[],
                        cat_designation=cat_designation,
                    )
                )
                topic_counter += 1

        return topics
