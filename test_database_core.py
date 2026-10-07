"""
Core database infrastructure tests.
Tests WITHOUT external dependencies - only SQLAlchemy.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import database components
from database import (
    Base, get_session, init_db,
    Session as SessionModel,
    Email as EmailModel,
    PortalCall,
    PendingQuote
)


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a fresh in-memory SQLite database for each test"""
    # Use in-memory database with StaticPool for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    # Create schema
    Base.metadata.create_all(bind=engine)

    # Replace global engine temporarily
    import database
    original_engine = database.engine
    original_sessionlocal = database.SessionLocal

    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield engine

    # Restore
    database.engine = original_engine
    database.SessionLocal = original_sessionlocal


class TestDatabaseSchema:
    """Test that database schema is correct"""

    def test_sessions_table_exists(self, test_db_engine):
        """Session table created with correct columns"""
        inspector = test_db_engine.inspect()
        assert "sessions" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("sessions")}
        assert "id" in columns
        assert "thread_id" in columns
        assert "classification" in columns
        assert "customer_email" in columns
        assert "subject" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_emails_table_exists(self, test_db_engine):
        """Email table created with correct columns"""
        inspector = test_db_engine.inspect()
        assert "emails" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("emails")}
        assert "id" in columns
        assert "gmail_message_id" in columns  # Idempotency key
        assert "thread_id" in columns
        assert "classification" in columns
        assert "is_customer_email" in columns
        assert "is_reply_sent" in columns

    def test_portal_calls_table_exists(self, test_db_engine):
        """PortalCall table for audit trail"""
        inspector = test_db_engine.inspect()
        assert "portal_calls" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("portal_calls")}
        assert "session_id" in columns
        assert "endpoint" in columns
        assert "request_body" in columns
        assert "response_status" in columns
        assert "response_body" in columns

    def test_pending_quotes_table_exists(self, test_db_engine):
        """PendingQuote table for delayed quote handling"""
        inspector = test_db_engine.inspect()
        assert "pending_quotes" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("pending_quotes")}
        assert "session_id" in columns
        assert "request_reference" in columns
        assert "status" in columns
        assert "timeout_at" in columns


class TestSessionCreation:
    """Test basic session creation and persistence"""

    def test_create_session(self, test_db_engine):
        """Create a session in database"""
        db = get_session()
        try:
            session = SessionModel(
                id="test-session-1",
                thread_id="thread-abc123",
                customer_email="customer@example.com",
                subject="Test Quote Request"
            )
            db.add(session)
            db.commit()

            # Verify it was saved
            retrieved = db.query(SessionModel).filter(
                SessionModel.id == "test-session-1"
            ).first()

            assert retrieved is not None
            assert retrieved.thread_id == "thread-abc123"
            assert retrieved.customer_email == "customer@example.com"
        finally:
            db.close()

    def test_session_timestamps(self, test_db_engine):
        """Sessions have created_at and updated_at timestamps"""
        db = get_session()
        try:
            session = SessionModel(
                id="test-session-2",
                thread_id="thread-xyz",
                customer_email="test@example.com",
                subject="Test"
            )
            db.add(session)
            db.commit()

            retrieved = db.query(SessionModel).filter(
                SessionModel.id == "test-session-2"
            ).first()

            assert retrieved.created_at is not None
            assert retrieved.updated_at is not None
            assert isinstance(retrieved.created_at, datetime)
        finally:
            db.close()


class TestEmailPersistence:
    """Test email storage and idempotency"""

    def test_store_email(self, test_db_engine):
        """Store email in database"""
        db = get_session()
        try:
            # Create session first
            session = SessionModel(
                id="s1", thread_id="t1",
                customer_email="c@ex.com", subject="test"
            )
            db.add(session)

            # Add email
            email = EmailModel(
                id="e1",
                session_id="s1",
                gmail_message_id="MSG_UNIQUE_ID",
                thread_id="t1",
                from_email="c@ex.com",
                subject="Quote Request",
                body="Need shipping quote",
                classification="rfq",
                received_at=datetime.utcnow()
            )
            db.add(email)
            db.commit()

            # Retrieve
            retrieved = db.query(EmailModel).filter(
                EmailModel.gmail_message_id == "MSG_UNIQUE_ID"
            ).first()

            assert retrieved is not None
            assert retrieved.classification == "rfq"
            assert retrieved.body == "Need shipping quote"
        finally:
            db.close()

    def test_idempotency_gmail_message_id(self, test_db_engine):
        """gmail_message_id is unique (idempotency key)"""
        db = get_session()
        try:
            session = SessionModel(
                id="s1", thread_id="t1",
                customer_email="c@ex.com", subject="test"
            )
            db.add(session)

            # First email
            email1 = EmailModel(
                id="e1",
                session_id="s1",
                gmail_message_id="UNIQUE_MSG_ID",
                thread_id="t1",
                from_email="c@ex.com",
                subject="Test",
                body="Body",
                classification="rfq",
                received_at=datetime.utcnow()
            )
            db.add(email1)
            db.commit()

            # Try to add duplicate - should fail or be prevented
            email2 = EmailModel(
                id="e2",
                session_id="s1",
                gmail_message_id="UNIQUE_MSG_ID",  # Same ID!
                thread_id="t1",
                from_email="c@ex.com",
                subject="Test2",
                body="Body2",
                classification="booking_request",
                received_at=datetime.utcnow()
            )
            db.add(email2)

            # Should fail due to unique constraint
            with pytest.raises(Exception):  # IntegrityError
                db.commit()
        finally:
            db.rollback()
            db.close()


class TestThreadGrouping:
    """Test that emails in same thread group to same session"""

    def test_multiple_emails_same_thread(self, test_db_engine):
        """Multiple emails in same thread belong to same session"""
        db = get_session()
        try:
            # Create session
            session = SessionModel(
                id="s1", thread_id="THREAD_ABC",
                customer_email="customer@example.com",
                subject="Original Subject"
            )
            db.add(session)
            db.commit()

            # Add first email
            email1 = EmailModel(
                id="e1",
                session_id="s1",
                gmail_message_id="MSG1",
                thread_id="THREAD_ABC",
                from_email="customer@example.com",
                subject="Original Subject",
                body="First email",
                classification="rfq",
                received_at=datetime.utcnow()
            )
            db.add(email1)

            # Add follow-up email to same thread
            email2 = EmailModel(
                id="e2",
                session_id="s1",  # Same session!
                gmail_message_id="MSG2",
                thread_id="THREAD_ABC",  # Same thread!
                from_email="customer@example.com",
                subject="Re: Original Subject",
                body="Follow-up email",
                classification="rfq",
                received_at=datetime.utcnow()
            )
            db.add(email2)
            db.commit()

            # Verify both in same session
            emails = db.query(EmailModel).filter(
                EmailModel.session_id == "s1"
            ).all()

            assert len(emails) == 2
            assert all(e.thread_id == "THREAD_ABC" for e in emails)
        finally:
            db.close()


class TestCommitAndRollback:
    """Test transaction handling"""

    def test_commit_persists_data(self, test_db_engine):
        """Commit saves data permanently"""
        # Write in session 1
        db1 = get_session()
        try:
            session = SessionModel(
                id="persist-test",
                thread_id="thread-persist",
                customer_email="persist@example.com",
                subject="Persist Test"
            )
            db1.add(session)
            db1.commit()
        finally:
            db1.close()

        # Read in session 2
        db2 = get_session()
        try:
            existing = db2.query(SessionModel).filter(
                SessionModel.id == "persist-test"
            ).first()

            assert existing is not None
            assert existing.customer_email == "persist@example.com"
        finally:
            db2.close()

    def test_rollback_discards_data(self, test_db_engine):
        """Rollback discards uncommitted data"""
        db = get_session()
        try:
            session = SessionModel(
                id="rollback-test",
                thread_id="thread-rollback",
                customer_email="rollback@example.com",
                subject="Rollback Test"
            )
            db.add(session)
            db.rollback()  # Rollback instead of commit
        finally:
            db.close()

        # Verify data wasn't saved
        db2 = get_session()
        try:
            existing = db2.query(SessionModel).filter(
                SessionModel.id == "rollback-test"
            ).first()

            assert existing is None
        finally:
            db2.close()


class TestConcurrency:
    """Test concurrent session access"""

    def test_multiple_sessions_independent(self, test_db_engine):
        """Multiple sessions can operate independently"""
        # Session 1: Write data
        db1 = get_session()
        try:
            s1 = SessionModel(
                id="s1", thread_id="t1",
                customer_email="user1@example.com", subject="User 1"
            )
            db1.add(s1)
            db1.commit()
        finally:
            # Don't close yet - keep it open
            pass

        # Session 2: Write different data (should not block)
        db2 = get_session()
        try:
            s2 = SessionModel(
                id="s2", thread_id="t2",
                customer_email="user2@example.com", subject="User 2"
            )
            db2.add(s2)
            db2.commit()
        finally:
            db2.close()

        # Session 3: Verify both were saved
        db3 = get_session()
        try:
            all_sessions = db3.query(SessionModel).all()
            assert len(all_sessions) == 2
        finally:
            db3.close()

        # Close session 1 now
        db1.close()


class TestDatabaseFactory:
    """Test get_session() factory"""

    def test_get_session_returns_session(self, test_db_engine):
        """get_session() returns a usable session"""
        db = get_session()

        assert db is not None
        # Should be able to query
        result = db.query(SessionModel).all()
        assert isinstance(result, list)

        db.close()

    def test_get_session_different_instances(self, test_db_engine):
        """Multiple calls to get_session() return different instances"""
        db1 = get_session()
        db2 = get_session()

        assert db1 is not db2
        assert id(db1) != id(db2)

        db1.close()
        db2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
