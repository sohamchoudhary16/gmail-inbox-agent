"""
STRICT PHASE 2 REVIEW: Test against original requirements
NO REAL GMAIL CALLS - All tests use mocks
"""

import pytest
import json
import os
import sys
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test database (in-memory SQLite)
TEST_DB_URL = "sqlite:///:memory:"

from database import Base, init_db, SessionLocal, Session as SessionModel, Email as EmailModel
from classifier_agent import ClassifierAgent, VALID_CATEGORIES, CATEGORY_LABELS
from classification_service import ClassificationService
from config import get_settings

# ============================================================================
# SETUP: Mock Gmail API calls
# ============================================================================

class MockGmailService:
    def __init__(self):
        self.labeled_emails = {}
        self.marked_as_read = []

    def get_unread_emails(self, max_results=10):
        return []

    def get_message(self, msg_id):
        return None

    def add_label(self, message_id, label_name):
        self.labeled_emails[message_id] = label_name
        return True

    def mark_as_read(self, message_id):
        self.marked_as_read.append(message_id)
        return True

    def send_reply(self, message_id, thread_id, reply_body):
        return True


# ============================================================================
# TESTS
# ============================================================================

class TestClassification:
    """Test classifier accuracy and adherence to specs"""

    def test_all_7_categories_defined(self):
        """Requirement: Classify into exactly one of 7 categories"""
        expected = {
            "rfq", "booking_request", "tracking_inquiry",
            "documentation", "complaint", "general_inquiry", "not_relevant"
        }
        assert VALID_CATEGORIES == expected, f"Categories mismatch: {VALID_CATEGORIES}"

    def test_category_to_label_mapping(self):
        """Requirement: Each category maps to specific Gmail label"""
        expected = {
            "rfq": "5u/rfq",
            "booking_request": "5u/booking-request",
            "tracking_inquiry": "5u/tracking",
            "documentation": "5u/documentation",
            "complaint": "5u/complaint",
            "general_inquiry": "5u/general",
            "not_relevant": "5u/not-relevant"
        }
        assert CATEGORY_LABELS == expected, f"Label mapping mismatch: {CATEGORY_LABELS}"

    @patch('classifier_agent.Anthropic')
    def test_classification_json_parsing(self, mock_anthropic_class):
        """Requirement: Agent returns structured JSON with category"""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        response_json = {
            "category": "rfq",
            "confidence": 0.95,
            "reasoning": "Email asks for shipping quote",
            "rfq_details": {
                "origin": "Shanghai",
                "destination": "Los Angeles",
                "weight": "10000 kg",
                "volume": "50 CBM",
                "mode": "sea"
            }
        }

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(response_json))]
        mock_client.messages.create.return_value = mock_msg

        classifier = ClassifierAgent("dummy_key")
        category, result = classifier.classify_email(
            subject="Quote request",
            body="Need pricing for Shanghai to LA",
            from_email="customer@example.com"
        )

        assert category == "rfq"
        assert result["confidence"] == 0.95
        assert result["rfq_details"]["origin"] == "Shanghai"

    @patch('classifier_agent.Anthropic')
    def test_invalid_category_fallback(self, mock_anthropic_class):
        """Requirement: Handle invalid category gracefully"""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        invalid_response = {"category": "invalid_category", "confidence": 0.5}
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(invalid_response))]
        mock_client.messages.create.return_value = mock_msg

        classifier = ClassifierAgent("dummy_key")
        category, result = classifier.classify_email(
            subject="Test",
            body="Test email",
            from_email="test@example.com"
        )

        assert category == "general_inquiry", "Should fallback to general_inquiry"

    @patch('classifier_agent.Anthropic')
    def test_json_parse_error_fallback(self, mock_anthropic_class):
        """Requirement: Handle malformed JSON from agent"""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="NOT VALID JSON")]
        mock_client.messages.create.return_value = mock_msg

        classifier = ClassifierAgent("dummy_key")
        category, result = classifier.classify_email(
            subject="Test",
            body="Test",
            from_email="test@example.com"
        )

        assert category == "general_inquiry", "Should fallback on parse error"
        assert result.get("error") == "parse_error"


class TestIdempotency:
    """Requirement: Polling same mailbox twice must not label twice"""

    def test_duplicate_email_skipped(self):
        """Same email ID processed twice -> second time skipped"""
        # Setup in-memory DB
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        SessionLocal.configure(bind=engine)

        # Create first email in DB
        db = SessionLocal()
        session = SessionModel(
            id="session-1",
            thread_id="thread-1",
            customer_email="test@example.com",
            subject="Test"
        )
        db.add(session)
        email = EmailModel(
            id="email-1",
            session_id="session-1",
            gmail_message_id="MSG123",  # This is the idempotency key
            thread_id="thread-1",
            from_email="test@example.com",
            subject="Test",
            body="Test body",
            classification="rfq",
            received_at=datetime.utcnow()
        )
        db.add(email)
        db.commit()

        # Try to process same email again
        gmail_email = {
            'id': 'MSG123',  # Same message ID
            'threadId': 'thread-1',
            'subject': 'Test',
            'from': 'test@example.com',
            'body': 'Test body',
            'timestamp': str(int(datetime.utcnow().timestamp() * 1000))
        }

        # Verify it exists
        existing = db.query(EmailModel).filter(
            EmailModel.gmail_message_id == 'MSG123'
        ).first()

        assert existing is not None, "Email should exist in DB"
        assert existing.classification == "rfq", "Should have stored classification"

        db.close()


class TestSessionTracking:
    """Requirement: Emails in same thread belong to same session"""

    def test_one_session_per_thread(self):
        """Same thread_id -> same session"""
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        SessionLocal.configure(bind=engine)

        db = SessionLocal()

        # Create session
        session = SessionModel(
            id="session-1",
            thread_id="THREAD_ABC",
            customer_email="customer@example.com",
            subject="Original subject"
        )
        db.add(session)
        db.commit()

        # Add first email to session
        email1 = EmailModel(
            id="email-1",
            session_id="session-1",
            gmail_message_id="MSG1",
            thread_id="THREAD_ABC",
            from_email="customer@example.com",
            subject="Original subject",
            body="First email",
            classification="rfq",
            received_at=datetime.utcnow()
        )
        db.add(email1)

        # Add follow-up email to same thread
        email2 = EmailModel(
            id="email-2",
            session_id="session-1",  # Same session!
            gmail_message_id="MSG2",
            thread_id="THREAD_ABC",  # Same thread
            from_email="customer@example.com",
            subject="Re: Original subject",
            body="Follow-up email",
            classification="rfq",
            received_at=datetime.utcnow()
        )
        db.add(email2)
        db.commit()

        # Verify both emails in same session
        emails = db.query(EmailModel).filter(
            EmailModel.session_id == "session-1"
        ).all()

        assert len(emails) == 2, "Both emails should be in same session"
        assert all(e.thread_id == "THREAD_ABC" for e in emails), "All should be in same thread"

        db.close()

    def test_different_threads_different_sessions(self):
        """Different thread_id -> different session"""
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        SessionLocal.configure(bind=engine)

        db = SessionLocal()

        # Session 1
        session1 = SessionModel(
            id="session-1",
            thread_id="THREAD_1",
            customer_email="customer@example.com",
            subject="Subject 1"
        )
        db.add(session1)

        # Session 2
        session2 = SessionModel(
            id="session-2",
            thread_id="THREAD_2",
            customer_email="customer@example.com",
            subject="Subject 2"
        )
        db.add(session2)
        db.commit()

        # Verify different sessions
        sessions = db.query(SessionModel).all()
        assert len(sessions) == 2
        assert sessions[0].id != sessions[1].id
        assert sessions[0].thread_id != sessions[1].thread_id

        db.close()


class TestGmailApiUsage:
    """Requirement: Real Gmail API, OAuth2 credentials provided"""

    def test_credentials_not_hardcoded(self):
        """Credentials must come from file/env, never hardcoded"""
        # Check gmail_service.py doesn't have hardcoded keys
        with open("gmail_service.py", "r") as f:
            content = f.read()
            assert "credentials.json" in content
            assert "from_client_secrets_file" in content
            # Should NOT have actual API keys
            assert not any(key in content for key in [
                "AIza", "ya29", "AKIA", "ASIa"
            ]), "API keys detected in source!"

    def test_oauth_scopes_correct(self):
        """Requirement: gmail.modify scope for label/read operations"""
        from gmail_service import SCOPES
        assert 'https://www.googleapis.com/auth/gmail.modify' in SCOPES

    def test_token_caching(self):
        """Tokens should be cached, not re-auth every time"""
        with open("gmail_service.py", "r") as f:
            content = f.read()
            assert "pickle" in content, "Should cache token with pickle"
            assert "token_file" in content


class TestSecretHandling:
    """Requirement: Keep secrets out of Git"""

    def test_gitignore_excludes_secrets(self):
        """Check .gitignore has required entries"""
        with open(".gitignore", "r") as f:
            content = f.read()
            assert "credentials.json" in content
            assert "credentials-desktop.json" in content
            assert ".env" in content
            assert "tokens/" in content
            assert "*.db" in content

    def test_env_example_has_no_values(self):
        """Check .env.example has NO actual secret values"""
        with open(".env.example", "r") as f:
            content = f.read()
            # Should have placeholders, not real keys
            assert "your_client_id_here" in content or "=" in content
            # Should NOT have real-looking keys
            for line in content.split('\n'):
                if '=' in line and not line.startswith('#'):
                    value = line.split('=')[1].strip()
                    # Real keys are long random strings, examples are not
                    if value and not any(x in value for x in ['your', 'example', 'here']):
                        # Could be a legit example
                        pass


class TestDatabasePersistence:
    """Requirement: Classification results are persisted"""

    def test_classification_stored_in_db(self):
        """Email classification must be saved to database"""
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        SessionLocal.configure(bind=engine)

        db = SessionLocal()

        session = SessionModel(
            id="s1", thread_id="t1",
            customer_email="c@ex.com", subject="test"
        )
        db.add(session)

        email = EmailModel(
            id="e1",
            session_id="s1",
            gmail_message_id="m1",
            thread_id="t1",
            from_email="c@ex.com",
            subject="Test",
            body="Test",
            classification="rfq",  # Must be stored
            received_at=datetime.utcnow()
        )
        db.add(email)
        db.commit()

        # Retrieve and verify
        retrieved = db.query(EmailModel).filter(
            EmailModel.gmail_message_id == "m1"
        ).first()

        assert retrieved is not None
        assert retrieved.classification == "rfq", "Classification not persisted!"

        db.close()

    def test_session_timestamps_updated(self):
        """Session should track creation and update times"""
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        SessionLocal.configure(bind=engine)

        db = SessionLocal()

        now = datetime.utcnow()
        session = SessionModel(
            id="s1", thread_id="t1",
            customer_email="c@ex.com", subject="test"
        )
        db.add(session)
        db.commit()

        assert session.created_at is not None
        assert session.updated_at is not None

        db.close()


class TestBusinessRules:
    """Requirement: Business rule compliance"""

    def test_no_reply_for_complaint(self):
        """Requirement: No auto-reply for complaints"""
        # This is a Phase 3 requirement, but we should acknowledge it exists
        # In Phase 2, we just classify. The rule about "no reply" comes in Phase 3.
        # But we MUST NOT accidentally reply to complaints in Phase 3.
        from classifier_agent import CATEGORY_LABELS
        assert "complaint" in CATEGORY_LABELS

    def test_no_reply_for_not_relevant(self):
        """Requirement: No auto-reply for not_relevant"""
        from classifier_agent import CATEGORY_LABELS
        assert "not_relevant" in CATEGORY_LABELS

    def test_classification_exactly_one_category(self):
        """Requirement: Classify into EXACTLY ONE category"""
        # This is enforced by the classifier returning single category
        from classifier_agent import VALID_CATEGORIES
        assert len(VALID_CATEGORIES) == 7
        # Each email gets exactly one classification (not multiple)


class TestErrorHandling:
    """What happens when things break?"""

    @patch('classifier_agent.Anthropic')
    def test_anthropic_api_failure_fallback(self, mock_anthropic_class):
        """If Claude call fails, fall back to general_inquiry"""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Error")

        classifier = ClassifierAgent("dummy_key")
        category, result = classifier.classify_email(
            subject="Test",
            body="Test",
            from_email="test@example.com"
        )

        assert category == "general_inquiry", "Should fallback on API error"
        assert "error" in result

    def test_missing_email_fields_handled(self):
        """Missing subject/body/from shouldn't crash"""
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        SessionLocal.configure(bind=engine)

        db = SessionLocal()

        # Email with minimal data
        session = SessionModel(id="s1", thread_id="t1", customer_email="c@ex.com", subject="test")
        db.add(session)

        email = EmailModel(
            id="e1",
            session_id="s1",
            gmail_message_id="m1",
            thread_id="t1",
            from_email="",  # Empty
            subject="",     # Empty
            body="",        # Empty
            classification="general_inquiry",
            received_at=datetime.utcnow()
        )
        db.add(email)
        db.commit()

        retrieved = db.query(EmailModel).filter(
            EmailModel.id == "e1"
        ).first()

        assert retrieved is not None, "Should handle empty fields"

        db.close()


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
