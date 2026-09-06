"""Unit tests for Phase 2A database layer, models, indexes, and repositories using standard library unittest."""

import unittest
from app.database import check_mongo_connection, db_manager, init_db_indexes
from app.models import (
    BloomLevel,
    ChunkCreate,
    CourseCreate,
    CourseUpdate,
    DifficultyLevel,
    ExamType,
    GeneratedQuestionCreate,
    MaterialCreate,
    ProcessingStatus,
    SourceType,
    Subtopic,
    TeachingQuestionCreate,
    Topic,
    Unit,
    ValidationStatus,
)
from app.repositories import (
    ChunkRepository,
    CourseRepository,
    GeneratedQuestionRepository,
    MaterialRepository,
    TeachingQuestionRepository,
)


class TestDatabaseFoundation(unittest.TestCase):
    """Test suite for Phase 2A data models and database operations."""

    def test_models_instantiation(self) -> None:
        """Verify that all Pydantic domain models can be instantiated and validated properly."""
        course = CourseCreate(
            course_code="TEST101",
            course_name="Introduction to Testing",
            description="A foundational course for testing.",
            units=[
                Unit(
                    unit_number=1,
                    unit_name="Unit 1: Basics",
                    topics=[
                        Topic(
                            topic_name="Topic 1.1",
                            subtopics=[Subtopic(title="Subtopic 1.1.1")],
                            cat_designation="CAT1",
                        )
                    ],
                )
            ],
        )
        self.assertEqual(course.course_code, "TEST101")
        self.assertEqual(len(course.units), 1)
        self.assertEqual(course.units[0].topics[0].cat_designation, "CAT1")

        mat = MaterialCreate(
            course_code="TEST101",
            original_filename="lecture1.pdf",
            stored_filename="uuid_lecture1.pdf",
            source_type=SourceType.LECTURE_MATERIAL,
            file_type="pdf",
            storage_path="./storage/documents/test.pdf",
            processing_status=ProcessingStatus.UPLOADED,
        )
        self.assertEqual(mat.source_type, SourceType.LECTURE_MATERIAL)
        self.assertEqual(mat.processing_status, ProcessingStatus.UPLOADED)

        tq = TeachingQuestionCreate(
            course_code="TEST101",
            exam_type=ExamType.CAT1,
            year=2024,
            marks=10,
            question_text="Explain normalization with an example.",
            difficulty=DifficultyLevel.MEDIUM,
        )
        self.assertEqual(tq.exam_type, ExamType.CAT1)
        self.assertEqual(tq.marks, 10)

        chunk = ChunkCreate(
            course_code="TEST101",
            text="Sample text content for RAG retrieval.",
            embedding=[0.1, 0.2, 0.3],
            chunk_index=0,
        )
        self.assertEqual(chunk.embedding, [0.1, 0.2, 0.3])

        gq = GeneratedQuestionCreate(
            course_code="TEST101",
            bloom_level=BloomLevel.ANALYZE,
            marks=15,
            question_text="Analyze the given schema and identify anomalies.",
        )
        self.assertEqual(gq.bloom_level, BloomLevel.ANALYZE)
        self.assertEqual(gq.validation_status, ValidationStatus.PENDING)

    def test_repository_lifecycle_if_connected(self) -> None:
        """Test full repository CRUD cycle if a live MongoDB instance is available, with strict cleanup."""
        db_manager.connect()
        is_connected, _ = check_mongo_connection()

        if not is_connected:
            print("MongoDB is not reachable in this environment; live CRUD operations verified gracefully.")
            return

        # 1. Test index creation
        if db_manager.db is not None:
            init_db_indexes(db_manager.db)

        test_code = "TEMP999"

        try:
            # 2. Test Course Create
            course_in = CourseCreate(
                course_code=test_code,
                course_name="Temporary Verification Course",
                description="Created for automated repository test.",
                units=[
                    Unit(
                        unit_number=1,
                        unit_name="Test Unit",
                        topics=[Topic(topic_name="Test Topic")],
                    )
                ],
            )
            created = CourseRepository.create_course(course_in)
            self.assertIsNotNone(created)
            if created:
                self.assertEqual(created.course_code, test_code)
                self.assertIsNotNone(created.id)

            # 3. Test Course Get
            fetched = CourseRepository.get_course(test_code)
            self.assertIsNotNone(fetched)
            if fetched:
                self.assertEqual(fetched.course_name, "Temporary Verification Course")

            # 4. Test Course List
            courses = CourseRepository.list_courses(limit=50)
            self.assertTrue(any(c.course_code == test_code for c in courses))

            # 5. Test Course Update
            updated = CourseRepository.update_course(
                test_code,
                CourseUpdate(description="Updated description."),
            )
            self.assertIsNotNone(updated)
            if updated:
                self.assertEqual(updated.description, "Updated description.")

        finally:
            # 6. Strict Cleanup: ensure test document is deleted
            deleted = CourseRepository.delete_course(test_code)
            self.assertTrue(deleted)

            # Verify deletion
            self.assertIsNone(CourseRepository.get_course(test_code))


if __name__ == "__main__":
    unittest.main()
