"""MongoDB client lifecycle and database access management using PyMongo."""

import logging
from typing import Any, Dict, Optional, Tuple
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from app.config import get_settings

logger = logging.getLogger(__name__)


class MongoDBManager:
    """Manages the lifecycle of the single reusable MongoClient instance."""

    def __init__(self) -> None:
        self.client: Optional[MongoClient[Dict[str, Any]]] = None
        self.db: Optional[Database[Dict[str, Any]]] = None

    def connect(self) -> None:
        """Initialize the MongoClient using configuration settings."""
        settings = get_settings()
        if self.client is None:
            try:
                # Set a reasonable serverSelectionTimeoutMS so healthchecks and startup do not hang indefinitely
                self.client = MongoClient(
                    settings.MONGODB_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                )
                self.db = self.client[settings.MONGODB_DB_NAME]
                logger.info("MongoDB client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB client: {type(e).__name__}")
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
        """Verify the database connectivity via ping command without exposing credentials."""
        if self.client is None:
            return False, "Database client is not initialized"
        try:
            # Run ping command on admin or target database
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


# Global database manager instance
db_manager = MongoDBManager()


def get_database() -> Optional[Database[Dict[str, Any]]]:
    """Return the active database instance."""
    return db_manager.db


def get_client() -> Optional[MongoClient[Dict[str, Any]]]:
    """Return the active MongoClient instance."""
    return db_manager.client


def check_mongo_connection() -> Tuple[bool, Optional[str]]:
    """Helper function to check MongoDB connection status."""
    return db_manager.ping()
