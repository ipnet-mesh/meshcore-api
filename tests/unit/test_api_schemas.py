"""Unit tests for API Pydantic schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from meshcore_api.api.schemas import (
    AdvertisementFilters,
    AdvertisementResponse,
    BulkTagUpdateRequest,
    CoordinateValue,
    ErrorResponse,
    MessageFilters,
    MessageResponse,
    NodeResponse,
    PaginationParams,
    PingRequest,
    SendChannelMessageRequest,
    SendMessageRequest,
    SendAdvertRequest,
    SendTelemetryRequestRequest,
    SendTracePathRequest,
    TagValueRequest,
    TagValueUpdateRequest,
    TelemetryFilters,
    TracePathFilters,
)


class TestPaginationParams:
    """Test PaginationParams schema."""

    def test_default_values(self):
        """Test default pagination values."""
        params = PaginationParams()
        assert params.limit == 100
        assert params.offset == 0

    def test_custom_values(self):
        """Test custom pagination values."""
        params = PaginationParams(limit=50, offset=100)
        assert params.limit == 50
        assert params.offset == 100

    def test_limit_min_validation(self):
        """Test limit minimum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(limit=0)

    def test_limit_max_validation(self):
        """Test limit maximum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(limit=1001)

    def test_offset_min_validation(self):
        """Test offset minimum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(offset=-1)


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_error_only(self):
        """Test error response with just error message."""
        response = ErrorResponse(error="Something went wrong")
        assert response.error == "Something went wrong"
        assert response.detail is None

    def test_error_with_detail(self):
        """Test error response with detail."""
        response = ErrorResponse(error="Error", detail="Additional info")
        assert response.error == "Error"
        assert response.detail == "Additional info"


class TestNodeResponse:
    """Test NodeResponse schema."""

    def test_from_attributes(self):
        """Test NodeResponse can be created with from_attributes."""
        response = NodeResponse(
            id=1,
            public_key="a" * 64,
            first_seen=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.public_key == "a" * 64

    def test_optional_fields(self):
        """Test NodeResponse optional fields."""
        response = NodeResponse(
            id=1,
            public_key="a" * 64,
            node_type="repeater",
            name="Test Node",
            last_seen=datetime.utcnow(),
            first_seen=datetime.utcnow(),
            created_at=datetime.utcnow(),
            tags={"friendly_name": "My Node"},
        )
        assert response.node_type == "repeater"
        assert response.name == "Test Node"
        assert response.tags == {"friendly_name": "My Node"}


class TestMessageResponse:
    """Test MessageResponse schema."""

    def test_basic_message(self):
        """Test basic message response."""
        response = MessageResponse(
            id=1,
            direction="inbound",
            message_type="contact",
            content="Hello World",
            received_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.direction == "inbound"
        assert response.content == "Hello World"

    def test_message_with_all_fields(self):
        """Test message response with all fields."""
        response = MessageResponse(
            id=1,
            direction="inbound",
            message_type="channel",
            pubkey_prefix="abc123",
            channel_idx=4,
            txt_type=1,
            path_len=3,
            signature="sig123",
            content="Hello",
            snr=8.5,
            sender_timestamp=datetime.utcnow(),
            received_at=datetime.utcnow(),
        )
        assert response.channel_idx == 4
        assert response.snr == 8.5


class TestMessageFilters:
    """Test MessageFilters schema."""

    def test_empty_filters(self):
        """Test empty message filters."""
        filters = MessageFilters()
        assert filters.pubkey_prefix is None
        assert filters.channel_idx is None
        assert filters.message_type is None

    def test_pubkey_prefix_validation(self):
        """Test pubkey prefix length validation."""
        # Valid prefix (2-12 chars)
        filters = MessageFilters(pubkey_prefix="ab")
        assert filters.pubkey_prefix == "ab"

        filters = MessageFilters(pubkey_prefix="a" * 12)
        assert len(filters.pubkey_prefix) == 12

    def test_pubkey_prefix_too_short(self):
        """Test pubkey prefix minimum length."""
        with pytest.raises(ValidationError):
            MessageFilters(pubkey_prefix="a")

    def test_pubkey_prefix_too_long(self):
        """Test pubkey prefix maximum length."""
        with pytest.raises(ValidationError):
            MessageFilters(pubkey_prefix="a" * 13)


class TestAdvertisementResponse:
    """Test AdvertisementResponse schema."""

    def test_basic_advertisement(self):
        """Test basic advertisement response."""
        response = AdvertisementResponse(
            id=1,
            public_key="a" * 64,
            received_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.public_key == "a" * 64


class TestAdvertisementFilters:
    """Test AdvertisementFilters schema."""

    def test_node_prefix_validation(self):
        """Test node prefix length validation."""
        filters = AdvertisementFilters(node_prefix="ab")
        assert filters.node_prefix == "ab"

        filters = AdvertisementFilters(node_prefix="a" * 64)
        assert len(filters.node_prefix) == 64


class TestTracePathFilters:
    """Test TracePathFilters schema."""

    def test_date_filters(self):
        """Test trace path date filters."""
        now = datetime.utcnow()
        filters = TracePathFilters(start_date=now, end_date=now)
        assert filters.start_date == now
        assert filters.end_date == now


class TestTelemetryFilters:
    """Test TelemetryFilters schema."""

    def test_all_filters(self):
        """Test all telemetry filters."""
        now = datetime.utcnow()
        filters = TelemetryFilters(
            node_prefix="abc",
            start_date=now,
            end_date=now,
        )
        assert filters.node_prefix == "abc"


class TestSendMessageRequest:
    """Test SendMessageRequest schema."""

    def test_valid_request(self):
        """Test valid send message request."""
        request = SendMessageRequest(
            destination="a" * 64,
            text="Hello World",
        )
        assert request.destination == "a" * 64
        assert request.text == "Hello World"
        assert request.text_type == "plain"

    def test_destination_hex_validation(self):
        """Test destination must be valid hex."""
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(destination="g" * 64, text="Hello")
        assert "hexadecimal" in str(exc_info.value).lower()

    def test_destination_case_normalization(self):
        """Test destination is normalized to lowercase."""
        request = SendMessageRequest(
            destination="A" * 64,
            text="Hello",
        )
        assert request.destination == "a" * 64

    def test_destination_length_validation(self):
        """Test destination must be 64 characters."""
        with pytest.raises(ValidationError):
            SendMessageRequest(destination="abc", text="Hello")

    def test_text_min_length(self):
        """Test text minimum length."""
        with pytest.raises(ValidationError):
            SendMessageRequest(destination="a" * 64, text="")

    def test_text_max_length(self):
        """Test text maximum length."""
        with pytest.raises(ValidationError):
            SendMessageRequest(destination="a" * 64, text="x" * 1001)


class TestSendChannelMessageRequest:
    """Test SendChannelMessageRequest schema."""

    def test_valid_request(self):
        """Test valid channel message request."""
        request = SendChannelMessageRequest(text="Broadcast message")
        assert request.text == "Broadcast message"
        assert request.flood is False

    def test_with_flood(self):
        """Test channel message with flood enabled."""
        request = SendChannelMessageRequest(text="Flood message", flood=True)
        assert request.flood is True


class TestSendAdvertRequest:
    """Test SendAdvertRequest schema."""

    def test_default_flood(self):
        """Test default flood value."""
        request = SendAdvertRequest()
        assert request.flood is False

    def test_with_flood(self):
        """Test advert with flood enabled."""
        request = SendAdvertRequest(flood=True)
        assert request.flood is True


class TestSendTracePathRequest:
    """Test SendTracePathRequest schema."""

    def test_valid_request(self):
        """Test valid trace path request."""
        request = SendTracePathRequest(destination="a" * 64)
        assert request.destination == "a" * 64

    def test_destination_validation(self):
        """Test destination validation."""
        with pytest.raises(ValidationError):
            SendTracePathRequest(destination="invalid")


class TestPingRequest:
    """Test PingRequest schema."""

    def test_valid_request(self):
        """Test valid ping request."""
        request = PingRequest(destination="b" * 64)
        assert request.destination == "b" * 64

    def test_mixed_case_normalization(self):
        """Test mixed case destination is normalized."""
        request = PingRequest(destination="AbCdEf" + "0" * 58)
        assert request.destination == "abcdef" + "0" * 58


class TestSendTelemetryRequestRequest:
    """Test SendTelemetryRequestRequest schema."""

    def test_valid_request(self):
        """Test valid telemetry request."""
        request = SendTelemetryRequestRequest(destination="c" * 64)
        assert request.destination == "c" * 64


class TestCoordinateValue:
    """Test CoordinateValue schema."""

    def test_valid_coordinate(self):
        """Test valid coordinate."""
        coord = CoordinateValue(latitude=37.7749, longitude=-122.4194)
        assert coord.latitude == 37.7749
        assert coord.longitude == -122.4194

    def test_latitude_range(self):
        """Test latitude range validation."""
        # Valid extremes
        CoordinateValue(latitude=-90, longitude=0)
        CoordinateValue(latitude=90, longitude=0)

        # Invalid
        with pytest.raises(ValidationError):
            CoordinateValue(latitude=-91, longitude=0)
        with pytest.raises(ValidationError):
            CoordinateValue(latitude=91, longitude=0)

    def test_longitude_range(self):
        """Test longitude range validation."""
        # Valid extremes
        CoordinateValue(latitude=0, longitude=-180)
        CoordinateValue(latitude=0, longitude=180)

        # Invalid
        with pytest.raises(ValidationError):
            CoordinateValue(latitude=0, longitude=-181)
        with pytest.raises(ValidationError):
            CoordinateValue(latitude=0, longitude=181)


class TestTagValueUpdateRequest:
    """Test TagValueUpdateRequest schema."""

    def test_string_tag(self):
        """Test string tag value."""
        tag = TagValueUpdateRequest(value_type="string", value="Test Value")
        assert tag.value_type == "string"
        assert tag.value == "Test Value"

    def test_number_tag_int(self):
        """Test number tag with integer value."""
        tag = TagValueUpdateRequest(value_type="number", value=42)
        assert tag.value == 42

    def test_number_tag_float(self):
        """Test number tag with float value."""
        tag = TagValueUpdateRequest(value_type="number", value=3.14)
        assert tag.value == 3.14

    def test_boolean_tag_true(self):
        """Test boolean tag with True value."""
        tag = TagValueUpdateRequest(value_type="boolean", value=True)
        assert tag.value is True

    def test_boolean_tag_false(self):
        """Test boolean tag with False value."""
        tag = TagValueUpdateRequest(value_type="boolean", value=False)
        assert tag.value is False

    def test_coordinate_tag(self):
        """Test coordinate tag value."""
        coord = CoordinateValue(latitude=40.7128, longitude=-74.0060)
        tag = TagValueUpdateRequest(value_type="coordinate", value=coord)
        assert tag.value.latitude == 40.7128
        assert tag.value.longitude == -74.0060

    def test_string_type_wrong_value(self):
        """Test string type with non-string value fails."""
        with pytest.raises(ValidationError):
            TagValueUpdateRequest(value_type="string", value=123)

    def test_number_type_wrong_value(self):
        """Test number type with non-number value fails."""
        with pytest.raises(ValidationError):
            TagValueUpdateRequest(value_type="number", value="not a number")

    def test_number_type_boolean_value_fails(self):
        """Test number type rejects boolean values."""
        with pytest.raises(ValidationError):
            TagValueUpdateRequest(value_type="number", value=True)

    def test_boolean_type_wrong_value(self):
        """Test boolean type with non-boolean value fails."""
        with pytest.raises(ValidationError):
            TagValueUpdateRequest(value_type="boolean", value="true")


class TestTagValueRequest:
    """Test TagValueRequest schema (includes key)."""

    def test_with_key(self):
        """Test tag value request with key."""
        tag = TagValueRequest(key="friendly_name", value_type="string", value="My Node")
        assert tag.key == "friendly_name"
        assert tag.value == "My Node"

    def test_key_min_length(self):
        """Test key minimum length."""
        with pytest.raises(ValidationError):
            TagValueRequest(key="", value_type="string", value="test")

    def test_key_max_length(self):
        """Test key maximum length."""
        with pytest.raises(ValidationError):
            TagValueRequest(key="a" * 129, value_type="string", value="test")


class TestBulkTagUpdateRequest:
    """Test BulkTagUpdateRequest schema."""

    def test_valid_bulk_update(self):
        """Test valid bulk tag update."""
        request = BulkTagUpdateRequest(
            tags=[
                TagValueRequest(key="name", value_type="string", value="Test"),
                TagValueRequest(key="count", value_type="number", value=5),
            ]
        )
        assert len(request.tags) == 2

    def test_empty_tags_fails(self):
        """Test empty tags list fails."""
        with pytest.raises(ValidationError):
            BulkTagUpdateRequest(tags=[])

    def test_too_many_tags_fails(self):
        """Test too many tags fails."""
        tags = [
            TagValueRequest(key=f"tag_{i}", value_type="string", value=f"val_{i}")
            for i in range(51)
        ]
        with pytest.raises(ValidationError):
            BulkTagUpdateRequest(tags=tags)
