# Gmail Inbox Automation - Project Structure

## Phase 1: Core Infrastructure (Completed)

### Configuration & Setup
- **requirements.txt** — All dependencies (FastAPI, Agno, SQLAlchemy, Gmail API client, etc.)
- **.env.example** — Template for environment variables (credentials kept out of git)
- **.gitignore** — Prevents credentials, tokens, database from being committed

### Database Layer
- **database.py** — SQLAlchemy ORM models:
  - `Session` — One per Gmail thread/conversation
  - `Email` — Individual messages with classification
  - `PortalCall` — Audit trail of all portal API calls
  - `PendingQuote` — Tracks quotes waiting for desk response (survives restart)

### Service Layer
- **gmail_service.py** — Gmail API wrapper
  - Fetch unread emails
  - Get full message content
  - Add labels (create if needed)
  - Send replies in thread
  - Mark as read

- **portal_service.py** — Customer portal API client
  - Get available ports
  - Get shipping rates
  - Get shipment status
  - Hand over quote to desk (returns reference ID)

- **agent_tools.py** — Tools callable by the AI agent
  - `get_shipping_rate()` — Look up lane pricing
  - `get_shipment_status()` — Look up container status
  - `get_available_ports()` — Resolve port names to codes
  - `handover_quote_to_desk()` — Trigger desk quote process

### Application
- **config.py** — Configuration management (reads from .env)
- **main.py** — FastAPI application with:
  - Database initialization on startup
  - Health check endpoint
  - Root dashboard (basic UI)

## Data Flow (Implemented So Far)

```
1. Gmail → gmail_service.get_unread_emails()
2. Store in database.Email
3. Agent calls agent_tools.* as needed
4. agent_tools call portal_service.*
5. Results logged in database.PortalCall
6. gmail_service sends reply back through Gmail API
```

## Secrets Management

**Never committed:**
- `.env` (use `.env.example` as template)
- `credentials.json`, `credentials-desktop.json`
- `tokens/` directory (Gmail token cache)
- Database file (if using local SQLite)

**Set before running:**
```bash
cp .env.example .env
# Edit .env with:
# - ANTHROPIC_API_KEY
# - PORTAL_BASE_URL, PORTAL_API_KEY (provided at session start)
# - GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET
# Copy credentials.json from interview-soham/
```

## Next Steps (Phase 2+)

- [ ] Phase 2: Email classification & labeling
- [ ] Phase 3: Portal integration & auto-replies
- [ ] Phase 4: Delayed quote handling (request handover → desk email matching → customer reply)
- [ ] Phase 5: Session/thread API and UI

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Copy Gmail credentials
cp ../interview-soham/credentials.json .

# Set up environment
cp .env.example .env
# Edit .env with your keys

# Run server
python -m uvicorn main:app --reload
```
