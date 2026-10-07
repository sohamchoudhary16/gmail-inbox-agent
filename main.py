from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import init_db, get_db
from config import get_settings
from api_routes import router
from worker import start_scheduler, stop_scheduler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gmail Inbox Automation", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")

    logger.info("Starting background scheduler...")
    start_scheduler()
    logger.info("Background scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    stop_scheduler()


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root(db: Session = Depends(get_db)):
    # Get stats
    from sqlalchemy import func
    from database import Session as SessionModel, Email as EmailModel

    total_sessions = db.query(SessionModel).count()
    total_emails = db.query(EmailModel).count()

    classifications = db.query(
        EmailModel.classification,
        func.count(EmailModel.id).label('count')
    ).group_by(EmailModel.classification).all()

    classification_html = "".join([
        f"<li>{c[0]}: {c[1]} emails</li>" for c in classifications
    ])

    return f"""
    <html>
        <head>
            <title>Gmail Inbox Automation</title>
            <style>
                body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
                h1 {{ color: #333; }}
                .card {{ background: white; padding: 20px; margin: 10px 0; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat {{ display: inline-block; margin-right: 20px; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #1976d2; }}
                .stat-label {{ color: #666; }}
                ul {{ list-style: none; padding: 0; }}
                li {{ padding: 5px 0; }}
                a {{ color: #1976d2; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .button {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px 0; }}
                .button:hover {{ background: #1565c0; }}
            </style>
        </head>
        <body>
            <h1>📧 Gmail Inbox Automation Service</h1>

            <div class="card">
                <h2>Status</h2>
                <p>✓ Service is running</p>
                <p>✓ Background scheduler active (polls every 30s)</p>
            </div>

            <div class="card">
                <h2>Statistics</h2>
                <div class="stat">
                    <div class="stat-value">{total_sessions}</div>
                    <div class="stat-label">Sessions</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{total_emails}</div>
                    <div class="stat-label">Emails Processed</div>
                </div>
            </div>

            <div class="card">
                <h2>Classifications</h2>
                <ul>
                    {classification_html if classification_html else "<li>No emails processed yet</li>"}
                </ul>
            </div>

            <div class="card">
                <h2>Actions</h2>
                <form action="/api/classify" method="POST">
                    <button type="submit" class="button">🔄 Classify Unread Emails Now</button>
                </form>
            </div>

            <div class="card">
                <h2>API Endpoints</h2>
                <ul>
                    <li><a href="/health">/health</a> - Health check</li>
                    <li><a href="/api/stats">/api/stats</a> - Statistics</li>
                    <li><a href="/api/sessions">/api/sessions</a> - List sessions</li>
                    <li><a href="/docs">/docs</a> - API documentation (Swagger)</li>
                </ul>
            </div>
        </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
