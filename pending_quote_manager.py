"""
Pending Quote Manager: State machine for quotes that fail portal creation.

Works with existing PendingQuote schema:
- Uses session_id to track per-thread state
- Uses timeout_at for expiration
- Uses status field for state transitions
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import uuid
import logging
from database import PendingQuote, Session, Email, get_session

logger = logging.getLogger(__name__)


class PendingQuoteManager:
    """Manage quotes pending portal resolution."""

    def __init__(self):
        self.db = get_session()

    def create_pending(
        self,
        email_id: str,
        session_id: str,
        origin: str = "",
        destination: str = "",
        timeout_hours: int = 24
    ) -> str:
        """
        Create pending quote when portal fails.

        Args:
            email_id: Gmail message ID
            session_id: Session ID (groups emails by thread)
            origin: Origin port for shipment
            destination: Destination port for shipment
            timeout_hours: When to escalate (default 24 hours)

        Returns:
            Pending quote ID
        """
        pending_id = str(uuid.uuid4())

        pending = PendingQuote(
            id=pending_id,
            session_id=session_id,
            email_id=email_id,
            request_reference=f"PENDING_{pending_id[:8]}",
            origin_port=origin,
            destination_port=destination,
            status="pending_portal_failure",
            timeout_at=datetime.utcnow() + timedelta(hours=timeout_hours)
        )

        self.db.add(pending)
        self.db.commit()

        logger.info(
            f"Created pending quote {pending_id} for session {session_id} "
            f"(expires: {pending.timeout_at})"
        )

        return pending_id

    def find_pending_in_session(self, session_id: str) -> Optional[PendingQuote]:
        """Find pending quote in same session (thread)."""
        return self.db.query(PendingQuote).filter(
            PendingQuote.session_id == session_id,
            PendingQuote.status.in_(["pending_portal_failure", "follow_up"])
        ).first()

    def handle_follow_up(
        self,
        session_id: str,
        pending: PendingQuote,
        portal_check_fn=None
    ) -> Tuple[str, Dict]:
        """
        Handle follow-up email to pending quote.

        Args:
            session_id: Session ID (for logging)
            pending: PendingQuote object to update
            portal_check_fn: Optional callback to check if quote is ready

        Returns:
            (status, details) tuple where status is one of:
            - "pending": still waiting for portal
            - "resolved": quote created
            - "escalated": timeout or too many follow-ups
        """
        # Check if expired
        if datetime.utcnow() > pending.timeout_at:
            logger.warning(
                f"Pending quote {pending.id} expired (24+ hours). "
                f"Escalating to human review."
            )
            pending.status = "escalated"
            self.db.commit()

            return "escalated", {
                "message": "Quote request has been escalated to our team for manual review.",
                "pending_id": pending.id
            }

        # Check if quote is now ready (if callback provided)
        if portal_check_fn:
            try:
                result = portal_check_fn(pending)

                if result.get("success"):
                    # Quote is ready!
                    pending.status = "resolved"
                    pending.quote_reply_sent = True
                    self.db.commit()

                    logger.info(
                        f"Pending quote {pending.id} resolved! "
                        f"Quote: {result.get('quote_id')}"
                    )

                    return "resolved", {
                        "message": f"Your quote is ready: {result.get('quote_id')}",
                        "quote_id": result.get("quote_id")
                    }
            except Exception as e:
                logger.error(f"Error checking quote status: {e}")

        # Still pending - mark as follow-up
        if pending.status == "pending_portal_failure":
            pending.status = "follow_up"

        self.db.commit()

        return "pending", {
            "message": f"We're still processing your request. "
                      f"Expected response within {24 - (datetime.utcnow() - pending.handover_timestamp).days} hours.",
            "pending_id": pending.id
        }

    def check_timeouts(self, portal_check_fn=None) -> Dict:
        """
        Cron job: check for expired pending quotes and escalate.

        This runs periodically (e.g., hourly) to find quotes that have
        exceeded their timeout window.
        """
        expired = self.db.query(PendingQuote).filter(
            PendingQuote.status.in_(["pending_portal_failure", "follow_up"]),
            PendingQuote.timeout_at < datetime.utcnow()
        ).all()

        escalated_count = 0
        resolved_count = 0

        for pending in expired:
            # Try portal one final time
            if portal_check_fn:
                try:
                    result = portal_check_fn(pending)

                    if result.get("success"):
                        pending.status = "resolved"
                        pending.quote_reply_sent = True
                        resolved_count += 1
                        logger.info(
                            f"Pending quote {pending.id} resolved after timeout check. "
                            f"Quote: {result.get('quote_id')}"
                        )
                    else:
                        pending.status = "escalated"
                        escalated_count += 1
                        logger.warning(f"Escalating expired pending quote {pending.id}")
                except Exception as e:
                    logger.error(f"Error checking quote {pending.id}: {e}")
                    pending.status = "escalated"
                    escalated_count += 1
            else:
                pending.status = "escalated"
                escalated_count += 1

            self.db.commit()

        return {
            "total_expired": len(expired),
            "resolved": resolved_count,
            "escalated": escalated_count
        }

    def get_status(self, pending_id: str) -> Dict:
        """Get status of pending quote."""
        pending = self.db.query(PendingQuote).filter(
            PendingQuote.id == pending_id
        ).first()

        if not pending:
            return {"error": "Not found"}

        time_remaining = (pending.timeout_at - datetime.utcnow()).total_seconds() / 3600

        return {
            "id": pending.id,
            "status": pending.status,
            "origin": pending.origin_port,
            "destination": pending.destination_port,
            "created_at": pending.handover_timestamp.isoformat(),
            "expires_at": pending.timeout_at.isoformat(),
            "time_remaining_hours": time_remaining if time_remaining > 0 else 0,
            "resolved": pending.quote_reply_sent
        }

    def close(self):
        """Close database session."""
        self.db.close()


# Portal decision engine
class PortalDecisionEngine:
    """Decide whether to call portal BEFORE making the call."""

    REQUIRES_PORTAL = {"rfq", "booking_request", "tracking_inquiry"}

    PORTAL_ACTIONS = {
        "rfq": "create_quote",
        "booking_request": "check_availability",
        "tracking_inquiry": "query_status"
    }

    @staticmethod
    def should_call_portal(category: str) -> bool:
        """Check if category needs portal call."""
        return category in PortalDecisionEngine.REQUIRES_PORTAL

    @staticmethod
    def get_portal_action(category: str) -> Optional[str]:
        """Get the specific portal action."""
        return PortalDecisionEngine.PORTAL_ACTIONS.get(category)


# Default replies for failures
FAILURE_REPLIES = {
    "CUSTOMER_NOT_FOUND": """Thank you for your RFQ.

We need to verify your account details before we can process this quote.
Please reply with:
- Company name
- Account number (if you have one)

Once verified, we'll provide a quote immediately.""",

    "ROUTE_NOT_AVAILABLE": """Thank you for your RFQ.

Unfortunately, we don't have availability for that route on the requested date.

Would you be interested in:
- A different departure date?
- A different port?

Please let us know and we'll get you a quote ASAP.""",

    "PORTAL_DOWN": """Thank you for your RFQ.

We're currently experiencing technical difficulties processing quotes.
Our team will manually review your request and respond within 2 hours.""",

    "SPACE_NOT_AVAILABLE": """Thank you for your booking request.

Unfortunately, we don't have space for that date/route.

Your options:
1. FCL service (if applicable)
2. Different date
3. Different port

Please let us know your preference.""",

    "SHIPMENT_NOT_FOUND": """Thank you for your tracking inquiry.

We couldn't find that shipment in our system.

Could you please verify:
- Container number (or Bill of Lading)
- Original shipment date
- Origin and destination

Once confirmed, we'll provide an immediate update.""",
}


def get_failure_reply(error: str) -> str:
    """Get professional reply template for portal failure."""
    return FAILURE_REPLIES.get(
        error,
        """Thank you for your inquiry.

We're currently processing your request. Our team will respond shortly."""
    )
