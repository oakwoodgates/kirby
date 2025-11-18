# Admin User Bootstrap Guide

This guide explains how to create the first admin user and API key for Kirby.

---

## Table of Contents

- [Overview](#overview)
- [Automatic Bootstrap (Recommended)](#automatic-bootstrap-recommended)
- [Manual Bootstrap](#manual-bootstrap)
- [Command-Line Options](#command-line-options)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

---

## Overview

Kirby requires API key authentication for all endpoints except `/health`. On a fresh deployment, you need to create the first admin user and API key to access the system.

The **bootstrap script** (`scripts/bootstrap_admin.py`) automates this process by:

1. ✅ Checking if any users already exist (prevents accidental overwrites)
2. ✅ Creating an admin user with specified email/username
3. ✅ Generating a cryptographically secure API key
4. ✅ Storing the hashed key in the database
5. ✅ Displaying the plaintext key **ONCE** (you must save it immediately!)

**IMPORTANT**: The API key is only shown once during creation. It cannot be retrieved later. Save it immediately in a secure location (password manager, secrets vault, etc.).

---

## Automatic Bootstrap (Recommended)

The deployment script (`deploy.sh`) automatically runs the bootstrap script if no users exist.

### During Initial Deployment

```bash
./deploy.sh
```

**What happens:**
1. Script checks if any users exist in the database
2. If none found, automatically creates admin user with:
   - Email: `admin@localhost`
   - Username: `admin`
3. Displays the API key prominently in the terminal output
4. API key is **NOT** stored in logs (only shown in terminal)

**Example output:**

```
========================================
  🔐 ADMIN USER CREATED
========================================

📧 Email:    admin@localhost
👤 Username: admin

🔑 API KEY (SAVE THIS NOW - IT WILL NOT BE SHOWN AGAIN):

    kb_81ab3f1c028c00f81d0eb48a6d352cb8320a40a5

========================================

⚠️  IMPORTANT: Copy this API key to a secure location!
   You will need it to access the API.
```

**Copy the API key immediately!** You'll need it to access the API.

### On Subsequent Deployments

If users already exist, the bootstrap script is skipped:

```
✓ Found 3 existing user(s)
[!] Skipping admin user creation

To create additional users, use the admin API:
  curl -X POST http://localhost:8000/admin/users \
    -H 'Authorization: Bearer YOUR_API_KEY' \
    -H 'Content-Type: application/json' \
    -d '{"email": "user@example.com", "username": "user1", "is_admin": false}'
```

---

## Manual Bootstrap

You can also run the bootstrap script manually if needed.

### Inside Docker Container (Recommended)

```bash
# Using default email/username (admin@localhost / admin)
docker compose exec collector python -m scripts.bootstrap_admin

# With custom email and username
docker compose exec collector python -m scripts.bootstrap_admin \
  --email admin@mycompany.com \
  --username myadmin
```

### Outside Docker (Local Development)

```bash
# Ensure you're in the project root directory
python -m scripts.bootstrap_admin

# With custom credentials
python -m scripts.bootstrap_admin \
  --email admin@mycompany.com \
  --username myadmin
```

### Success Output

```
================================================================================
✅  ADMIN USER CREATED SUCCESSFULLY
================================================================================

📧  Email:    admin@mycompany.com
👤  Username: myadmin
🔐  Admin:    Yes

🔑  API KEY (SAVE THIS IMMEDIATELY - IT WILL NOT BE SHOWN AGAIN):

    kb_f4e3d2c1b0a9876543210fedcba9876543210fed

================================================================================

Next steps:
  1. Save the API key in a secure location (password manager)
  2. Test the API key:
     curl -H 'Authorization: Bearer kb_f4e3d2c1b0a9876543210fedcba9876543210fed' \
       https://your-server/starlistings

  3. Create additional users via admin API:
     curl -X POST https://your-server/admin/users \
       -H 'Authorization: Bearer kb_f4e3d2c1b0a9876543210fedcba9876543210fed' \
       -H 'Content-Type: application/json' \
       -d '{"email": "user@example.com", "username": "user1", "is_admin": false}'

================================================================================
```

---

## Command-Line Options

### `--email`

**Description**: Email address for the admin user
**Default**: `admin@localhost`
**Example**:
```bash
docker compose exec collector python -m scripts.bootstrap_admin \
  --email admin@mycompany.com
```

### `--username`

**Description**: Username for the admin user
**Default**: `admin`
**Example**:
```bash
docker compose exec collector python -m scripts.bootstrap_admin \
  --username myadmin
```

### `--force`

**Description**: Force creation even if users already exist
**Default**: `false`
**Warning**: ⚠️ **DANGEROUS!** This can create duplicate users or bypass safety checks.
**Use Case**: Recovery scenarios only (e.g., all existing API keys lost)

**Example**:
```bash
docker compose exec collector python -m scripts.bootstrap_admin \
  --email recovery@mycompany.com \
  --username recovery_admin \
  --force
```

### Combined Example

```bash
docker compose exec collector python -m scripts.bootstrap_admin \
  --email admin@production.com \
  --username prod_admin
```

---

## Security Considerations

### API Key Generation

- **Algorithm**: Uses Python's `secrets.token_hex(20)` for cryptographically secure random number generation
- **Format**: `kb_` prefix + 40 hexadecimal characters (160 bits of entropy)
- **Storage**: SHA-256 hashed before storage in database
- **Display**: Only prefix (`kb_xxxxxxx`) shown in database queries

### Best Practices

1. **Save Immediately**: API key is shown only once - save it to a password manager immediately
2. **Secure Storage**: Store in environment variables, secrets vault, or password manager (NOT in code or version control)
3. **Rotation**: Create new API keys periodically and revoke old ones
4. **Least Privilege**: Create non-admin users for day-to-day operations (use admin only when necessary)
5. **Monitoring**: Track API key usage via `last_used_at` timestamp

### What's Stored in Database

| Field | Value | Purpose |
|-------|-------|---------|
| `key_hash` | SHA-256 hash | For authentication verification |
| `key_prefix` | `kb_xxxxxxx` (first 10 chars) | For identification in UI/logs |
| `is_active` | `true` | Enable/disable key without deletion |
| `rate_limit` | `10000` | Requests per time window (admin default) |
| `expires_at` | `null` | Optional expiration date |
| `last_used_at` | Timestamp | Track key usage |

**The plaintext API key is NEVER stored in the database.**

---

## Troubleshooting

### Error: "Database already has X user(s)"

**Cause**: Users already exist in the database
**Solution**:
- If you lost your API key, create a new one via admin API (if you have another admin key)
- If completely locked out, use `--force` flag (last resort)
- For production, consider manual database access to create API key

### Error: "Email 'admin@localhost' already exists"

**Cause**: Email already in use
**Solution**: Use `--email` flag with a different email address

### Error: "Username 'admin' already exists"

**Cause**: Username already in use
**Solution**: Use `--username` flag with a different username

### Error: "Could not connect to database"

**Cause**: Database not running or connection misconfigured
**Solution**:
1. Check database is running: `docker compose ps timescaledb`
2. Verify `.env` file has correct `DATABASE_URL`
3. Ensure database migrations have run: `docker compose exec collector alembic upgrade head`

### Lost All API Keys

If you've lost all API keys and are completely locked out:

**Option 1: Create New Admin Key (via bootstrap with force)**
```bash
docker compose exec collector python -m scripts.bootstrap_admin \
  --email recovery@localhost \
  --username recovery \
  --force
```

**Option 2: Manual Database Access**
```bash
# Connect to database
docker compose exec timescaledb psql -U kirby -d kirby

# Generate hash for new key (use Python to generate kb_xxx key and SHA-256 hash)
# Then insert manually:
INSERT INTO api_keys (user_id, key_hash, key_prefix, name, is_active, rate_limit)
VALUES (1, 'YOUR_SHA256_HASH', 'kb_xxxxxxx', 'Recovery Key', true, 10000);
```

---

## Creating Additional Users

After bootstrap, create additional users via the admin API:

### Create Regular User

```bash
curl -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer kb_YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "user1",
    "is_admin": false
  }'
```

### Create Additional Admin User

```bash
curl -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer kb_YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin2@example.com",
    "username": "admin2",
    "is_admin": true
  }'
```

### Create API Key for User

```bash
# Get user ID first
curl http://localhost:8000/admin/users \
  -H "Authorization: Bearer kb_YOUR_ADMIN_KEY"

# Create API key for user (replace USER_ID)
curl -X POST http://localhost:8000/admin/users/USER_ID/keys \
  -H "Authorization: Bearer kb_YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "rate_limit": 1000
  }'
```

**Response includes the plaintext API key** (only shown once):
```json
{
  "id": 2,
  "user_id": 5,
  "key_prefix": "kb_a1b2c3d4",
  "name": "Production Key",
  "is_active": true,
  "rate_limit": 1000,
  "created_at": "2025-11-17T10:30:00Z",
  "key": "kb_a1b2c3d4e5f6789012345678901234567890abcd"
}
```

---

## See Also

- [README.md](../README.md) - Main project documentation
- [DEPLOYMENT.md](../DEPLOYMENT.md) - Production deployment guide
- [docs/API_AUTHENTICATION.md](API_AUTHENTICATION.md) - API authentication reference

---

**Last Updated**: November 17, 2025
