"""Node management and querying endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from ...database.models import Message, Node, NodeTag, Telemetry
from ...utils.address import normalize_public_key, validate_public_key
from ..dependencies import get_db
from ..schemas import (
    CoordinateValue,
    MessageListResponse,
    NodeListResponse,
    NodeResponse,
    TelemetryListResponse,
)

router = APIRouter()


def get_node_tags_dict(node_public_key: str, db: Session) -> dict:
    """
    Get all tags for a node as a dictionary.

    Args:
        node_public_key: Node public key
        db: Database session

    Returns:
        Dictionary mapping tag keys to values
    """
    tags = db.query(NodeTag).filter(NodeTag.node_public_key == node_public_key).all()

    result = {}
    for tag in tags:
        if tag.value_type == "string":
            result[tag.key] = tag.value_string
        elif tag.value_type == "number":
            result[tag.key] = tag.value_number
        elif tag.value_type == "boolean":
            result[tag.key] = tag.value_boolean
        elif tag.value_type == "coordinate":
            result[tag.key] = {"latitude": tag.latitude, "longitude": tag.longitude}

    return result


def validate_full_public_key(public_key: str) -> str:
    """
    Validate and normalize a full 64-character public key.

    Note: This only validates the format, not whether the node exists in the database.
    Messages and telemetry can exist for nodes that haven't been added to the nodes table yet.

    Args:
        public_key: Public key (must be exactly 64 hex characters)

    Returns:
        Normalized full public key (64 hex characters, lowercase)

    Raises:
        HTTPException: If public key format is invalid
    """
    # Validate length
    if len(public_key) != 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public key must be exactly 64 hexadecimal characters. Use /nodes/{prefix} to resolve partial keys.",
        )

    # Normalize and validate hex characters
    try:
        normalized_key = normalize_public_key(public_key)
        if not validate_public_key(normalized_key, allow_prefix=False):
            raise ValueError("Invalid public key length")
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public key must be exactly 64 hexadecimal characters",
        )

    return normalized_key


@router.get(
    "/nodes",
    response_model=NodeListResponse,
    summary="List all nodes",
    description="Get a paginated list of all known nodes with optional sorting",
)
async def list_nodes(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of nodes to return"),
    offset: int = Query(0, ge=0, description="Number of nodes to skip"),
    sort_by: str = Query(
        "last_seen", description="Field to sort by (last_seen, first_seen, public_key)"
    ),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db),
) -> NodeListResponse:
    """
    List all nodes with pagination and sorting.

    Args:
        limit: Maximum number of nodes to return (1-1000)
        offset: Number of nodes to skip for pagination
        sort_by: Field to sort by (last_seen, first_seen, public_key)
        order: Sort order (asc or desc)
        db: Database session

    Returns:
        Paginated list of nodes
    """
    # Build query
    query = db.query(Node)

    # Apply sorting
    sort_field = Node.last_seen
    if sort_by == "first_seen":
        sort_field = Node.first_seen
    elif sort_by == "public_key":
        sort_field = Node.public_key

    if order == "desc":
        query = query.order_by(desc(sort_field))
    else:
        query = query.order_by(asc(sort_field))

    # Get total count
    total = query.count()

    # Apply pagination
    nodes = query.limit(limit).offset(offset).all()

    # Convert nodes to response models with tags
    node_responses = []
    for node in nodes:
        node_dict = {
            "id": node.id,
            "public_key": node.public_key,
            "node_type": node.node_type,
            "name": node.name,
            "last_seen": node.last_seen,
            "first_seen": node.first_seen,
            "created_at": node.created_at,
            "tags": get_node_tags_dict(node.public_key, db),
        }
        node_responses.append(NodeResponse(**node_dict))

    return NodeListResponse(
        nodes=node_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/nodes/{prefix}",
    response_model=NodeListResponse,
    summary="Search nodes by public key prefix",
    description="Find all nodes whose public key starts with the given prefix (2-64 characters)",
)
async def search_nodes_by_prefix(
    prefix: str,
    db: Session = Depends(get_db),
) -> NodeListResponse:
    """
    Search for nodes by public key prefix.

    Args:
        prefix: Public key prefix (2-64 hex characters)
        db: Database session

    Returns:
        List of matching nodes

    Raises:
        HTTPException: If prefix is invalid
    """
    # Validate prefix length
    if len(prefix) < 2 or len(prefix) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prefix must be between 2 and 64 characters",
        )

    # Normalize and validate prefix
    normalized_prefix = normalize_public_key(prefix)
    if not validate_public_key(normalized_prefix, allow_prefix=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prefix must contain only hexadecimal characters",
        )

    # Use the optimized prefix search method
    nodes = Node.find_by_prefix(db, normalized_prefix)

    # Convert nodes to response models with tags
    node_responses = []
    for node in nodes:
        node_dict = {
            "id": node.id,
            "public_key": node.public_key,
            "node_type": node.node_type,
            "name": node.name,
            "last_seen": node.last_seen,
            "first_seen": node.first_seen,
            "created_at": node.created_at,
            "tags": get_node_tags_dict(node.public_key, db),
        }
        node_responses.append(NodeResponse(**node_dict))

    return NodeListResponse(
        nodes=node_responses,
        total=len(nodes),
        limit=len(nodes),
        offset=0,
    )


@router.get(
    "/nodes/{public_key}/messages",
    response_model=MessageListResponse,
    summary="Get messages for a specific node",
    description="Get all messages sent to or from a specific node (requires full 64-character public key)",
)
async def get_node_messages(
    public_key: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    """
    Get messages for a specific node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        limit: Maximum number of messages to return
        offset: Number of messages to skip
        db: Database session

    Returns:
        Paginated list of messages

    Raises:
        HTTPException: If public key format is invalid
    """
    # Validate full public key
    normalized_key = validate_full_public_key(public_key)
    prefix12 = normalized_key[:12]

    # Query messages
    query = (
        db.query(Message)
        .filter(Message.message_type == "contact")
        .filter(Message.pubkey_prefix == prefix12)
        .order_by(desc(Message.sender_timestamp))
    )

    total = query.count()
    messages = query.limit(limit).offset(offset).all()

    return MessageListResponse(
        messages=[msg.__dict__ for msg in messages],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/nodes/{public_key}/telemetry",
    response_model=TelemetryListResponse,
    summary="Get telemetry data for a node",
    description="Get all telemetry data received from a specific node (requires full 64-character public key)",
)
async def get_node_telemetry(
    public_key: str,
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of telemetry records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of telemetry records to skip"),
    db: Session = Depends(get_db),
) -> TelemetryListResponse:
    """
    Get telemetry data for a specific node.

    Args:
        public_key: Node public key (must be exactly 64 hex characters)
        limit: Maximum number of records to return
        offset: Number of records to skip
        db: Database session

    Returns:
        Paginated list of telemetry records

    Raises:
        HTTPException: If public key format is invalid
    """
    # Validate full public key
    normalized_key = validate_full_public_key(public_key)

    # Query telemetry
    query = (
        db.query(Telemetry)
        .filter(Telemetry.node_public_key == normalized_key)
        .order_by(desc(Telemetry.received_at))
    )

    total = query.count()
    telemetry = query.limit(limit).offset(offset).all()

    return TelemetryListResponse(
        telemetry=[t.__dict__ for t in telemetry],
        total=total,
        limit=limit,
        offset=offset,
    )
