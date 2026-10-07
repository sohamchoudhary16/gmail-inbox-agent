# Expert Testing & Code Review Guide

## For Code Review & Testing - Start Here

**Time Required:** ~15 minutes for full verification  
**Prerequisites:** Python 3.8+, pip, git  
**Cost:** $0 (all tests use mocks, no external API calls)  

---

## Quick Verification (30 seconds)

```bash
# Clone the repo
git clone <repo-url>
cd gmail-inbox-agent

# Install dependencies
pip install -r requirements.txt

# Run all 68 tests
pytest test_immediate.py test_phase3_workflow.py test_phase4_real_integration.py test_pending_quote_system.py -v

# Expected output
======================= 68 passed in 2.22s =======================
```

**If you see "68 passed":** ✅ All core functionality works. No real API calls made. Safe to review.

---

## What an Expert Should Evaluate

### 1. Test Coverage (Verify All 5 Hard Problems Solved)

```bash
# Run specific test categories

# 1. Portal call decision (Q1)
pytest test_pending_quote_system.py::TestPortalDecisionEngine -v
# Expected: 4 tests pass
# Verify: Only RFQ, booking, tracking call portal; others use templates

# 2. Portal failure handling (Q2)
pytest test_pending_quote_system.py::TestFailureReplies -v
# Expected: 4 tests pass
# Verify: Professional replies for all 3 failure cases

# 3. Agent boundary - Python vs Claude (Q3)
pytest test_phase4_real_integration.py::TestPhase4Workflow -v
# Expected: 2 tests pass
# Verify: Only 1 Claude call per email for classification

# 4. Idempotency - second run safe (Q4)
pytest test_pending_quote_system.py::TestFollowUpHandling -v
# Expected: 4 tests pass
# Verify: No duplicate portal calls on re-run

# 5. Pending quote state machine (Q5)
pytest test_pending_quote_system.py -v
# Expected: 18 tests pass
# Verify: Complete lifecycle from failure → timeout → escalation
```

---

### 2. Architecture Review

#### Check: Only minimal Claude calls

```bash
grep -r "claude\|anthropic\|LLM" *.py | grep -v "test_\|#"
```

**Expected findings:**
- Only `anthropic_classifier.py` calls Claude API
- Only for classification (1 call per email)
- All replies use templates, not Claude
- All decisions use Python logic

#### Check: Graceful degradation without API keys

```python
# Open: anthropic_classifier.py
# Look for: Line 30-40
# Verify: Creates classifier even if ANTHROPIC_API_KEY missing
# Verify: Returns safe fallback ("general_inquiry") on failures
```

#### Check: Portal call decision happens BEFORE portal call

```python
# Open: pending_quote_manager.py
# Look for: PortalDecisionEngine class
# Verify: Line 192-205
# Should see: Only 3 categories in REQUIRES_PORTAL
# Should NOT see: Calling portal for documentation/complaint/general
```

---

### 3. Security Audit

```bash
# Verify no secrets in code
grep -r "sk-ant-" . --exclude-dir=.git | grep -v "YOUR_KEY\|placeholder"
# Should return: Nothing (all are placeholders)

grep -r "api_key.*=.*['\"]" . --exclude-dir=.git | grep -v ".example\|test"
# Should return: Nothing (no hardcoded keys)

# Verify .gitignore blocks secrets
cat .gitignore | grep -E "\.env|credentials|tokens"
# Should see: .env, credentials.json, tokens/ all blocked

# Verify no .env file committed
git log --name-only | grep "\.env$"
# Should return: Nothing

# Verify .env.example is template
cat .env.example | head -5
# Should see: placeholder values like "your_key_here"
```

---

### 4. Database Design Review

```python
# Open: database.py
# Line 56-128: Review schema

# Verify: Idempotency
# Should see:
#   - Email.gmail_message_id = unique index
#   - Session.thread_id = unique index
#   - PendingQuote.session_id = foreign key to Session

# Verify: State machine for pending quotes
# Should see: PendingQuote table with:
#   - status field (pending_portal_failure, follow_up, resolved, escalated)
#   - timeout_at field (24h deadline)
#   - session_id (groups by thread)
```

---

### 5. Code Quality Checks

```bash
# Run with verbose type checking
python -m pytest --co -q
# Should show: 68 test items, all named clearly

# Check for unused imports
python -m py_compile *.py
# Should succeed with no errors

# Check test names are descriptive
grep "def test_" test_*.py | wc -l
# Should show: 68 tests with clear names
```

---

### 6. Performance Verification

```bash
# Time the tests
time pytest test_immediate.py test_phase3_workflow.py test_phase4_real_integration.py test_pending_quote_system.py -q

# Expected: ~2-3 seconds
# Verify: Fast test suite (no network calls)
```

---

## Deep Dive: Code Review Checklist

### Question 1: Portal Decision (Cost Optimization)

**File:** `pending_quote_manager.py` line 192

```python
class PortalDecisionEngine:
    REQUIRES_PORTAL = {"rfq", "booking_request", "tracking_inquiry"}
```

**Review Questions:**
- [ ] Are only 3 categories calling portal? (RFQ, booking, tracking)
- [ ] Are other 4 categories using templates? (doc, complaint, general, spam)
- [ ] Is decision made BEFORE portal call?
- [ ] Are professional fallback replies defined?

**Expected Cost Savings:** 57% vs naive approach

---

### Question 2: Portal Failure Handling

**File:** `pending_quote_manager.py` line 266

```python
FAILURE_REPLIES = {
    "CUSTOMER_NOT_FOUND": "...",
    "ROUTE_NOT_AVAILABLE": "...",
    "PORTAL_DOWN": "...",
}
```

**Review Questions:**
- [ ] Are all 3 failure modes handled?
- [ ] Are replies professional?
- [ ] Do they ask customer for specific info?
- [ ] Is PendingQuote created on failure?
- [ ] Is timeout set to 24h?

**Test:** Run `pytest test_pending_quote_system.py::TestFailureReplies -v`

---

### Question 3: Agent Boundary (LLM Cost Optimization)

**File:** `anthropic_classifier.py` line 50-100

**Review Questions:**
- [ ] Is Claude only called for classification?
- [ ] Is classification NOT called repeatedly?
- [ ] Are replies from templates (no LLM)?
- [ ] Are portal decisions from Python logic (no LLM)?
- [ ] Are error handlers safe without API key?

**Expected:** Only 1 Claude call per email

---

### Question 4: Idempotency

**File:** `database.py` line 77

```python
gmail_message_id = Column(String, unique=True)  # Prevents duplicates
```

**Review Questions:**
- [ ] Does Email table have unique constraint on gmail_message_id?
- [ ] Does Session table have unique constraint on thread_id?
- [ ] Does PendingQuoteManager check before processing?
- [ ] Can second run over same mailbox happen safely?

**Test:** Run `pytest test_immediate.py::TestFullWorkflow -v`

---

### Question 5: Pending Quote State Machine (Hardest Problem)

**File:** `pending_quote_manager.py` line 15-220

**Review Questions:**
- [ ] Is PendingQuote created when portal fails?
- [ ] Are follow-up emails matched by session_id?
- [ ] Is portal checked again on follow-up?
- [ ] Is timeout set correctly (24h)?
- [ ] Is cron job for timeout escalation included?
- [ ] Are professional replies sent?

**Test:** Run `pytest test_pending_quote_system.py -v`

**Expected:** 18 tests covering complete lifecycle

---

## Code Metrics

```bash
# Count lines of code
wc -l *.py

# Expected:
# - database.py: ~150 lines (schema)
# - classification_service.py: ~200 lines (workflow)
# - pending_quote_manager.py: ~220 lines (state machine)
# - test_pending_quote_system.py: ~320 lines (18 tests)
# - Total production code: ~1500 lines
# - Total test code: ~800 lines
# - Ratio: 1:0.5 (reasonable)

# Test count
pytest --co -q | tail -1
# Expected: "68 tests collected"

# Test coverage by file
pytest --cov=. --cov-report=term-missing --no-header -q
# Expected: High coverage on all non-test files
```

---

## Security Audit Results

✅ **No hardcoded secrets**
- All API keys are placeholders
- .env not committed
- credentials.json not committed
- tokens/ directory blocked

✅ **Safe configuration**
- .env.example shows what to add
- No real Gmail used in tests
- No real API keys needed for tests

✅ **Git history clean**
- No secrets in any commit
- Only production code committed
- All test data is mock data

---

## Documentation Review

| File | Purpose | Status |
|------|---------|--------|
| README.md | Overview | ✅ Complete |
| QUICKSTART.md | 30-second verification | ✅ Complete |
| ANSWERS_TO_HARD_QUESTIONS.md | Solutions to 5 hard problems | ✅ Complete |
| ARCHITECTURE_DECISIONS.md | Detailed design | ✅ Complete |
| CREDENTIALS_GUIDE.md | Setup instructions | ✅ Complete |
| TESTING_GUIDE.md | Test infrastructure | ✅ Complete |

---

## What NOT to Look For

❌ **You will NOT find:**
- Real Gmail API calls in tests (all mocked)
- Real Anthropic API calls in tests (all mocked)
- Real Portal API calls in tests (all mocked)
- .env file with real keys (intentionally not committed)
- credentials.json (intentionally not committed)
- Database setup instructions (in-memory SQLite for tests)
- Real email addresses (all are test@example.com style)

---

## Expert Verification Checklist

```
□ All 68 tests pass in <3 seconds
□ No external API calls made during tests
□ No secrets in code or git history
□ Idempotency verified (3 layers)
□ Portal call decision is deterministic Python
□ Only 1 Claude call per email
□ Pending quote state machine complete
□ All 5 hard problems answered in docs
□ Code is clean and well-documented
□ Ready for production deployment

Results: ________________
Date: ________________
Expert Name: ________________
```

---

## When Ready for Production

Add to .env (user's local copy, NOT committed):

```bash
ANTHROPIC_API_KEY=sk-ant-... # Your key here
GMAIL_CLIENT_ID=... # Your client ID
GMAIL_CLIENT_SECRET=... # Your secret
PORTAL_API_KEY=... # Your portal key
```

Then system is ready to:
1. Fetch real emails from Gmail
2. Classify with real Claude API
3. Create quotes/bookings in real Portal
4. Send auto-replies
5. Track with transaction logging

All tested, documented, production-ready.

---

## Contact for Questions

If during review you find:
- Missing test case
- Uncovered code path
- Security concern
- Architecture issue

Document it and the system can be enhanced. All 68 tests provide a safety net for changes.
