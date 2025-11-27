"""Node tag management endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_db, check_write_enabled
from ..schemas import (
    NodeResponse, NodeListResponse,
    NodeTagResponse, NodeTagListResponse, TagValueRequest, TagValueUpdateRequest,
    BulkTagUpdateRequest, BulkTagUpdateResponse, TagKeysResponse,
    CoordinateValue,
)
from ...database.models import Node, NodeTag
from ...utils.address import normalize_public_key, extract_prefix

router = APIRouter()


def validate_full_public_key(public_key: str) -> str:
    """
    Validate and normalize a full 64-character public key.

    Args:
        public_key: Public key (must be exactly 64 hex characters)

    Returns:
        Normalized full public key (64 hex characters, lowercase)

    Raises:
        HTTPException: If public key is invalid
    """
    from ...utils.address import validate_public_key

    # Validate length
    if len(public_key) != 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public key must be exactly 64 hexadecimal characters. Use /nodes/{prefix} to resolve partial keys.",
        )

    # Normalize and validate hex characters
    normalized_key = normalize_public_key(public_key)
    if not validate_public_key(normalized_key, allow_prefix=False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public key must contain only hexadecimal characters",
        )

    return normalized_key


def db_model_to_response(tag: NodeTag) -> NodeTagResponse:
    """Convert database model to API response."""
    if tag.value_type == 'string':
        value = tag.value_string
    elif tag.value_type == 'number':
        value = tag.value_number
    elif tag.value_type == 'boolean':
        value = tag.value_boolean
    elif tag.value_type == 'coordinate':
        value = CoordinateValue(latitude=tag.latitude, longitude=tag.longitude)
    else:
        raise ValueError(f"Unknown value type: {tag.value_type}")

    return NodeTagResponse(
        id=tag.id,
        node_public_key=tag.node_public_key,
        key=tag.key,
        value_type=tag.value_type,
        value=value,
        created_at=tag.created_at,
        updated_at=tag.updated_at
    )


def ensure_node_exists(db: Session, public_key: str) -> Node:
    """Ensure a node exists, creating it if necessary."""
    node = db.query(Node).filter(Node.public_key == public_key).first()
    if not node:
        # Create node if it doesn't exist
        node = Node(
            public_key=public_key,
            public_key_prefix_2=extract_prefix(public_key, 2),
            public_key_prefix_8=extract_prefix(public_key, 8),
        )
        db.add(node)
        db.flush()  # Flush to get the ID but don't commit yet
    return node


def create_or_update_tag(db: Session, node_public_key: str, tag_request: TagValueRequest) -> NodeTag:
    """Create or update a tag with proper type handling."""
    # Check if tag exists
    existing = db.query(NodeTag).filter_by(
        node_public_key=node_public_key,
        key=tag_request.key
    ).first()

    # Prepare values
    value_string = None
    value_number = None
    value_boolean = None
    latitude = None
    longitude = None

    if tag_request.value_type == 'string':
        value_string = tag_request.value
    elif tag_request.value_type == 'number':
        value_number = float(tag_request.value)
    elif tag_request.value_type == 'boolean':
        value_boolean = tag_request.value
    elif tag_request.value_type == 'coordinate':
        latitude = tag_request.value.latitude
        longitude = tag_request.value.longitude

    if existing:
        # Update existing tag
        existing.value_type = tag_request.value_type
        existing.value_string = value_string
        existing.value_number = value_number
        existing.value_boolean = value_boolean
        existing.latitude = latitude
        existing.longitude = longitude
        existing.updated_at = datetime.now()
        return existing
    else:
        # Create new tag
        tag = NodeTag(
            node_public_key=node_public_key,
            key=tag_request.key,
            value_type=tag_request.value_type,
            value_string=value_string,
            value_number=value_number,
            value_boolean=value_boolean,
            latitude=latitude,
            longitude=longitude,
        )
        db.add(tag)
        return tag


@router.get(
    "/nodes/{public_key}/tags",
    response_model=NodeTagListResponse,
    summary="Get all tags for a node",
    description="Get all custom metadata tags for a specific node (requires full 64-character public key)",
)
async def get_node_tags(
    public_key: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    offset: int = Query(0, ge=0, description="Number of tags to skip"),
    db: Session = Depends(get_db),
) -> NodeTagListResponse:
    """
    Get all tags for a node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        limit: Maximum number of tags to return
        offset: Number of tags to skip for pagination
        db: Database session

    Returns:
        List of tags with pagination info
    """
    # Validate full public key
    normalized_key = validate_full_public_key(public_key)

    # Query tags
    query = db.query(NodeTag).filter(NodeTag.node_public_key == normalized_key)
    total = query.count()
    tags = query.order_by(NodeTag.key).limit(limit).offset(offset).all()

    # Convert to response models
    tag_responses = [db_model_to_response(tag) for tag in tags]

    return NodeTagListResponse(
        tags=tag_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get(
    "/nodes/{public_key}/tags/{key}",
    response_model=NodeTagResponse,
    summary="Get a specific tag",
    description="Get the value of a specific tag for a node (requires full 64-character public key)",
)
async def get_node_tag(
    public_key: str,
    key: str,
    db: Session = Depends(get_db),
) -> NodeTagResponse:
    """
    Get a specific tag for a node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        key: Tag key
        db: Database session

    Returns:
        Tag value and metadata
    """
    # Validate full public key
    normalized_key = validate_full_public_key(public_key)

    # Query tag
    tag = db.query(NodeTag).filter_by(
        node_public_key=normalized_key,
        key=key
    ).first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag '{key}' not found for node {normalized_key[:8]}...",
        )

    return db_model_to_response(tag)


@router.put(
    "/nodes/{public_key}/tags/{key}",
    response_model=NodeTagResponse,
    summary="Set or update a tag",
    description="Set or update a single tag for a node (requires full 64-character public key)",
    dependencies=[Depends(check_write_enabled)],
)
async def set_node_tag(
    public_key: str,
    key: str,
    tag_value: TagValueUpdateRequest,
    db: Session = Depends(get_db),
) -> NodeTagResponse:
    """
    Set or update a tag for a node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        key: Tag key (from URL path)
        tag_value: Tag value and type (without key)
        db: Database session

    Returns:
        Updated tag
    """
    # Validate full public key
    normalized_key = validate_full_public_key(public_key)

    # Ensure node exists (will create if it doesn't)
    ensure_node_exists(db, normalized_key)

    # Create TagValueRequest with key from URL
    tag_request = TagValueRequest(
        key=key,
        value_type=tag_value.value_type,
        value=tag_value.value
    )

    # Create or update tag
    tag = create_or_update_tag(db, normalized_key, tag_request)
    db.commit()
    db.refresh(tag)

    return db_model_to_response(tag)


@router.post(
    "/nodes/{public_key}/tags/bulk",
    response_model=BulkTagUpdateResponse,
    summary="Bulk update tags",
    description="Update multiple tags on a single node (requires full 64-character public key)",
    dependencies=[Depends(check_write_enabled)],
)
async def bulk_update_tags(
    public_key: str,
    request: BulkTagUpdateRequest,
    db: Session = Depends(get_db),
) -> BulkTagUpdateResponse:
    """
    Bulk update multiple tags on a node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        request: List of tags to update
        db: Database session

    Returns:
        Success status and updated tags
    """
    try:
        # Validate full public key
        normalized_key = validate_full_public_key(public_key)

        # Ensure node exists (will create if it doesn't)
        ensure_node_exists(db, normalized_key)

        # Update all tags
        updated_tags = []
        for tag_request in request.tags:
            tag = create_or_update_tag(db, normalized_key, tag_request)
            updated_tags.append(tag)

        # Commit all changes atomically
        db.commit()

        # Refresh and convert to responses
        tag_responses = []
        for tag in updated_tags:
            db.refresh(tag)
            tag_responses.append(db_model_to_response(tag))

        return BulkTagUpdateResponse(
            success=True,
            message=f"Successfully updated {len(tag_responses)} tags",
            updated_count=len(tag_responses),
            tags=tag_responses
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tags: {str(e)}"
        )


@router.delete(
    "/nodes/{public_key}/tags/{key}",
    summary="Delete a tag",
    description="Delete a specific tag from a node (requires full 64-character public key)",
    dependencies=[Depends(check_write_enabled)],
)
async def delete_node_tag(
    public_key: str,
    key: str,
    db: Session = Depends(get_db),
):
    """
    Delete a tag from a node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        key: Tag key
        db: Database session

    Returns:
        Success message
    """
    # Validate full public key
    normalized_key = validate_full_public_key(public_key)

    # Query tag
    tag = db.query(NodeTag).filter_by(
        node_public_key=normalized_key,
        key=key
    ).first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag '{key}' not found for node {normalized_key[:8]}...",
        )

    db.delete(tag)
    db.commit()

    return {"success": True, "message": f"Tag '{key}' deleted"}


@router.get(
    "/tags",
    response_model=NodeTagListResponse,
    summary="Query tags across all nodes",
    description="Query tags with optional filters by key, value type, or node public key (full 64 chars)",
)
async def query_tags(
    key: Optional[str] = Query(None, description="Filter by tag key"),
    value_type: Optional[str] = Query(None, description="Filter by value type"),
    node_public_key: Optional[str] = Query(None, min_length=64, max_length=64, description="Filter by node public key (full 64 hex characters)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tags to return"),
    offset: int = Query(0, ge=0, description="Number of tags to skip"),
    db: Session = Depends(get_db),
) -> NodeTagListResponse:
    """
    Query tags across all nodes.

    Args:
        key: Optional filter by tag key
        value_type: Optional filter by value type
        node_public_key: Optional filter by node public key (must be exactly 64 hex characters)
        limit: Maximum number of tags to return
        offset: Number of tags to skip for pagination
        db: Database session

    Returns:
        List of matching tags with pagination info
    """
    # Build query
    query = db.query(NodeTag)

    if key:
        query = query.filter(NodeTag.key == key)

    if value_type:
        query = query.filter(NodeTag.value_type == value_type)

    if node_public_key:
        # Validate and normalize the full public key
        from ...utils.address import validate_public_key
        try:
            normalized_key = normalize_public_key(node_public_key)
            if not validate_public_key(normalized_key, allow_prefix=False):
                raise ValueError("Invalid public key length")
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_public_key must be exactly 64 hexadecimal characters",
            )
        query = query.filter(NodeTag.node_public_key == normalized_key)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    tags = query.order_by(NodeTag.node_public_key, NodeTag.key).limit(limit).offset(offset).all()

    # Convert to response models
    tag_responses = [db_model_to_response(tag) for tag in tags]

    return NodeTagListResponse(
        tags=tag_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get(
    "/tags/keys",
    response_model=TagKeysResponse,
    summary="List all unique tag keys",
    description="Get a list of all unique tag keys in use across all nodes",
)
async def get_tag_keys(
    db: Session = Depends(get_db),
) -> TagKeysResponse:
    """
    Get all unique tag keys.

    Args:
        db: Database session

    Returns:
        List of unique tag keys
    """
    # Query distinct keys
    keys = db.query(NodeTag.key).distinct().order_by(NodeTag.key).all()
    key_list = [key[0] for key in keys]

    return TagKeysResponse(
        keys=key_list,
        total=len(key_list)
    )


# Helper functions for querying nodes by tags

def _apply_tag_value_filter(query, tag_value: str):
    """Apply tag value filter with smart type coercion."""
    # Try boolean
    if tag_value.lower() in ('true', 'false'):
        bool_value = tag_value.lower() == 'true'
        return query.filter(
            NodeTag.value_type == 'boolean',
            NodeTag.value_boolean == bool_value
        )

    # Try number
    try:
        num_value = float(tag_value)
        return query.filter(
            NodeTag.value_type == 'number',
            NodeTag.value_number == num_value
        )
    except ValueError:
        pass

    # Default to string
    return query.filter(
        NodeTag.value_type == 'string',
        NodeTag.value_string == tag_value
    )


def _apply_node_sorting(query, sort_by: str, order: str):
    """Apply sorting to node query."""
    from sqlalchemy import desc, asc

    sort_field = Node.last_seen
    if sort_by == "first_seen":
        sort_field = Node.first_seen
    elif sort_by == "public_key":
        sort_field = Node.public_key

    if order == "desc":
        return query.order_by(desc(sort_field))
    return query.order_by(asc(sort_field))


@router.get(
    "/nodes/by-tag",
    response_model=NodeListResponse,
    summary="Query nodes by tag",
    description="Get nodes that have a specific tag key/value pair",
)
async def query_nodes_by_tag(
    tag_key: str = Query(..., description="Tag key to filter by"),
    tag_value: str = Query(..., description="Tag value to match (or 'EXISTS' for any value)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of nodes to return"),
    offset: int = Query(0, ge=0, description="Number of nodes to skip"),
    sort_by: str = Query("last_seen", description="Field to sort by (last_seen, first_seen, public_key)"),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db),
) -> NodeListResponse:
    """
    Query nodes by tag key/value.

    Args:
        tag_key: Tag key to filter by
        tag_value: Tag value to match (supports boolean, number, string, or 'EXISTS' for any value)
        limit: Maximum number of nodes to return
        offset: Number of nodes to skip for pagination
        sort_by: Field to sort by
        order: Sort order
        db: Database session

    Returns:
        Paginated list of nodes matching the tag criteria
    """
    # Build base query with join
    query = db.query(Node).join(
        NodeTag, Node.public_key == NodeTag.node_public_key
    ).filter(NodeTag.key == tag_key)

    # Apply value filter (with type coercion)
    if tag_value.upper() != "EXISTS":
        query = _apply_tag_value_filter(query, tag_value)

    # Apply sorting
    query = _apply_node_sorting(query, sort_by, order)

    # Get total count
    total = query.count()

    # Apply pagination
    nodes = query.limit(limit).offset(offset).all()

    return NodeListResponse(
        nodes=nodes,
        total=total,
        limit=limit,
        offset=offset
    )
