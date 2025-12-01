"""Unit tests for SignalStrength model, schemas, and API endpoint."""

import os
import tempfile
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from meshcore_api.api.schemas import (
    SignalStrengthFilters,
    SignalStrengthListResponse,
    SignalStrengthResponse,
)
from meshcore_api.database import engine
from meshcore_api.database.models import Node, SignalStrength


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


# =============================================================================
# SignalStrength Database Model Tests
# =============================================================================


class TestSignalStrengthModel:
    """Test SignalStrength database model."""

    def test_create_signal_strength_record(self, db_engine):
        """Test creating a SignalStrength record."""
        source_key = "a" * 64
        dest_key = "b" * 64

        with db_engine.session_scope() as session:
            signal = SignalStrength(
                source_public_key=source_key,
                destination_public_key=dest_key,
                snr=15.5,
            )
            session.add(signal)

        with db_engine.session_scope() as session:
            found = session.query(SignalStrength).first()
            assert found is not None
            assert found.source_public_key == source_key
            assert found.destination_public_key == dest_key
            assert found.snr == 15.5
            assert found.recorded_at is not None

    def test_create_signal_strength_with_trace_path_id(self, db_engine):
        """Test creating a SignalStrength record with trace_path_id."""
        source_key = "c" * 64
        dest_key = "d" * 64

        with db_engine.session_scope() as session:
            signal = SignalStrength(
                source_public_key=source_key,
                destination_public_key=dest_key,
                snr=-5.2,
                trace_path_id=42,
            )
            session.add(signal)

        with db_engine.session_scope() as session:
            found = session.query(SignalStrength).first()
            assert found.trace_path_id == 42
            assert found.snr == -5.2

    def test_signal_strength_negative_snr(self, db_engine):
        """Test SignalStrength can store negative SNR values."""
        with db_engine.session_scope() as session:
            signal = SignalStrength(
                source_public_key="e" * 64,
                destination_public_key="f" * 64,
                snr=-20.5,
            )
            session.add(signal)

        with db_engine.session_scope() as session:
            found = session.query(SignalStrength).first()
            assert found.snr == -20.5

    def test_multiple_signal_strength_records(self, db_engine):
        """Test creating multiple SignalStrength records."""
        with db_engine.session_scope() as session:
            for i in range(5):
                signal = SignalStrength(
                    source_public_key=f"{i}" * 64,
                    destination_public_key=f"{i+1}" * 64,
                    snr=10.0 + i,
                    trace_path_id=i,
                )
                session.add(signal)

        with db_engine.session_scope() as session:
            count = session.query(SignalStrength).count()
            assert count == 5

    def test_query_by_source_public_key(self, db_engine):
        """Test querying SignalStrength by source public key."""
        source_key = "a" * 64

        with db_engine.session_scope() as session:
            # Create multiple records with different sources
            session.add(
                SignalStrength(
                    source_public_key=source_key,
                    destination_public_key="b" * 64,
                    snr=10.0,
                )
            )
            session.add(
                SignalStrength(
                    source_public_key=source_key,
                    destination_public_key="c" * 64,
                    snr=12.0,
                )
            )
            session.add(
                SignalStrength(
                    source_public_key="d" * 64,
                    destination_public_key="e" * 64,
                    snr=8.0,
                )
            )

        with db_engine.session_scope() as session:
            records = (
                session.query(SignalStrength)
                .filter(SignalStrength.source_public_key == source_key)
                .all()
            )
            assert len(records) == 2

    def test_query_by_destination_public_key(self, db_engine):
        """Test querying SignalStrength by destination public key."""
        dest_key = "z" * 64

        with db_engine.session_scope() as session:
            session.add(
                SignalStrength(
                    source_public_key="a" * 64,
                    destination_public_key=dest_key,
                    snr=10.0,
                )
            )
            session.add(
                SignalStrength(
                    source_public_key="b" * 64,
                    destination_public_key=dest_key,
                    snr=12.0,
                )
            )
            session.add(
                SignalStrength(
                    source_public_key="c" * 64,
                    destination_public_key="d" * 64,
                    snr=8.0,
                )
            )

        with db_engine.session_scope() as session:
            records = (
                session.query(SignalStrength)
                .filter(SignalStrength.destination_public_key == dest_key)
                .all()
            )
            assert len(records) == 2

    def test_query_by_trace_path_id(self, db_engine):
        """Test querying SignalStrength by trace_path_id."""
        with db_engine.session_scope() as session:
            session.add(
                SignalStrength(
                    source_public_key="a" * 64,
                    destination_public_key="b" * 64,
                    snr=10.0,
                    trace_path_id=100,
                )
            )
            session.add(
                SignalStrength(
                    source_public_key="b" * 64,
                    destination_public_key="c" * 64,
                    snr=12.0,
                    trace_path_id=100,
                )
            )
            session.add(
                SignalStrength(
                    source_public_key="d" * 64,
                    destination_public_key="e" * 64,
                    snr=8.0,
                    trace_path_id=200,
                )
            )

        with db_engine.session_scope() as session:
            records = (
                session.query(SignalStrength).filter(SignalStrength.trace_path_id == 100).all()
            )
            assert len(records) == 2


# =============================================================================
# SignalStrength API Schema Tests
# =============================================================================


class TestSignalStrengthResponse:
    """Test SignalStrengthResponse schema."""

    def test_basic_response(self):
        """Test basic SignalStrengthResponse creation."""
        response = SignalStrengthResponse(
            id=1,
            source_public_key="a" * 64,
            destination_public_key="b" * 64,
            snr=15.5,
            recorded_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.source_public_key == "a" * 64
        assert response.destination_public_key == "b" * 64
        assert response.snr == 15.5
        assert response.trace_path_id is None

    def test_response_with_trace_path_id(self):
        """Test SignalStrengthResponse with trace_path_id."""
        response = SignalStrengthResponse(
            id=2,
            source_public_key="c" * 64,
            destination_public_key="d" * 64,
            snr=-5.2,
            trace_path_id=42,
            recorded_at=datetime.utcnow(),
        )
        assert response.trace_path_id == 42
        assert response.snr == -5.2

    def test_response_negative_snr(self):
        """Test SignalStrengthResponse with negative SNR."""
        response = SignalStrengthResponse(
            id=3,
            source_public_key="e" * 64,
            destination_public_key="f" * 64,
            snr=-20.5,
            recorded_at=datetime.utcnow(),
        )
        assert response.snr == -20.5


class TestSignalStrengthListResponse:
    """Test SignalStrengthListResponse schema."""

    def test_empty_list(self):
        """Test SignalStrengthListResponse with empty list."""
        response = SignalStrengthListResponse(
            signal_strengths=[],
            total=0,
            limit=100,
            offset=0,
        )
        assert len(response.signal_strengths) == 0
        assert response.total == 0

    def test_list_with_items(self):
        """Test SignalStrengthListResponse with items."""
        items = [
            SignalStrengthResponse(
                id=i,
                source_public_key=f"{i}" * 64,
                destination_public_key=f"{i+1}" * 64,
                snr=10.0 + i,
                recorded_at=datetime.utcnow(),
            )
            for i in range(3)
        ]
        response = SignalStrengthListResponse(
            signal_strengths=items,
            total=3,
            limit=100,
            offset=0,
        )
        assert len(response.signal_strengths) == 3
        assert response.total == 3

    def test_list_pagination(self):
        """Test SignalStrengthListResponse pagination fields."""
        response = SignalStrengthListResponse(
            signal_strengths=[],
            total=100,
            limit=10,
            offset=50,
        )
        assert response.limit == 10
        assert response.offset == 50


class TestSignalStrengthFilters:
    """Test SignalStrengthFilters schema."""

    def test_empty_filters(self):
        """Test empty SignalStrengthFilters."""
        filters = SignalStrengthFilters()
        assert filters.source_public_key is None
        assert filters.destination_public_key is None
        assert filters.start_date is None
        assert filters.end_date is None

    def test_source_public_key_filter(self):
        """Test source_public_key filter."""
        filters = SignalStrengthFilters(source_public_key="a" * 64)
        assert filters.source_public_key == "a" * 64

    def test_source_public_key_too_short(self):
        """Test source_public_key minimum length validation."""
        with pytest.raises(ValidationError):
            SignalStrengthFilters(source_public_key="a" * 63)

    def test_source_public_key_too_long(self):
        """Test source_public_key maximum length validation."""
        with pytest.raises(ValidationError):
            SignalStrengthFilters(source_public_key="a" * 65)

    def test_destination_public_key_filter(self):
        """Test destination_public_key filter."""
        filters = SignalStrengthFilters(destination_public_key="b" * 64)
        assert filters.destination_public_key == "b" * 64

    def test_destination_public_key_too_short(self):
        """Test destination_public_key minimum length validation."""
        with pytest.raises(ValidationError):
            SignalStrengthFilters(destination_public_key="b" * 63)

    def test_destination_public_key_too_long(self):
        """Test destination_public_key maximum length validation."""
        with pytest.raises(ValidationError):
            SignalStrengthFilters(destination_public_key="b" * 65)

    def test_date_filters(self):
        """Test date filters."""
        now = datetime.utcnow()
        filters = SignalStrengthFilters(start_date=now, end_date=now)
        assert filters.start_date == now
        assert filters.end_date == now

    def test_all_filters(self):
        """Test all filters together."""
        now = datetime.utcnow()
        filters = SignalStrengthFilters(
            source_public_key="a" * 64,
            destination_public_key="b" * 64,
            start_date=now,
            end_date=now,
        )
        assert filters.source_public_key == "a" * 64
        assert filters.destination_public_key == "b" * 64
        assert filters.start_date == now
        assert filters.end_date == now


# =============================================================================
# Event Handler Tests for SignalStrength
# =============================================================================


class TestResolvePrefixToFullKey:
    """Test _resolve_prefix_to_full_key method."""

    def test_resolve_single_match(self, db_engine):
        """Test resolving prefix with single matching node."""
        from meshcore_api.subscriber.event_handler import EventHandler

        public_key = "ab" + "c" * 62

        with db_engine.session_scope() as session:
            node = Node(
                public_key=public_key,
                public_key_prefix_2=public_key[:2],
                public_key_prefix_8=public_key[:8],
            )
            session.add(node)

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, "ab")
            assert result == public_key

    def test_resolve_no_match(self, db_engine):
        """Test resolving prefix with no matching nodes."""
        from meshcore_api.subscriber.event_handler import EventHandler

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, "zz")
            assert result is None

    def test_resolve_multiple_matches_uses_most_recent(self, db_engine):
        """Test resolving prefix with multiple matches uses most recent last_seen."""
        from meshcore_api.subscriber.event_handler import EventHandler

        key1 = "ab" + "1" * 62
        key2 = "ab" + "2" * 62
        key3 = "ab" + "3" * 62

        now = datetime.utcnow()
        old_time = now - timedelta(hours=1)
        very_old_time = now - timedelta(hours=2)

        with db_engine.session_scope() as session:
            # Add nodes with different last_seen times
            session.add(
                Node(
                    public_key=key1,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key1[:8],
                    last_seen=very_old_time,
                )
            )
            session.add(
                Node(
                    public_key=key2,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key2[:8],
                    last_seen=now,  # Most recent
                )
            )
            session.add(
                Node(
                    public_key=key3,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key3[:8],
                    last_seen=old_time,
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, "ab")
            assert result == key2  # Should be the most recent one

    def test_resolve_multiple_matches_no_last_seen(self, db_engine):
        """Test resolving prefix with multiple matches and no last_seen uses first."""
        from meshcore_api.subscriber.event_handler import EventHandler

        key1 = "ab" + "1" * 62
        key2 = "ab" + "2" * 62

        with db_engine.session_scope() as session:
            # Add nodes without last_seen
            session.add(
                Node(
                    public_key=key1,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key1[:8],
                )
            )
            session.add(
                Node(
                    public_key=key2,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key2[:8],
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, "ab")
            # Should return one of them (first one in query order)
            assert result in [key1, key2]

    def test_resolve_empty_prefix(self, db_engine):
        """Test resolving empty prefix returns None."""
        from meshcore_api.subscriber.event_handler import EventHandler

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, "")
            assert result is None

    def test_resolve_none_prefix(self, db_engine):
        """Test resolving None prefix returns None."""
        from meshcore_api.subscriber.event_handler import EventHandler

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, None)
            assert result is None

    def test_resolve_single_char_prefix(self, db_engine):
        """Test resolving single character prefix returns None."""
        from meshcore_api.subscriber.event_handler import EventHandler

        handler = EventHandler()
        with db_engine.session_scope() as session:
            result = handler._resolve_prefix_to_full_key(session, "a")
            assert result is None


class TestCreateSignalStrengthRecords:
    """Test _create_signal_strength_records method."""

    def test_create_records_for_consecutive_pairs(self, db_engine):
        """Test creating SignalStrength records for consecutive node pairs."""
        from meshcore_api.subscriber.event_handler import EventHandler

        # Create nodes for the path
        key_ab = "ab" + "1" * 62
        key_cd = "cd" + "2" * 62
        key_ef = "ef" + "3" * 62

        with db_engine.session_scope() as session:
            session.add(
                Node(
                    public_key=key_ab,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key_ab[:8],
                )
            )
            session.add(
                Node(
                    public_key=key_cd,
                    public_key_prefix_2="cd",
                    public_key_prefix_8=key_cd[:8],
                )
            )
            session.add(
                Node(
                    public_key=key_ef,
                    public_key_prefix_2="ef",
                    public_key_prefix_8=key_ef[:8],
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            handler._create_signal_strength_records(
                session,
                trace_path_id=1,
                path_hashes=["ab", "cd", "ef"],
                snr_values=[10.0, 15.0, 12.0],
            )

        # Should create 2 records (cd->ef with snr 15.0, and ef with snr 12.0)
        # Actually: snr_values[1] is from ab->cd, snr_values[2] is from cd->ef
        with db_engine.session_scope() as session:
            records = session.query(SignalStrength).all()
            assert len(records) == 2

            # First record: ab -> cd with SNR 15.0 (snr_values[1])
            record1 = [r for r in records if r.destination_public_key == key_cd][0]
            assert record1.source_public_key == key_ab
            assert record1.snr == 15.0
            assert record1.trace_path_id == 1

            # Second record: cd -> ef with SNR 12.0 (snr_values[2])
            record2 = [r for r in records if r.destination_public_key == key_ef][0]
            assert record2.source_public_key == key_cd
            assert record2.snr == 12.0
            assert record2.trace_path_id == 1

    def test_create_records_skips_unresolvable_prefixes(self, db_engine):
        """Test that unresolvable prefixes are skipped."""
        from meshcore_api.subscriber.event_handler import EventHandler

        # Only create node for "ab", not for "cd" or "ef"
        key_ab = "ab" + "1" * 62

        with db_engine.session_scope() as session:
            session.add(
                Node(
                    public_key=key_ab,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key_ab[:8],
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            handler._create_signal_strength_records(
                session,
                trace_path_id=1,
                path_hashes=["ab", "cd", "ef"],
                snr_values=[10.0, 15.0, 12.0],
            )

        # No records should be created because cd and ef can't be resolved
        with db_engine.session_scope() as session:
            count = session.query(SignalStrength).count()
            assert count == 0

    def test_create_records_single_node_path(self, db_engine):
        """Test that single-node path creates no records."""
        from meshcore_api.subscriber.event_handler import EventHandler

        key_ab = "ab" + "1" * 62

        with db_engine.session_scope() as session:
            session.add(
                Node(
                    public_key=key_ab,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key_ab[:8],
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            handler._create_signal_strength_records(
                session,
                trace_path_id=1,
                path_hashes=["ab"],
                snr_values=[10.0],
            )

        # No records should be created (need at least 2 nodes for a pair)
        with db_engine.session_scope() as session:
            count = session.query(SignalStrength).count()
            assert count == 0

    def test_create_records_empty_path(self, db_engine):
        """Test that empty path creates no records."""
        from meshcore_api.subscriber.event_handler import EventHandler

        handler = EventHandler()
        with db_engine.session_scope() as session:
            handler._create_signal_strength_records(
                session,
                trace_path_id=1,
                path_hashes=[],
                snr_values=[],
            )

        with db_engine.session_scope() as session:
            count = session.query(SignalStrength).count()
            assert count == 0

    def test_create_records_handles_none_values(self, db_engine):
        """Test that None values in path or snr are handled."""
        from meshcore_api.subscriber.event_handler import EventHandler

        key_ab = "ab" + "1" * 62
        key_cd = "cd" + "2" * 62

        with db_engine.session_scope() as session:
            session.add(
                Node(
                    public_key=key_ab,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key_ab[:8],
                )
            )
            session.add(
                Node(
                    public_key=key_cd,
                    public_key_prefix_2="cd",
                    public_key_prefix_8=key_cd[:8],
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            handler._create_signal_strength_records(
                session,
                trace_path_id=1,
                path_hashes=["ab", None, "cd"],
                snr_values=[10.0, None, 12.0],
            )

        # Should skip the None entries
        with db_engine.session_scope() as session:
            count = session.query(SignalStrength).count()
            # snr_values[1] is None, so ab->None is skipped
            # snr_values[2] is 12.0, dest is "cd", source is None, so skipped
            assert count == 0

    def test_create_records_mismatched_lengths(self, db_engine):
        """Test handling of mismatched path_hashes and snr_values lengths."""
        from meshcore_api.subscriber.event_handler import EventHandler

        key_ab = "ab" + "1" * 62
        key_cd = "cd" + "2" * 62
        key_ef = "ef" + "3" * 62

        with db_engine.session_scope() as session:
            session.add(
                Node(
                    public_key=key_ab,
                    public_key_prefix_2="ab",
                    public_key_prefix_8=key_ab[:8],
                )
            )
            session.add(
                Node(
                    public_key=key_cd,
                    public_key_prefix_2="cd",
                    public_key_prefix_8=key_cd[:8],
                )
            )
            session.add(
                Node(
                    public_key=key_ef,
                    public_key_prefix_2="ef",
                    public_key_prefix_8=key_ef[:8],
                )
            )

        handler = EventHandler()
        with db_engine.session_scope() as session:
            # More path_hashes than snr_values
            handler._create_signal_strength_records(
                session,
                trace_path_id=1,
                path_hashes=["ab", "cd", "ef"],
                snr_values=[10.0, 15.0],  # Missing one SNR value
            )

        # Should only create 1 record (ab->cd with snr 15.0)
        with db_engine.session_scope() as session:
            records = session.query(SignalStrength).all()
            assert len(records) == 1
            assert records[0].source_public_key == key_ab
            assert records[0].destination_public_key == key_cd
            assert records[0].snr == 15.0
