"""Unit tests for database cleanup functionality."""

from unittest.mock import Mock, patch

import pytest

from meshcore_api.database.cleanup import DataCleanup


class TestDataCleanup:
    """Test database cleanup operations."""

    def test_cleanup_initialization(self):
        """Test DataCleanup initialization."""
        retention_days = 30
        cleanup = DataCleanup(retention_days=retention_days)

        assert cleanup.retention_days == retention_days

    def test_cleanup_initialization_custom_retention(self):
        """Test DataCleanup initialization with custom retention."""
        retention_days = 45
        cleanup = DataCleanup(retention_days=retention_days)

        assert cleanup.retention_days == 45

    @patch('meshcore_api.database.cleanup.session_scope')
    @patch('meshcore_api.database.cleanup.delete')
    @patch('meshcore_api.database.cleanup.logger')
    def test_cleanup_old_data(self, mock_logger, mock_delete, mock_session_scope):
        """Test cleanup old data functionality."""
        # Setup mocks
        mock_session = Mock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session_scope.return_value.__exit__.return_value = None

        mock_result = Mock()
        mock_result.rowcount = 100
        mock_session.execute.return_value = mock_result

        # Create cleanup instance
        cleanup = DataCleanup(retention_days=30)

        # Run cleanup
        result = cleanup.cleanup_old_data()

        # Verify result structure
        assert "messages" in result
        assert "advertisements" in result
        assert "telemetry" in result
        assert "trace_paths" in result
        assert "events_log" in result

        # Verify all delete operations were called
        assert mock_session.execute.call_count == 5
        assert mock_delete.call_count == 5

        # Verify logger was called
        mock_logger.info.assert_called()

    @patch('meshcore_api.database.cleanup.session_scope')
    def test_cleanup_with_different_retention_days(self, mock_session_scope):
        """Test cleanup with different retention periods."""
        mock_session = Mock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session_scope.return_value.__exit__.return_value = None

        mock_result = Mock()
        mock_result.rowcount = 50
        mock_session.execute.return_value = mock_result

        # Test with 7 days retention
        cleanup = DataCleanup(retention_days=7)
        result = cleanup.cleanup_old_data()

        assert cleanup.retention_days == 7
        assert isinstance(result, dict)

    @patch('meshcore_api.database.cleanup.session_scope')
    @patch('meshcore_api.database.cleanup.logger')
    def test_cleanup_logging(self, mock_logger, mock_session_scope):
        """Test cleanup logging functionality."""
        mock_session = Mock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session_scope.return_value.__exit__.return_value = None

        mock_result = Mock()
        mock_result.rowcount = 25
        mock_session.execute.return_value = mock_result

        cleanup = DataCleanup(retention_days=30)
        cleanup.cleanup_old_data()

        # Verify logging calls
        assert mock_logger.info.call_count >= 2  # Start and completion messages
        mock_logger.debug.assert_called_once()  # Detailed breakdown

    def test_cleanup_retention_validation(self):
        """Test cleanup retention period validation."""
        # Test various valid retention periods
        valid_periods = [1, 7, 30, 90, 365]

        for period in valid_periods:
            cleanup = DataCleanup(retention_days=period)
            assert cleanup.retention_days == period

    @patch('meshcore_api.database.cleanup.session_scope')
    def test_cleanup_result_counts(self, mock_session_scope):
        """Test cleanup returns correct deletion counts."""
        mock_session = Mock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session_scope.return_value.__exit__.return_value = None

        # Mock different deletion counts for each table
        mock_results = [10, 5, 15, 8, 12]  # Different row counts
        mock_session.execute.side_effect = [Mock(rowcount=count) for count in mock_results]

        cleanup = DataCleanup(retention_days=30)
        result = cleanup.cleanup_old_data()

        # Verify all expected keys are present
        expected_keys = ["messages", "advertisements", "telemetry", "trace_paths", "events_log"]
        for key in expected_keys:
            assert key in result

        # Verify total calculation
        expected_total = sum(mock_results)
        assert sum(result.values()) == expected_total