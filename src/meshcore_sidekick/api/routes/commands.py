"""Command endpoints for sending messages and requests to the mesh network."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_meshcore
from ..schemas import (
    SendMessageRequest, SendMessageResponse,
    SendChannelMessageRequest, SendChannelMessageResponse,
    SendAdvertRequest, SendAdvertResponse,
    SendTracePathRequest, SendTracePathResponse,
    PingRequest, PingResponse,
    SendTelemetryRequestRequest, SendTelemetryRequestResponse,
)
from ...meshcore.interface import MeshCoreInterface

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/commands/send_message",
    response_model=SendMessageResponse,
    summary="Send a direct message",
    description="Send a direct message to a specific node by public key",
)
async def send_message(
    request: SendMessageRequest,
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> SendMessageResponse:
    """
    Send a direct message to a node.

    Args:
        request: Message request with destination, text, and text_type
        meshcore: MeshCore interface instance

    Returns:
        Response with success status and estimated delivery time

    Raises:
        HTTPException: If message sending fails
    """
    try:
        # Send message via MeshCore
        event = await meshcore.send_message(
            destination=request.destination,
            text=request.text,
            text_type=request.text_type,
        )

        # Extract estimated delivery time if available
        estimated_ms = event.payload.get("estimated_delivery_ms") if event.payload else None

        logger.info(f"Message sent to {request.destination[:8]}...")

        return SendMessageResponse(
            success=True,
            message=f"Message sent to {request.destination[:8]}...",
            estimated_delivery_ms=estimated_ms,
        )

    except Exception as e:
        logger.error(f"Failed to send message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}",
        )


@router.post(
    "/commands/send_channel_message",
    response_model=SendChannelMessageResponse,
    summary="Send a channel message",
    description="Broadcast a message to all nodes on the channel",
)
async def send_channel_message(
    request: SendChannelMessageRequest,
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> SendChannelMessageResponse:
    """
    Send a channel broadcast message.

    Args:
        request: Channel message request with text and flood setting
        meshcore: MeshCore interface instance

    Returns:
        Response with success status

    Raises:
        HTTPException: If message sending fails
    """
    try:
        # Send channel message via MeshCore
        await meshcore.send_channel_message(
            text=request.text,
            flood=request.flood,
        )

        logger.info("Channel message sent")

        return SendChannelMessageResponse(
            success=True,
            message="Channel message sent successfully",
        )

    except Exception as e:
        logger.error(f"Failed to send channel message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send channel message: {str(e)}",
        )


@router.post(
    "/commands/send_advert",
    response_model=SendAdvertResponse,
    summary="Send an advertisement",
    description="Broadcast an advertisement to announce this device on the network",
)
async def send_advert(
    request: SendAdvertRequest,
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> SendAdvertResponse:
    """
    Send a self-advertisement.

    Args:
        request: Advertisement request with flood setting
        meshcore: MeshCore interface instance

    Returns:
        Response with success status

    Raises:
        HTTPException: If advertisement sending fails
    """
    try:
        # Send advertisement via MeshCore
        await meshcore.send_advert(flood=request.flood)

        logger.info("Advertisement sent")

        return SendAdvertResponse(
            success=True,
            message="Advertisement sent successfully",
        )

    except Exception as e:
        logger.error(f"Failed to send advertisement: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send advertisement: {str(e)}",
        )


@router.post(
    "/commands/send_trace_path",
    response_model=SendTracePathResponse,
    summary="Initiate a trace path",
    description="Initiate a trace path request to discover the route to a destination node",
)
async def send_trace_path(
    request: SendTracePathRequest,
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> SendTracePathResponse:
    """
    Initiate a trace path to a destination.

    Args:
        request: Trace path request with destination public key
        meshcore: MeshCore interface instance

    Returns:
        Response with success status and initiator tag

    Raises:
        HTTPException: If trace path initiation fails
    """
    try:
        # Initiate trace path via MeshCore
        event = await meshcore.send_trace_path(destination=request.destination)

        # Extract initiator tag if available
        initiator_tag = event.payload.get("initiator_tag") if event.payload else None

        logger.info(f"Trace path initiated to {request.destination[:8]}...")

        return SendTracePathResponse(
            success=True,
            message=f"Trace path initiated to {request.destination[:8]}...",
            initiator_tag=initiator_tag,
        )

    except Exception as e:
        logger.error(f"Failed to initiate trace path: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate trace path: {str(e)}",
        )


@router.post(
    "/commands/ping",
    response_model=PingResponse,
    summary="Ping a node",
    description="Send a ping request to check connectivity to a specific node",
)
async def ping_node(
    request: PingRequest,
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> PingResponse:
    """
    Ping a node to check connectivity.

    Args:
        request: Ping request with destination public key
        meshcore: MeshCore interface instance

    Returns:
        Response with success status

    Raises:
        HTTPException: If ping fails
    """
    try:
        # Send ping via MeshCore
        await meshcore.ping(destination=request.destination)

        logger.info(f"Ping sent to {request.destination[:8]}...")

        return PingResponse(
            success=True,
            message=f"Ping sent to {request.destination[:8]}...",
        )

    except Exception as e:
        logger.error(f"Failed to send ping: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send ping: {str(e)}",
        )


@router.post(
    "/commands/send_telemetry_request",
    response_model=SendTelemetryRequestResponse,
    summary="Request telemetry from a node",
    description="Send a request to a node to return its telemetry data (sensors, battery, etc.)",
)
async def send_telemetry_request(
    request: SendTelemetryRequestRequest,
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> SendTelemetryRequestResponse:
    """
    Request telemetry from a node.

    Args:
        request: Telemetry request with destination public key
        meshcore: MeshCore interface instance

    Returns:
        Response with success status

    Raises:
        HTTPException: If telemetry request fails
    """
    try:
        # Send telemetry request via MeshCore
        await meshcore.send_telemetry_request(destination=request.destination)

        logger.info(f"Telemetry request sent to {request.destination[:8]}...")

        return SendTelemetryRequestResponse(
            success=True,
            message=f"Telemetry request sent to {request.destination[:8]}...",
        )

    except Exception as e:
        logger.error(f"Failed to send telemetry request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send telemetry request: {str(e)}",
        )
