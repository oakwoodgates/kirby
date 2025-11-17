# Exports Directory Troubleshooting Guide

## Issue Summary

Export scripts may fail on Digital Ocean deployments due to missing or incorrectly configured `exports` directory.

## Root Cause

The `exports` directory is in `.gitignore` (to avoid committing large export files), and the deployment script (`deploy.sh`) wasn't creating it with proper permissions on new deployments.

## Fixes Applied

### 1. Updated `deploy.sh` ✅

Added exports directory creation with proper permissions:
```bash
mkdir -p logs backups exports
chmod 755 exports
```

### 2. Created Diagnostic Script ✅

New script to troubleshoot exports directory issues: `scripts/check_exports.py`

---

## How to Fix Existing Digital Ocean Deployment

If you've already deployed to Digital Ocean and exports aren't working, follow these steps:

### Option A: Re-run Deploy Script (Recommended)

```bash
# SSH to your Digital Ocean droplet
ssh your-user@your-server-ip

# Navigate to kirby directory
cd ~/kirby

# Pull latest changes (includes deploy.sh fix)
git pull

# Re-run deployment (will create exports directory)
./deploy.sh
```

### Option B: Manual Fix

If you don't want to re-run the full deployment:

```bash
# SSH to your Digital Ocean droplet
ssh your-user@your-server-ip

# Navigate to kirby directory
cd ~/kirby

# Create exports directory if it doesn't exist
mkdir -p exports

# Set proper permissions
chmod 755 exports

# Restart collector to pick up the mount
docker compose restart collector
```

---

## Verify Exports Directory is Working

### 1. Run Diagnostic Script

```bash
# On Digital Ocean
docker compose exec collector python -m scripts.check_exports

# Expected output: "✅ All checks passed!"
```

### 2. Test Export Command

```bash
# Try a small export (last 1 day)
docker compose exec collector python -m scripts.export_candles \
  --coin=BTC \
  --quote=USDT \
  --database=training \
  --market-type=perps \
  --intervals=1m \
  --days=1 \
  --format=parquet

# Check if files were created
ls -lh exports/
```

### 3. Check Docker Volume Mount

```bash
# Verify collector container has the volume mounted
docker compose exec collector ls -la /app/exports

# Should show the exports directory contents
```

---

## Common Issues and Solutions

### Issue 1: Permission Denied

**Error**: `PermissionError: [Errno 13] Permission denied: '/app/exports/...'`

**Solution**:
```bash
# On host (Digital Ocean)
chmod 755 exports

# If still failing, try:
sudo chown -R 1000:1000 exports  # 1000 is the kirby user UID in Docker
```

### Issue 2: Directory Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: '/app/exports'`

**Solution**: Volume mount not working. Check docker-compose.yml has:
```yaml
collector:
  volumes:
    - ./exports:/app/exports
```

Then restart:
```bash
docker compose restart collector
```

### Issue 3: Exports Created but Can't Access from Host

**Problem**: Files created in `/app/exports` inside container, but not visible on host in `./exports`

**Cause**: Bind mount not configured correctly

**Solution**:
```bash
# Stop container
docker compose stop collector

# Verify volume configuration in docker-compose.yml
cat docker-compose.yml | grep -A2 "volumes:"

# Should see: - ./exports:/app/exports

# Restart with fresh mount
docker compose up -d collector
```

### Issue 4: SELinux/AppArmor Blocking Mounts

**Error**: Permission denied even with correct permissions

**Solution** (if using SELinux):
```bash
# Check SELinux status
sestatus

# Add SELinux label to exports directory
sudo chcon -Rt svirt_sandbox_file_t exports/

# Or disable SELinux (not recommended for production)
sudo setenforce 0
```

---

## Understanding the Exports Setup

### Directory Structure

```
kirby/
├── exports/                # Host directory (bind mounted)
│   ├── .gitkeep           # Preserves directory in git
│   ├── .gitignore         # Ignores export files
│   ├── README.md          # Documentation
│   └── *.csv/*.parquet    # Exported data files (ignored by git)
```

### Docker Volume Mount

From `docker-compose.yml`:
```yaml
collector:
  volumes:
    - ./exports:/app/exports  # Host:Container mapping
```

- **Host path**: `./exports` (relative to docker-compose.yml)
- **Container path**: `/app/exports` (inside collector container)
- **Type**: Bind mount (directory from host is mounted into container)

### How It Works

1. Export script runs inside container
2. Writes files to `/app/exports` (container path)
3. Files appear in `./exports` (host path) due to bind mount
4. Files persist on host even if container is removed

### Why .gitignore?

Export files can be **very large** (100s of MB to GBs). The `.gitignore` prevents:
- Bloating the git repository
- Slow git operations
- Accidental commits of large data files

But `.gitkeep` ensures the directory structure is preserved in git.

---

## Diagnostic Checklist

Run through this checklist on Digital Ocean:

- [ ] Exports directory exists: `ls -ld exports`
- [ ] Proper permissions: `ls -ld exports` (should show `drwxr-xr-x`)
- [ ] Docker volume mounted: `docker compose exec collector ls -la /app/exports`
- [ ] Can create files: `docker compose exec collector python -m scripts.check_exports`
- [ ] Test export works: Run small export command
- [ ] Files visible on host: `ls -lh exports/`

---

## Prevention for Future Deployments

The `deploy.sh` script now **automatically**:
1. Creates `exports` directory
2. Sets correct permissions (755)
3. Verifies it before starting services

**No manual intervention needed for new deployments!**

---

## Need More Help?

If exports still aren't working after following this guide:

1. Run the diagnostic script and share output:
   ```bash
   docker compose exec collector python -m scripts.check_exports > exports_diagnostic.txt
   cat exports_diagnostic.txt
   ```

2. Check Docker logs:
   ```bash
   docker compose logs collector | grep -i export
   ```

3. Verify mount in container:
   ```bash
   docker compose exec collector mount | grep exports
   ```

4. Check file system type (some FS don't support bind mounts):
   ```bash
   df -Th exports/
   ```

Share the output of these commands for further troubleshooting.
