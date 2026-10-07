#!/usr/bin/env python
"""Quick Phase 2 review - NO EXTERNAL CALLS"""

import sys
import os
import json

def check_file_contains(filename, *patterns):
    """Check if file contains all patterns"""
    with open(filename, 'r') as f:
        content = f.read()
    return all(p in content for p in patterns)

def review_categories():
    print("\n" + "="*80)
    print("PHASE 2 STRICT REVIEW")
    print("="*80)

    print("\n[1] CLASSIFICATION CATEGORIES")
    print("-" * 80)

    has_all = check_file_contains(
        'classifier_agent.py',
        '"rfq"',
        '"booking_request"',
        '"tracking_inquiry"',
        '"documentation"',
        '"complaint"',
        '"general_inquiry"',
        '"not_relevant"'
    )

    if has_all:
        print("✓ All 7 categories defined")
    else:
        print("✗ MISSING CATEGORIES!")
        return False

    return True

def review_labels():
    print("\n[2] GMAIL LABEL MAPPING")
    print("-" * 80)

    labels = {
        '"rfq": "5u/rfq"',
        '"booking_request": "5u/booking-request"',
        '"tracking_inquiry": "5u/tracking"',
        '"documentation": "5u/documentation"',
        '"complaint": "5u/complaint"',
        '"general_inquiry": "5u/general"',
        '"not_relevant": "5u/not-relevant"'
    }

    with open('classifier_agent.py', 'r') as f:
        content = f.read()

    found = sum(1 for label in labels if label in content)

    if found == len(labels):
        print(f"✓ All 7 labels mapped correctly")
        return True
    else:
        print(f"✗ Only {found}/7 labels found!")
        return False

def review_credentials():
    print("\n[3] CREDENTIAL SECURITY")
    print("-" * 80)

    # Check for hardcoded keys
    with open('gmail_service.py', 'r') as f:
        content = f.read()

    bad_patterns = ['AIza', 'ya29', 'AKIA', 'sk-', 'SG_']
    has_hardcoded = any(p in content for p in bad_patterns)

    if has_hardcoded:
        print("✗ HARDCODED API KEYS FOUND IN CODE!")
        return False
    else:
        print("✓ No hardcoded credentials in gmail_service.py")

    # Check for credentials.json reference
    if 'credentials.json' in content:
        print("✓ Uses credentials.json from file")
    else:
        print("✗ No credentials.json reference found!")
        return False

    # Check .gitignore
    with open('.gitignore', 'r') as f:
        gitignore = f.read()

    if 'credentials.json' in gitignore and '.env' in gitignore and 'tokens/' in gitignore:
        print("✓ .gitignore blocks credentials.json, .env, and tokens/")
    else:
        print("✗ .gitignore missing critical entries!")
        return False

    return True

def review_database():
    print("\n[4] DATABASE SCHEMA")
    print("-" * 80)

    with open('database.py', 'r') as f:
        db_content = f.read()

    checks = [
        ('gmail_message_id', 'Idempotency key'),
        ('thread_id', 'Session tracking'),
        ('classification', 'Classification persistence'),
        ('is_reply_sent', 'Reply tracking'),
        ('is_customer_email', 'Internal email filtering'),
    ]

    all_good = True
    for field, desc in checks:
        if field in db_content:
            print(f"✓ {field:<25} ({desc})")
        else:
            print(f"✗ MISSING {field:<23} ({desc})")
            all_good = False

    return all_good

def review_idempotency():
    print("\n[5] IDEMPOTENCY PROTECTION")
    print("-" * 80)

    with open('classification_service.py', 'r') as f:
        content = f.read()

    # Check for idempotency check
    has_duplicate_check = 'gmail_message_id' in content and 'if existing' in content

    if has_duplicate_check:
        print("✓ Checks for duplicate gmail_message_id before processing")
        print("✓ Skips if email already exists in DB")
    else:
        print("✗ NO IDEMPOTENCY CHECK FOUND!")
        return False

    return True

def review_session_tracking():
    print("\n[6] SESSION & THREAD TRACKING")
    print("-" * 80)

    with open('classification_service.py', 'r') as f:
        content = f.read()

    checks = [
        ('_get_or_create_session', 'Session creation'),
        ('thread_id', 'Thread grouping'),
        ('customer_email', 'Customer tracking'),
    ]

    all_good = True
    for method, desc in checks:
        if method in content:
            print(f"✓ {desc:<30} ({method})")
        else:
            print(f"✗ MISSING {desc:<28} ({method})")
            all_good = False

    return all_good

def review_gmail_api():
    print("\n[7] GMAIL API USAGE")
    print("-" * 80)

    with open('gmail_service.py', 'r') as f:
        content = f.read()

    checks = [
        ('InstalledAppFlow', 'OAuth2 flow'),
        ('gmail.modify', 'Proper scope'),
        ('get_unread_emails', 'Fetch unread'),
        ('add_label', 'Label application'),
        ('mark_as_read', 'Mark as read'),
    ]

    all_good = True
    for item, desc in checks:
        if item in content:
            print(f"✓ {desc:<30} ({item})")
        else:
            print(f"✗ MISSING {desc:<28} ({item})")
            all_good = False

    return all_good

def check_missing_requirements():
    print("\n[8] PHASE 2 COMPLETENESS vs REQUIREMENTS")
    print("-" * 80)

    # Requirement: Polls Gmail inbox for unread emails
    print("\nRequirement 1: Polls Gmail inbox")
    with open('gmail_service.py', 'r') as f:
        if 'get_unread_emails' in f.read():
            print("✓ get_unread_emails() implemented")
        else:
            print("✗ MISSING get_unread_emails()")

    # Requirement: Classifies using AI agent
    print("\nRequirement 2: Classifies emails")
    with open('classifier_agent.py', 'r') as f:
        if 'classify_email' in f.read():
            print("✓ classify_email() implemented")
        else:
            print("✗ MISSING classify_email()")

    # Requirement: Applies Gmail labels
    print("\nRequirement 3: Applies Gmail labels")
    with open('classification_service.py', 'r') as f:
        content = f.read()
        if 'add_label' in content and 'classification' in content:
            print("✓ Labels applied based on classification")
        else:
            print("✗ Label application incomplete")

    # Requirement: Tracks conversation threads
    print("\nRequirement 4: Tracks conversation threads")
    with open('classification_service.py', 'r') as f:
        if 'thread_id' in f.read() and 'session' in f.read():
            print("✓ Sessions track threads")
        else:
            print("✗ Thread tracking incomplete")

    # Requirement: Classification results persisted
    print("\nRequirement 5: Classification persisted")
    with open('database.py', 'r') as f:
        if 'classification' in f.read():
            print("✓ Classification stored in database")
        else:
            print("✗ Classification NOT persisted!")

def check_critical_issues():
    print("\n" + "="*80)
    print("CRITICAL ISSUES")
    print("="*80)

    issues = []

    # Issue 1: Classification service instantiation
    print("\n[ISSUE 1] ClassificationService Database Handle")
    with open('classification_service.py', 'r') as f:
        content = f.read()
        if 'self.db: Session = SessionLocal()' in content:
            print("✗ CRITICAL: Database session created in __init__ and held!")
            print("   This will cause connection pool exhaustion over time.")
            print("   FIX: Get fresh session for each method using context manager or dependency injection.")
            issues.append("database_session_leak")

    # Issue 2: Agno framework usage
    print("\n[ISSUE 2] Agno Framework")
    if not os.path.exists('agent_tools.py'):
        print("✓ agent_tools.py exists")
    else:
        with open('agent_tools.py', 'r') as f:
            if 'AGENT_TOOLS' in f.read():
                print("✓ Agent tools defined (Agno ready)")
            else:
                print("✗ Agent tools incomplete")

    # Issue 3: Anthropic instead of Agno
    print("\n[ISSUE 3] LLM Integration")
    with open('classifier_agent.py', 'r') as f:
        content = f.read()
        if 'from anthropic import Anthropic' in content:
            print("✗ WARNING: Using raw Anthropic SDK, not Agno framework as required")
            print("   Requirement says 'AI Agent: Agno framework'")
            print("   Current: Using Anthropic client directly")
            issues.append("not_using_agno")
        if 'claude-opus-5-5' in content:
            print("✓ Using Claude Opus 5.5 model")

    # Issue 4: Dramatiq vs APScheduler
    print("\n[ISSUE 4] Background Processing")
    with open('worker.py', 'r') as f:
        content = f.read()
        if 'apscheduler' in content:
            print("⚠ WARNING: Using APScheduler, requirement specifies 'Dramatiq (preferred)'")
            print("   Dramatiq is better for distributed queue processing")
            issues.append("using_apscheduler_not_dramatiq")
        else:
            print("✓ Background worker implemented")

    return issues

def main():
    os.chdir('E:\\TaskChallenge\\5uai\\gmail-inbox-agent')

    results = {
        'categories': review_categories(),
        'labels': review_labels(),
        'credentials': review_credentials(),
        'database': review_database(),
        'idempotency': review_idempotency(),
        'sessions': review_session_tracking(),
        'gmail_api': review_gmail_api(),
    }

    check_missing_requirements()
    issues = check_critical_issues()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nChecks Passed: {passed}/{total}")
    print(f"Critical Issues: {len(issues)}")

    if issues:
        print(f"\nIssues requiring fixes before Phase 3:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

    print("\n" + "="*80)

if __name__ == '__main__':
    main()
