from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, ForeignKey, JSON, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session as SQLSession
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inbox_automation.db")

# Connection pool and SQLite settings
if "sqlite" in DATABASE_URL:
    # SQLite settings
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 10},
        poolclass=None,  # Disable pooling for SQLite
    )
else:
    # Production database settings with connection pooling
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Test connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
    )

# Session factory - call this to get a fresh session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session() -> SQLSession:
    """
    Factory function to create a fresh database session.
    Use this in each request/operation.

    Example:
        db = get_session()
        try:
            # Use db
        finally:
            db.close()
    """
    return SessionLocal()


@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log database connections for debugging"""
    logger.debug(f"Database connection established")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    thread_id = Column(String, unique=True, index=True)
    classification = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emails = relationship("Email", back_populates="session")
    portal_calls = relationship("PortalCall", back_populates="session")
    pending_quotes = relationship("PendingQuote", back_populates="session")


class Email(Base):
    __tablename__ = "emails"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), index=True)
    gmail_message_id = Column(String, unique=True, index=True)
    thread_id = Column(String, index=True)
    from_email = Column(String)
    subject = Column(String)
    body = Column(Text)
    classification = Column(String, nullable=True)
    is_customer_email = Column(Boolean, default=True)
    is_reply_sent = Column(Boolean, default=False)
    received_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="emails")
    portal_calls = relationship("PortalCall", back_populates="email")


class PortalCall(Base):
    __tablename__ = "portal_calls"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), index=True)
    email_id = Column(String, ForeignKey("emails.id"), nullable=True)
    endpoint = Column(String)
    request_body = Column(JSON)
    response_status = Column(Integer)
    response_body = Column(JSON)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="portal_calls")
    email = relationship("Email", back_populates="portal_calls")


class PendingQuote(Base):
    __tablename__ = "pending_quotes"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), index=True)
    email_id = Column(String, ForeignKey("emails.id"))
    request_reference = Column(String, unique=True, index=True)
    origin_port = Column(String)
    destination_port = Column(String)
    weight = Column(String)
    volume = Column(String)
    mode = Column(String, nullable=True)
    status = Column(String, default="pending")
    handover_timestamp = Column(DateTime, default=datetime.utcnow)
    timeout_at = Column(DateTime)
    quote_response_email_id = Column(String, ForeignKey("emails.id"), nullable=True)
    quote_reply_sent = Column(Boolean, default=False)

    session = relationship("Session", back_populates="pending_quotes")


def init_db():
    """Initialize database schema"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized")


def get_db():
    """
    FastAPI dependency for request-scoped database session.
    Automatically closes the session when the request completes.

    Usage in FastAPI:
        @app.get("/endpoint")
        async def endpoint(db: Session = Depends(get_db)):
            # db is automatically closed after request
            ...
    """
    db = get_session()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
