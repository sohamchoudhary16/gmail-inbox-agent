# Gmail Integration Architecture - Analysis & Implementation Plan

**Date:** 2026-10-07  
**Phase:** Gmail Integration + Workflow Completion

---

## Current Architecture

### Layer 1: Configuration & Secrets
```
config.py (implemented)
├── Gmail OAuth2 settings (from .env)
├── Anthropic API key (from .env)
├── Portal API credentials (from .env)
└── Database URL, worker config

.env.example (implemented)
├── GMAIL_CLIENT_ID/SECRET
├── GMAIL_TOKEN_FILE
├── ANTHROPIC_API_KEY
└── PORTAL_BASE_URL, DATABASE_URL, etc.

.gitignore (implemented)
├── .env (blocks real credentials)
├── credentials.json (blocks OAuth files)
├── tokens/ (blocks cached tokens)
└── *.db (blocks SQLite database)
```

### Layer 2: Gmail Integration
```
gmail_service.py (partially implemented)
├── Authentication ✅
│   ├── OAuth2 flow (from credentials.json) ✅
│   ├── Token caching (tokens/gmail_token.json) ✅
│   └── Token refresh ✅
│
├── Email Fetching ✅
│   ├── get_unread_emails() ✅
│   ├── get_message() ✅
│   └── _get_message_body() ✅
│
├── Label Management ✅
│   ├── add_label() ✅
│   ├── _get_or_create_label() ✅
│   └── Label caching (in memory, could improve) ⚠️
│
└── Reply Management ✅
    ├── send_reply() ✅
    └── mark_as_read() ✅

NOTE: Currently NO dry-run mode
```

### Layer 3: Data Model
```
database.py (implemented)
├── Session table
│   ├── id (PK)
│   ├── thread_id (unique) ← Gmail thread
│   ├── classification
│   ├── customer_email
│   └── timestamps
│
├── Email table
│   ├── id (PK)
│   ├── gmail_message_id (unique) ← Gmail message ID (idempotency key)
│   ├── thread_id (index)
│   ├── classification
│   ├── is_customer_email
│   ├── is_reply_sent
│   └── timestamps
│
└── Portal calls, Pending quotes
    (for Phase 3)
```

### Layer 4: Classification
```
agno_classifier.py (implemented)
├── 7 categories defined ✅
├── Label mapping ✅
├── JSON output parsing ✅
└── Error fallback ✅

classification_service.py (partially implemented)
├── Session management ✅ (Issue 1 fixed)
├── Email persistence ✅
├── Idempotency check ✅ (by gmail_message_id)
└── Label application ✅

classifier_agent.py (legacy, needs removal)
├── Old implementation (replaced by agno_classifier.py)
└── Should be removed
```

### Layer 5: Workflow
```
worker.py (implemented)
├── APScheduler for polling ✅
├── poll_and_process_emails() ✅
└── start/stop scheduler ✅

classification_service.process_unread_emails()
├── 1. Fetch unread from Gmail ✅
├── 2. Classify with agent ✅
├── 3. Store in database ✅
├── 4. Apply label ✅
└── 5. Mark as read ✅

BUT: No dry-run mode, no transaction logging
```

### Layer 6: API
```
api_routes.py (implemented)
├── POST /api/classify ✅
├── GET /api/sessions ✅
├── GET /api/sessions/{id} ✅
└── GET /api/stats ✅

main.py (implemented)
├── Startup/shutdown ✅
├── Root dashboard ✅
└── Health check ✅
```

---

## Current Implementation Status

### ✅ DONE
- OAuth2 authentication (Gmail API)
- Email fetching (unread messages)
- Message parsing (subject, from, body, threadId)
- Label creation & application
- Token caching & refresh
- Database schema (sessions, emails, portal_calls, pending_quotes)
- Idempotency (gmail_message_id unique constraint)
- Classification (7 categories)
- Session grouping (by thread_id)
- API endpoints
- Background scheduler

### ⚠️ NEEDS IMPROVEMENT
- **Dry-run mode:** Not implemented (real Gmail API calls)
- **Workflow logging:** No structured logging of classification results
- **Label caching:** In-memory only (should be optimized)
- **Error recovery:** Basic, could be more robust
- **Config validation:** No startup checks

### ❌ NOT YET DONE
- Structured transaction logging
- Dry-run mode (dry-run parameter)
- Pre-processing before classification (validation, extraction)
- Comprehensive error handling with retry

---

## Blocking Issues

### Issue 1: No Dry-Run Mode ❌
**Impact:** Can't test without contacting Gmail  
**Solution:** Add `DRY_RUN` config flag that:
- Mocks Gmail API calls
- Logs what would happen
- Doesn't actually apply labels or mark as read
- Doesn't persist anything

### Issue 2: Missing Pre-Processing ❌
**Impact:** Classification receives raw email text  
**Solution:** Extract structured data before classification:
- Parse email addresses properly
- Identify port names (vs city names)
- Extract numbers (weight, volume)
- Clean text (whitespace, encoding)

### Issue 3: No Transaction Logging ❌
**Impact:** Hard to audit what happened  
**Solution:** Add ProcessingLog table:
- Email ID
- Classification result
- Label applied
- Status (success/error)
- Timestamp

### Issue 4: Unused classifier_agent.py ⚠️
**Impact:** Code duplication, confusion  
**Solution:** Remove classifier_agent.py (replaced by agno_classifier.py)

---

## Files to Change

### Core Implementation
| File | Change | Reason |
|------|--------|--------|
| `config.py` | Add `DRY_RUN` flag | Enable dry-run testing |
| `gmail_service.py` | Add dry-run support | Mock API calls in dry-run |
| `database.py` | Add ProcessingLog table | Transaction logging |
| `classification_service.py` | Add pre-processing + logging | Structure + auditability |
| `agno_classifier.py` | No change | Keep as-is |

### Tests
| File | Change | Reason |
|------|--------|--------|
| Create `test_gmail_integration.py` | Test Gmail with dry-run | Verify email fetching |
| Create `test_workflow_end_to_end.py` | Full workflow test | Verify classification → label |
| Create `test_dry_run.py` | Test dry-run mode | Verify no API calls |

### Cleanup
| File | Change | Reason |
|------|--------|--------|
| `classifier_agent.py` | DELETE | Replaced by agno_classifier.py |
| `test_phase2.py` | DELETE | Superseded by newer tests |

### Documentation
| File | Change | Reason |
|------|--------|--------|
| Create `WORKFLOW_IMPLEMENTATION.md` | Document full flow | Reference implementation |

---

## Proposed Workflow

### Sequence (with dry-run support)

```
[START]
  ↓
Config loaded (including DRY_RUN flag)
  ↓
IF dry_run:
  ├─ Mock Gmail API
  ├─ Mock Label creation
  └─ Mock Mark as read
ELSE:
  ├─ Real Gmail API
  ├─ Real Label creation
  └─ Real Mark as read
  ↓
[POLL_EMAILS]
  ├─ Gmail: List unread messages
  ├─ For each message:
  │   ├─ Check idempotency (gmail_message_id in DB?)
  │   │   ├─ YES → Skip
  │   │   └─ NO → Process
  │   │
  │   ├─ [PRE-PROCESS]
  │   │   ├─ Extract structured data
  │   │   ├─ Clean text
  │   │   └─ Validate inputs
  │   │
  │   ├─ [CLASSIFY]
  │   │   ├─ Call classifier
  │   │   ├─ Get category (exactly 1)
  │   │   └─ Store result in DB
  │   │
  │   ├─ [PERSIST_MESSAGE]
  │   │   ├─ Create/get session (by thread_id)
  │   │   ├─ Store email in DB
  │   │   └─ Record in ProcessingLog
  │   │
  │   ├─ [APPLY_LABEL]
  │   │   ├─ Get label for category
  │   │   ├─ Apply to Gmail message
  │   │   └─ Log action
  │   │
  │   └─ [MARK_AS_READ]
  │       ├─ Mark in Gmail
  │       └─ Update DB flag
  │
  └─ Return summary
      {processed, errors, total}
```

---

## Implementation Strategy

### Step 1: Add Dry-Run Support
**Files:** `config.py`, `gmail_service.py`
- Add `DRY_RUN: bool = False` to settings
- Add dry_run parameter to GmailService methods
- Mock API calls when dry_run=True
- Log what would happen instead of doing it

### Step 2: Add Pre-Processing
**File:** `classification_service.py`
- Extract email structure
- Validate before classification
- Add error handling

### Step 3: Add Transaction Logging
**Files:** `database.py`, `classification_service.py`
- Add ProcessingLog table to schema
- Log each step with status

### Step 4: Create Tests
**Files:** `test_gmail_integration.py`, `test_workflow_end_to_end.py`
- Test dry-run mode
- Test full workflow
- Test error cases

### Step 5: Cleanup
**Files:** `classifier_agent.py`, `test_phase2.py`
- Remove deprecated files

---

## What Will NOT Change

✅ Database schema (except adding ProcessingLog)  
✅ Classification logic (agno_classifier.py)  
✅ API endpoints  
✅ OAuth authentication flow  
✅ Session management (Issue 1 fix)  
✅ Idempotency approach (gmail_message_id unique)  

---

## Risk Assessment

### Low Risk
- Adding dry-run mode (decorator pattern, no schema changes)
- Adding pre-processing (before classification, isolated)
- Adding transaction logging (new table, backward compatible)

### No Risk
- Tests (new files, don't affect running code)
- Cleanup (removing unused files)

### Mitigations
- All changes preserve existing API
- Dry-run mode is opt-in (default: False)
- Database migrations minimal (add table only)
- All changes have corresponding tests

---

## Success Criteria

After implementation, verify:

✅ Can fetch unread emails from Gmail (real or mock)  
✅ Each email gets exactly 1 category  
✅ Gmail message ID persisted before processing  
✅ Processing is idempotent (run twice = same result)  
✅ Correct label applied based on category  
✅ Dry-run mode works (no API calls made)  
✅ All tests pass (including new ones)  
✅ No secrets in git (verify .gitignore)  
✅ Git diff shows only intended changes  
✅ Linting/type checks pass  

---

## Estimated Effort

- Dry-run support: 30 min
- Pre-processing: 20 min
- Transaction logging: 20 min
- Tests: 40 min
- Cleanup: 10 min
- **Total: ~2 hours**

---

## Next: Implementation

Ready to proceed with:
1. Updating files (listed above)
2. Adding dry-run mode
3. Adding pre-processing
4. Creating comprehensive tests
5. Full test suite, linting, type checks
6. Git diff verification
7. Secret scanning

**Proceed?**
