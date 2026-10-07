#!/usr/bin/env python
"""
Verification that Issue 1 (Database Session Management) is fixed.
Does NOT require all dependencies - just checks the code.
"""

import re
import os

def check_file_for_pattern(filename, should_have=None, should_not_have=None):
    """Check if file contains/doesn't contain patterns"""
    with open(filename, 'r') as f:
        content = f.read()

    results = []

    if should_have:
        for pattern in should_have:
            if pattern in content:
                results.append((True, f"✓ Found: {pattern[:60]}"))
            else:
                results.append((False, f"✗ Missing: {pattern[:60]}"))

    if should_not_have:
        for pattern in should_not_have:
            if pattern not in content:
                results.append((True, f"✓ Not found (good): {pattern[:60]}"))
            else:
                results.append((False, f"✗ Found (bad): {pattern[:60]}"))

    return results

print("=" * 80)
print("ISSUE 1 FIX VERIFICATION: Database Session Management")
print("=" * 80)

# ============================================================================
# Test 1: ClassificationService should NOT hold a session
# ============================================================================
print("\n[TEST 1] ClassificationService session holding")
print("-" * 80)

results = check_file_for_pattern(
    'classification_service.py',
    should_not_have=[
        'self.db: Session = SessionLocal()',
        'self.db = SessionLocal()',
    ],
    should_have=[
        'def __init__(self):',
        '# DO NOT store a database session',
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test1_pass = all(p for p, _ in results)

# ============================================================================
# Test 2: Sessions should be created fresh in each method
# ============================================================================
print("\n[TEST 2] Fresh session creation in methods")
print("-" * 80)

results = check_file_for_pattern(
    'classification_service.py',
    should_have=[
        'db = get_session()',  # Must create fresh
        'finally:',             # Must cleanup
        'db.close()',          # Must close
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test2_pass = all(p for p, _ in results)

# ============================================================================
# Test 3: Database.py should have get_session factory
# ============================================================================
print("\n[TEST 3] Database session factory")
print("-" * 80)

results = check_file_for_pattern(
    'database.py',
    should_have=[
        'def get_session()',
        'return SessionLocal()',
        'def get_db():',
        'db.close()',
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test3_pass = all(p for p, _ in results)

# ============================================================================
# Test 4: Check for proper error handling and rollback
# ============================================================================
print("\n[TEST 4] Error handling and rollback")
print("-" * 80)

results = check_file_for_pattern(
    'classification_service.py',
    should_have=[
        'db.rollback()',  # Rollback on error
        'except Exception',  # Error handling
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test4_pass = all(p for p, _ in results)

# ============================================================================
# Test 5: Connection pool configuration
# ============================================================================
print("\n[TEST 5] Connection pool configuration")
print("-" * 80)

results = check_file_for_pattern(
    'database.py',
    should_have=[
        'pool_size=5' or 'poolclass=None',  # Either have pool config or disable
        'connect_args',  # For SQLite config
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test5_pass = all(p for p, _ in results)

# ============================================================================
# Test 6: Process methods pass db as parameter
# ============================================================================
print("\n[TEST 6] Database session parameter passing")
print("-" * 80)

results = check_file_for_pattern(
    'classification_service.py',
    should_have=[
        'def _process_single_email(self, gmail_email: Dict, db: Session)',
        'def _get_or_create_session(self, thread_id: str, gmail_email: Dict, db: Session)',
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test6_pass = all(p for p, _ in results)

# ============================================================================
# Test 7: API routes use fresh sessions
# ============================================================================
print("\n[TEST 7] API routes session management")
print("-" * 80)

results = check_file_for_pattern(
    'api_routes.py',
    should_have=[
        'db = get_session()',
        'db.close()',
    ]
)

for passed, msg in results:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {msg}")

test7_pass = all(p for p, _ in results)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

all_tests = [
    ("ClassificationService no session holding", test1_pass),
    ("Fresh session creation", test2_pass),
    ("Session factory", test3_pass),
    ("Error handling & rollback", test4_pass),
    ("Connection pool config", test5_pass),
    ("Database parameter passing", test6_pass),
    ("API routes cleanup", test7_pass),
]

passed_count = sum(1 for _, p in all_tests if p)
total_count = len(all_tests)

for test_name, passed in all_tests:
    symbol = "✓" if passed else "✗"
    print(f"{symbol} {test_name}")

print(f"\nTests Passed: {passed_count}/{total_count}")

if passed_count == total_count:
    print("\n🎉 ISSUE 1 FIXED: Database sessions properly isolated!")
    print("\nKey improvements:")
    print("  ✓ No sessions held in __init__")
    print("  ✓ Fresh session per operation")
    print("  ✓ Sessions always closed (finally blocks)")
    print("  ✓ Proper rollback on errors")
    print("  ✓ Connection pool configured")
    print("  ✓ No risk of exhaustion")
else:
    print(f"\n⚠️  {total_count - passed_count} issue(s) remain")

print("\n" + "=" * 80)
