import httpx
import logging
from typing import Optional, Dict, List
from config import get_settings

logger = logging.getLogger(__name__)


class PortalService:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.portal_base_url
        self.api_key = self.settings.portal_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def get_docs(self) -> Optional[Dict]:
        """Get portal API documentation"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/docs")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching portal docs: {e}")
            return None

    async def get_ports(self) -> Optional[List[str]]:
        """Get list of available ports with their UN/LOCODE codes"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/ports",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching ports: {e}")
            return None

    async def get_rate(
        self,
        origin: str,
        destination: str,
        weight: str,
        volume: str,
        mode: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get shipping rate for a lane.

        Returns:
        - rate_data: Dict with price info
        - None if lane not found
        - Special response if desk needs to price it
        """
        try:
            params = {
                "origin": origin,
                "destination": destination,
                "weight": weight,
                "volume": volume
            }
            if mode:
                params["mode"] = mode

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rates",
                    params=params,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Rate not found for lane {origin}-{destination}")
                return {"status": "not_found"}
            elif e.response.status_code == 202:
                # Desk will price this
                try:
                    return e.response.json()
                except:
                    return {"status": "desk_pricing"}
            else:
                logger.error(f"HTTP error fetching rate: {e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching rate: {e}")
            return None

    async def handover_quote_to_desk(
        self,
        origin: str,
        destination: str,
        weight: str,
        volume: str,
        callback_email: str,
        mode: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Hand over a quote request to the quotations desk.
        Returns the request reference ID.
        """
        try:
            payload = {
                "origin": origin,
                "destination": destination,
                "weight": weight,
                "volume": volume,
                "callback_email": callback_email
            }
            if mode:
                payload["mode"] = mode

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/quotes/handover",
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error handing over quote: {e}")
            return None

    async def get_shipment(self, container_id: str) -> Optional[Dict]:
        """Get shipment status and ETA for a container"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/shipments/{container_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Shipment not found: {container_id}")
                return {"status": "not_found"}
            else:
                logger.error(f"HTTP error fetching shipment: {e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching shipment: {e}")
            return None
