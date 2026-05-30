# Security Guidelines

## ⚠️ Never Commit These Files

The following files contain sensitive credentials and must **NEVER** be committed to version control:

### API Keys & Credentials
- ✗ `auradev/.env` - Contains `ANTHROPIC_API_KEY`
- ✗ `gcp-service-account.json` - GCP service account private key
- ✗ Any `*-key.json` files
- ✗ `client_secret*.json` - OAuth client secrets
- ✗ Any `.env` files (except `.env.example`)

### Session Data
- ✗ `session.log` - May contain sensitive telemetry
- ✗ `*.db` files - Database with user activity
- ✗ `auradev_sessions.db`

### Temporary Files
- ✗ `*.wav`, `*.mp3` - Generated audio files
- ✗ `audio_cache/` directory
- ✗ `__pycache__/` directories

## ✅ What You CAN Commit

- ✓ `.env.example` - Template with placeholder values
- ✓ `README.md`, documentation
- ✓ Source code (`.py` files)
- ✓ Requirements files
- ✓ Test files (as long as they use env vars, not hardcoded secrets)

## Pre-Commit Checklist

Before running `git commit`:

1. **Check status**: `git status` - Look for any `.env`, `.json`, or `.log` files
2. **Check diff**: `git diff --cached` - Make sure no API keys are visible
3. **Search for secrets**: 
   ```bash
   git diff --cached | grep -i "api_key\|secret\|private_key\|password"
   ```
4. **Verify .gitignore**: Ensure `.gitignore` is up to date

## If You Accidentally Commit a Secret

1. **DO NOT** just delete the file and commit again - it's still in git history
2. **Immediately rotate the exposed credential** (regenerate API key, delete service account)
3. Remove from git history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/secret/file" \
     --prune-empty --tag-name-filter cat -- --all
   ```
4. Force push (if already pushed): `git push --force`
5. Notify your team if the repo is shared

## Current Protected Files

These are currently in `.gitignore`:

```
.env
auradev/.env
*service-account*.json
gcp-*.json
client_secret*.json
*.log
*.db
*.wav
__pycache__/
```

## Environment Variables

Always use environment variables for secrets:

```python
# ✓ Good
api_key = os.getenv("ANTHROPIC_API_KEY")

# ✗ Bad - NEVER hardcode
api_key = "sk-ant-api03-..."
```

## GCP Service Account Security

- Store JSON key outside the repo or in `.gitignore`
- Use least-privilege IAM roles (only "Vertex AI User", not "Owner")
- Rotate keys every 90 days
- Never commit `GOOGLE_APPLICATION_CREDENTIALS` path with actual key content
- Use Application Default Credentials when possible (`gcloud auth application-default login`)
