"""
Tests for Pending Quote State Machine
Tests the hardest problem: managing state across multiple emails.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from pending_quote_manager import (
    PendingQuoteManager,
    PortalDecisionEngine,
    get_failure_reply
)
from database import PendingQuote, get_session
from test_fixtures import get_test_database


class TestPortalDecisionEngine:
    """Test portal call decision logic."""

    def test_rfq_requires_portal(self):
        """RFQ emails always need portal call."""
        assert PortalDecisionEngine.should_call_portal("rfq") is True
        assert PortalDecisionEngine.get_portal_action("rfq") == "create_quote"

    def test_booking_requires_portal(self):
        """Booking emails need portal call."""
        assert PortalDecisionEngine.should_call_portal("booking_request") is True
        assert PortalDecisionEngine.get_portal_action("booking_request") == "check_availability"

    def test_tracking_requires_portal(self):
        """Tracking emails need portal call."""
        assert PortalDecisionEngine.should_call_portal("tracking_inquiry") is True
        assert PortalDecisionEngine.get_portal_action("tracking_inquiry") == "query_status"

    def test_others_dont_require_portal(self):
        """Non-portal categories don't call portal."""
        categories = ["documentation", "complaint", "general_inquiry", "not_relevant"]

        for cat in categories:
            assert PortalDecisionEngine.should_call_portal(cat) is False
            assert PortalDecisionEngine.get_portal_action(cat) is None


class TestPendingQuoteCreation:
    """Test creating pending quotes when portal fails."""

    def test_create_pending_quote(self):
        """Create pending quote on portal failure."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        pending_id = manager.create_pending(
            email_id="MSG_RFQ_001",
            session_id="SESSION_123",
            origin="Shanghai",
            destination="LA",
            timeout_hours=24
        )

        assert pending_id is not None

        # Verify stored
        pending = db.query(PendingQuote).filter(
            PendingQuote.id == pending_id
        ).first()

        assert pending is not None
        assert pending.status == "pending_portal_failure"
        assert pending.session_id == "SESSION_123"
        assert pending.email_id == "MSG_RFQ_001"
        assert pending.origin_port == "Shanghai"
        assert pending.destination_port == "LA"

    def test_pending_quote_expiration(self):
        """Pending quote has correct expiration time."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        before = datetime.utcnow()
        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_123",
            timeout_hours=24
        )
        after = datetime.utcnow()

        pending = db.query(PendingQuote).filter(
            PendingQuote.id == pending_id
        ).first()

        # Expiration should be ~24 hours from now
        delta = (pending.timeout_at - pending.handover_timestamp).total_seconds() / 3600
        assert 23.9 < delta < 24.1


class TestFollowUpHandling:
    """Test handling follow-up emails to pending quotes."""

    def test_find_pending_in_session(self):
        """Find pending quote in same session."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        # Create pending
        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC",
            origin="Shanghai",
            destination="LA"
        )

        # Find by session
        found = manager.find_pending_in_session("SESSION_ABC")
        assert found is not None
        assert found.id == pending_id

    def test_follow_up_while_pending(self):
        """Handle follow-up while quote still pending."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        # Create pending
        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC"
        )
        pending = db.query(PendingQuote).first()

        # Handle follow-up
        status, details = manager.handle_follow_up(
            session_id="SESSION_ABC",
            pending=pending,
            portal_check_fn=None
        )

        assert status == "pending"
        assert pending.status == "follow_up"
        assert "processing" in details["message"].lower()

    def test_follow_up_resolves_quote(self):
        """Follow-up resolves quote when portal has it."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC"
        )
        pending = db.query(PendingQuote).first()

        # Mock portal check - quote is ready
        def mock_check(p):
            return {"success": True, "quote_id": "QUOTE_123"}

        status, details = manager.handle_follow_up(
            session_id="SESSION_ABC",
            pending=pending,
            portal_check_fn=mock_check
        )

        assert status == "resolved"
        assert "QUOTE_123" in details["message"]
        assert pending.status == "resolved"
        assert pending.quote_reply_sent is True

    def test_follow_up_escalates_on_timeout(self):
        """Escalate if 24+ hours have passed."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        # Create old pending (>24 hours ago)
        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC"
        )
        pending = db.query(PendingQuote).first()
        pending.handover_timestamp = datetime.utcnow() - timedelta(hours=25)
        pending.timeout_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        # Handle follow-up
        status, details = manager.handle_follow_up(
            session_id="SESSION_ABC",
            pending=pending,
            portal_check_fn=None
        )

        assert status == "escalated"
        assert pending.status == "escalated"


class TestTimeoutCronJob:
    """Test cron job for checking expired pending quotes."""

    def test_timeout_finds_expired(self):
        """Find and escalate expired pending quotes."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        # Create expired pending
        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC"
        )
        pending = db.query(PendingQuote).first()
        pending.handover_timestamp = datetime.utcnow() - timedelta(hours=25)
        pending.timeout_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        # Run timeout check
        result = manager.check_timeouts(portal_check_fn=None)

        assert result["total_expired"] == 1
        assert result["escalated"] == 1

        # Verify escalated
        pending = db.query(PendingQuote).first()
        assert pending.status == "escalated"

    def test_timeout_resolves_if_available(self):
        """Resolve if quote becomes available before timeout."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC"
        )
        pending = db.query(PendingQuote).first()
        pending.handover_timestamp = datetime.utcnow() - timedelta(hours=25)
        pending.timeout_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        # Mock portal - quote is ready
        def mock_check(p):
            return {"success": True, "quote_id": "QUOTE_456"}

        result = manager.check_timeouts(portal_check_fn=mock_check)

        assert result["total_expired"] == 1
        assert result["resolved"] == 1

        # Verify resolved
        pending = db.query(PendingQuote).first()
        assert pending.status == "resolved"


class TestFailureReplies:
    """Test professional failure reply templates."""

    def test_customer_not_found_reply(self):
        """Reply for customer not found in portal."""
        reply = get_failure_reply("CUSTOMER_NOT_FOUND")

        assert "verify" in reply.lower()
        assert "Company name" in reply

    def test_route_not_available_reply(self):
        """Reply for unavailable route."""
        reply = get_failure_reply("ROUTE_NOT_AVAILABLE")

        assert "route" in reply.lower()
        assert "different" in reply.lower()

    def test_portal_down_reply(self):
        """Reply for portal down."""
        reply = get_failure_reply("PORTAL_DOWN")

        assert "technical" in reply.lower()
        assert "2 hours" in reply

    def test_default_reply(self):
        """Default reply for unknown errors."""
        reply = get_failure_reply("UNKNOWN_ERROR")

        assert reply is not None
        assert len(reply) > 0


class TestGetStatus:
    """Test getting pending quote status."""

    def test_get_pending_status(self):
        """Get status of pending quote."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        pending_id = manager.create_pending(
            email_id="MSG_001",
            session_id="SESSION_ABC",
            origin="Shanghai",
            destination="LA"
        )

        status = manager.get_status(pending_id)

        assert status["id"] == pending_id
        assert status["status"] == "pending_portal_failure"
        assert status["origin"] == "Shanghai"
        assert status["destination"] == "LA"
        assert status["time_remaining_hours"] > 23

    def test_get_nonexistent_status(self):
        """Get status returns error for nonexistent."""
        db = get_test_database()
        manager = PendingQuoteManager()
        manager.db = db

        status = manager.get_status("NONEXISTENT_ID")
        assert "error" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
