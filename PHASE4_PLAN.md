# Phase 4: Real Integration Plan

**Status:** Ready to Start  
**Estimated Scope:** Real Gmail + Anthropic + Portal APIs  
**Test Coverage:** Full end-to-end with mocks for external services  

---

## Phase 4 Overview

Integrate real external services while maintaining testability:
1. **Real Gmail OAuth2** (replace mock)
2. **Real Anthropic API** (replace mock classifier)
3. **Portal API** (case creation)
4. **Transaction Logging** (ProcessingLog table)
5. **Error Handling & Retry Logic** (production-ready)

---

## Architecture: Phases 1-4 Complete

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: Foundation                                     │
│ ✅ Database schema (SQLAlchemy ORM)                     │
│ ✅ Config management (Pydantic Settings)                │
│ ✅ FastAPI skeleton                                     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ PHASE 2: Email Processing Pipeline                      │
│ ✅ Mock Gmail Service (fetch, label, mark read)         │
│ ✅ Mock Classifier (7-category classification)          │
│ ✅ Classification Workflow (idempotency)                │
│ ✅ Session Management (Issue 1 fixed)                   │
│ ✅ 19 tests (all passing)                               │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ PHASE 3: Auto-Reply Generation                          │
│ ✅ AutoReplyGenerator (5 reply categories)              │
│ ✅ Professional templates                               │
│ ✅ Complete end-to-end workflow                         │
│ ✅ 13 tests (all passing)                               │
│ ✅ Total: 32 tests passing                              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ PHASE 4: Real Integration (NOW)                         │
│ ⏳ Real Gmail OAuth2                                    │
│ ⏳ Real Anthropic API                                   │
│ ⏳ Real Portal API                                      │
│ ⏳ Transaction Logging                                  │
│ ⏳ Error Handling & Retry                               │
│ ⏳ End-to-end integration tests                         │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Strategy

### Principle: Maintain Testability
**Every real service gets a mock version for testing.**

```python
# Production: Real Gmail
gmail_service = GmailService(creds=real_creds, dry_run=False)

# Testing: Mock Gmail (still works same way)
gmail_service = MockGmailService(dry_run=True)
```

### Principle: Gradual Integration
**Each service integrated independently, tested thoroughly, then combined.**

---

## Phase 4 Breakdown

### 1. Real Gmail OAuth2 Integration (Highest Priority)

**Current State:** `gmail_service.py` has stubs

**What to Implement:**
- Load OAuth2 credentials from `.env`
- Initialize InstalledAppFlow
- Cache tokens in `tokens/gmail_token.json`
- Handle token refresh
- Real API calls for: `get_unread_emails()`, `add_label()`, `mark_as_read()`, `send_reply()`

**Testing Strategy:**
- Keep MockGmailService for unit tests
- Create test account (separate from user's real Gmail)
- Integration tests with test account
- Dry-run mode to simulate without sending

**Blocking Issues:**
- None - all stubs in place

---

### 2. Real Anthropic API (High Priority)

**Current State:** `agno_classifier.py` uses Anthropic SDK (temporary)

**What to Implement:**
- Replace keyword-based MockClassifier
- Use Anthropic API with real LLM
- Proper prompt engineering for classification
- Add confidence scores
- Cache classifications (optional)

**Testing Strategy:**
- Mock Anthropic API responses in tests
- Real API tests with test emails
- Performance monitoring

**Blocking Issues:**
- Need ANTHROPIC_API_KEY in .env

---

### 3. Portal API Integration (Medium Priority)

**Current State:** `portal_api.py` has stubs

**What to Implement:**
- Authentication (API key from .env)
- Create cases from classified emails
- Update cases with replies
- Handle RFQ → Quote creation
- Handle Booking → Booking confirmation

**Testing Strategy:**
- Mock Portal API responses
- Integration with classification workflow
- Error handling for API failures

**Blocking Issues:**
- Need PORTAL_API_KEY and PORTAL_API_URL in .env
- Need Portal API documentation

---

### 4. Transaction Logging (Medium Priority)

**Current State:** `ProcessingLog` table defined but unused

**What to Implement:**
- Log every email processed
- Log classifications
- Log replies sent
- Log API calls (Portal, Anthropic)
- Log errors and retries

**Testing Strategy:**
- Verify logs written to database
- Query logs for audit trail

**Schema:**
```python
class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    
    id = Column(String, primary_key=True)
    email_id = Column(String, ForeignKey("emails.gmail_message_id"))
    action = Column(String)  # fetch, classify, reply, label, mark_read
    status = Column(String)  # success, error
    details = Column(JSON)   # full details
    error_message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

### 5. Error Handling & Retry Logic (Medium Priority)

**What to Implement:**
- Graceful handling of API failures
- Retry logic with exponential backoff
- Circuit breaker pattern (optional)
- Comprehensive error logging
- Admin notifications (optional)

**Testing Strategy:**
- Mock API failures
- Test retry logic
- Test graceful degradation

---

## Implementation Order

### Step 1: Real Gmail OAuth2 (Foundation)
Without this, can't test with real emails.

```bash
# 1. Set up test Gmail account
# 2. Generate OAuth2 credentials
# 3. Test get_unread_emails() with real account
# 4. Test add_label() and mark_as_read()
# 5. Add integration tests
```

### Step 2: Real Anthropic API (Classification)
With Gmail working, can test real classification.

```bash
# 1. Implement real classifier
# 2. Test with real emails from test Gmail account
# 3. Verify accuracy of 7-category classification
# 4. Add integration tests
```

### Step 3: Portal API (Case Creation)
With classification working, can create cases.

```bash
# 1. Get Portal API documentation
# 2. Implement case creation
# 3. Test RFQ → Quote flow
# 4. Test Booking → Confirmation flow
# 5. Add integration tests
```

### Step 4: Transaction Logging (Audit Trail)
Throughout all above steps.

```bash
# 1. Add logging to each API call
# 2. Store logs in ProcessingLog table
# 3. Create log viewer/dashboard (optional)
```

### Step 5: Error Handling & Retry (Reliability)
Throughout all above steps.

```bash
# 1. Add try/catch to all API calls
# 2. Implement retry logic
# 3. Add comprehensive error logging
# 4. Test failure scenarios
```

---

## Environment Setup (Prerequisites)

### Required .env Variables
```env
# Gmail OAuth2
GMAIL_CLIENT_ID=your-client-id
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REDIRECT_URI=http://localhost:8080/auth/callback

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Portal API
PORTAL_API_KEY=your-key
PORTAL_API_URL=https://portal.example.com/api

# Database
DATABASE_URL=sqlite:///./test.db

# App
DRY_RUN=false
DEBUG=true
```

### Test Account Setup
1. Create test Gmail account (not user's real account)
2. Generate OAuth2 credentials via Google Cloud Console
3. Add test emails to trigger workflows
4. Set DRY_RUN=true for safe testing

---

## Testing Strategy

### Unit Tests (Keep Existing)
```bash
pytest test_immediate.py -v  # Phase 2: 19 tests
pytest test_phase3_workflow.py -v  # Phase 3: 13 tests
```

### Integration Tests (Phase 4 New)
```bash
pytest test_phase4_integration.py -v
# Tests:
# - Real Gmail + Mock Anthropic
# - Real Anthropic + Mock Gmail
# - Real Gmail + Real Anthropic
# - Portal API integration
# - Transaction logging
# - Error handling & retry
```

### End-to-End Tests (Phase 4 New)
```bash
pytest test_phase4_e2e.py -v
# Tests complete workflow with test Gmail account
```

### Manual Testing
```bash
# 1. Send email to test Gmail account
# 2. Run: python main.py
# 3. Verify email processed
# 4. Check Portal for created case
# 5. Verify auto-reply sent
```

---

## Success Criteria

✅ **Real Gmail OAuth2 working**
- Can fetch unread emails from test account
- Can apply labels
- Can mark as read
- Can send replies

✅ **Real Anthropic API working**
- Can classify emails with real LLM
- Accuracy > 90% on test set
- Handles all 7 categories correctly

✅ **Portal API integration working**
- Can create cases from RFQ emails
- Can update cases with booking confirmations
- Error handling for API failures

✅ **Transaction logging complete**
- Every email logged
- Every API call logged
- Queries for audit trail working

✅ **Error handling robust**
- Retries on transient failures
- Graceful degradation on permanent failures
- Comprehensive error logging

✅ **All tests passing**
- 32 Phase 2+3 tests still passing
- 15+ Phase 4 integration tests passing
- End-to-end workflow tested

---

## Risk Assessment

### Low Risk
- Gmail OAuth2 (well-documented, widely used)
- Anthropic API (REST API, clear docs)
- Database logging (straightforward SQL)

### Medium Risk
- Portal API integration (depends on unknown API spec)
- Token refresh logic (timing issues)
- Error handling across all services

### Mitigation
- Comprehensive mocking for all external services
- Separate test account for Gmail
- Dry-run mode for safe testing
- Detailed error logging
- Fallback to mock services if real ones fail

---

## Timeline

| Phase | Task | Est. Time | Status |
|-------|------|-----------|--------|
| 4.1 | Real Gmail OAuth2 | 2-3 hours | Ready to Start |
| 4.2 | Real Anthropic API | 1-2 hours | Depends on 4.1 |
| 4.3 | Portal API | 1-2 hours | Depends on 4.2 |
| 4.4 | Transaction Logging | 1 hour | Parallel |
| 4.5 | Error Handling & Retry | 1 hour | Parallel |
| 4.6 | Integration Tests | 2-3 hours | Parallel |
| **Total** | | **8-11 hours** | **Ready** |

---

## What This Unlocks

✅ **Production Ready** - Real APIs working  
✅ **Fully Tested** - Comprehensive test coverage  
✅ **Fully Logged** - Complete audit trail  
✅ **Reliable** - Error handling & retry logic  
✅ **Scalable** - Ready for real email volume  
✅ **Maintainable** - Clean architecture, well-documented  

---

## Next Step

Ready to proceed with Phase 4.1: Real Gmail OAuth2 Integration.

Start with:
```bash
# 1. Set up test Gmail account
# 2. Create OAuth2 credentials
# 3. Implement real GmailService
# 4. Add integration tests
```

---

**Current Status:**
- ✅ Phase 1: Foundation (Complete)
- ✅ Phase 2: Email Processing (Complete, 19 tests)
- ✅ Phase 3: Auto-Replies (Complete, 13 tests)
- ⏳ Phase 4: Real Integration (Ready to Start)

**Total Tests:** 32 passing ✅  
**Ready for:** Phase 4.1 (Gmail OAuth2)
