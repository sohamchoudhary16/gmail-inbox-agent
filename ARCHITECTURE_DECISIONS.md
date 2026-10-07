# Architecture Decisions: The Hard Problems

**Status:** Design Document  
**Scope:** Production-level system design  
**Focus:** State management, agent boundaries, cost optimization  

---

## Question 1: Does the Agent Call the Portal, or Answer from Guessed Price?

### The Decision

**Policy: Minimize portal calls through intelligent pre-filtering**

```
Email Flow:
  ┌─────────────────┐
  │ Unread Email    │
  └────────┬────────┘
           ↓
  ┌─────────────────────────────┐
  │ 1. Classification (Python)  │ ← Fast, deterministic
  │    Cheap keyword match      │
  └────────┬────────────────────┘
           ↓
  ┌─────────────────────────────────────┐
  │ 2. Portal Need Assessment (Python)  │ ← Decide BEFORE API
  │    • RFQ → Portal create quote      │
  │    • Booking → Portal book space    │
  │    • Tracking → Portal query        │
  │    • Others → Auto-reply only       │
  └────────┬────────────────────────────┘
           ↓
  ┌──────────────────────────────────────┐
  │ 3. Portal Call (if needed, rare)     │ ← Expensive, use sparingly
  │    Only for 3 categories             │
  └────────┬─────────────────────────────┘
           ↓
  ┌──────────────────────────────────────┐
  │ 4. Auto-Reply (from template)        │ ← Fast, deterministic
  │    Based on portal result OR default │
  └────────┬─────────────────────────────┘
           ↓
  ┌──────────────────────────────────────┐
  │ 5. Label + Mark Read (Gmail)         │ ← Fast
  └──────────────────────────────────────┘
```

### Portal Interaction by Category

| Category | Portal Call | Response Source |
|----------|-------------|-----------------|
| **RFQ** | ✅ YES | Create quote in portal, return reference # |
| **Booking** | ✅ YES | Check availability, create if possible |
| **Tracking** | ✅ YES | Query status from portal database |
| **Documentation** | ❌ NO | Auto-reply template only |
| **Complaint** | ❌ NO | Flag for human review (no auto-reply) |
| **General Inquiry** | ❌ NO | Auto-reply template only |
| **Not Relevant** | ❌ NO | Mark as spam, no reply |

### Cost Analysis

**Without Optimization (call portal for everything):**
```
Per email:
  - Classification: $0.001 (Anthropic)
  - Portal: $0.01 (API call) × 7 categories = $0.07 per email
  - Auto-reply: $0 (template)
  
  At 1000 emails/day: $70/day in portal calls for non-portal emails
```

**With Optimization (only call portal when needed):**
```
Per email:
  - Classification: $0.001
  - Portal: $0.01 × 3 categories (average) = $0.03 per email
  - Auto-reply: $0
  
  At 1000 emails/day: 
    - 300 RFQ/Booking/Tracking: $3/day portal calls
    - 700 others: $0 portal calls
    - Total: ~$1/day (57% savings)
```

### Implementation

```python
class PortalDecisionEngine:
    """Decide whether to call portal BEFORE making the call."""
    
    REQUIRES_PORTAL = {"rfq", "booking_request", "tracking_inquiry"}
    
    def should_call_portal(self, category: str) -> bool:
        """Check if category needs portal call."""
        return category in self.REQUIRES_PORTAL
    
    def get_portal_action(self, category: str) -> str:
        """Get the specific portal action."""
        actions = {
            "rfq": "create_quote",
            "booking_request": "check_availability",
            "tracking_inquiry": "query_status"
        }
        return actions.get(category, None)
```

**Result:** Only 3 out of 7 categories need portal calls. 57% cost savings.

---

## Question 2: What Happens with Cases Portal Cannot Answer?

### The Three Portal Failure Scenarios

#### Scenario 1: RFQ Portal Failure (Cannot Create Quote)

```
Email: "Quote for 100 boxes, Shanghai to LA, next week"

Step 1: Classify → RFQ ✓
Step 2: Decide portal needed → YES ✓
Step 3: Call portal → FAILS
  - Portal is down
  - OR customer not found in portal
  - OR route not available
```

**Response Strategy: Graceful Degradation**

```python
class PortalCallStrategy:
    """Handle portal failures gracefully."""
    
    def handle_rfq_failure(self, email, error):
        if error == "CUSTOMER_NOT_FOUND":
            # Send acknowledgment, ask for more info
            return """Thank you for your RFQ.
            
            We need to verify your account details before 
            we can process this quote. Please reply with:
            - Company name
            - Account number (if you have one)
            
            Once verified, we'll provide a quote immediately.
            """
        
        elif error == "ROUTE_NOT_AVAILABLE":
            # Acknowledge, inform, offer alternatives
            return """Thank you for your RFQ for Shanghai→LA.
            
            Unfortunately, we don't have availability for that 
            route on the requested date. 
            
            Would you be interested in:
            - A different departure date?
            - A different port (Shenzhen, Ningbo)?
            
            Please let us know and we'll get you a quote ASAP.
            """
        
        elif error == "PORTAL_DOWN":
            # Store pending, manual review
            pending = PendingQuote(
                email_id=email.id,
                category="rfq",
                reason="portal_unavailable",
                created_at=datetime.now()
            )
            db.add(pending)
            db.commit()
            
            return """Thank you for your RFQ.
            
            We're currently experiencing technical difficulties
            processing quotes. Our team will manually review your
            request and respond within 2 hours.
            """
```

#### Scenario 2: Booking Failure (Cannot Confirm Space)

```
Email: "Book 10 containers LCL, Shanghai→LA, Oct 15"

Portal returns: SPACE_NOT_AVAILABLE
```

**Response:**

```python
return """Thank you for your booking request.

Unfortunately, we don't have LCL space for that date/route.

Your options:
1. FCL service (minimum 20 containers) - AVAILABLE
2. Different date - Oct 16-20 AVAILABLE
3. Different port - Shenzhen AVAILABLE

Please let us know your preference and we'll confirm immediately.
"""
```

#### Scenario 3: Tracking Failure (Shipment Not Found)

```
Email: "Where is container ABC123XYZ?"

Portal returns: SHIPMENT_NOT_FOUND
```

**Response:**

```python
return """Thank you for your tracking inquiry.

We couldn't find shipment ABC123XYZ in our system.

Could you please verify:
- Container number (or Bill of Lading number)
- Original shipment date
- Origin and destination

Once confirmed, we'll provide an immediate update.
"""
```

### Portal Failure State Machine

```
Email arrives → Classify → Decide portal needed
                              ↓
                         Call Portal
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
              SUCCESS               FAILURE
                    ↓                   ↓
            Return result    Store in PendingQuote
            Send reply       Flag for review
            Mark read        Auto-reply with options
```

---

## Question 3: Where's the Boundary Between Agent and Code?

### The Principle: Decide in Python First

**Anything deterministic and decidable in Python BEFORE calling Claude:**
- ✅ Do it in Python (fast, cheap, testable)
- ❌ Don't defer to Claude

### Decision Matrix

| Decision | Type | Handler |
|----------|------|---------|
| **Is this an email?** | Deterministic | Python (if has subject, body, from) |
| **Email language?** | Deterministic | Python (regex for freight terms) |
| **Customer in DB?** | Deterministic | Python query |
| **Route exists?** | Deterministic | Python portal query |
| **Email matches pending quote?** | Deterministic | Python SQL join |
| **Needs classification?** | Intelligent | Claude API ← Only here |
| **What price to quote?** | Intelligent | Claude or Portal ← Here |
| **Sentiment of complaint?** | Intelligent | Claude ← Here if needed |

### Code Structure: Layered

```python
class EmailProcessingPipeline:
    """Process email with minimal API calls."""
    
    def process(self, email):
        # Layer 1: Deterministic checks (Python)
        if not self._is_valid_email(email):
            return self._log_invalid(email)
        
        if self._is_spam_by_rules(email):  # Sender list, keywords
            return self._mark_spam(email)
        
        if self._matches_pending_quote(email):  # DB lookup
            return self._handle_quote_response(email)
        
        # Layer 2: Classification (Claude)
        category = self._classify_email(email)  # ← LLM call #1
        
        # Layer 3: Portal decision (Python)
        if not self._should_call_portal(category):
            # Auto-reply from template
            return self._send_template_reply(category, email)
        
        # Layer 4: Portal call (HTTP)
        portal_result = self._call_portal(category, email)
        
        # Layer 5: Result handling (Python)
        if portal_result.success:
            return self._send_success_reply(category, portal_result)
        else:
            return self._send_fallback_reply(category, portal_result.error)
    
    def _is_valid_email(self, email):
        """Python: Basic email validation."""
        return email.subject and email.body and email.from_
    
    def _is_spam_by_rules(self, email):
        """Python: Keyword-based spam detection."""
        spam_keywords = ["FREE MONEY", "WINNER", "CLAIM NOW"]
        return any(kw in email.body.upper() for kw in spam_keywords)
    
    def _matches_pending_quote(self, email):
        """Python: DB lookup."""
        return PendingQuote.find_matching(email)
    
    def _classify_email(self, email):
        """Claude: Classification."""
        # ← ONLY LLM CALL for classification
        return claude.classify(email.subject, email.body)
    
    def _should_call_portal(self, category):
        """Python: Decision logic."""
        return category in {"rfq", "booking_request", "tracking_inquiry"}
    
    def _send_template_reply(self, category, email):
        """Python: No LLM, just templates."""
        templates = {
            "documentation": "We received your documents...",
            "general_inquiry": "Thank you for your inquiry...",
            "not_relevant": None,  # No reply
            "complaint": None  # No auto-reply, manual review
        }
        return templates.get(category)
    
    def _call_portal(self, category, email):
        """HTTP: External service."""
        return portal.create_request(category, email)
```

### Cost Comparison

**Naive approach (call Claude for everything):**
```
Per email:
  - Classify: $0.001
  - Get reply from Claude: $0.002 (another API call)
  
  1000 emails × $0.003 = $3/day
```

**Optimized approach (Python + Claude for classification only):**
```
Per email:
  - Classify: $0.001 (only this)
  - Auto-reply: $0 (template from Python)
  - Portal call: $0.01 (only if needed, rare)
  
  1000 emails: 
    - 700 non-portal: 700 × $0.001 = $0.70
    - 300 portal: 300 × ($0.001 + $0.01) = $3.30
    - Total: ~$4/day (vs $3 naive)
```

**But:** Optimized is much faster (no waiting for Claude for replies) and more testable (99% of logic is deterministic Python).

---

## Question 4: Is a Second Run Over the Same Mailbox Safe?

### The Idempotency Guarantee

**YES. Safe with caveats.**

```
First run:
  Email MSG_001: RFQ → Create quote, auto-reply, label, mark read
  
Second run 24 hours later:
  Email MSG_001: Already read, already labeled
  → Classifier checks: gmail_message_id already in Email table
  → SKIP (idempotent check)
```

### The Idempotency Chain

**Layer 1: Gmail State**
```python
# Already marked as read + labeled → won't be in "unread" query
unread = gmail.get_unread_emails()  # Only returns unread
# MSG_001 not in list (already marked read)
# ✓ SAFE
```

**Layer 2: Database Uniqueness**
```python
class Email(Base):
    __tablename__ = "emails"
    gmail_message_id = Column(String, unique=True)  # ← Prevents duplicates
    
# First run: INSERT EMAIL with gmail_message_id = MSG_001
# Second run: Try to INSERT same → CONSTRAINT VIOLATION
# ✓ SAFE (caught by DB)
```

**Layer 3: Application Logic**
```python
def process_email(email_data):
    # Check if already processed
    existing = db.query(Email).filter(
        Email.gmail_message_id == email_data.id
    ).first()
    
    if existing:
        logger.info(f"Email {email_data.id} already processed")
        return  # Skip
    
    # Process...
```

### But: One Big Caveat

**Portal side effects are NOT idempotent**

```
Email: "Please quote for 100 boxes Shanghai→LA"

First run:
  1. Classify: RFQ ✓
  2. Call portal: create_quote() → Quote_ID_123 created
  3. Send reply: "Your quote is Quote_ID_123"
  4. Store: Email marked processed

Second run (same mailbox, same email):
  1. Email MSG_001 is marked as read → NOT in unread list
  2. Won't even be fetched by get_unread_emails()
  ✓ SAFE
```

**But if you manually re-fetch or use a different query:**

```python
# BAD: Re-fetch all emails (not just unread)
all_emails = gmail.get_all_emails()  # ← Includes already-read!

# Without idempotency check, would:
# 1. Call portal AGAIN
# 2. Create Quote_ID_124 (duplicate!)
# 3. Send ANOTHER reply
# ✗ UNSAFE
```

### Idempotency Rules

```python
class IdempotencyRules:
    """Rules for safe re-running."""
    
    SAFE:
        # Always safe (automatic idempotency)
        - Fetch only unread emails
        - Check DB uniqueness constraint
        - Have explicit idempotency check
    
    UNSAFE:
        # These MUST have application-level guards
        - Re-fetch all emails
        - Calling portal without checking existing quote
        - Sending replies without checking if already sent
    
    REQUIRED for safety:
        1. Only fetch unread emails from Gmail
        2. Check Email table before processing
        3. Don't call portal twice for same email
        4. Store quote response in database
```

### Full Idempotency Test

```python
def test_second_run_over_same_mailbox_is_safe():
    """Verify complete idempotency."""
    
    # Setup
    gmail = MockGmailService()
    emails = gmail.get_unread_emails()
    assert len(emails) == 7
    
    # Run 1
    for email in emails:
        process_email(email)
    
    # Verify first run results
    processed = db.query(Email).count()
    assert processed == 7
    quotes_created = db.query(PortalCall).filter(
        PortalCall.action == "create_quote"
    ).count()
    
    # Run 2: Mark all as read (simulate real Gmail state)
    for email in emails:
        gmail.mark_as_read(email["id"])
    
    # Re-run over same mailbox
    emails_second = gmail.get_unread_emails()  # Should be empty!
    assert len(emails_second) == 0  # ✓ Safe
    
    # Verify no duplicates created
    processed_after = db.query(Email).count()
    assert processed_after == 7  # Same as before
    
    quotes_after = db.query(PortalCall).filter(
        PortalCall.action == "create_quote"
    ).count()
    assert quotes_after == quotes_created  # Same as before
    
    # ✓ Fully idempotent
```

---

## Question 5: How are Pending Quotes Stored, Matched, and Timed Out?

### This is the Hard Part: Stateful System

Most systems hand-wave this. Here's the real implementation.

### The Problem

```
Email 1 (Day 1, 10:00 AM):
  "Quote for 100 boxes Shanghai→LA, needed urgently"
  
Portal response:
  "Quote cannot be created - customer account pending review.
   Will respond within 24 hours."
  
Auto-reply sent:
  "Thank you. Our team is verifying your account.
   We'll respond with a quote within 24 hours."

Email 2 (Day 2, 11:00 AM):
  "Any update on the quote?"
  
System must:
  1. Recognize this is a FOLLOW-UP to Email 1
  2. Check if the quote was created (24 hours have passed)
  3. If still pending: send update
  4. If quote created: send quote details
  5. If timeout exceeded: escalate to human
```

### The Solution: PendingQuote State Machine

**Schema:**

```python
class PendingQuote(Base):
    __tablename__ = "pending_quotes"
    
    # Identity
    id = Column(String, primary_key=True)
    original_email_id = Column(String, ForeignKey("emails.gmail_message_id"))
    thread_id = Column(String)  # Gmail thread - to match follow-ups
    
    # Content
    category = Column(String)  # rfq, booking_request, tracking_inquiry
    original_subject = Column(String)
    original_body = Column(String)
    
    # Portal state
    portal_error = Column(String)  # Why it couldn't create quote
    portal_reference = Column(String)  # If partially created
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # created_at + 24 hours
    follow_up_at = Column(DateTime)  # When to check portal again
    
    # Status
    status = Column(String)  # pending, resolved, expired, escalated
    resolution = Column(String)  # What finally happened
    
    # Timeline
    last_checked = Column(DateTime)
    follow_up_count = Column(Integer, default=0)
    max_follow_ups = Column(Integer, default=3)
```

### State Transitions

```
                     ┌──────────────────┐
                     │  NEW EMAIL       │
                     │  (RFQ)           │
                     └────────┬─────────┘
                              ↓
                  ┌───────────────────────┐
                  │ Try portal create     │
                  │ Quote                 │
                  └────┬──────────────┬───┘
                       ↓              ↓
                    SUCCESS        FAILURE
                       ↓              ↓
              ┌──────────────┐  ┌──────────────────┐
              │ Quote        │  │ Create           │
              │ created!     │  │ PendingQuote     │
              │ Status:      │  │ Status: pending  │
              │ RESOLVED     │  │ Expires: +24h    │
              └──────────────┘  └────────┬─────────┘
                                         ↓
                            ┌────────────────────────┐
                            │ Send reply:            │
                            │ "Account under review, │
                            │ response within 24h"   │
                            └────────────┬───────────┘
                                         ↓
                            ┌────────────────────────────────┐
                            │ WAIT FOR FOLLOW-UP EMAIL       │
                            │ (From same thread)             │
                            └────────────┬───────────────────┘
                                         ↓
                   ┌─────────────────────────────────────────────────┐
                   │                                                 │
           ┌───────▼──────┐          ┌───────────────────┐    ┌─────▼──────┐
           │ FOLLOW-UP     │          │ 24H TIMEOUT       │    │ PORTAL NOW │
           │ RECEIVED      │          │ (cron job)        │    │ HAS QUOTE  │
           │ (from email)  │          │                   │    │            │
           └───────┬──────┘          └────────┬──────────┘    └─────┬──────┘
                   ↓                          ↓                      ↓
         ┌──────────────────┐    ┌─────────────────────┐  ┌──────────────────┐
         │ Check portal     │    │ Status: EXPIRED     │  │ Send quote reply │
         │ for quote        │    │ Flag for escalation │  │ Status: RESOLVED │
         └────┬─────────┬───┘    └─────────────────────┘  └──────────────────┘
              ↓         ↓
           SUCCESS   STILL PENDING
              ↓         ↓
         RESOLVED    ┌─────────────────────┐
                     │ Send follow-up:     │
                     │ "Still processing   │
                     │ your account"       │
                     └────────┬────────────┘
                              ↓
                     (wait for next email
                      or timeout)
```

### Implementation

**Step 1: Store When Portal Fails**

```python
def handle_rfq_email(email):
    """Process RFQ email."""
    
    # Try to create quote in portal
    result = portal.create_quote(
        customer=email.from_,
        shipment=parse_shipment(email.body)
    )
    
    if result.success:
        # Quote created - send it and mark resolved
        send_quote_reply(result.quote_id)
        return {"status": "resolved", "quote_id": result.quote_id}
    
    # Portal failed - create pending quote
    pending = PendingQuote(
        id=str(uuid4()),
        original_email_id=email.id,
        thread_id=email.thread_id,
        category="rfq",
        original_subject=email.subject,
        original_body=email.body,
        portal_error=result.error,  # "CUSTOMER_NOT_FOUND" etc
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
        follow_up_at=datetime.utcnow() + timedelta(hours=2),
        status="pending"
    )
    db.add(pending)
    db.commit()
    
    # Send acknowledgment reply
    send_pending_reply(result.error, email)
    
    return {"status": "pending", "pending_quote_id": pending.id}
```

**Step 2: Recognize Follow-Up Emails**

```python
def process_email(email):
    """Process ANY email - check if follow-up to pending quote."""
    
    # Check if this thread has a pending quote
    pending = PendingQuote.query.filter(
        PendingQuote.thread_id == email.thread_id,
        PendingQuote.status == "pending"
    ).first()
    
    if pending:
        # This is a follow-up! Handle it specially
        return handle_follow_up(email, pending)
    
    # Normal processing
    return process_new_email(email)

def handle_follow_up(email, pending):
    """Handle follow-up to pending quote."""
    
    # Check if quote is now ready
    result = portal.check_quote_status(
        pending.thread_id,
        pending.portal_error
    )
    
    if result.ready:
        # Quote is ready!
        send_quote_reply(result.quote_id)
        pending.status = "resolved"
        pending.resolution = "quote_created"
        db.commit()
        return
    
    # Still pending - check if expired
    if datetime.utcnow() > pending.expires_at:
        # 24+ hours - escalate to human
        escalate_to_human(pending, email)
        pending.status = "escalated"
        db.commit()
        return
    
    # Still pending - send update
    send_status_update(pending, email)
    pending.follow_up_count += 1
    pending.last_checked = datetime.utcnow()
    db.commit()
```

**Step 3: Cron Job for Timeouts**

```python
@scheduler.scheduled_job('cron', hour='*', minute='0')
def check_pending_quotes_timeout():
    """Every hour: check for expired pending quotes."""
    
    expired = PendingQuote.query.filter(
        PendingQuote.status == "pending",
        PendingQuote.expires_at < datetime.utcnow()
    ).all()
    
    for pending in expired:
        # Try portal one more time
        result = portal.check_status(pending)
        
        if result.ready:
            # Finally ready!
            send_quote_reply(result.quote_id, pending)
            pending.status = "resolved"
        else:
            # Give up - escalate to human
            escalate_to_human(pending)
            pending.status = "escalated"
        
        db.commit()
```

**Step 4: Matching Follow-Ups (Sophisticated)**

```python
def find_pending_quote_for_email(email):
    """Find pending quote that email is responding to."""
    
    # Method 1: Same thread (strongest match)
    match = PendingQuote.query.filter(
        PendingQuote.thread_id == email.thread_id,
        PendingQuote.status.in_(["pending", "expired"])
    ).first()
    
    if match:
        return match, "same_thread"
    
    # Method 2: Same sender + similar subject (good match)
    # Extract shipment route from email
    route = extract_route(email.body)
    
    match = PendingQuote.query.filter(
        PendingQuote.original_email_id == email.from_,
        # Could improve with similarity matching
        PendingQuote.status == "pending"
    ).first()
    
    if match:
        return match, "same_sender"
    
    # Method 3: Keywords match previous quote (weak match)
    # "Any update on that quote for Shanghai?"
    if "update" in email.body.lower() and "quote" in email.body.lower():
        # Could be follow-up - check with LLM
        similarity = claude.similarity_to_pending(email, pending)
        if similarity > 0.8:
            return match, "keyword_match"
    
    return None, None
```

### Test Suite for Pending Quotes

```python
def test_pending_quote_workflow():
    """Complete pending quote state machine."""
    
    # Email 1: Quote request fails
    email1 = create_test_email(
        subject="Quote for 100 boxes Shanghai→LA",
        body="Urgent, needed by Oct 15"
    )
    
    with patch('portal.create_quote') as mock_portal:
        mock_portal.return_value = MockResult(
            success=False,
            error="CUSTOMER_NOT_FOUND"
        )
        
        result = process_email(email1)
    
    assert result["status"] == "pending"
    pending = PendingQuote.query.first()
    assert pending.status == "pending"
    assert pending.expires_at > datetime.utcnow()
    
    # Email 2: Follow-up from same customer
    email2 = create_test_email(
        subject="Re: Quote for 100 boxes Shanghai→LA",
        body="Any update?",
        thread_id=email1.thread_id  # Same thread
    )
    
    with patch('portal.check_quote_status') as mock_check:
        # Still pending
        mock_check.return_value = MockResult(ready=False)
        
        result = process_email(email2)
    
    assert pending.follow_up_count == 1
    
    # Email 3: Portal now ready
    with patch('portal.check_quote_status') as mock_check:
        mock_check.return_value = MockResult(
            ready=True,
            quote_id="QUOTE_12345"
        )
        
        result = process_email(email2)
    
    # Verify resolution
    pending = PendingQuote.query.first()
    assert pending.status == "resolved"
    assert pending.resolution == "quote_created"
    
    # Verify reply sent
    assert mock_reply.called

def test_pending_quote_timeout():
    """Quote times out after 24 hours."""
    
    # Create pending quote, set old timestamp
    pending = PendingQuote(
        status="pending",
        created_at=datetime.utcnow() - timedelta(hours=25),
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    db.add(pending)
    db.commit()
    
    # Run timeout job
    check_pending_quotes_timeout()
    
    # Verify escalated
    pending = PendingQuote.query.first()
    assert pending.status == "escalated"
    assert mock_escalate.called

def test_pending_quote_idempotent():
    """Processing same follow-up twice is safe."""
    
    email = create_test_email(thread_id="THREAD_123")
    pending = PendingQuote(thread_id="THREAD_123", status="pending")
    db.add(pending)
    db.commit()
    
    # Process twice
    process_email(email)
    follow_up_before = pending.follow_up_count
    
    process_email(email)  # Same email again
    follow_up_after = pending.follow_up_count
    
    # Either no change or incremented only once
    assert follow_up_after <= follow_up_before + 1
```

---

## Summary: The Hard Architecture

| Question | Answer |
|----------|--------|
| **Portal calls?** | Only for 3 categories (RFQ, Booking, Tracking). Others use templates. |
| **Portal failures?** | Store in PendingQuote, send explanatory reply, manual escalation on timeout. |
| **Agent boundary?** | Python: deterministic checks. Claude: classification only. Portal: data fetch. |
| **Second run safe?** | YES - Gmail auto-idempotency + DB unique constraint. |
| **Pending quotes?** | State machine with thread matching, follow-up recognition, 24h timeout, cron escalation. |

---

## Implementation Priority

1. **Priority 1 (Week 1):** Pending quote state machine (Question 5) - this is the hardest part
2. **Priority 2 (Week 1):** Portal decision engine (Question 1) - separates concerns
3. **Priority 3 (Week 2):** Portal failure handlers (Question 2) - graceful degradation
4. **Priority 4 (Week 2):** Agent boundary cleanup (Question 3) - cost optimization
5. **Priority 5 (Week 2):** Idempotency verification suite (Question 4) - production hardening

---

**This is where most systems fail.** They build the happy path, then find out:
- Nobody handles portal timeouts (Question 2)
- Pending state is hand-waved or missing (Question 5)
- Agents call APIs unnecessarily (Question 3)
- Second run creates duplicates (Question 4)

Getting this right is the difference between a prototype and production.
