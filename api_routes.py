"""
API routes for email classification and session management.

NOTE: Each route gets a fresh database session via Depends(get_db).
The session is automatically closed when the request completes.
ClassificationService also creates its own fresh sessions for each operation.
This ensures no session pooling issues or connection exhaustion.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, get_session, Session as SessionModel, Email as EmailModel
from classification_service import ClassificationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["inbox"])

# Create singleton instance - it doesn't hold any database sessions
classification_service = ClassificationService()


@router.post("/classify")
async def trigger_classification():
    """
    Trigger email classification.
    Fetches unread emails, classifies them, and applies labels.

    Note: ClassificationService.process_unread_emails() creates its own
    fresh database session internally.
    """
    result = classification_service.process_unread_emails()

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "status": "success",
        "processed": result.get("processed", 0),
        "errors": result.get("errors", 0),
        "total": result.get("total", 0)
    }


@router.get("/sessions")
async def list_sessions(limit: int = 50, offset: int = 0):
    """
    List all sessions with their classifications.

    Note: ClassificationService.get_sessions() creates its own
    fresh database session internally.
    """
    sessions = classification_service.get_sessions(limit=limit, offset=offset)

    return {
        "status": "success",
        "count": len(sessions),
        "sessions": sessions
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get detailed information about a specific session.
    Includes all emails in the thread and portal API calls made.

    Note: ClassificationService.get_session_detail() creates its own
    fresh database session internally.
    """
    session = classification_service.get_session_detail(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "status": "success",
        "session": session
    }


@router.get("/stats")
async def get_stats():
    """
    Get statistics about classified emails.
    Creates a fresh database session for this query.
    """
    db = get_session()
    try:
        total_sessions = db.query(SessionModel).count()
        total_emails = db.query(EmailModel).count()

        # Count by classification
        classifications = db.query(
            EmailModel.classification,
            func.count(EmailModel.id).label('count')
        ).group_by(EmailModel.classification).all()

        classification_counts = {
            c[0]: c[1] for c in classifications
        }

        return {
            "status": "success",
            "total_sessions": total_sessions,
            "total_emails": total_emails,
            "classifications": classification_counts
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats")
    finally:
        db.close()
