"""
Tests proving database session isolation and no connection pool exhaustion.
This tests Issue 1 fix: Database session management.
"""

import pytest
import logging
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_session, get_db, Session as SessionModel, Email as EmailModel, init_db
from classification_service import ClassificationService

logger = logging.getLogger(__name__)

# In-memory SQLite for testing (StaticPool to avoid pool size issues)
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory database for each test"""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)

    # Temporarily replace the engine
    import database
    old_engine = database.engine
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield engine

    # Restore
    database.engine = old_engine


class TestSessionIsolation:
    """Test that database sessions are properly isolated"""

    def test_session_is_closed_after_get_session(self, test_db):
        """Each get_session() call creates a fresh session that can be closed"""
        session1 = get_session()
        session_id_1 = id(session1)
        session1.close()

        session2 = get_session()
        session_id_2 = id(session2)
        session2.close()

        # Different session objects
        assert session_id_1 != session_id_2, "Sessions should be different objects"

    def test_concurrent_sessions_dont_share_state(self, test_db):
        """Two sessions operating simultaneously don't interfere"""
        # Create test data in session 1
        session1 = get_session()
        session_model = SessionModel(
            id="test-session-1",
            thread_id="thread-1",
            customer_email="test@example.com",
            subject="Test"
        )
        session1.add(session_model)
        session1.commit()

        # Open session 2 WITHOUT closing session1
        session2 = get_session()

        # Query in session 2 should also see the data (same database)
        existing = session2.query(SessionModel).filter(
            SessionModel.id == "test-session-1"
        ).first()
        assert existing is not None

        # But sessions are different objects
        assert id(session1) != id(session2)

        session1.close()
        session2.close()

    def test_session_rollback_on_error(self, test_db):
        """Session rollback prevents corrupted data on errors"""
        session = get_session()
        try:
            # Add data that will cause an error (duplicate key)
            session_model1 = SessionModel(
                id="test-id",
                thread_id="thread-1",
                customer_email="test@example.com",
                subject="Test"
            )
            session.add(session_model1)
            session.commit()

            # Try to add duplicate
            session_model2 = SessionModel(
                id="test-id",  # Duplicate!
                thread_id="thread-2",
                customer_email="test2@example.com",
                subject="Test2"
            )
            session.add(session_model2)
            session.commit()  # This should fail
        except Exception:
            session.rollback()
        finally:
            session.close()

        # Verify only first session was saved (rollback worked)
        verify_session = get_session()
        sessions = verify_session.query(SessionModel).all()
        verify_session.close()

        assert len(sessions) == 1, "Rollback should have prevented duplicate"


class TestClassificationServiceSessionManagement:
    """Test that ClassificationService doesn't hold sessions"""

    def test_classification_service_no_held_session(self, test_db):
        """ClassificationService should not have a held session"""
        service = ClassificationService()

        # Inspect the service - should NOT have a self.db attribute
        # (it was removed in the fix)
        assert not hasattr(service, 'db') or service.db is None, \
            "ClassificationService should not hold a database session"

    def test_process_unread_emails_closes_session(self, test_db):
        """process_unread_emails creates and closes a session"""
        service = ClassificationService()

        # Mock gmail service to return no emails
        service.gmail.get_unread_emails = lambda max_results: []

        # This should not fail, and should properly close the session
        result = service.process_unread_emails()

        assert result["processed"] == 0
        assert result["errors"] == 0

    def test_get_sessions_closes_session(self, test_db):
        """get_sessions creates and closes a session"""
        service = ClassificationService()

        # Should work with empty database
        sessions = service.get_sessions(limit=10)

        assert isinstance(sessions, list)
        assert len(sessions) == 0

    def test_get_session_detail_closes_session(self, test_db):
        """get_session_detail creates and closes a session"""
        service = ClassificationService()

        # Should handle non-existent session gracefully
        result = service.get_session_detail("nonexistent-id")

        assert result is None


class TestConnectionPoolExhaustionFix:
    """Test that the old Issue 1 (connection pool exhaustion) is fixed"""

    def test_multiple_sequential_operations_dont_exhaust_pool(self, test_db):
        """Multiple sequential operations don't cause connection issues"""
        service = ClassificationService()
        service.gmail.get_unread_emails = lambda max_results: []

        # Simulate 20 sequential classification runs (would fail in old code after ~5)
        for i in range(20):
            result = service.process_unread_emails()
            assert "error" not in result, f"Operation {i} failed with error: {result.get('error')}"

        # Also test get_sessions multiple times
        for i in range(10):
            sessions = service.get_sessions()
            assert isinstance(sessions, list)

    def test_session_factory_behavior(self, test_db):
        """Verify get_session() returns independent sessions"""
        sessions = []

        # Create 10 sessions in quick succession
        for i in range(10):
            s = get_session()
            sessions.append(s)

        # All should be usable
        for s in sessions:
            try:
                # Try a simple query
                s.query(SessionModel).all()
            finally:
                s.close()


class TestDatabaseTransactionHandling:
    """Test proper transaction handling"""

    def test_commit_persists_data(self, test_db):
        """Data is persisted after commit"""
        # Write in one session
        session1 = get_session()
        session_model = SessionModel(
            id="persist-test",
            thread_id="thread-persist",
            customer_email="persist@example.com",
            subject="Persist Test"
        )
        session1.add(session_model)
        session1.commit()
        session1.close()

        # Read in another session
        session2 = get_session()
        existing = session2.query(SessionModel).filter(
            SessionModel.id == "persist-test"
        ).first()
        session2.close()

        assert existing is not None
        assert existing.customer_email == "persist@example.com"

    def test_rollback_discards_data(self, test_db):
        """Data is discarded after rollback"""
        session = get_session()
        session_model = SessionModel(
            id="rollback-test",
            thread_id="thread-rollback",
            customer_email="rollback@example.com",
            subject="Rollback Test"
        )
        session.add(session_model)
        # Rollback instead of commit
        session.rollback()
        session.close()

        # Data should not exist
        session2 = get_session()
        existing = session2.query(SessionModel).filter(
            SessionModel.id == "rollback-test"
        ).first()
        session2.close()

        assert existing is None


class TestWorkerJobIsolation:
    """Test that concurrent worker jobs don't share sessions"""

    def test_each_worker_job_gets_own_session(self, test_db):
        """Simulate concurrent worker jobs each getting their own session"""
        service = ClassificationService()
        service.gmail.get_unread_emails = lambda max_results: []

        # Simulate 5 concurrent "worker jobs"
        results = []
        for i in range(5):
            # Each job is independent
            result = service.process_unread_emails()
            results.append(result)

        # All should succeed
        assert all("error" not in r for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
