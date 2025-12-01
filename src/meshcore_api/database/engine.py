"""Database engine and session management."""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseEngine:
    """Manages database connection and session lifecycle."""

    def __init__(self, db_path: str):
        """
        Initialize database engine.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None

    def initialize(self) -> None:
        """Initialize database engine and create tables if needed."""
        # Ensure parent directory exists
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        # Create engine with SQLite-specific settings
        connection_string = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            connection_string,
            echo=False,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},  # Allow multi-threaded access
        )

        # Enable foreign keys for SQLite
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            cursor.close()

        # Create all tables
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized at {self.db_path}")

        # Create session factory
        self.session_factory = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """
        Create a new database session.

        Returns:
            SQLAlchemy Session instance

        Raises:
            RuntimeError: If database not initialized
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations.

        Yields:
            SQLAlchemy Session

        Example:
            with db_engine.session_scope() as session:
                node = Node(public_key="01ab2186...")
                session.add(node)
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database engine."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database engine closed")


# Global database engine instance
_db_engine: Optional[DatabaseEngine] = None


def init_database(db_path: str) -> DatabaseEngine:
    """
    Initialize global database engine.

    Args:
        db_path: Path to SQLite database file

    Returns:
        DatabaseEngine instance
    """
    global _db_engine
    _db_engine = DatabaseEngine(db_path)
    _db_engine.initialize()
    return _db_engine


def get_database() -> DatabaseEngine:
    """
    Get global database engine instance.

    Returns:
        DatabaseEngine instance

    Raises:
        RuntimeError: If database not initialized
    """
    if not _db_engine:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_engine


def get_session() -> Session:
    """
    Get a new database session from global engine.

    Returns:
        SQLAlchemy Session

    Raises:
        RuntimeError: If database not initialized
    """
    return get_database().get_session()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope using global database engine.

    Yields:
        SQLAlchemy Session
    """
    with get_database().session_scope() as session:
        yield session
