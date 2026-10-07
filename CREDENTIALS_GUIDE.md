# Safe Credentials Management - NEVER Commit Real Keys

**Golden Rule:** Never put real credentials anywhere that could be committed to git.

---

## Setup (Do This Once)

### Step 1: Create `.env` File (LOCAL ONLY - Not in Git)

```bash
# In gmail-inbox-agent directory, create .env file
# This file is IGNORED by git (see .gitignore)
```

**File: `.env` (create locally, NEVER commit)**
```
# Anthropic API Key - DO NOT commit this file!
ANTHROPIC_API_KEY=sk-ant-YOUR_REAL_KEY_HERE

# Gmail OAuth2 - DO NOT commit this file!
GMAIL_CLIENT_ID=YOUR_REAL_CLIENT_ID.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=YOUR_REAL_CLIENT_SECRET

# Portal API - DO NOT commit this file!
PORTAL_BASE_URL=https://portal.example.com
PORTAL_API_KEY=your_portal_key_here

# Service Config
DATABASE_URL=sqlite:///./inbox_automation.db
DRY_RUN=true
```

---

## Option 1: Use a TEST Gmail Account (Recommended)

### Create Separate Gmail Account for Testing

1. **Create new Gmail account** (don't use your real account)
   - Go to https://accounts.google.com/signup
   - Use a test email: `your-name+test@gmail.com`
   - This keeps testing separate from your real inbox

2. **Get OAuth2 credentials for TEST account**
   - Go to https://console.cloud.google.com
   - Create new project: "Gmail Inbox Automation Test"
   - Enable Gmail API
   - Create OAuth2 credentials (Desktop app)
   - Download credentials → save as `credentials.json`
   - Put in `.env` file, NOT in repository

3. **Why this works:**
   - ✅ Test account only receives test emails
   - ✅ Real Gmail account never touched
   - ✅ Safe to experiment
   - ✅ Can delete test account anytime

---

## Option 2: Use Environment Variables (Most Secure)

### Set Environment Variables Temporarily

**PowerShell (Windows):**
```powershell
# Set temporarily (only for this session)
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
$env:GMAIL_CLIENT_ID="YOUR_CLIENT_ID"
$env:GMAIL_CLIENT_SECRET="YOUR_CLIENT_SECRET"

# Run the app
python -m uvicorn main:app --reload

# Unset when done
Remove-Item env:ANTHROPIC_API_KEY
```

**Bash/Linux/Mac:**
```bash
# Set temporarily
export ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
export GMAIL_CLIENT_ID="YOUR_CLIENT_ID"
export GMAIL_CLIENT_SECRET="YOUR_CLIENT_SECRET"

# Run the app
python -m uvicorn main:app --reload

# Unset when done
unset ANTHROPIC_API_KEY
```

---

## Recommended Approach (Safest)

### 1. Create Test Gmail Account
```
DO create: test-email+automation@gmail.com
DON'T use: your-real-email@gmail.com
```

### 2. Create `.env` File Locally
```
Location: gmail-inbox-agent/.env (local only)
Contents: Your test account credentials
Permissions: Never commit to git
```

### 3. Verify `.gitignore` Blocks It
```bash
# Check that .gitignore has these entries
grep -E "\.env|credentials|tokens" .gitignore

# Should output:
# .env
# credentials.json
# tokens/
```

### 4. Run Tests (With Mocks, No Real Credentials Needed)
```bash
# These tests run WITHOUT any credentials
pytest test_immediate.py -v

# These work because they use MockGmailService and MockClassifier
# No real Gmail or API calls
```

### 5. Run App (Requires .env File)
```bash
# Only when you want to use real Gmail
# Make sure .env is in place first
python -m uvicorn main:app --reload
```

---

## Credential Files - What Goes Where

### ✅ Safe Locations (Local Only, Ignored by Git)

```
gmail-inbox-agent/
├── .env                              ← Local credentials (IGNORED by git)
├── credentials.json                  ← OAuth2 file (IGNORED by git)
├── tokens/
│   └── gmail_token.json             ← Token cache (IGNORED by git)
```

### ❌ NEVER Commit These

- `.env` — Contains API keys
- `credentials.json` — OAuth2 secrets
- `credentials-desktop.json` — OAuth2 secrets
- `tokens/` directory — Contains cached tokens
- `.env.local`, `.env.*.local` — Any env file variant

---

## Verification: Nothing Committed

### Check Git Status
```bash
# See what would be committed
git status

# Should NOT show:
# - .env
# - credentials.json
# - tokens/
# - *.db

# If they appear in red, they're not ignored properly!
```

### Verify .gitignore
```bash
# Check if file is ignored
git check-ignore -v .env
# Should output: .env   <path-to-.gitignore>

git check-ignore -v credentials.json
# Should output: credentials.json   <path-to-.gitignore>
```

### Never Accidentally Commit
```bash
# Before committing, ALWAYS run:
git status

# Look for these files - if present, FIX IT:
# - .env
# - credentials.json
# - tokens/
# - *.db

# If any appear, don't commit!
```

---

## API Keys - Where to Get Them

### Anthropic API Key
1. Go to https://console.anthropic.com
2. Create account or log in
3. Go to API Keys section
4. Create new API key
5. Copy it: `sk-ant-...`
6. Put ONLY in `.env` file (locally)

**Format in .env:**
```
ANTHROPIC_API_KEY=sk-ant-YOUR_ACTUAL_KEY_HERE
```

### Gmail OAuth2
1. Go to https://console.cloud.google.com
2. Create new project
3. Enable Gmail API
4. Create OAuth2 credentials (Desktop app)
5. Download credentials.json
6. Keep in project folder (ignored by git)

**File: `credentials.json` (local only)**
```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    ...
  }
}
```

### Portal API Key (if you have one)
```
PORTAL_BASE_URL=https://your-portal.com
PORTAL_API_KEY=your_portal_key_here
```

---

## Testing WITHOUT Any Credentials

The test infrastructure is designed so you **don't need credentials** for testing:

```python
# These work WITHOUT .env file:
from test_fixtures import get_mock_gmail_service, get_mock_classifier

def test_classification():
    gmail = get_mock_gmail_service()  # Mock, no Gmail needed
    classifier = get_mock_classifier()  # Mock, no Claude needed
    
    emails = gmail.get_unread_emails()  # Returns sample data
    # ... test flows without any real credentials
```

**To run tests:**
```bash
pytest test_immediate.py -v
# No credentials needed!
```

---

## Checklist: Credentials Setup

- [ ] Created test Gmail account (test-account@gmail.com)
- [ ] Created `.env` file locally (NOT in git)
- [ ] Put Anthropic API key in `.env`
- [ ] Put Gmail credentials in `.env` or `credentials.json`
- [ ] Verified `.gitignore` blocks `.env` and `credentials.json`
- [ ] Tested: `git check-ignore -v .env` returns a path
- [ ] Tests pass without `.env`: `pytest test_immediate.py -v`
- [ ] App starts with `.env` in place: `python -m uvicorn main:app --reload`
- [ ] Verified: No credentials in git history: `git log --all --full-history -- .env`

---

## Recovery: If Credentials Accidentally Committed

⚠️ **If you ever commit credentials by mistake:**

1. **REVOKE THE KEY IMMEDIATELY**
   - https://console.anthropic.com → Revoke API key
   - https://console.cloud.google.com → Disable OAuth2 credentials
   
2. **Remove from Git history** (irreversible!)
   ```bash
   git filter-branch --tree-filter 'rm -f .env credentials.json' HEAD
   git push --force-all
   ```

3. **Generate new credentials**
   - Create new API keys
   - Update `.env` locally

---

## Summary

**SAFE APPROACH:**
1. ✅ Create test Gmail account (separate from your real account)
2. ✅ Create `.env` file locally (add to `.gitignore`)
3. ✅ Put credentials ONLY in `.env`
4. ✅ Never commit `.env`
5. ✅ Verify with `git check-ignore -v .env`
6. ✅ Use mocks for testing (no credentials needed)
7. ✅ Use real credentials only for integration testing

**NEVER:**
- ❌ Hardcode API keys in Python files
- ❌ Commit `.env` to git
- ❌ Use real Gmail account for testing
- ❌ Put credentials in `.env.example`
- ❌ Share credentials in chat, email, or messages

---

**Status:** Ready to use credentials safely  
**Test account:** Recommended (separate from real Gmail)  
**Credentials storage:** `.env` file (local only, ignored by git)  

You're all set! Your real Gmail is safe, and your API keys are secure. 🔒
