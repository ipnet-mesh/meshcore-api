"""Tag import functionality for bulk loading node tags from JSON files."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from .api.schemas import TagValueRequest, CoordinateValue
from .api.routes.tags import ensure_node_exists, create_or_update_tag
from .database.engine import DatabaseEngine
from .utils.address import normalize_public_key, validate_public_key


@dataclass
class TagValidationError:
    """Represents a validation error."""

    node_public_key: Optional[str]
    tag_key: Optional[str]
    message: str


@dataclass
class ValidationResult:
    """Result of JSON file validation."""

    valid: bool
    errors: List[TagValidationError]
    node_count: int
    tag_count: int

    def print_errors(self):
        """Print validation errors to stderr."""
        if not self.errors:
            return

        print("\nValidation errors:", file=sys.stderr)
        for error in self.errors:
            if error.node_public_key and error.tag_key:
                print(f"  Node {error.node_public_key[:8]}..., tag '{error.tag_key}': {error.message}", file=sys.stderr)
            elif error.node_public_key:
                print(f"  Node {error.node_public_key[:8]}...: {error.message}", file=sys.stderr)
            else:
                print(f"  {error.message}", file=sys.stderr)


@dataclass
class ImportResult:
    """Result of tag import operation."""

    success: bool
    nodes_processed: int
    tags_processed: int
    errors: List[TagValidationError]

    def print_summary(self, dry_run: bool = False):
        """Print import summary."""
        if dry_run:
            print(f"\nDRY RUN - No changes applied")
            print(f"Would update {self.nodes_processed} nodes with {self.tags_processed} tags")
        else:
            if self.success:
                print(f"\nSuccessfully updated {self.nodes_processed} nodes with {self.tags_processed} tags")
            else:
                print(f"\nPartially completed: {self.nodes_processed} nodes, {self.tags_processed} tags", file=sys.stderr)

        if self.errors:
            print(f"\nErrors encountered: {len(self.errors)}", file=sys.stderr)
            for error in self.errors[:10]:  # Show first 10 errors
                if error.node_public_key and error.tag_key:
                    print(f"  Node {error.node_public_key[:8]}..., tag '{error.tag_key}': {error.message}", file=sys.stderr)
                elif error.node_public_key:
                    print(f"  Node {error.node_public_key[:8]}...: {error.message}", file=sys.stderr)
                else:
                    print(f"  {error.message}", file=sys.stderr)
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors", file=sys.stderr)


class TagImporter:
    """Handles importing tags from JSON files into the database."""

    def __init__(self, db_engine: DatabaseEngine):
        """
        Initialize tag importer.

        Args:
            db_engine: Database engine instance
        """
        self.db_engine = db_engine

    def load_and_validate_json(self, file_path: str) -> tuple[Optional[Dict], ValidationResult]:
        """
        Load and validate JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Tuple of (parsed data, validation result)
        """
        errors = []

        # Check file exists
        if not Path(file_path).exists():
            errors.append(TagValidationError(None, None, f"File not found: {file_path}"))
            return None, ValidationResult(False, errors, 0, 0)

        # Parse JSON
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(TagValidationError(None, None, f"Invalid JSON: {e}"))
            return None, ValidationResult(False, errors, 0, 0)
        except Exception as e:
            errors.append(TagValidationError(None, None, f"Error reading file: {e}"))
            return None, ValidationResult(False, errors, 0, 0)

        # Validate structure
        if not isinstance(data, dict):
            errors.append(TagValidationError(None, None, "JSON root must be an object"))
            return None, ValidationResult(False, errors, 0, 0)

        node_count = 0
        tag_count = 0

        # Validate each node and its tags
        for node_key, tags in data.items():
            # Validate public key
            try:
                normalized_key = normalize_public_key(node_key)
            except ValueError as e:
                errors.append(TagValidationError(
                    node_key,
                    None,
                    "Invalid public key format (must be hexadecimal characters)"
                ))
                continue

            if not validate_public_key(normalized_key, allow_prefix=False):
                errors.append(TagValidationError(
                    node_key,
                    None,
                    "Invalid public key length (must be 64 hexadecimal characters)"
                ))
                continue

            # Validate tags structure
            if not isinstance(tags, dict):
                errors.append(TagValidationError(
                    normalized_key,
                    None,
                    "Tags must be an object"
                ))
                continue

            node_count += 1

            # Validate each tag
            for tag_key, tag_data in tags.items():
                tag_count += 1

                # Validate tag structure
                if not isinstance(tag_data, dict):
                    errors.append(TagValidationError(
                        normalized_key,
                        tag_key,
                        "Tag must be an object with 'value_type' and 'value' fields"
                    ))
                    continue

                if 'value_type' not in tag_data or 'value' not in tag_data:
                    errors.append(TagValidationError(
                        normalized_key,
                        tag_key,
                        "Tag must have 'value_type' and 'value' fields"
                    ))
                    continue

                # Validate using Pydantic schema
                try:
                    # Convert coordinate dict to CoordinateValue if needed
                    value = tag_data['value']
                    if tag_data['value_type'] == 'coordinate':
                        if isinstance(value, dict):
                            value = CoordinateValue(**value)
                        else:
                            raise ValueError("Coordinate value must be an object with 'latitude' and 'longitude'")

                    TagValueRequest(
                        key=tag_key,
                        value_type=tag_data['value_type'],
                        value=value
                    )
                except PydanticValidationError as e:
                    error_messages = '; '.join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                    errors.append(TagValidationError(
                        normalized_key,
                        tag_key,
                        f"Validation error: {error_messages}"
                    ))
                except ValueError as e:
                    errors.append(TagValidationError(
                        normalized_key,
                        tag_key,
                        str(e)
                    ))

        valid = len(errors) == 0
        return data, ValidationResult(valid, errors, node_count, tag_count)

    def import_tags(
        self,
        data: Dict[str, Dict[str, Any]],
        dry_run: bool = False,
        continue_on_error: bool = False,
        verbose: bool = False
    ) -> ImportResult:
        """
        Import tags from validated data.

        Args:
            data: Validated tag data (node_public_key -> {tag_key -> tag_data})
            dry_run: If True, don't actually write to database
            continue_on_error: If True, continue processing on errors
            verbose: If True, show detailed output

        Returns:
            Import result with statistics and errors
        """
        errors = []
        nodes_processed = 0
        tags_processed = 0

        if dry_run:
            # In dry-run mode, just count what would be processed
            for node_key, tags in data.items():
                normalized_key = normalize_public_key(node_key)
                if verbose:
                    print(f"Would update node {normalized_key[:8]}...:")
                nodes_processed += 1
                for tag_key, tag_data in tags.items():
                    tags_processed += 1
                    if verbose:
                        value_display = tag_data['value']
                        if tag_data['value_type'] == 'coordinate':
                            value_display = f"({tag_data['value']['latitude']}, {tag_data['value']['longitude']})"
                        print(f"  - {tag_key}: {value_display}")

            return ImportResult(True, nodes_processed, tags_processed, errors)

        # Process in batches for better performance
        BATCH_SIZE = 100
        batch = []

        for node_key, tags in data.items():
            normalized_key = normalize_public_key(node_key)
            batch.append((normalized_key, tags))

            if len(batch) >= BATCH_SIZE:
                success, processed_nodes, processed_tags, batch_errors = self._process_batch(
                    batch, continue_on_error, verbose
                )
                nodes_processed += processed_nodes
                tags_processed += processed_tags
                errors.extend(batch_errors)

                if not success and not continue_on_error:
                    return ImportResult(False, nodes_processed, tags_processed, errors)

                batch = []

        # Process remaining batch
        if batch:
            success, processed_nodes, processed_tags, batch_errors = self._process_batch(
                batch, continue_on_error, verbose
            )
            nodes_processed += processed_nodes
            tags_processed += processed_tags
            errors.extend(batch_errors)

            if not success and not continue_on_error:
                return ImportResult(False, nodes_processed, tags_processed, errors)

        success = len(errors) == 0 or continue_on_error
        return ImportResult(success, nodes_processed, tags_processed, errors)

    def _process_batch(
        self,
        batch: List[tuple[str, Dict[str, Any]]],
        continue_on_error: bool,
        verbose: bool
    ) -> tuple[bool, int, int, List[TagValidationError]]:
        """
        Process a batch of nodes and tags.

        Args:
            batch: List of (node_public_key, tags_dict) tuples
            continue_on_error: If True, continue processing on errors
            verbose: If True, show detailed output

        Returns:
            Tuple of (success, nodes_processed, tags_processed, errors)
        """
        errors = []
        nodes_processed = 0
        tags_processed = 0

        try:
            with self.db_engine.session_scope() as session:
                for node_key, tags in batch:
                    try:
                        # Ensure node exists
                        ensure_node_exists(session, node_key)

                        if verbose:
                            print(f"Processing node {node_key[:8]}...: {len(tags)} tags")

                        # Process each tag
                        for tag_key, tag_data in tags.items():
                            try:
                                # Convert coordinate dict to CoordinateValue if needed
                                value = tag_data['value']
                                if tag_data['value_type'] == 'coordinate':
                                    if isinstance(value, dict):
                                        value = CoordinateValue(**value)

                                tag_request = TagValueRequest(
                                    key=tag_key,
                                    value_type=tag_data['value_type'],
                                    value=value
                                )

                                create_or_update_tag(session, node_key, tag_request)
                                tags_processed += 1

                            except Exception as e:
                                error_msg = f"Failed to create/update tag: {e}"
                                errors.append(TagValidationError(node_key, tag_key, error_msg))
                                if not continue_on_error:
                                    raise

                        nodes_processed += 1

                    except Exception as e:
                        error_msg = f"Failed to process node: {e}"
                        errors.append(TagValidationError(node_key, None, error_msg))
                        if not continue_on_error:
                            raise

                # Commit happens automatically on successful exit from session_scope

        except Exception as e:
            # Transaction will be rolled back automatically
            if not continue_on_error:
                return False, nodes_processed, tags_processed, errors

        return True, nodes_processed, tags_processed, errors

    def import_from_file(
        self,
        file_path: str,
        dry_run: bool = False,
        continue_on_error: bool = False,
        validate_only: bool = False,
        verbose: bool = False
    ) -> ImportResult:
        """
        Import tags from a JSON file.

        Args:
            file_path: Path to JSON file
            dry_run: If True, don't actually write to database
            continue_on_error: If True, continue processing on errors
            validate_only: If True, only validate without processing
            verbose: If True, show detailed output

        Returns:
            Import result with statistics and errors
        """
        print(f"Reading tags from: {file_path}")

        # Load and validate
        data, validation_result = self.load_and_validate_json(file_path)

        if not validation_result.valid:
            validation_result.print_errors()
            return ImportResult(False, 0, 0, validation_result.errors)

        print(f"Validated: {validation_result.node_count} nodes, {validation_result.tag_count} tags")

        if validate_only:
            print("Validation complete (--validate-only mode)")
            return ImportResult(True, 0, 0, [])

        # Import tags
        if not dry_run:
            print("Importing tags...")

        result = self.import_tags(data, dry_run, continue_on_error, verbose)
        result.print_summary(dry_run)

        return result
