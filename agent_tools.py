"""
Agent tools for the Agno AI agent.
These tools wrap the portal service and make it callable by the agent.
"""

from portal_service import PortalService
from typing import Optional, Dict
import json
import logging

logger = logging.getLogger(__name__)
portal_service = PortalService()


def get_shipping_rate(
    origin: str,
    destination: str,
    weight: str,
    volume: str,
    mode: Optional[str] = None
) -> str:
    """
    Get shipping rate for a lane.

    Args:
        origin: Origin port/city name or UN/LOCODE
        destination: Destination port/city name or UN/LOCODE
        weight: Weight in the unit specified by customer
        volume: Volume in the unit specified by customer
        mode: Optional shipping mode (sea/air, LCL/FCL if applicable)

    Returns:
        JSON string with rate information or status
    """
    import asyncio
    try:
        result = asyncio.run(portal_service.get_rate(origin, destination, weight, volume, mode))
        return json.dumps(result or {"error": "Failed to fetch rate"})
    except Exception as e:
        logger.error(f"Error in get_shipping_rate: {e}")
        return json.dumps({"error": str(e)})


def get_shipment_status(container_id: str) -> str:
    """
    Get shipment status and ETA for a container.

    Args:
        container_id: Container or booking reference number

    Returns:
        JSON string with shipment information (status, ETA, events)
    """
    import asyncio
    try:
        result = asyncio.run(portal_service.get_shipment(container_id))
        return json.dumps(result or {"error": "Shipment not found"})
    except Exception as e:
        logger.error(f"Error in get_shipment_status: {e}")
        return json.dumps({"error": str(e)})


def get_available_ports() -> str:
    """
    Get list of available ports with their UN/LOCODE codes.
    Use this to resolve port names to their codes.

    Returns:
        JSON string with list of ports and their codes
    """
    import asyncio
    try:
        result = asyncio.run(portal_service.get_ports())
        return json.dumps(result or {"error": "Failed to fetch ports"})
    except Exception as e:
        logger.error(f"Error in get_available_ports: {e}")
        return json.dumps({"error": str(e)})


def handover_quote_to_desk(
    origin: str,
    destination: str,
    weight: str,
    volume: str,
    callback_email: str,
    mode: Optional[str] = None
) -> str:
    """
    Hand over a quote request to the quotations desk.
    This is used when the portal cannot price a lane immediately.

    Args:
        origin: Origin port/city
        destination: Destination port/city
        weight: Weight
        volume: Volume
        callback_email: Email to send the quote response to (typically the shared inbox)
        mode: Optional shipping mode

    Returns:
        JSON string with request reference ID for tracking
    """
    import asyncio
    try:
        result = asyncio.run(portal_service.handover_quote_to_desk(
            origin, destination, weight, volume, callback_email, mode
        ))
        return json.dumps(result or {"error": "Failed to handover quote"})
    except Exception as e:
        logger.error(f"Error in handover_quote_to_desk: {e}")
        return json.dumps({"error": str(e)})


# Tool definitions for Agno framework
AGENT_TOOLS = [
    {
        "name": "get_shipping_rate",
        "description": "Get shipping rate for a specific lane",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin port/city"},
                "destination": {"type": "string", "description": "Destination port/city"},
                "weight": {"type": "string", "description": "Weight"},
                "volume": {"type": "string", "description": "Volume"},
                "mode": {"type": "string", "description": "Shipping mode (optional)"}
            },
            "required": ["origin", "destination", "weight", "volume"]
        },
        "func": get_shipping_rate
    },
    {
        "name": "get_shipment_status",
        "description": "Get current status and ETA for a shipment",
        "parameters": {
            "type": "object",
            "properties": {
                "container_id": {"type": "string", "description": "Container or booking reference"}
            },
            "required": ["container_id"]
        },
        "func": get_shipment_status
    },
    {
        "name": "get_available_ports",
        "description": "Get list of available ports and their UN/LOCODE codes",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "func": get_available_ports
    },
    {
        "name": "handover_quote_to_desk",
        "description": "Hand over a quote request to the quotations desk for manual pricing",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "weight": {"type": "string"},
                "volume": {"type": "string"},
                "callback_email": {"type": "string", "description": "Email to send response to"},
                "mode": {"type": "string"}
            },
            "required": ["origin", "destination", "weight", "volume", "callback_email"]
        },
        "func": handover_quote_to_desk
    }
]
