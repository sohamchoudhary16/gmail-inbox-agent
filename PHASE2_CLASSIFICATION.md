# Phase 2: Email Classification & Labeling

## What's New

### 1. Classifier Agent (`classifier_agent.py`)
Uses Claude Opus 5.5 to classify emails into 7 categories:
- **rfq** — Price request
- **booking_request** — Booking request
- **tracking_inquiry** — Where is shipment?
- **documentation** — Documents submission
- **complaint** — Service complaint
- **general_inquiry** — General question
- **not_relevant** — Spam/noise

**Output:** Category + confidence + RFQ details (origin, destination, weight, volume, mode)

### 2. Classification Service (`classification_service.py`)
Orchestrates the full pipeline:
1. Fetch unread emails from Gmail
2. **Idempotency check**: Skip if already processed (by gmail_message_id)
3. Classify using agent
4. **Create or find session** (one per Gmail thread)
5. Store email & classification in database
6. **Apply Gmail label** (5u/rfq, 5u/booking-request, etc.)
7. Mark email as read

**Key feature:** Idempotency prevents double-labeling same email

### 3. Background Worker (`worker.py`)
APScheduler-based poller:
- Polls inbox every 30 seconds (configurable)
- Runs classification pipeline on unread emails
- Survives app restart (scheduled job re-registered on startup)

### 4. API Routes (`api_routes.py`)
New endpoints:
- `POST /api/classify` — Manually trigger classification
- `GET /api/sessions` — List all sessions with classifications
- `GET /api/sessions/{session_id}` — Get session details + email history
- `GET /api/stats` — Stats by classification category

### 5. Enhanced Dashboard
Root page now shows:
- Live statistics (sessions, emails, classifications)
- List of emails by category
- Button to manually trigger classification
- Links to all API endpoints

## Data Structure

### Session
One per Gmail thread. Contains:
- `id` (UUID)
- `thread_id` (Gmail's thread ID)
- `classification` (the dominant category, updated as emails arrive)
- `customer_email` (email address)
- `subject` (thread subject)

### Email
One per message. Contains:
- `id` (UUID)
- `session_id` (links to session)
- `gmail_message_id` (idempotency key)
- `thread_id` (for indexing)
- `classification` (the category)
- `body` (full message text)
- `is_reply_sent` (whether we already replied)

### PortalCall
One per API call to the customer portal. Used to audit "what did we ask, what did we get?"

## Flow: Email → Classification → Label

```
Unread email arrives
        ↓
Check idempotency (gmail_message_id exists?) → YES → Skip
        ↓ NO
Classify with agent (Claude)
        ↓
Get or create Session (by thread_id)
        ↓
Store Email + classification in DB
        ↓
Apply Gmail label (5u/rfq, etc.)
        ↓
Mark as read
        ↓
Done
```

## Idempotency: The Critical Part

**Problem:** If the worker restarts or runs twice, we can't label the same email twice.

**Solution:** 
- Each email has a `gmail_message_id` from Gmail (globally unique)
- Before processing, query DB for that message ID
- If found → skip (already processed)
- If not found → process and store the ID

**This means:**
- Polling the inbox 100 times is safe
- Worker can crash/restart without double-labeling
- Second run sees the message is in the DB and skips it

## Testing

### Manual Classification
```bash
# Trigger classification via API
curl -X POST http://localhost:8000/api/classify

# Response:
{
  "status": "success",
  "processed": 3,
  "errors": 0,
  "total": 3
}
```

### View Sessions
```bash
curl http://localhost:8000/api/sessions?limit=10

# Response:
{
  "status": "success",
  "count": 3,
  "sessions": [
    {
      "id": "...",
      "thread_id": "...",
      "classification": "rfq",
      "customer_email": "customer@example.com",
      "subject": "Quote request for Shanghai to LA",
      "email_count": 2,
      "created_at": "2026-10-07T12:00:00",
      "updated_at": "2026-10-07T12:05:00"
    },
    ...
  ]
}
```

### View Session Detail
```bash
curl http://localhost:8000/api/sessions/{session_id}
```

## Configuration

In `.env`:
```
POLL_INTERVAL_SECONDS=30    # How often to poll (currently disabled while testing)
ANTHROPIC_API_KEY=...       # Required for classification
GMAIL_CLIENT_ID=...         # Required for Gmail auth
```

## Next Steps (Phase 3)

Phase 2 is complete when:
- ✓ Emails are being classified
- ✓ Labels are applied in Gmail
- ✓ Sessions track conversation threads
- ✓ No double-labeling on re-runs

Phase 3 will:
- Integrate portal API for rate lookups
- Generate auto-replies for each category
- Call portal.get_rate() when it's an RFQ
- Send tracked replies (in thread, never new message)
- Handle partial replies (ask for missing info)
