"""
Service for processing emails: classify, label, and track sessions.
Handles idempotency and persistence.

IMPORTANT: This service creates a FRESH database session for each operation.
No sessions are held or reused. This prevents connection pool exhaustion.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import get_session, Email as EmailModel, Session as SessionModel, PortalCall
from gmail_service import GmailService
from classifier_agent import ClassifierAgent
from config import get_settings

logger = logging.getLogger(__name__)


class ClassificationService:
    def __init__(self):
        """Initialize service. NO database session is held here."""
        self.settings = get_settings()
        self.gmail = GmailService()
        self.classifier = ClassifierAgent(self.settings.anthropic_api_key)
        # DO NOT store a database session - create fresh for each operation

    def process_unread_emails(self) -> Dict:
        """
        Main entry point: fetch unread emails, classify them, apply labels.
        Creates a FRESH database session for this operation.
        Returns summary of what was processed.
        """
        db = get_session()
        try:
            # Get unread emails from Gmail
            unread = self.gmail.get_unread_emails(max_results=20)

            if not unread:
                logger.info("No unread emails")
                return {"processed": 0, "errors": 0}

            processed = 0
            errors = 0

            for email in unread:
                try:
                    if self._process_single_email(email, db):
                        processed += 1
                    else:
                        errors += 1
                except Exception as e:
                    logger.error(f"Error processing email {email.get('id')}: {e}")
                    db.rollback()  # Rollback on error
                    errors += 1

            return {
                "processed": processed,
                "errors": errors,
                "total": len(unread)
            }

        except Exception as e:
            logger.error(f"Error in process_unread_emails: {e}")
            db.rollback()
            return {"processed": 0, "errors": 1, "error": str(e)}
        finally:
            # ALWAYS close the session, even if errors occur
            db.close()
            logger.debug("Database session closed")

    def _process_single_email(self, gmail_email: Dict, db: Session) -> bool:
        """
        Process a single email: check idempotency, classify, label, store.

        Args:
            gmail_email: Email data from Gmail API
            db: Database session (created fresh by caller)

        Returns:
            True if successfully processed, False otherwise.
        """
        gmail_msg_id = gmail_email.get('id')
        thread_id = gmail_email.get('threadId')

        if not gmail_msg_id or not thread_id:
            logger.warning("Email missing id or threadId")
            return False

        # Check idempotency: already processed?
        existing = db.query(EmailModel).filter(
            EmailModel.gmail_message_id == gmail_msg_id
        ).first()

        if existing:
            logger.info(f"Email {gmail_msg_id} already processed, skipping")
            return False

        # Classify email
        category, classification_details = self.classifier.classify_email(
            subject=gmail_email.get('subject', ''),
            body=gmail_email.get('body', ''),
            from_email=gmail_email.get('from', '')
        )

        # Get or create session (one per thread)
        session = self._get_or_create_session(thread_id, gmail_email, db)

        # Store email in database
        email_record = EmailModel(
            id=str(uuid.uuid4()),
            session_id=session.id,
            gmail_message_id=gmail_msg_id,
            thread_id=thread_id,
            from_email=gmail_email.get('from', ''),
            subject=gmail_email.get('subject', ''),
            body=gmail_email.get('body', ''),
            classification=category,
            received_at=datetime.fromtimestamp(int(gmail_email.get('timestamp', 0)) / 1000),
        )

        db.add(email_record)
        db.commit()

        logger.info(f"Stored email {gmail_msg_id} in database with classification {category}")

        # Apply Gmail label
        label = self.classifier.get_label_for_category(category)
        if self.gmail.add_label(gmail_msg_id, label):
            logger.info(f"Applied label {label} to email {gmail_msg_id}")
        else:
            logger.warning(f"Failed to apply label {label} to email {gmail_msg_id}")

        # Mark as read (processed)
        self.gmail.mark_as_read(gmail_msg_id)

        return True

    def _get_or_create_session(self, thread_id: str, gmail_email: Dict, db: Session) -> SessionModel:
        """
        Get existing session for thread or create new one.

        Args:
            thread_id: Gmail thread ID
            gmail_email: Email data from Gmail
            db: Database session (provided by caller)
        """
        existing = db.query(SessionModel).filter(
            SessionModel.thread_id == thread_id
        ).first()

        if existing:
            logger.info(f"Using existing session for thread {thread_id}")
            return existing

        # Create new session
        session = SessionModel(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            customer_email=gmail_email.get('from', ''),
            subject=gmail_email.get('subject', ''),
        )

        db.add(session)
        db.commit()

        logger.info(f"Created new session {session.id} for thread {thread_id}")
        return session

    def get_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Get all sessions with their classification status.
        Creates a FRESH database session for this query.
        """
        db = get_session()
        try:
            sessions = db.query(SessionModel).offset(offset).limit(limit).all()

            result = []
            for session in sessions:
                emails = db.query(EmailModel).filter(
                    EmailModel.session_id == session.id
                ).all()

                result.append({
                    "id": session.id,
                    "thread_id": session.thread_id,
                    "classification": session.classification,
                    "customer_email": session.customer_email,
                    "subject": session.subject,
                    "email_count": len(emails),
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                })

            return result
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []
        finally:
            db.close()

    def get_session_detail(self, session_id: str) -> Optional[Dict]:
        """
        Get detailed information about a session.
        Creates a FRESH database session for this query.
        """
        db = get_session()
        try:
            session = db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).first()

            if not session:
                return None

            emails = db.query(EmailModel).filter(
                EmailModel.session_id == session_id
            ).all()

            portal_calls = db.query(PortalCall).filter(
                PortalCall.session_id == session_id
            ).all()

            return {
                "id": session.id,
                "thread_id": session.thread_id,
                "classification": session.classification,
                "customer_email": session.customer_email,
                "subject": session.subject,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "emails": [
                    {
                        "id": e.id,
                        "from": e.from_email,
                        "subject": e.subject,
                        "classification": e.classification,
                        "received_at": e.received_at.isoformat() if e.received_at else None,
                    }
                    for e in emails
                ],
                "portal_calls": [
                    {
                        "id": pc.id,
                        "endpoint": pc.endpoint,
                        "status": pc.response_status,
                        "created_at": pc.created_at.isoformat(),
                    }
                    for pc in portal_calls
                ]
            }
        except Exception as e:
            logger.error(f"Error getting session detail: {e}")
            return None
        finally:
            db.close()
