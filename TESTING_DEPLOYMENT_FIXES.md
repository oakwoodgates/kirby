# Testing Deployment Fixes

## Summary of Changes

### Files Modified

1. **[deploy.sh](deploy.sh)**
   - Fixed training database migration approach
   - Now uses `scripts/migrate_training_db.py` instead of shell variable expansion
   - Added final verification step using `scripts/verify_deployment.py`
   - Fully idempotent - safe to run multiple times

2. **[scripts/migrate_training_db.py](scripts/migrate_training_db.py)** (NEW FILE)
   - Python script to run Alembic migrations on training database
   - Uses Settings to get TRAINING_DATABASE_URL from environment
   - Converts asyncpg URL to psycopg2 format for Alembic
   - Proper error handling and logging

3. **[DEPLOYMENT.md](DEPLOYMENT.md)**
   - **Section 5**: Completely rewritten to use `./deploy.sh` as PRIMARY method
   - Manual steps moved to collapsible "Advanced" section
   - Clear explanation of what deploy.sh does
   - **Section 7.6**: Simplified to emphasize deploy.sh for updates too
   - Added rollback instructions
   - Removed confusing manual steps that caused issues

4. **[CLAUDE.md](CLAUDE.md)**
   - Updated Deployment section to reflect both databases
   - Updated Essential Commands to include training database commands
   - Added verification steps for both databases

### What Was Fixed

**Problem**: DEPLOYMENT.md Section 5 documented manual steps that ONLY set up production database. Users following the guide would NOT get training database (kirby_training).

**Solution**:
- Made `./deploy.sh` the PRIMARY deployment method for both fresh deploys and updates
- deploy.sh now automatically sets up BOTH databases
- Manual steps are now in an "Advanced" collapsible section
- deploy.sh is idempotent (safe to run multiple times)

---

## Testing Plan

### Step 1: Commit and Push Changes

On your **local Windows machine**, commit these changes:

```bash
cd c:\Users\funky\sites\oakwoodgates\trading\platform\kirby

git add deploy.sh
git add scripts/migrate_training_db.py
git add DEPLOYMENT.md
git add CLAUDE.md
git add TESTING_DEPLOYMENT_FIXES.md

git commit -m "Fix deployment process to create both databases automatically

- Add migrate_training_db.py script for reliable training DB migrations
- Update deploy.sh to use new migration script and add verification
- Rewrite DEPLOYMENT.md Section 5 to use deploy.sh as primary method
- Update CLAUDE.md with correct deployment information
- Make deployment idempotent and fully automated"

git push origin main
```

### Step 2: Test on Digital Ocean Server

SSH to your Digital Ocean server:

```bash
ssh kirby@YOUR_SERVER_IP
cd ~/kirby
```

#### Test 2a: Verify Current State

```bash
# Check current databases
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 8

docker compose exec timescaledb psql -U kirby -d kirby_training -c "SELECT COUNT(*) FROM starlistings;" 2>&1
# May fail if database doesn't exist yet - that's OK
```

#### Test 2b: Pull Latest Changes

```bash
git pull origin main
```

#### Test 2c: Run Deployment Script

```bash
chmod +x deploy.sh
./deploy.sh
```

**Watch for these checkmarks:**
- [✓] .env file already exists (won't overwrite)
- [✓] Docker is installed
- [✓] Docker Compose is installed
- [✓] Docker images built
- [✓] Services started
- [✓] Database is ready
- [✓] Production migrations completed
- [✓] Production configuration synced
- [✓] Production starlistings: 8
- [✓] Training database created (or already exists)
- [✓] TimescaleDB extension enabled
- [✓] Training migrations completed
- [✓] Training configuration synced
- [✓] Training starlistings: 24
- [✓] API is healthy
- **[✓] Final Verification** (NEW - this is the key part)
  - [✓] Production database verified (8 starlistings)
  - [✓] Training database verified (24 starlistings)

#### Test 2d: Manual Verification

After deploy.sh completes successfully:

```bash
# Check production database
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 8 starlistings

# Check training database
docker compose exec timescaledb psql -U kirby -d kirby_training -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 24 starlistings

# Check services are running
docker compose ps
# All services should be "Up" and healthy

# Check API
curl http://localhost:8000/health
# Should return {"status":"healthy",...}

# Check collector logs
docker compose logs --tail=50 collector
# Should show WebSocket connections and data collection
```

#### Test 2e: pgAdmin Verification

Access pgAdmin via SSH tunnel:

```bash
# On your local machine (new terminal)
ssh -L 5050:localhost:5050 kirby@YOUR_SERVER_IP
```

Then open http://localhost:5050 in your browser and verify:
- Production database (kirby) shows 8 starlistings
- Training database (kirby_training) shows 24 starlistings

---

## Expected Results

### Success Criteria

✅ **deploy.sh runs without errors**
✅ **Production database (kirby):**
- 8 starlistings
- Tables: candles, funding_rates, open_interest, starlistings, exchanges, coins, quote_currencies, market_types, intervals

✅ **Training database (kirby_training):**
- 24 starlistings
- Same tables as production

✅ **Services running:**
- kirby-timescaledb (healthy)
- kirby-collector (running)
- kirby-api (running)
- kirby-pgadmin (running)

✅ **API responding:**
- http://localhost:8000/health returns healthy status

✅ **Collector working:**
- Logs show WebSocket connections
- Real-time data being collected

---

## Troubleshooting

### Issue: Training database not created

**Check:**
```bash
docker compose logs collector | grep "Training"
```

**If you see errors**, run manually:
```bash
docker compose exec timescaledb psql -U kirby -c "CREATE DATABASE kirby_training;"
docker compose exec timescaledb psql -U kirby -d kirby_training -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
docker compose exec collector python -m scripts.migrate_training_db
docker compose exec collector python -m scripts.sync_training_config
```

### Issue: Migration script not found

**Check:**
```bash
docker compose exec collector ls -la scripts/migrate_training_db.py
```

**If missing**, make sure you pushed the file and pulled on server:
```bash
git status
git pull origin main
docker compose restart collector
```

### Issue: Password authentication failed

**Check .env file has POSTGRES_PASSWORD set:**
```bash
cat .env | grep POSTGRES_PASSWORD
```

**Restart services if password was changed:**
```bash
docker compose restart collector api
```

---

## Rollback Plan

If deployment fails:

```bash
# Option 1: Try again (deploy.sh is idempotent)
./deploy.sh

# Option 2: Rollback to previous commit
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>
docker compose down
docker compose up -d --build

# Option 3: Nuclear option (resets everything)
docker compose down -v
git pull origin main
./deploy.sh
```

---

## Next Steps After Successful Testing

Once you confirm everything works:

1. **Document the success** - Let me know the results
2. **Backfill training data** (optional):
   ```bash
   docker compose exec collector python -m scripts.backfill_training --coin=BTC --days=7
   ```
3. **Monitor for 24 hours** - Check logs and database growth
4. **Update any external documentation** - Share the successful deployment with your team

---

## Questions to Answer After Testing

1. Did deploy.sh run without errors?
2. Does kirby_training database exist with 24 starlistings?
3. Are both production and training collectors running?
4. Can you see both databases in pgAdmin?
5. Is the API returning healthy status?

Please report back with answers to these questions and any error messages you encounter.
