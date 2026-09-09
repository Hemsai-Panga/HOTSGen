"""Deterministic CAT/FAT exam paper question extraction and structuring engine."""

import logging
import re
from typing import List, Optional, Tuple
from app.ingestion.syllabus_aligner import SyllabusAligner
from app.models.course import CourseInDB
from app.models.extracted_content import ExtractedPageContent
from app.models.material import MaterialInDB
from app.models.syllabus_alignment import ScopeStatus
from app.models.teaching_question import DifficultyLevel, ExamType, TeachingQuestionCreate

logger = logging.getLogger(__name__)

# Question start regexes: e.g. "1.", "Q1.", "Question 1:", "1)", "[1]", "1 (a)", "Q. 2"
QUESTION_START_PATTERN = re.compile(
    r"^(?:(?:Question|Ques|Q)\.?\s*(\d{1,2}[a-zA-Z]?)|(\d{1,2})[\.\)\:]|\[(\d{1,2})\]|\((\d{1,2})\))\s*(.*)$",
    re.IGNORECASE,
)

# Subquestion pattern: e.g. "(a)", "(b)", "a)", "b)", "(i)", "i.", "(A)"
SUBQUESTION_PATTERN = re.compile(
    r"^\s*(?:\(([a-zA-Z]|\d+|[ivxIVX]+)\)|([a-zA-Z]|[ivxIVX]+)\))\s+(.*)$"
)

# Section header pattern: e.g. "PART - A", "SECTION B", "PART 1"
SECTION_PATTERN = re.compile(
    r"^(?:PART|SECTION|Part|Section)\s*[-–:]*\s*([A-Za-z0-9IVX]+)(.*)$",
    re.IGNORECASE,
)

# Marks pattern: e.g. "[10 Marks]", "(5M)", "[10M]", "(10 marks)", "[5]", "(5+5=10 Marks)"
MARKS_PATTERN = re.compile(
    r"(?:\[|\()?\s*(\d{1,2})\s*(?:Marks?|marks?|M|m)?\s*(?:\]|\))|"
    r"\(\s*\d+\s*\+\s*\d+\s*=\s*(\d{1,2})\s*(?:Marks?|marks?|M|m)?\s*\)|"
    r"\[\s*(\d{1,2})\s*\]|"
    r"\b(\d{1,2})\s*(?:Marks?|marks?|M|m)\b"
)

# Common university exam header noise to strip
NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*vellore\s+institute\s+of\s+technology", re.IGNORECASE),
    re.compile(r"^\s*school\s+of\s+computer\s+science", re.IGNORECASE),
    re.compile(r"^\s*continuous\s+assessment\s+test", re.IGNORECASE),
    re.compile(r"^\s*final\s+assessment\s+test", re.IGNORECASE),
    re.compile(r"^\s*fall\s+semester|winter\s+semester", re.IGNORECASE),
    re.compile(r"^\s*reg(?:\.|istration)?\s*no(?:\.|:)?", re.IGNORECASE),
    re.compile(r"^\s*duration\s*:|time\s*:\s*\d+", re.IGNORECASE),
    re.compile(r"^\s*max(?:\.|imum)?\s*marks\s*:\s*\d+", re.IGNORECASE),
    re.compile(r"^\s*course\s+code\s*:", re.IGNORECASE),
    re.compile(r"^\s*course\s+name\s*:", re.IGNORECASE),
    re.compile(r"^\s*answer\s+all\s+(?:the\s+)?questions", re.IGNORECASE),
    re.compile(r"^\s*page\s+\d+\s+of\s+\d+", re.IGNORECASE),
]


class RawQuestionBlock:
    """Internal accumulator for parsing a single exam question before structuring."""

    def __init__(
        self,
        question_number: str,
        section: Optional[str] = None,
        page_number: Optional[int] = None,
    ):
        self.question_number = question_number
        self.section = section
        self.page_number = page_number
        self.lines: List[str] = []
        self.subquestions: List[str] = []
        self.explicit_marks: Optional[int] = None

    def add_line(self, line: str) -> None:
        self.lines.append(line)

    def add_subquestion(self, sub_text: str) -> None:
        self.subquestions.append(sub_text.strip())

    def get_full_text(self) -> str:
        return " ".join(" ".join(self.lines).split())


class ExamQuestionParser:
    """Extracts, structures, and aligns exam questions from raw extracted text."""

    @staticmethod
    def infer_exam_metadata(
        material: MaterialInDB,
        full_text: str,
    ) -> Tuple[ExamType, int]:
        """Infer exam_type and year from material metadata or header text."""
        # 1. Exam Type
        exam_type = material.exam_type
        if exam_type is None:
            text_lower = full_text.lower()
            if "cat-1" in text_lower or "cat 1" in text_lower or "cat1" in text_lower or "assessment test - 1" in text_lower or "assessment test 1" in text_lower:
                exam_type = ExamType.CAT1
            elif "cat-2" in text_lower or "cat 2" in text_lower or "cat2" in text_lower or "assessment test - 2" in text_lower or "assessment test 2" in text_lower:
                exam_type = ExamType.CAT2
            elif "fat" in text_lower or "final assessment" in text_lower or "term end" in text_lower:
                exam_type = ExamType.FAT
            else:
                exam_type = ExamType.FAT

        # 2. Year
        year = material.year
        if year is None:
            # Search for 4 digit year 2020-2030
            year_matches = re.findall(r"\b(20[2-3]\d)\b", full_text)
            if year_matches:
                year = int(year_matches[0])
            else:
                year = 2024

        return exam_type, year

    @staticmethod
    def is_noise_line(line: str) -> bool:
        """Check if a line matches header or administrative test noise."""
        line_strip = line.strip()
        if not line_strip:
            return True
        for pattern in NOISE_LINE_PATTERNS:
            if pattern.search(line_strip):
                return True
        return False

    @staticmethod
    def extract_marks(line: str) -> Optional[int]:
        """Extract mark value from question text if present."""
        matches = MARKS_PATTERN.findall(line)
        if matches:
            for group in matches:
                for val in group:
                    if val and val.isdigit():
                        marks_val = int(val)
                        if 1 <= marks_val <= 100:
                            return marks_val
        return None

    @staticmethod
    def infer_question_type(text: str) -> str:
        """Heuristically identify the pedagogical question type."""
        text_lower = text.lower()

        # MCQ check: presence of multiple choice option markers (A) (B) (C) (D) or A) B) C) D)
        mcq_options = re.findall(r"(?:\([a-dA-D]\)|(?:\b|\s)[A-D]\))\s+[^\(\)\n]+", text)
        if len(mcq_options) >= 3 or ("(a)" in text_lower and "(b)" in text_lower and "(c)" in text_lower and "(d)" in text_lower and len(text) < 300):
            return "mcq"

        # Design / Modeling
        if any(w in text_lower for w in [
            "design an er", "construct an er", "draw the er", "draw er", "schema design",
            "normalize the following", "decompose the relation", "create table",
            "write sql query", "write relational algebra", "design a relational",
        ]):
            return "design"

        # Scenario / Case Study
        if any(w in text_lower for w in [
            "consider the following scenario", "assume that", "suppose a company",
            "suppose an enterprise", "a university database", "a hospital management",
            "an e-commerce", "case study", "scenario:", "a banking system",
        ]):
            return "scenario"

        # Numerical / Computation
        if any(w in text_lower for w in [
            "calculate", "compute", "find the order of b+", "index size", "cost of query",
            "throughput", "lossless decomposition", "closure of attribute",
        ]):
            return "numerical"

        # Default to theoretical
        return "theoretical"

    @staticmethod
    def infer_difficulty(marks: int, q_type: str, text: str) -> DifficultyLevel:
        """Infer difficulty rating based on marks, structure, and verbs."""
        text_lower = text.lower()

        # Hard criteria: High marks or complex multi-step design/scenario
        if marks >= 12 or (marks >= 8 and q_type in ("design", "scenario") and ("normalize" in text_lower or "bcnf" in text_lower or "concurrency" in text_lower)):
            return DifficultyLevel.HARD

        # Easy criteria: Direct definitions, short MCQs, low marks
        if marks <= 4 or q_type == "mcq" or any(text_lower.startswith(w) for w in ["define", "state", "list", "what is", "name"]):
            return DifficultyLevel.EASY

        # Default medium
        return DifficultyLevel.MEDIUM

    @staticmethod
    def parse_pages(
        pages: List[ExtractedPageContent],
        material: MaterialInDB,
        course: Optional[CourseInDB] = None,
    ) -> List[TeachingQuestionCreate]:
        """
        Parse raw extracted pages of an exam paper into structured question records.
        """
        full_text = "\n".join(p.text for p in pages)
        exam_type, year = ExamQuestionParser.infer_exam_metadata(material, full_text)

        # Build topic catalog for deterministic syllabus alignment if course has units
        topic_catalog = None
        if course and course.units:
            topic_catalog = SyllabusAligner.build_catalog(course.units)

        blocks: List[RawQuestionBlock] = []
        current_block: Optional[RawQuestionBlock] = None
        current_section: Optional[str] = None

        for page in sorted(pages, key=lambda p: p.page_number):
            lines = [l.strip() for l in page.text.split("\n")]

            for raw_line in lines:
                if not raw_line:
                    continue

                # 1. Check Section header
                sec_match = SECTION_PATTERN.match(raw_line)
                if sec_match:
                    current_section = f"Part {sec_match.group(1).upper()}"
                    continue

                # 2. Check noise line
                if ExamQuestionParser.is_noise_line(raw_line):
                    continue

                # 3. Check Question start
                q_match = QUESTION_START_PATTERN.match(raw_line)
                if q_match:
                    # Determine question number
                    q_num = next((g for g in q_match.groups()[:4] if g), "Q")
                    remainder = q_match.group(5) if len(q_match.groups()) >= 5 else ""

                    # Save prior block if valid
                    if current_block and len(current_block.lines) > 0:
                        blocks.append(current_block)

                    current_block = RawQuestionBlock(
                        question_number=q_num,
                        section=current_section,
                        page_number=page.page_number,
                    )

                    if remainder:
                        current_block.add_line(remainder)
                        marks = ExamQuestionParser.extract_marks(remainder)
                        if marks:
                            current_block.explicit_marks = marks
                    continue

                # 4. Check Subquestion line
                sub_match = SUBQUESTION_PATTERN.match(raw_line)
                if sub_match and current_block:
                    sub_label = sub_match.group(1) or sub_match.group(2)
                    sub_content = sub_match.group(3)
                    formatted_sub = f"({sub_label}) {sub_content}"
                    current_block.add_line(formatted_sub)
                    current_block.add_subquestion(formatted_sub)

                    marks = ExamQuestionParser.extract_marks(sub_content)
                    if marks:
                        current_block.explicit_marks = (current_block.explicit_marks or 0) + marks
                    continue

                # 5. Continuation line
                if current_block:
                    current_block.add_line(raw_line)
                    marks = ExamQuestionParser.extract_marks(raw_line)
                    if marks and not current_block.explicit_marks:
                        current_block.explicit_marks = marks
                elif len(raw_line) > 20:
                    # Fallback block if question numbering was missing/imperfect
                    current_block = RawQuestionBlock(
                        question_number=f"Q{len(blocks)+1}",
                        section=current_section,
                        page_number=page.page_number,
                    )
                    current_block.add_line(raw_line)

        # Flush final block
        if current_block and len(current_block.lines) > 0:
            blocks.append(current_block)

        # Structure questions
        structured_questions: List[TeachingQuestionCreate] = []

        for block in blocks:
            text = block.get_full_text()
            if len(text) < 15:
                continue

            # Assign marks (default 10 if not found)
            marks = block.explicit_marks if block.explicit_marks and 1 <= block.explicit_marks <= 100 else 10

            # Infer type and difficulty
            q_type = ExamQuestionParser.infer_question_type(text)
            difficulty = ExamQuestionParser.infer_difficulty(marks, q_type, text)

            # Deterministic Syllabus Mapping (Requirement 6)
            unit_id: Optional[str] = None
            unit_num: Optional[int] = None
            topic_id: Optional[str] = None
            topic_name: Optional[str] = None
            subtopic_id: Optional[str] = None
            subtopic_name: Optional[str] = None
            confidence: Optional[float] = None

            if topic_catalog:
                alignment = SyllabusAligner.align_single_segment(
                    catalog=topic_catalog,
                    material_id=material.id or "",
                    course_code=material.course_code,
                    page_number=block.page_number or 1,
                    text=text,
                )
                if alignment.scope_status == ScopeStatus.IN_SYLLABUS and alignment.confidence >= 0.35:
                    unit_id = alignment.unit_id
                    topic_id = alignment.topic_id
                    topic_name = alignment.topic_name
                    subtopic_id = alignment.subtopic_id
                    confidence = alignment.confidence

                    # Extract unit number from unit_id e.g. "BCSE301_U2" -> 2
                    if unit_id and "_U" in unit_id:
                        try:
                            unit_num = int(unit_id.split("_U")[-1])
                        except ValueError:
                            unit_num = None

            structured_questions.append(
                TeachingQuestionCreate(
                    course_code=material.course_code,
                    unit=unit_num,
                    unit_id=unit_id,
                    topic=topic_name,
                    topic_id=topic_id,
                    subtopic=subtopic_name,
                    subtopic_id=subtopic_id,
                    exam_type=exam_type,
                    year=year,
                    marks=marks,
                    question_text=text,
                    question_number=block.question_number,
                    section=block.section,
                    subquestions=block.subquestions if block.subquestions else None,
                    difficulty=difficulty,
                    question_type=q_type,
                    source_material_id=material.id,
                    page_number=block.page_number,
                    confidence=confidence,
                )
            )

        logger.info(f"Extracted {len(structured_questions)} teaching questions from material '{material.id}'.")
        return structured_questions
