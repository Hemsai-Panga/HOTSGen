"""MongoDB client lifecycle, collection access, and index management using PyMongo."""

import logging
from typing import Any, Dict, Optional, Tuple
from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Collection Name Constants
COLLECTION_COURSES = "courses"
COLLECTION_MATERIALS = "materials"
COLLECTION_EXTRACTED_CONTENT = "extracted_content"
COLLECTION_SYLLABUS_ALIGNMENTS = "syllabus_alignments"
COLLECTION_TEACHING_QUESTIONS = "teaching_questions"
COLLECTION_CHUNKS = "chunks"
COLLECTION_GENERATED_QUESTIONS = "generated_questions"


def init_db_indexes(db: Database) -> None:
    """Create sensible database indexes for fast query filtering."""
    try:
        # Courses Collection: unique course_code index
        db[COLLECTION_COURSES].create_indexes([
            IndexModel([("course_code", ASCENDING)], unique=True, name="idx_course_code_unique"),
        ])

        # Materials Collection: index by course and processing state
        db[COLLECTION_MATERIALS].create_indexes([
            IndexModel([("course_code", ASCENDING)], name="idx_material_course_code"),
            IndexModel([("processing_status", ASCENDING)], name="idx_material_processing_status"),
        ])

        # Extracted Content: index by material_id and course_code for fast pipeline reads
        db[COLLECTION_EXTRACTED_CONTENT].create_indexes([
            IndexModel([("material_id", ASCENDING)], name="idx_ec_material_id"),
            IndexModel([("course_code", ASCENDING)], name="idx_ec_course_code"),
            IndexModel([("material_id", ASCENDING), ("page_number", ASCENDING)], name="idx_ec_material_page"),
        ])

        # Syllabus Alignments: indexed for scoped retrieval filtering by course, topic, and scope status
        db[COLLECTION_SYLLABUS_ALIGNMENTS].create_indexes([
            IndexModel([("material_id", ASCENDING)], name="idx_sa_material_id"),
            IndexModel([("course_code", ASCENDING)], name="idx_sa_course_code"),
            IndexModel([("scope_status", ASCENDING)], name="idx_sa_scope_status"),
            IndexModel([("course_code", ASCENDING), ("scope_status", ASCENDING)], name="idx_sa_course_scope"),
            IndexModel([("topic_id", ASCENDING)], name="idx_sa_topic_id"),
            IndexModel([("material_id", ASCENDING), ("page_number", ASCENDING)], name="idx_sa_material_page"),
        ])

        # Teaching Questions: indexed for retrieval filtering by course, topic, exam type, year, source material
        db[COLLECTION_TEACHING_QUESTIONS].create_indexes([
            IndexModel([("source_material_id", ASCENDING)], name="idx_tq_material_id"),
            IndexModel([("course_code", ASCENDING)], name="idx_tq_course_code"),
            IndexModel([("exam_type", ASCENDING)], name="idx_tq_exam_type"),
            IndexModel([("year", DESCENDING)], name="idx_tq_year"),
            IndexModel([("topic", ASCENDING)], name="idx_tq_topic"),
            IndexModel([("topic_id", ASCENDING)], name="idx_tq_topic_id"),
            IndexModel([("unit_id", ASCENDING)], name="idx_tq_unit_id"),
            IndexModel([("course_code", ASCENDING), ("exam_type", ASCENDING), ("year", DESCENDING)], name="idx_tq_course_exam_year"),
            IndexModel([("course_code", ASCENDING), ("topic_id", ASCENDING), ("exam_type", ASCENDING)], name="idx_tq_compound"),
        ])

        # Chunks: indexed for filtered metadata lookup prior to semantic retrieval
        db[COLLECTION_CHUNKS].create_indexes([
            IndexModel([("material_id", ASCENDING)], name="idx_chunk_material_id"),
            IndexModel([("course_code", ASCENDING)], name="idx_chunk_course_code"),
            IndexModel([("unit_id", ASCENDING)], name="idx_chunk_unit_id"),
            IndexModel([("topic_id", ASCENDING)], name="idx_chunk_topic_id"),
            IndexModel([("scope_status", ASCENDING)], name="idx_chunk_scope_status"),
            IndexModel([("course_code", ASCENDING), ("unit_id", ASCENDING), ("topic_id", ASCENDING)], name="idx_chunk_course_unit_topic"),
            IndexModel([("course_code", ASCENDING), ("topic", ASCENDING)], name="idx_chunk_compound"),
        ])

        # Generated Questions: indexed by course and generation timestamp
        db[COLLECTION_GENERATED_QUESTIONS].create_indexes([
            IndexModel([("course_code", ASCENDING)], name="idx_gq_course_code"),
            IndexModel([("created_at", DESCENDING)], name="idx_gq_created_at"),
        ])

        logger.info("MongoDB indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Could not create database indexes: {type(e).__name__} - {e}")


import re


def _sanitize_error_msg(error_msg: str) -> str:
    """Mask credentials in error messages to prevent leaking secrets."""
    return re.sub(r"://([^:]+):([^@]+)@", "://***:***@", str(error_msg))


class MongoDBManager:
    """Manages the lifecycle of the single reusable MongoClient instance."""

    def __init__(self) -> None:
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None

    def connect(self) -> None:
        """Initialize the MongoClient using configuration settings."""
        settings = get_settings()
        if self.client is None:
            try:
                self.client = MongoClient(
                    settings.MONGODB_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                )
                self.db = self.client[settings.MONGODB_DB_NAME]
                logger.info("MongoDB client initialized.")
                
                # Check connection and apply indexes if reachable
                if self.ping()[0]:
                    init_db_indexes(self.db)
            except Exception as e:
                sanitized_msg = _sanitize_error_msg(str(e))
                logger.error(f"Failed to initialize MongoDB client: {type(e).__name__} - {sanitized_msg}")
                self.client = None
                self.db = None

    def close(self) -> None:
        """Close the MongoClient connection if open."""
        if self.client is not None:
            try:
                self.client.close()
                logger.info("MongoDB client connection closed.")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {type(e).__name__}")
            finally:
                self.client = None
                self.db = None

    def ping(self) -> Tuple[bool, Optional[str]]:
        """Verify database connectivity via ping command without exposing credentials."""
        if self.client is None:
            return False, "Database client is not initialized"
        try:
            self.client.admin.command("ping")
            return True, None
        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            logger.warning(f"MongoDB connection check failed: {type(e).__name__}")
            return False, f"Connection failure: {type(e).__name__}"
        except PyMongoError as e:
            logger.warning(f"MongoDB query error: {type(e).__name__}")
            return False, f"Database error: {type(e).__name__}"
        except Exception as e:
            logger.warning(f"Unexpected error pinging MongoDB: {type(e).__name__}")
            return False, f"Unexpected error: {type(e).__name__}"

    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """Return a typed collection from the active database."""
        if self.db is None:
            self.connect()
        if self.db is not None:
            return self.db[collection_name]
        return None


# Global database manager instance
db_manager = MongoDBManager()


def get_database() -> Optional[Database]:
    """Return the active database instance."""
    return db_manager.db


def get_client() -> Optional[MongoClient]:
    """Return the active MongoClient instance."""
    return db_manager.client


def check_mongo_connection() -> Tuple[bool, Optional[str]]:
    """Helper function to check MongoDB connection status."""
    return db_manager.ping()


def get_courses_collection() -> Optional[Collection]:
    """Return the courses collection."""
    return db_manager.get_collection(COLLECTION_COURSES)


def get_materials_collection() -> Optional[Collection]:
    """Return the materials collection."""
    return db_manager.get_collection(COLLECTION_MATERIALS)


def get_extracted_content_collection() -> Optional[Collection]:
    """Return the extracted content collection."""
    return db_manager.get_collection(COLLECTION_EXTRACTED_CONTENT)


def get_syllabus_alignments_collection() -> Optional[Collection]:
    """Return the syllabus alignments collection."""
    return db_manager.get_collection(COLLECTION_SYLLABUS_ALIGNMENTS)


def get_teaching_questions_collection() -> Optional[Collection]:
    """Return the teaching questions collection."""
    return db_manager.get_collection(COLLECTION_TEACHING_QUESTIONS)


def get_chunks_collection() -> Optional[Collection]:
    """Return the chunks collection."""
    return db_manager.get_collection(COLLECTION_CHUNKS)


def get_generated_questions_collection() -> Optional[Collection]:
    """Return the generated questions collection."""
    return db_manager.get_collection(COLLECTION_GENERATED_QUESTIONS)
