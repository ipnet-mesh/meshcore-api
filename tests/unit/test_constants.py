"""Unit tests for constants module - fixed to match actual implementation."""

import pytest

from meshcore_api import constants as const


class TestConstants:
    """Test application constants."""

    def test_node_type_map_structure(self):
        """Test that NODE_TYPE_MAP has correct structure."""
        assert hasattr(const, "NODE_TYPE_MAP")
        assert isinstance(const.NODE_TYPE_MAP, dict)

        # Check that it contains expected node types
        expected_keys = [0, 1, 2]
        for key in expected_keys:
            assert key in const.NODE_TYPE_MAP

        # Check that values are strings
        for value in const.NODE_TYPE_MAP.values():
            assert isinstance(value, str)

    def test_node_type_map_values(self):
        """Test specific values in NODE_TYPE_MAP."""
        assert const.NODE_TYPE_MAP[0] == "unknown"
        assert const.NODE_TYPE_MAP[1] == "cli"
        assert const.NODE_TYPE_MAP[2] == "rep"

    def test_node_type_name_with_valid_numbers(self):
        """Test node_type_name function with valid numeric inputs."""
        assert const.node_type_name(0) == "unknown"
        assert const.node_type_name(1) == "cli"
        assert const.node_type_name(2) == "rep"

    def test_node_type_name_with_invalid_numbers(self):
        """Test node_type_name function with invalid numeric inputs."""
        assert const.node_type_name(3) == "unknown"
        assert const.node_type_name(999) == "unknown"
        assert const.node_type_name(-1) == "unknown"

    def test_node_type_name_with_string_numbers(self):
        """Test node_type_name function with string representations of numbers."""
        assert const.node_type_name("0") == "unknown"
        assert const.node_type_name("1") == "cli"
        assert const.node_type_name("2") == "rep"

    def test_node_type_name_with_invalid_string_numbers(self):
        """Test node_type_name function with invalid string numbers."""
        assert const.node_type_name("3") == "unknown"
        assert const.node_type_name("999") == "unknown"
        assert const.node_type_name("-1") == "unknown"

    def test_node_type_name_with_valid_string_types(self):
        """Test node_type_name function with valid string type names."""
        assert const.node_type_name("unknown") == "unknown"
        assert const.node_type_name("cli") == "cli"
        assert const.node_type_name("rep") == "rep"

    def test_node_type_name_case_insensitive_strings(self):
        """Test node_type_name function with case insensitive string inputs."""
        assert const.node_type_name("UNKNOWN") == "unknown"
        assert const.node_type_name("CLI") == "cli"
        assert const.node_type_name("REP") == "rep"
        assert const.node_type_name("Cli") == "cli"
        assert const.node_type_name("ReP") == "rep"

    def test_node_type_name_with_whitespace(self):
        """Test node_type_name function handles whitespace correctly."""
        assert const.node_type_name("  cli  ") == "cli"
        assert const.node_type_name("\trep\n") == "rep"

    def test_node_type_name_with_invalid_strings(self):
        """Test node_type_name function with invalid string inputs."""
        assert const.node_type_name("invalid") == "unknown"
        assert const.node_type_name("not_a_type") == "unknown"
        assert const.node_type_name("random") == "unknown"

    def test_node_type_name_with_none_input(self):
        """Test node_type_name function with None input."""
        assert const.node_type_name(None) == "unknown"

    def test_node_type_name_with_non_numeric_strings(self):
        """Test node_type_name function with non-numeric strings."""
        assert const.node_type_name("abc") == "unknown"
        assert const.node_type_name("12.34") == "unknown"
        assert const.node_type_name("1abc") == "unknown"

    def test_node_type_name_with_edge_cases(self):
        """Test node_type_name function with edge cases."""
        # Empty string
        assert const.node_type_name("") == "unknown"

        # Float values (int() conversion truncates)
        assert const.node_type_name(1.0) == "cli"
        assert const.node_type_name(2.5) == "rep"  # int(2.5) == 2
        assert const.node_type_name(3.7) == "unknown"  # int(3.7) == 3

        # Boolean values
        assert const.node_type_name(True) == "cli"  # True is 1
        assert const.node_type_name(False) == "unknown"  # False is 0

    def test_node_type_map_immutability(self):
        """Test that NODE_TYPE_MAP is not accidentally modified."""
        original_map = const.NODE_TYPE_MAP.copy()

        # The function should not modify the global map
        const.node_type_name("test")

        assert const.NODE_TYPE_MAP == original_map

    def test_node_type_function_consistency(self):
        """Test that node_type_name is consistent across calls."""
        test_inputs = [0, 1, 2, "0", "1", "2", "cli", "rep", "unknown"]

        for input_val in test_inputs:
            result1 = const.node_type_name(input_val)
            result2 = const.node_type_name(input_val)
            assert result1 == result2

    def test_node_type_comprehensive_coverage(self):
        """Test that all node type mappings are covered."""
        # Test that all keys in NODE_TYPE_MAP work
        for key, expected_value in const.NODE_TYPE_MAP.items():
            result = const.node_type_name(key)
            assert result == expected_value

        # Test that all values in NODE_TYPE_MAP work when passed as strings
        for expected_value in const.NODE_TYPE_MAP.values():
            result = const.node_type_name(expected_value)
            assert result == expected_value
