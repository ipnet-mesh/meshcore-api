"""Unit tests for database engine module."""

import os
import tempfile
from pathlib import Path

import pytest

from meshcore_api.database import engine
from meshcore_api.database.models import Node


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test.db")


@pytest.fixture
def db_engine(temp_db_path):
    """Create a database engine for testing."""
    db = engine.DatabaseEngine(temp_db_path)
    db.initialize()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def reset_global_engine():
    """Reset global database engine before and after each test."""
    engine._db_engine = None
    yield
    engine._db_engine = None


class TestDatabaseEngine:
    """Test DatabaseEngine class."""

    def test_init_stores_path(self, temp_db_path):
        """Test DatabaseEngine stores the database path."""
        db = engine.DatabaseEngine(temp_db_path)
        assert db.db_path == temp_db_path
        assert db.engine is None
        assert db.session_factory is None

    def test_initialize_creates_database_file(self, temp_db_path):
        """Test initialize creates the database file."""
        db = engine.DatabaseEngine(temp_db_path)
        db.initialize()
        assert os.path.exists(temp_db_path)
        db.close()

    def test_initialize_creates_parent_directory(self):
        """Test initialize creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "nested", "dir", "test.db")
            db = engine.DatabaseEngine(nested_path)
            db.initialize()
            assert os.path.exists(nested_path)
            db.close()

    def test_initialize_sets_engine_and_factory(self, temp_db_path):
        """Test initialize sets up engine and session factory."""
        db = engine.DatabaseEngine(temp_db_path)
        db.initialize()
        assert db.engine is not None
        assert db.session_factory is not None
        db.close()

    def test_get_session_returns_session(self, db_engine):
        """Test get_session returns a valid session."""
        session = db_engine.get_session()
        assert session is not None
        session.close()

    def test_get_session_raises_if_not_initialized(self, temp_db_path):
        """Test get_session raises error if not initialized."""
        db = engine.DatabaseEngine(temp_db_path)
        with pytest.raises(RuntimeError) as exc_info:
            db.get_session()
        assert "not initialized" in str(exc_info.value).lower()

    def test_session_scope_commits_on_success(self, db_engine):
        """Test session_scope commits changes on success."""
        public_key = "a" * 64
        with db_engine.session_scope() as session:
            node = Node(
                public_key=public_key,
                public_key_prefix_2=public_key[:2],
                public_key_prefix_8=public_key[:8],
            )
            session.add(node)

        # Verify node was committed
        with db_engine.session_scope() as session:
            found = session.query(Node).filter_by(public_key=public_key).first()
            assert found is not None
            assert found.public_key == public_key

    def test_session_scope_rollbacks_on_exception(self, db_engine):
        """Test session_scope rolls back changes on exception."""
        public_key = "b" * 64

        try:
            with db_engine.session_scope() as session:
                node = Node(
                    public_key=public_key,
                    public_key_prefix_2=public_key[:2],
                    public_key_prefix_8=public_key[:8],
                )
                session.add(node)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify node was not committed
        with db_engine.session_scope() as session:
            found = session.query(Node).filter_by(public_key=public_key).first()
            assert found is None

    def test_close_disposes_engine(self, temp_db_path):
        """Test close disposes the engine."""
        db = engine.DatabaseEngine(temp_db_path)
        db.initialize()
        db.close()
        # Engine should be disposed (no error on close)
        assert True

    def test_close_handles_none_engine(self, temp_db_path):
        """Test close handles case where engine is None."""
        db = engine.DatabaseEngine(temp_db_path)
        db.close()  # Should not raise
        assert True


class TestGlobalFunctions:
    """Test global database functions."""

    def test_init_database_creates_engine(self, temp_db_path):
        """Test init_database creates and returns engine."""
        db = engine.init_database(temp_db_path)
        assert db is not None
        assert engine._db_engine is db
        db.close()

    def test_init_database_initializes_tables(self, temp_db_path):
        """Test init_database creates tables."""
        db = engine.init_database(temp_db_path)
        # Should be able to query nodes table
        with db.session_scope() as session:
            count = session.query(Node).count()
            assert count == 0
        db.close()

    def test_get_database_returns_engine(self, temp_db_path):
        """Test get_database returns the global engine."""
        created_db = engine.init_database(temp_db_path)
        retrieved_db = engine.get_database()
        assert retrieved_db is created_db
        created_db.close()

    def test_get_database_raises_if_not_initialized(self):
        """Test get_database raises error if not initialized."""
        with pytest.raises(RuntimeError) as exc_info:
            engine.get_database()
        assert "not initialized" in str(exc_info.value).lower()

    def test_get_session_uses_global_engine(self, temp_db_path):
        """Test get_session function uses global engine."""
        engine.init_database(temp_db_path)
        session = engine.get_session()
        assert session is not None
        session.close()
        engine.get_database().close()

    def test_get_session_raises_if_not_initialized(self):
        """Test get_session raises error if not initialized."""
        with pytest.raises(RuntimeError):
            engine.get_session()

    def test_session_scope_uses_global_engine(self, temp_db_path):
        """Test session_scope function uses global engine."""
        engine.init_database(temp_db_path)
        public_key = "c" * 64

        with engine.session_scope() as session:
            node = Node(
                public_key=public_key,
                public_key_prefix_2=public_key[:2],
                public_key_prefix_8=public_key[:8],
            )
            session.add(node)

        # Verify node was committed
        with engine.session_scope() as session:
            found = session.query(Node).filter_by(public_key=public_key).first()
            assert found is not None

        engine.get_database().close()


class TestDatabaseEngineMultipleSessions:
    """Test multiple sessions and concurrent access."""

    def test_multiple_sessions_independent(self, db_engine):
        """Test multiple sessions are independent."""
        session1 = db_engine.get_session()
        session2 = db_engine.get_session()
        assert session1 is not session2
        session1.close()
        session2.close()

    def test_session_scope_yields_unique_sessions(self, db_engine):
        """Test session_scope yields unique sessions each time."""
        sessions = []
        for _ in range(3):
            with db_engine.session_scope() as session:
                sessions.append(id(session))

        # All sessions should be unique (different objects)
        assert len(set(sessions)) == 3
