"""Command endpoints for sending messages and requests to the mesh network."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...meshcore.interface import MeshCoreInterface
from ...queue import CommandQueueManager, CommandType, QueueFullError
from ..dependencies import check_write_enabled, get_command_queue, get_meshcore
from ..schemas import (
    PingRequest,
    PingResponse,
    QueueInfoSchema,
    SendAdvertRequest,
    SendAdvertResponse,
    SendChannelMessageRequest,
    SendChannelMessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    SendTelemetryRequestRequest,
    SendTelemetryRequestResponse,
    SendTracePathRequest,
    SendTracePathResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/commands/send_message",
    response_model=SendMessageResponse,
    summary="Send a direct message",
    description="Send a direct message to a specific node by public key",
    dependencies=[Depends(check_write_enabled)],
)
async def send_message(
    request: SendMessageRequest,
    queue_manager: CommandQueueManager = Depends(get_command_queue),
) -> SendMessageResponse:
    """
    Send a direct message to a node.

    Args:
        request: Message request with destination, text, and text_type
        queue_manager: Command queue manager instance

    Returns:
        Response with success status, estimated delivery time, and queue info

    Raises:
        HTTPException: If message sending fails or queue is full
    """
    try:
        # Enqueue message command
        result, queue_info = await queue_manager.enqueue(
            command_type=CommandType.SEND_MESSAGE,
            parameters={
                "destination": request.destination,
                "text": request.text,
                "text_type": request.text_type,
            },
        )

        # Extract estimated delivery time from result details if available
        estimated_ms = None
        if result.details and "event" in result.details:
            event_dict = result.details["event"]
            if event_dict:
                estimated_ms = event_dict.get("estimated_delivery_ms")

        logger.info(f"Message queued for {request.destination[:8]}...")

        return SendMessageResponse(
            success=result.success,
            message=result.message,
            estimated_delivery_ms=estimated_ms,
            queue_info=QueueInfoSchema(**queue_info.to_dict()) if queue_info else None,
        )

    except QueueFullError:
        logger.warning("Command queue is full")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command queue is full. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to queue message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue message: {str(e)}",
        )


@router.post(
    "/commands/send_channel_message",
    response_model=SendChannelMessageResponse,
    summary="Send a channel message",
    description="Broadcast a message to all nodes on the channel",
    dependencies=[Depends(check_write_enabled)],
)
async def send_channel_message(
    request: SendChannelMessageRequest,
    queue_manager: CommandQueueManager = Depends(get_command_queue),
) -> SendChannelMessageResponse:
    """
    Send a channel broadcast message.

    Args:
        request: Channel message request with text and flood setting
        queue_manager: Command queue manager instance

    Returns:
        Response with success status and queue info

    Raises:
        HTTPException: If message sending fails or queue is full
    """
    try:
        # Enqueue channel message command
        result, queue_info = await queue_manager.enqueue(
            command_type=CommandType.SEND_CHANNEL_MESSAGE,
            parameters={
                "text": request.text,
                "flood": request.flood,
            },
        )

        logger.info("Channel message queued")

        return SendChannelMessageResponse(
            success=result.success,
            message=result.message,
            queue_info=QueueInfoSchema(**queue_info.to_dict()) if queue_info else None,
        )

    except QueueFullError:
        logger.warning("Command queue is full")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command queue is full. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to queue channel message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue channel message: {str(e)}",
        )


@router.post(
    "/commands/send_advert",
    response_model=SendAdvertResponse,
    summary="Send an advertisement",
    description="Broadcast an advertisement to announce this device on the network",
    dependencies=[Depends(check_write_enabled)],
)
async def send_advert(
    request: SendAdvertRequest,
    queue_manager: CommandQueueManager = Depends(get_command_queue),
) -> SendAdvertResponse:
    """
    Send a self-advertisement.

    Args:
        request: Advertisement request with flood setting
        queue_manager: Command queue manager instance

    Returns:
        Response with success status and queue info

    Raises:
        HTTPException: If advertisement sending fails or queue is full
    """
    try:
        # Enqueue advertisement command
        result, queue_info = await queue_manager.enqueue(
            command_type=CommandType.SEND_ADVERT,
            parameters={
                "flood": request.flood,
            },
        )

        logger.info("Advertisement queued")

        return SendAdvertResponse(
            success=result.success,
            message=result.message,
            queue_info=QueueInfoSchema(**queue_info.to_dict()) if queue_info else None,
        )

    except QueueFullError:
        logger.warning("Command queue is full")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command queue is full. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to queue advertisement: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue advertisement: {str(e)}",
        )


@router.post(
    "/commands/send_trace_path",
    response_model=SendTracePathResponse,
    summary="Initiate a trace path",
    description="Initiate a trace path request to discover the route to a destination node",
    dependencies=[Depends(check_write_enabled)],
)
async def send_trace_path(
    request: SendTracePathRequest,
    queue_manager: CommandQueueManager = Depends(get_command_queue),
) -> SendTracePathResponse:
    """
    Initiate a trace path to a destination.

    Args:
        request: Trace path request with destination public key
        queue_manager: Command queue manager instance

    Returns:
        Response with success status, initiator tag, and queue info

    Raises:
        HTTPException: If trace path initiation fails or queue is full
    """
    try:
        # Enqueue trace path command
        result, queue_info = await queue_manager.enqueue(
            command_type=CommandType.SEND_TRACE_PATH,
            parameters={
                "destination": request.destination,
            },
        )

        # Extract initiator tag from result details if available
        initiator_tag = None
        if result.details and "event" in result.details:
            event_dict = result.details["event"]
            if event_dict:
                initiator_tag = event_dict.get("initiator_tag")

        logger.info(f"Trace path queued for {request.destination[:8]}...")

        return SendTracePathResponse(
            success=result.success,
            message=result.message,
            initiator_tag=initiator_tag,
            queue_info=QueueInfoSchema(**queue_info.to_dict()) if queue_info else None,
        )

    except QueueFullError:
        logger.warning("Command queue is full")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command queue is full. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to queue trace path: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue trace path: {str(e)}",
        )


@router.post(
    "/commands/ping",
    response_model=PingResponse,
    summary="Ping a node",
    description="Send a ping request to check connectivity to a specific node",
    dependencies=[Depends(check_write_enabled)],
)
async def ping_node(
    request: PingRequest,
    queue_manager: CommandQueueManager = Depends(get_command_queue),
) -> PingResponse:
    """
    Ping a node to check connectivity.

    Args:
        request: Ping request with destination public key
        queue_manager: Command queue manager instance

    Returns:
        Response with success status and queue info

    Raises:
        HTTPException: If ping fails or queue is full
    """
    try:
        # Enqueue ping command
        result, queue_info = await queue_manager.enqueue(
            command_type=CommandType.PING,
            parameters={
                "destination": request.destination,
            },
        )

        logger.info(f"Ping queued for {request.destination[:8]}...")

        return PingResponse(
            success=result.success,
            message=result.message,
            queue_info=QueueInfoSchema(**queue_info.to_dict()) if queue_info else None,
        )

    except QueueFullError:
        logger.warning("Command queue is full")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command queue is full. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to queue ping: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue ping: {str(e)}",
        )


@router.post(
    "/commands/send_telemetry_request",
    response_model=SendTelemetryRequestResponse,
    summary="Request telemetry from a node",
    description="Send a request to a node to return its telemetry data (sensors, battery, etc.)",
    dependencies=[Depends(check_write_enabled)],
)
async def send_telemetry_request(
    request: SendTelemetryRequestRequest,
    queue_manager: CommandQueueManager = Depends(get_command_queue),
) -> SendTelemetryRequestResponse:
    """
    Request telemetry from a node.

    Args:
        request: Telemetry request with destination public key
        queue_manager: Command queue manager instance

    Returns:
        Response with success status and queue info

    Raises:
        HTTPException: If telemetry request fails or queue is full
    """
    try:
        # Enqueue telemetry request command
        result, queue_info = await queue_manager.enqueue(
            command_type=CommandType.SEND_TELEMETRY_REQUEST,
            parameters={
                "destination": request.destination,
            },
        )

        logger.info(f"Telemetry request queued for {request.destination[:8]}...")

        return SendTelemetryRequestResponse(
            success=result.success,
            message=result.message,
            queue_info=QueueInfoSchema(**queue_info.to_dict()) if queue_info else None,
        )

    except QueueFullError:
        logger.warning("Command queue is full")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command queue is full. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to queue telemetry request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue telemetry request: {str(e)}",
        )
