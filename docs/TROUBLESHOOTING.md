# Troubleshooting Guide

## Docker Image Staleness Issue

### Problem: Code Changes Not Reflected After Rebuild

**Symptoms:**
- You've updated code and run `docker compose build`, but changes aren't reflected
- Tests that should pass are still failing with old behavior
- Debug logging you added doesn't appear in output

### Root Cause:

Docker uses layer caching for faster builds. When you run `docker compose build`, it may use cached layers from a previous build, especially if the Dockerfile itself hasn't changed.

### Diagnostic Command:

**The key command that identified our issue:**

```bash
docker images | grep kirby-collector
```

**Example Output:**
```
kirby-collector            latest   a30312e4bd1a   2 hours ago   1.28GB
kirby-collector-training   latest   24dcc936d58d   9 hours ago   913MB
```

**What to look for:**
- Check the "CREATED" timestamp column
- If your image is hours/days old but you just made code changes, **the build used cached layers**
- Different services (`collector` vs `collector-training`) may have different timestamps

### Solution 1: Force Rebuild Without Cache

```bash
# For specific service
docker compose build --no-cache collector

# With profiles (for optional services)
docker compose --profile vpn --profile tools build --no-cache collector-training

# Or rebuild everything
docker compose build --no-cache
```

### Solution 2: Rebuild and Verify

```bash
# Rebuild
docker compose build collector-training

# Immediately verify the timestamp
docker images | grep kirby-collector-training

# Should show "X seconds ago" or "X minutes ago"
```

### Real-World Example:

During Binance `num_trades` debugging:

1. **Problem**: Backfills ran without errors but `num_trades` was NULL in database
2. **Investigation**: Added extensive debug logging to `scripts/backfill.py`
3. **Expectation**: Debug messages should appear in backfill output
4. **Reality**: No debug messages appeared - old code was running
5. **Discovery**: Ran `docker images | grep kirby-collector`
   - `kirby-collector`: 13 minutes ago ✅
   - `kirby-collector-training`: **9 hours ago** ❌
6. **Root Cause**: `collector-training` image was from before python-binance was added to `pyproject.toml`
7. **Fix**: `docker compose --profile vpn --profile tools build --no-cache collector-training`
8. **Verification**: Image timestamp showed "28 seconds ago"
9. **Result**: Debug logging appeared, num_trades populated correctly

### Prevention:

**After updating dependencies in `pyproject.toml`:**
```bash
# Always force rebuild to ensure pip installs new packages
docker compose build --no-cache
```

**After code changes in `src/` or `scripts/`:**
```bash
# Regular rebuild usually works, but verify timestamp
docker compose build
docker images | grep kirby-
```

**Before running critical tests:**
```bash
# Quick verification that images are fresh
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}" | grep kirby
```

### Related Issues:

**Issue: "Module not found" after adding dependency**
- Check: `docker images` timestamp
- Cause: Using old image without new dependency
- Fix: `docker compose build --no-cache`

**Issue: Changes to environment variables not reflected**
- Check: Image timestamp AND container restart
- Fix: `docker compose up -d --force-recreate`

**Issue: Different behavior on local vs production**
- Check: Git commit hash and image timestamps match
- Fix: Ensure production has latest code and rebuilt images

### Debugging Checklist:

When code changes don't take effect:

- [ ] Check git: `git log --oneline -3` (verify commit is latest)
- [ ] Check image timestamp: `docker images | grep <service-name>`
- [ ] Check if image is older than code changes
- [ ] Force rebuild: `docker compose build --no-cache <service>`
- [ ] Verify new timestamp: `docker images | grep <service-name>`
- [ ] Restart containers: `docker compose restart <service>`
- [ ] Test again and verify behavior changed

### Pro Tips:

1. **Always check image timestamps** when debugging unexpected behavior
2. **Use `--no-cache`** after dependency changes (`pyproject.toml`, `package.json`, etc.)
3. **Tag images with git commit hash** for production deployments
4. **Document the build date** in your deployment logs
5. **Automate image timestamp checks** in CI/CD pipelines

---

## Other Common Issues

### VPN Connection Issues

**Symptoms:**
- "Service unavailable from a restricted location" when accessing Binance
- Geo-blocking errors from exchange APIs

**Solution:**
```bash
# Check VPN status
docker compose logs vpn | grep "You are connected"

# Verify VPN IP
docker compose exec vpn curl -s https://ipinfo.io/json | grep country

# Restart VPN
docker compose restart vpn
sleep 30
```

See [docs/NORDVPN_SETUP.md](NORDVPN_SETUP.md) for full VPN configuration.

### Database Connection Errors

**Symptoms:**
- "relation does not exist"
- "could not connect to server"

**Solutions:**
```bash
# Check if database is running
docker compose ps timescaledb

# Check database logs
docker compose logs timescaledb | tail -50

# Verify migrations ran
docker compose exec collector alembic current

# Run migrations if needed
docker compose exec collector alembic upgrade head
```

### Import Errors

**Symptoms:**
- `ModuleNotFoundError: No module named 'X'`
- After adding new dependency

**Solution:**
```bash
# Rebuild with --no-cache to install new dependencies
docker compose build --no-cache

# Verify package installed in container
docker compose exec collector pip list | grep <package-name>
```

---

**Last Updated:** November 5, 2025
**Contributed By:** Debugging session that solved Binance num_trades issue
