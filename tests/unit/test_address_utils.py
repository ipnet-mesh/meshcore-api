"""Unit tests for address utility functions."""

import pytest

from meshcore_api.utils.address import (
    extract_prefix,
    is_valid_public_key,
    matches_prefix,
    normalize_public_key,
    validate_public_key,
)


class TestIsValidPublicKey:
    """Test is_valid_public_key function."""

    def test_valid_hex_lowercase(self):
        """Test valid lowercase hex string."""
        assert is_valid_public_key("abcdef0123456789") is True

    def test_valid_hex_uppercase(self):
        """Test valid uppercase hex string."""
        assert is_valid_public_key("ABCDEF0123456789") is True

    def test_valid_hex_mixed_case(self):
        """Test valid mixed case hex string."""
        assert is_valid_public_key("AbCdEf0123456789") is True

    def test_valid_64_char_key(self):
        """Test valid 64-character hex key."""
        key = "a" * 64
        assert is_valid_public_key(key) is True

    def test_empty_string(self):
        """Test empty string returns False."""
        assert is_valid_public_key("") is False

    def test_none_value(self):
        """Test None value returns False."""
        assert is_valid_public_key(None) is False

    def test_invalid_characters(self):
        """Test string with invalid characters returns False."""
        assert is_valid_public_key("xyz123") is False
        assert is_valid_public_key("abc-def") is False
        assert is_valid_public_key("abc def") is False
        assert is_valid_public_key("abc@def") is False

    def test_short_valid_hex(self):
        """Test short but valid hex strings."""
        assert is_valid_public_key("ab") is True
        assert is_valid_public_key("12") is True


class TestValidatePublicKey:
    """Test validate_public_key function."""

    def test_valid_64_char_key(self):
        """Test valid 64-character key."""
        key = "a" * 64
        assert validate_public_key(key) is True

    def test_valid_64_char_mixed_hex(self):
        """Test valid 64-character key with mixed hex."""
        key = "abc123" + "d" * 58
        assert validate_public_key(key) is True

    def test_invalid_63_char_key(self):
        """Test 63-character key fails without allow_prefix."""
        key = "a" * 63
        assert validate_public_key(key) is False

    def test_invalid_65_char_key(self):
        """Test 65-character key fails."""
        key = "a" * 65
        assert validate_public_key(key) is False

    def test_prefix_allowed_short_key(self):
        """Test short key passes with allow_prefix=True."""
        assert validate_public_key("abc", allow_prefix=True) is True
        assert validate_public_key("ab", allow_prefix=True) is True

    def test_prefix_not_allowed_short_key(self):
        """Test short key fails with allow_prefix=False."""
        assert validate_public_key("abc", allow_prefix=False) is False
        assert validate_public_key("ab", allow_prefix=False) is False

    def test_empty_string(self):
        """Test empty string fails validation."""
        assert validate_public_key("") is False
        assert validate_public_key("", allow_prefix=True) is False

    def test_invalid_characters(self):
        """Test invalid characters fail validation."""
        key = "xyz" + "a" * 61
        assert validate_public_key(key) is False


class TestNormalizePublicKey:
    """Test normalize_public_key function."""

    def test_lowercase_conversion(self):
        """Test uppercase key is converted to lowercase."""
        key = "ABCDEF0123456789"
        assert normalize_public_key(key) == "abcdef0123456789"

    def test_already_lowercase(self):
        """Test lowercase key remains lowercase."""
        key = "abcdef0123456789"
        assert normalize_public_key(key) == "abcdef0123456789"

    def test_mixed_case_conversion(self):
        """Test mixed case key is converted to lowercase."""
        key = "AbCdEf0123456789"
        assert normalize_public_key(key) == "abcdef0123456789"

    def test_64_char_key(self):
        """Test 64-character key normalization."""
        key = "A" * 64
        assert normalize_public_key(key) == "a" * 64

    def test_short_key_normalization(self):
        """Test short keys can be normalized."""
        assert normalize_public_key("AB") == "ab"
        assert normalize_public_key("ABC123") == "abc123"

    def test_invalid_key_raises_error(self):
        """Test invalid key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid public key"):
            normalize_public_key("xyz123")

    def test_empty_string_raises_error(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid public key"):
            normalize_public_key("")

    def test_invalid_characters_raises_error(self):
        """Test invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid public key"):
            normalize_public_key("abc-def")


class TestExtractPrefix:
    """Test extract_prefix function."""

    def test_default_2_char_prefix(self):
        """Test default 2-character prefix extraction."""
        key = "abcdef0123456789"
        assert extract_prefix(key) == "ab"

    def test_custom_length_prefix(self):
        """Test custom length prefix extraction."""
        key = "abcdef0123456789"
        assert extract_prefix(key, length=8) == "abcdef01"
        assert extract_prefix(key, length=12) == "abcdef012345"

    def test_uppercase_normalized(self):
        """Test uppercase key is normalized before extraction."""
        key = "ABCDEF0123456789"
        assert extract_prefix(key) == "ab"

    def test_64_char_key_prefix(self):
        """Test prefix extraction from 64-character key."""
        key = "abc123" + "d" * 58
        assert extract_prefix(key, length=6) == "abc123"

    def test_key_too_short_raises_error(self):
        """Test key shorter than requested prefix raises ValueError."""
        key = "abc"
        with pytest.raises(ValueError, match="too short"):
            extract_prefix(key, length=10)

    def test_invalid_key_raises_error(self):
        """Test invalid key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid public key"):
            extract_prefix("xyz123")

    def test_exact_length_prefix(self):
        """Test extracting prefix same length as key."""
        key = "abcd"
        assert extract_prefix(key, length=4) == "abcd"


class TestMatchesPrefix:
    """Test matches_prefix function."""

    def test_exact_match(self):
        """Test exact prefix match."""
        full_key = "abcdef0123456789"
        prefix = "abc"
        assert matches_prefix(full_key, prefix) is True

    def test_full_key_match(self):
        """Test full key matches itself."""
        key = "a" * 64
        assert matches_prefix(key, key) is True

    def test_case_insensitive_match(self):
        """Test case-insensitive prefix matching."""
        full_key = "abcdef0123456789"
        prefix = "ABC"
        assert matches_prefix(full_key, prefix) is True

    def test_no_match(self):
        """Test non-matching prefix."""
        full_key = "abcdef0123456789"
        prefix = "xyz"
        assert matches_prefix(full_key, prefix) is False

    def test_prefix_longer_than_key(self):
        """Test prefix longer than full key."""
        full_key = "abc"
        prefix = "abcdef"
        assert matches_prefix(full_key, prefix) is False

    def test_invalid_full_key(self):
        """Test invalid full key returns False."""
        assert matches_prefix("xyz123", "xyz") is False

    def test_invalid_prefix(self):
        """Test invalid prefix returns False."""
        full_key = "abcdef0123456789"
        assert matches_prefix(full_key, "xyz") is False

    def test_64_char_keys(self):
        """Test matching with 64-character keys."""
        full_key = "abc123" + "d" * 58
        prefix = "abc123"
        assert matches_prefix(full_key, prefix) is True

    def test_empty_prefix(self):
        """Test empty prefix returns False."""
        full_key = "abcdef0123456789"
        assert matches_prefix(full_key, "") is False

    def test_empty_full_key(self):
        """Test empty full key returns False."""
        assert matches_prefix("", "abc") is False


class TestAddressUtilsIntegration:
    """Integration tests for combined address utility functions."""

    def test_normalize_and_extract_workflow(self):
        """Test normalizing then extracting prefix."""
        key = "ABCDEF0123456789"
        normalized = normalize_public_key(key)
        prefix = extract_prefix(normalized, length=6)
        assert prefix == "abcdef"

    def test_validate_normalize_extract_workflow(self):
        """Test full workflow: validate, normalize, extract."""
        key = "ABC123" + "D" * 58
        assert validate_public_key(key) is True
        normalized = normalize_public_key(key)
        assert normalized == "abc123" + "d" * 58
        prefix = extract_prefix(normalized, length=6)
        assert prefix == "abc123"

    def test_prefix_matching_workflow(self):
        """Test finding matching keys with prefixes."""
        keys = [
            "abc123" + "a" * 58,
            "abc456" + "b" * 58,
            "def789" + "c" * 58,
        ]
        search_prefix = "abc"

        matching = [k for k in keys if matches_prefix(k, search_prefix)]
        assert len(matching) == 2
        assert all(matches_prefix(k, search_prefix) for k in matching)
