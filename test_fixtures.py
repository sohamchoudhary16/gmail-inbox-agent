"""
Test fixtures and mocks for immediate testing.
All tests run WITHOUT contacting real Gmail, Claude, or databases.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import Mock, MagicMock
import tempfile
import os

# Sample test emails for all classification types
SAMPLE_EMAILS = {
    "rfq": {
        "id": "MSG_RFQ_001",
        "threadId": "THREAD_RFQ_001",
        "subject": "Quote request - Shanghai to Los Angeles",
        "from": "buyer@customer.com",
        "body": """
Hello,

We need a shipping quote for:
- Origin: Shanghai, China
- Destination: Los Angeles, USA
- Weight: 5000 kg
- Volume: 25 CBM
- Mode: Sea (LCL preferred)

Please provide pricing for ASAP shipment.

Best regards,
John Smith
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "rfq",
        "expected_label": "5u/rfq"
    },

    "booking_request": {
        "id": "MSG_BOOKING_001",
        "threadId": "THREAD_BOOKING_001",
        "subject": "Booking request - Quote #12345",
        "from": "booking@customer.com",
        "body": """
We would like to book the following shipment based on your quote:

Quote #12345
Origin: Rotterdam
Destination: Singapore
Weight: 10 tons
Volume: 50 CBM
Service: Sea FCL
ETD: 2026-10-15

Please confirm booking and send us the BL number.

Thanks,
Sarah Johnson
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "booking_request",
        "expected_label": "5u/booking-request"
    },

    "tracking_inquiry": {
        "id": "MSG_TRACKING_001",
        "threadId": "THREAD_TRACKING_001",
        "subject": "Tracking - Where is container ABC123?",
        "from": "ops@customer.com",
        "body": """
Hi,

Can you please provide the current status and ETA for:

Container: ABC123
Booking Ref: BKG-2026-10-001

The shipment was supposed to arrive on 2026-10-10.
We need to know if there are any delays.

Thank you,
Operations Team
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "tracking_inquiry",
        "expected_label": "5u/tracking"
    },

    "documentation": {
        "id": "MSG_DOCS_001",
        "threadId": "THREAD_DOCS_001",
        "subject": "Submitting documents for shipment BKG-2026-10-001",
        "from": "logistics@customer.com",
        "body": """
Please find attached the following documents for shipment BKG-2026-10-001:

- Bill of Lading (original)
- Packing List (3 pages)
- Commercial Invoice
- Customs Declaration
- Certificate of Origin

These are required for customs clearance in Singapore.

Kind regards,
Documentation Team
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "documentation",
        "expected_label": "5u/documentation"
    },

    "complaint": {
        "id": "MSG_COMPLAINT_001",
        "threadId": "THREAD_COMPLAINT_001",
        "subject": "COMPLAINT: Damaged goods in shipment ABC123",
        "from": "manager@customer.com",
        "body": """
This is a formal complaint regarding shipment ABC123.

The goods arrived damaged due to poor packaging by your warehouse.
This has caused us significant losses and customer dissatisfaction.

We expect:
1. Full compensation for damaged goods
2. Free reshipment
3. Investigation report

This is unacceptable service. We are reviewing our logistics provider options.

Regards,
Management
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "complaint",
        "expected_label": "5u/complaint"
    },

    "general_inquiry": {
        "id": "MSG_GENERAL_001",
        "threadId": "THREAD_GENERAL_001",
        "subject": "Do you offer consolidation services?",
        "from": "info@customer.com",
        "body": """
Hello,

I'm interested in learning more about your consolidation services.
We have multiple shipments going to the same region and would like to
consolidate them to save on costs.

Could you provide information about:
- Service coverage
- Consolidation points
- Cost savings
- Timeline

Thanks,
Alex Chen
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "general_inquiry",
        "expected_label": "5u/general"
    },

    "not_relevant": {
        "id": "MSG_SPAM_001",
        "threadId": "THREAD_SPAM_001",
        "subject": "LIMITED TIME: Get FREE shipping supplies!",
        "from": "promo@randomsite.com",
        "body": """
CLICK HERE for the best shipping supplies at the lowest prices!

Limited time offer - 50% OFF packing materials, tape, and boxes!

Don't miss out! This offer expires in 24 hours.

SHOP NOW → https://randomsite.com/promo
""",
        "timestamp": str(int(datetime.utcnow().timestamp() * 1000)),
        "expected_category": "not_relevant",
        "expected_label": "5u/not-relevant"
    }
}


class MockGmailService:
    """Mock Gmail API that simulates real behavior without contacting Google."""

    def __init__(self, sample_emails: Optional[Dict] = None, dry_run: bool = True):
        """
        Initialize mock Gmail service.

        Args:
            sample_emails: Dict of sample emails to return
            dry_run: If True, don't actually modify anything
        """
        self.sample_emails = sample_emails or SAMPLE_EMAILS
        self.dry_run = dry_run
        self.labeled_emails = {}
        self.marked_as_read = []
        self.created_labels = {}
        self.sent_replies = []
        self.call_log = []

    def get_unread_emails(self, max_results: int = 10) -> List[Dict]:
        """Mock: Return sample emails as if they were unread."""
        self.call_log.append(("get_unread_emails", max_results))
        emails = list(self.sample_emails.values())[:max_results]
        return emails

    def get_message(self, message_id: str) -> Optional[Dict]:
        """Mock: Get a specific email by ID."""
        self.call_log.append(("get_message", message_id))
        for email in self.sample_emails.values():
            if email["id"] == message_id:
                return email.copy()
        return None

    def add_label(self, message_id: str, label_name: str) -> bool:
        """Mock: Record that a label was added."""
        self.call_log.append(("add_label", message_id, label_name))
        if self.dry_run:
            self.labeled_emails[message_id] = label_name
            return True
        return True

    def _get_or_create_label(self, label_name: str) -> str:
        """Mock: Return a fake label ID."""
        self.call_log.append(("get_or_create_label", label_name))
        if label_name not in self.created_labels:
            self.created_labels[label_name] = f"LABEL_ID_{len(self.created_labels)}"
        return self.created_labels[label_name]

    def mark_as_read(self, message_id: str) -> bool:
        """Mock: Record that message was marked as read."""
        self.call_log.append(("mark_as_read", message_id))
        if self.dry_run:
            self.marked_as_read.append(message_id)
            return True
        return True

    def send_reply(self, message_id: str, thread_id: str, reply_body: str) -> bool:
        """Mock: Record that a reply was sent."""
        self.call_log.append(("send_reply", message_id, thread_id))
        if self.dry_run:
            self.sent_replies.append({
                "message_id": message_id,
                "thread_id": thread_id,
                "body": reply_body
            })
            return True
        return True


class MockClassifier:
    """Mock classifier that returns consistent results for testing."""

    def __init__(self, sample_emails: Optional[Dict] = None):
        """Initialize mock classifier."""
        self.sample_emails = sample_emails or SAMPLE_EMAILS
        self.call_log = []

    def classify_email(self, subject: str, body: str, from_email: str):
        """Mock: Classify email based on keywords."""
        self.call_log.append(("classify_email", subject))

        # Simple keyword-based mock classification
        combined = f"{subject} {body}".lower()

        if "quote" in combined or "pricing" in combined:
            category = "rfq"
        elif "booking" in combined or "book" in combined:
            category = "booking_request"
        elif "tracking" in combined or "where is" in combined or "status" in combined:
            category = "tracking_inquiry"
        elif "document" in combined or "bol" in combined or "packing list" in combined:
            category = "documentation"
        elif "complaint" in combined or "damage" in combined or "issue" in combined:
            category = "complaint"
        elif "consolidation" in combined or "service" in combined or "information" in combined:
            category = "general_inquiry"
        else:
            category = "not_relevant"

        return category, {
            "category": category,
            "confidence": 0.95,
            "reasoning": f"Mock classification based on keywords",
            "rfq_details": {
                "origin": None,
                "destination": None,
                "weight": None,
                "volume": None,
                "mode": None
            }
        }

    def get_label_for_category(self, category: str) -> str:
        """Get label for category."""
        labels = {
            "rfq": "5u/rfq",
            "booking_request": "5u/booking-request",
            "tracking_inquiry": "5u/tracking",
            "documentation": "5u/documentation",
            "complaint": "5u/complaint",
            "general_inquiry": "5u/general",
            "not_relevant": "5u/not-relevant"
        }
        return labels.get(category, "5u/general")


class TestDatabase:
    """In-memory test database using SQLite in memory."""

    def __init__(self):
        """Initialize in-memory test database."""
        import sqlalchemy
        from database import Base, SessionLocal

        # Create in-memory engine
        self.engine = sqlalchemy.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=sqlalchemy.pool.StaticPool
        )

        # Create schema
        Base.metadata.create_all(bind=self.engine)

        # Create session
        TestSessionLocal = sqlalchemy.orm.sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        self.session = TestSessionLocal()

    def close(self):
        """Close database."""
        self.session.close()

    def add(self, obj):
        """Add object to database."""
        self.session.add(obj)

    def commit(self):
        """Commit transaction."""
        self.session.commit()

    def query(self, model):
        """Query database."""
        return self.session.query(model)


# Test configuration
class TestConfig:
    """Configuration for tests."""

    # Use in-memory SQLite
    DATABASE_URL = "sqlite:///:memory:"

    # Gmail config (unused in tests)
    GMAIL_CLIENT_ID = "test-client-id"
    GMAIL_CLIENT_SECRET = "test-client-secret"
    GMAIL_TOKEN_FILE = "/tmp/test-token.json"
    GMAIL_MAILBOX_EMAIL = "test@example.com"

    # Anthropic (unused in tests)
    ANTHROPIC_API_KEY = "test-api-key"

    # Portal (unused in tests)
    PORTAL_BASE_URL = "https://portal.test.local"
    PORTAL_API_KEY = "test-portal-key"

    # Test mode
    DRY_RUN = True
    POLL_INTERVAL_SECONDS = 30


def get_mock_gmail_service(dry_run: bool = True) -> MockGmailService:
    """Get a mock Gmail service for testing."""
    return MockGmailService(SAMPLE_EMAILS, dry_run=dry_run)


def get_mock_classifier() -> MockClassifier:
    """Get a mock classifier for testing."""
    return MockClassifier(SAMPLE_EMAILS)


def get_test_database() -> TestDatabase:
    """Get an in-memory test database."""
    return TestDatabase()


def get_sample_email(category: str) -> Dict:
    """Get a sample email for a specific category."""
    return SAMPLE_EMAILS.get(category, SAMPLE_EMAILS["not_relevant"]).copy()


def get_all_sample_emails() -> List[Dict]:
    """Get all sample emails."""
    return [email.copy() for email in SAMPLE_EMAILS.values()]
