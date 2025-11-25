"""Node management and querying endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import (
    NodeResponse, NodeListResponse, MessageListResponse,
    PathListResponse, TelemetryListResponse,
)
from ...database.models import Node, Message, Path, Telemetry
from ...utils.address import normalize_public_key, validate_public_key

router = APIRouter()


def resolve_public_key_or_prefix(prefix: str, db: Session) -> str:
    """
    Resolve a public key or prefix to a full public key.

    Args:
        prefix: Public key (64 chars) or prefix (2+ chars)
        db: Database session

    Returns:
        Full public key (64 hex characters)

    Raises:
        HTTPException: If prefix is invalid, no match found, or multiple matches
    """
    # Validate prefix length
    if len(prefix) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public key or prefix must be at least 2 characters",
        )

    # Normalize prefix
    normalized_prefix = normalize_public_key(prefix)
    if not validate_public_key(normalized_prefix, allow_prefix=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public key or prefix must contain only hexadecimal characters",
        )

    # If it's already 64 characters, just validate it exists
    if len(normalized_prefix) == 64:
        node = db.query(Node).filter(Node.public_key == normalized_prefix).first()
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node not found: {normalized_prefix[:8]}...",
            )
        return normalized_prefix

    # Otherwise, resolve the prefix
    nodes = Node.find_by_prefix(db, normalized_prefix)

    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No node found matching prefix '{prefix}'",
        )

    if len(nodes) > 1:
        matching_keys = [node.public_key[:8] + "..." for node in nodes[:5]]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prefix '{prefix}' matches {len(nodes)} nodes: {', '.join(matching_keys)}. Please use a longer prefix.",
        )

    return nodes[0].public_key


@router.get(
    "/nodes",
    response_model=NodeListResponse,
    summary="List all nodes",
    description="Get a paginated list of all known nodes with optional sorting",
)
async def list_nodes(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of nodes to return"),
    offset: int = Query(0, ge=0, description="Number of nodes to skip"),
    sort_by: str = Query("last_seen", description="Field to sort by (last_seen, first_seen, public_key)"),
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

    return NodeListResponse(
        nodes=[NodeResponse.model_validate(node) for node in nodes],
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

    return NodeListResponse(
        nodes=[NodeResponse.model_validate(node) for node in nodes],
        total=len(nodes),
        limit=len(nodes),
        offset=0,
    )


@router.get(
    "/nodes/{public_key}/messages",
    response_model=MessageListResponse,
    summary="Get messages for a specific node",
    description="Get all messages sent to or from a specific node (supports prefix matching with 2+ characters)",
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
        public_key: Node public key (64 hex characters) or prefix (2+ characters)
        limit: Maximum number of messages to return
        offset: Number of messages to skip
        db: Database session

    Returns:
        Paginated list of messages

    Raises:
        HTTPException: If public key/prefix is invalid, not found, or matches multiple nodes
    """
    # Resolve prefix to full public key
    normalized_key = resolve_public_key_or_prefix(public_key, db)

    # Query messages
    query = db.query(Message).filter(
        (Message.from_public_key == normalized_key) |
        (Message.to_public_key == normalized_key)
    ).order_by(desc(Message.timestamp))

    total = query.count()
    messages = query.limit(limit).offset(offset).all()

    return MessageListResponse(
        messages=[msg.__dict__ for msg in messages],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/nodes/{public_key}/paths",
    response_model=PathListResponse,
    summary="Get routing paths for a node",
    description="Get all known routing paths to a specific node (supports prefix matching with 2+ characters)",
)
async def get_node_paths(
    public_key: str,
    db: Session = Depends(get_db),
) -> PathListResponse:
    """
    Get routing paths for a specific node.

    Args:
        public_key: Node public key (64 hex characters) or prefix (2+ characters)
        db: Database session

    Returns:
        List of routing paths

    Raises:
        HTTPException: If public key/prefix is invalid, not found, or matches multiple nodes
    """
    # Resolve prefix to full public key
    normalized_key = resolve_public_key_or_prefix(public_key, db)

    # Query paths
    paths = db.query(Path).filter(
        Path.node_public_key == normalized_key
    ).order_by(desc(Path.updated_at)).all()

    return PathListResponse(
        paths=[path.__dict__ for path in paths],
        total=len(paths),
    )


@router.get(
    "/nodes/{public_key}/telemetry",
    response_model=TelemetryListResponse,
    summary="Get telemetry data for a node",
    description="Get all telemetry data received from a specific node (supports prefix matching with 2+ characters)",
)
async def get_node_telemetry(
    public_key: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of telemetry records to return"),
    offset: int = Query(0, ge=0, description="Number of telemetry records to skip"),
    db: Session = Depends(get_db),
) -> TelemetryListResponse:
    """
    Get telemetry data for a specific node.

    Args:
        public_key: Node public key (64 hex characters) or prefix (2+ characters)
        limit: Maximum number of records to return
        offset: Number of records to skip
        db: Database session

    Returns:
        Paginated list of telemetry records

    Raises:
        HTTPException: If public key/prefix is invalid, not found, or matches multiple nodes
    """
    # Resolve prefix to full public key
    normalized_key = resolve_public_key_or_prefix(public_key, db)

    # Query telemetry
    query = db.query(Telemetry).filter(
        Telemetry.node_public_key == normalized_key
    ).order_by(desc(Telemetry.received_at))

    total = query.count()
    telemetry = query.limit(limit).offset(offset).all()

    return TelemetryListResponse(
        telemetry=[t.__dict__ for t in telemetry],
        total=total,
        limit=limit,
        offset=offset,
    )
