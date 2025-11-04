# Kirby - Digital Ocean Deployment Guide

This guide will walk you through deploying Kirby to Digital Ocean using Docker Compose.

## Table of Contents
- [Prerequisites](#prerequisites)
- [1. Create Digital Ocean Droplet](#1-create-digital-ocean-droplet)
- [2. Initial Server Setup](#2-initial-server-setup)
- [3. Install Docker](#3-install-docker)
- [4. Deploy Kirby](#4-deploy-kirby)
- [5. Configure and Start Services](#5-configure-and-start-services)
- [6. Verify Deployment](#6-verify-deployment)
- [7. Monitoring and Maintenance](#7-monitoring-and-maintenance)
- [8. Security Hardening](#8-security-hardening)
- [9. Troubleshooting](#9-troubleshooting)

---

## Prerequisites

- Digital Ocean account
- SSH key pair (or ability to create one)
- Domain name (optional, for production use)
- Basic command line knowledge

---

## 1. Create Digital Ocean Droplet

### Step 1.1: Create Droplet

1. Log into Digital Ocean: https://cloud.digitalocean.com
2. Click **Create** → **Droplets**
3. Choose configuration:
   - **Image**: Ubuntu 24.04 (LTS) x64
   - **Droplet Size**:
     - Minimum: Basic - $12/mo (2 GB RAM, 1 vCPU, 50 GB SSD)
     - Recommended: Basic - $18/mo (2 GB RAM, 2 vCPU, 60 GB SSD)
     - Production: Basic - $24/mo (4 GB RAM, 2 vCPU, 80 GB SSD)
   - **Datacenter**: Choose closest to your target market (e.g., New York for US markets)
   - **Authentication**: SSH keys (recommended) or Password
   - **Hostname**: `kirby-collector` (or your choice)
   - **Tags**: `kirby`, `production`, `crypto`

4. Click **Create Droplet**

### Step 1.2: Note Your Droplet IP

Once created, note your droplet's public IP address:
```
Droplet IP: xxx.xxx.xxx.xxx
```

---

## 2. Initial Server Setup

### Step 2.1: Connect via SSH

```bash
ssh root@YOUR_DROPLET_IP
```

### Step 2.2: Update System

```bash
apt update && apt upgrade -y
```

### Step 2.3: Set Timezone (Optional)

```bash
timedatectl set-timezone America/New_York  # Or your preferred timezone
timedatectl
```

### Step 2.4: Create Non-Root User (Recommended)

```bash
# Create user
adduser kirby

# Add to sudo group
usermod -aG sudo kirby

# Copy SSH keys (if using SSH authentication)
rsync --archive --chown=kirby:kirby ~/.ssh /home/kirby
```

### Step 2.5: Switch to New User

```bash
su - kirby
```

Or reconnect:
```bash
ssh kirby@YOUR_DROPLET_IP
```

---

## 3. Install Docker

### Step 3.1: Install Docker

```bash
# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index
sudo apt update

# Install Docker
sudo apt install -y docker-ce docker-ce-cli containerd.io
```

### Step 3.2: Install Docker Compose

```bash
# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Verify installation
docker compose version
```

### Step 3.3: Add User to Docker Group

```bash
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
exit
# SSH back in
ssh kirby@YOUR_DROPLET_IP
```

### Step 3.4: Verify Docker Installation

```bash
docker run hello-world
```

You should see a success message.

---

## 4. Deploy Kirby

### Step 4.1: Install Git

```bash
sudo apt install -y git
```

### Step 4.2: Clone Repository

```bash
cd ~
git clone https://github.com/oakwoodgates/kirby.git
cd kirby
```

> **Note**: Replace with your actual repository URL

### Step 4.3: Set Up Directory Structure

```bash
# Create logs directory
mkdir -p logs

# Set permissions
chmod 755 logs
```

---

## 5. Configure and Start Services

### Automated Deployment (Recommended)

The easiest way to deploy Kirby is using the automated deployment script. This sets up **both** production and training databases automatically.

#### Step 5.1: Make Deploy Script Executable

```bash
chmod +x deploy.sh
```

#### Step 5.2: Run Automated Deployment

```bash
./deploy.sh
```

The script will automatically:
- ✅ Create `.env` file with generated password (if doesn't exist)
- ✅ Check Docker and Docker Compose are installed
- ✅ Create necessary directories
- ✅ Build Docker images
- ✅ Start all services
- ✅ Create **production database** (kirby) with 8 starlistings
- ✅ Create **training database** (kirby_training) with 24 starlistings
- ✅ Run migrations on both databases
- ✅ Sync configurations for both databases
- ✅ Verify everything is working correctly

**Expected Output:**
```bash
========================================
  Kirby Deployment Script
========================================

[✓] .env file created with generated password
[!] IMPORTANT: Your database password is: <generated_password>
[!] Save this password securely!

[✓] Docker is installed
[✓] Docker Compose is installed
[✓] Directories created
[✓] Docker images built
[✓] Services started
[✓] Database is ready

========================================
  Setting up Production Database
========================================
[✓] Production migrations completed
[✓] Production configuration synced
[✓] Production starlistings: 8

========================================
  Setting up Training Database
========================================
[✓] Training database created
[✓] TimescaleDB extension enabled
[✓] Training migrations completed
[✓] Training configuration synced
[✓] Training starlistings: 24

========================================
  Final Verification
========================================
Running comprehensive verification...
[✓] Production database verified (8 starlistings)
[✓] Training database verified (24 starlistings)

========================================
  Deployment Complete!
========================================
```

#### Step 5.3: Save Your Database Password

If this is a fresh deployment, the script generated a random password. **Save it securely!**

You can find it in the `.env` file:
```bash
cat .env | grep POSTGRES_PASSWORD
```

#### Step 5.4: View Logs

Check that everything is working:

```bash
docker compose logs -f collector
```

You should see:
- ✅ "Connected to Hyperliquid WebSocket"
- ✅ "Subscribed to candles" (8 times for production trading pairs)
- ✅ "Collector connected and running"

**Press Ctrl+C to exit logs**

---

### Manual Deployment (Advanced)

If you prefer manual control over each step, follow these instructions instead of using `./deploy.sh`:

<details>
<summary>Click to expand manual deployment steps</summary>

#### Manual Step 1: Create Environment File

```bash
cp .env.example .env
nano .env  # or use vim
```

**Edit the following values:**

```bash
# REQUIRED: Change this password!
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD_HERE

# Update DATABASE_URL with your password
DATABASE_URL=postgresql+asyncpg://kirby:YOUR_SECURE_PASSWORD_HERE@timescaledb:5432/kirby

# Update TRAINING_DATABASE_URL with your password
TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:YOUR_SECURE_PASSWORD_HERE@timescaledb:5432/kirby_training

# Set to production
ENVIRONMENT=production

# Optional: Adjust log level
LOG_LEVEL=info

# Optional: Adjust collector settings
COLLECTOR_MAX_RETRIES=5
COLLECTOR_RESTART_DELAY=30
```

**Generate a secure password:**
```bash
openssl rand -base64 32
```

Save and exit (`Ctrl+X`, then `Y`, then `Enter` in nano).

#### Manual Step 2: Review Configuration

Check your starlisting configuration:
```bash
cat config/starlistings.yaml      # Production config (8 starlistings)
cat config/training_stars.yaml    # Training config (24 starlistings)
```

#### Manual Step 3: Build Docker Images

```bash
docker compose build
```

This will take a few minutes on first build.

#### Manual Step 4: Start Services

```bash
docker compose up -d
```

#### Manual Step 5: Wait for Database

```bash
# Wait 10 seconds for database to be ready
sleep 10
```

#### Manual Step 6: Setup Production Database

```bash
# Run migrations
docker compose exec collector alembic upgrade head

# Sync configuration
docker compose exec collector python -m scripts.sync_config

# Verify
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 8
```

#### Manual Step 7: Setup Training Database

```bash
# Create database
docker compose exec timescaledb psql -U kirby -c "CREATE DATABASE kirby_training;"

# Enable TimescaleDB extension
docker compose exec timescaledb psql -U kirby -d kirby_training -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Run migrations
docker compose exec collector python -m scripts.migrate_training_db

# Sync configuration
docker compose exec collector python -m scripts.sync_training_config

# Verify
docker compose exec timescaledb psql -U kirby -d kirby_training -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 24
```

#### Manual Step 8: Restart Services

```bash
docker compose restart collector api
```

#### Manual Step 9: View Logs

```bash
docker compose logs -f collector
```

</details>

---

## 6. Verify Deployment

### Step 6.1: Check API Health

```bash
curl http://localhost:8000/health
```

Expected output:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-26T...",
  "database": "connected",
  "version": "0.1.0"
}
```

### Step 6.2: Check Starlistings

```bash
curl http://localhost:8000/starlistings | jq
```

You should see your configured trading pairs.

### Step 6.3: Wait for Data Collection

Wait 1-2 minutes for the collector to gather some candles, then check:

```bash
curl "http://localhost:8000/candles/hyperliquid/BTC/USD/perps/1m?limit=5" | jq
```

### Step 6.4: Check Database Directly

```bash
docker compose exec timescaledb psql -U kirby -d kirby

# Inside psql:
SELECT COUNT(*) FROM candles;
SELECT * FROM candles LIMIT 5;

# Exit psql
\q
```

### Step 6.5: Verify Collector is Running

```bash
# Check collector logs
docker compose logs --tail=50 collector

# Look for messages like:
# "Connected to Hyperliquid WebSocket"
# "Subscribed to candles"
```

### Step 6.6: Backfill Historical Data (Optional)

After your collector is running and collecting real-time data, you may want to backfill historical candle data. This is useful for:
- Building historical datasets for analysis
- Filling gaps if the collector was offline
- Getting data from before your deployment

**Important Notes**:
- ⚠️ All commands below use `docker compose exec collector` - this runs the script **inside** the Docker container
- The backfill script uses CCXT which maps Hyperliquid's USD quotes to USDC internally (this is how CCXT represents Hyperliquid markets)
- Your data will be stored as USD in the database - the USDC mapping is automatic

#### Backfill 1 Day of Data (Quick Test)

```bash
# Backfill 1 day of BTC data across all intervals
docker compose exec collector python -m scripts.backfill --exchange=hyperliquid --coin=BTC --days=1

# Expected output:
# - 1m: ~1,440 candles
# - 15m: ~96 candles
# - 4h: ~6 candles
# - 1d: ~1 candle
```

#### Backfill 30 Days for a Specific Coin

```bash
# Backfill 30 days of SOL data
docker compose exec collector python -m scripts.backfill --exchange=hyperliquid --coin=SOL --days=30
```

#### Backfill All Active Starlistings

```bash
# Backfill 90 days for all configured trading pairs
docker compose exec collector python -m scripts.backfill --all --days=90

# For 1 year of data (this will take longer)
docker compose exec collector python -m scripts.backfill --all --days=365
```

#### Monitor Backfill Progress

```bash
# Watch the backfill logs in real-time
docker compose logs -f collector

# Check how many candles were backfilled
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM candles;"

# Check candles by interval
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT i.name as interval, COUNT(*) as candle_count
FROM candles c
JOIN starlistings s ON c.starlisting_id = s.id
JOIN intervals i ON s.interval_id = i.id
GROUP BY i.name
ORDER BY i.name;
"
```

#### Backfill Best Practices

**Start Small**: Test with 1 day first to verify everything works
```bash
docker compose exec collector python -m scripts.backfill --coin=BTC --days=1
```

**Rate Limiting**: The backfill script automatically handles rate limits, but large backfills will take time
- 1 day: ~1-2 minutes per coin
- 30 days: ~5-10 minutes per coin
- 365 days: ~30-60 minutes per coin

**Run During Low Traffic**: For large backfills (>30 days), run during off-peak hours to avoid impacting real-time collection

**Check for Duplicates**: The backfill uses `UPSERT` logic, so running it multiple times won't create duplicates - it will update existing candles

#### Verify Backfill Results

```bash
# Check date range of backfilled data
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT
  MIN(time) as earliest_candle,
  MAX(time) as latest_candle,
  COUNT(*) as total_candles
FROM candles;
"

# Check backfill completeness for BTC 1m
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT
  c.symbol as coin,
  i.name as interval,
  COUNT(*) as candle_count,
  MIN(ca.time) as earliest,
  MAX(ca.time) as latest
FROM candles ca
JOIN starlistings s ON ca.starlisting_id = s.id
JOIN coins c ON s.coin_id = c.id
JOIN intervals i ON s.interval_id = i.id
WHERE c.symbol = 'BTC' AND i.name = '1m'
GROUP BY c.symbol, i.name;
"
```

### Step 6.7: Backfill Funding Rates (Optional)

After your collector is running and collecting real-time funding/OI data, you may want to backfill historical funding rate data. This provides historical context for funding rate trends.

**Important Notes**:
- ⚠️ All commands use `docker compose exec collector` - runs inside the Docker container
- Funding rates update hourly on Hyperliquid (24 records/day)
- **API Limitation**: Historical endpoint ONLY provides `funding_rate` and `premium`
  - ❌ NO historical data for: `mark_price`, `oracle_price`, `mid_price`, `open_interest`, `next_funding_time`
  - ✅ Real-time collector captures ALL fields going forward
  - Safe to run - won't overwrite real-time data (uses COALESCE)
- Uses minute-precision timestamps aligned with candle data
- Safe to run multiple times (UPSERT with COALESCE preserves existing data)

#### Backfill 7 Days (Recommended Starting Point)

```bash
# Backfill 7 days for BTC
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=7

# Expected output:
# - Funding rates: ~168 records (24 per day × 7 days)
# - Only funding_rate and premium populated (API limitation)
# - Other fields (mark_price, OI, etc.) remain NULL or preserve existing real-time data
```

#### Backfill Specific Coins

```bash
# Backfill 30 days for SOL
docker compose exec collector python -m scripts.backfill_funding --coin=SOL --days=30

# Backfill 90 days for both BTC and SOL (run separately)
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=90
docker compose exec collector python -m scripts.backfill_funding --coin=SOL --days=90
```

#### Backfill All Configured Coins

```bash
# Backfill 30 days for all coins in starlistings.yaml
docker compose exec collector python -m scripts.backfill_funding --all --days=30

# For maximum historical data (365 days)
docker compose exec collector python -m scripts.backfill_funding --all --days=365
```

#### Monitor Backfill Progress

```bash
# Watch backfill logs
docker compose logs -f collector

# Check funding rates count
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT COUNT(*) as total_funding_records FROM funding_rates;
"

# Check open interest count
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT COUNT(*) as total_oi_records FROM open_interest;
"

# View recent funding/OI data by coin
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT
  co.symbol as coin,
  COUNT(DISTINCT f.time) as funding_records,
  COUNT(DISTINCT o.time) as oi_records,
  MIN(f.time) as earliest,
  MAX(f.time) as latest
FROM funding_rates f
JOIN starlistings s ON f.starlisting_id = s.id
JOIN coins co ON s.coin_id = co.id
LEFT JOIN open_interest o ON f.time = o.time AND f.starlisting_id = o.starlisting_id
GROUP BY co.symbol
ORDER BY co.symbol;
"
```

#### Verify Backfill Data Quality

```bash
# Check for gaps in funding data (should update hourly)
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT
  time,
  funding_rate,
  mark_price,
  open_interest
FROM funding_rates f
JOIN starlistings s ON f.starlisting_id = s.id
JOIN coins c ON s.coin_id = c.id
WHERE c.symbol = 'BTC'
ORDER BY time DESC
LIMIT 10;
"

# Verify timestamp alignment with candles
docker compose exec timescaledb psql -U kirby -d kirby -c "
SELECT
  'candles' as source,
  time,
  close as value
FROM candles
WHERE starlisting_id = 1
ORDER BY time DESC
LIMIT 3
UNION ALL
SELECT
  'funding' as source,
  time,
  funding_rate as value
FROM funding_rates
WHERE starlisting_id = 1
ORDER BY time DESC
LIMIT 3;
"
```

#### Backfill Best Practices

**1. Start Small**: Always test with 7 days first
```bash
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=7
```

**2. Data Retention**: Consider your storage needs
- 7 days: ~168 records per coin (24 per day)
- 30 days: ~720 records per coin
- 365 days: ~8,760 records per coin
- **Note**: Backfill only populates funding_rate and premium (API limitation)

**3. Rate Limiting**: The backfill script respects Hyperliquid API limits
- 7 days: <1 minute per coin
- 30 days: 1-2 minutes per coin
- 365 days: 5-10 minutes per coin

**4. Concurrent Backfills**: Safe to backfill candles and funding simultaneously
```bash
# Terminal 1: Backfill candles
docker compose exec collector python -m scripts.backfill --coin=BTC --days=30

# Terminal 2: Backfill funding (simultaneously)
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=30
```

**5. Data Consistency**: Funding backfills use minute-precision timestamps
- Aligns with candle data: `2025-11-02 20:00:00+00`
- Easy to JOIN: `ON f.time = c.time`
- Consistent with 1-minute buffering strategy
- **Real-time collector provides complete data** (all price fields + OI)

#### Common Issues

**Issue**: "No funding history found"
```bash
# Verify coin symbol is correct (case-sensitive)
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=1

# Check if coin exists in starlistings
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT * FROM coins;"
```

**Issue**: Backfill is slow
```bash
# This is normal - funding history API has rate limits
# For 365 days, expect 5-10 minutes per coin
# Monitor progress with: docker compose logs -f collector
```

**Issue**: Duplicate prevention
```bash
# Safe to re-run - uses UPSERT (ON CONFLICT DO UPDATE)
# Will update existing records, not create duplicates
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=7
```

---

## 7. Monitoring and Maintenance

### Step 7.1: Set Up Automatic Restarts

Services are already configured with `restart: unless-stopped` in docker-compose.yml.

To verify:
```bash
docker compose ps
```

### Step 7.2: Monitor Resource Usage

```bash
# Docker stats
docker stats

# System resources
htop  # Install: sudo apt install htop
```

### Step 7.3: Set Up Log Rotation

Create log rotation config:
```bash
sudo nano /etc/logrotate.d/docker-containers
```

Add:
```
/var/lib/docker/containers/*/*.log {
  rotate 7
  daily
  compress
  missingok
  delaycompress
  copytruncate
}
```

### Step 7.4: Database Backups

Create backup script:
```bash
nano ~/backup-kirby.sh
```

Add:
```bash
#!/bin/bash
BACKUP_DIR="/home/kirby/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
docker compose exec -T timescaledb pg_dump -U kirby kirby | gzip > "$BACKUP_DIR/kirby_$DATE.sql.gz"

# Keep only last 7 days
find $BACKUP_DIR -name "kirby_*.sql.gz" -mtime +7 -delete

echo "Backup completed: kirby_$DATE.sql.gz"
```

Make executable and test:
```bash
chmod +x ~/backup-kirby.sh
./backup-kirby.sh
```

Set up daily cron job:
```bash
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * /home/kirby/backup-kirby.sh >> /home/kirby/logs/backup.log 2>&1
```

### Step 7.5: Monitor Disk Space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up old images (careful!)
docker image prune -a
```

### Step 7.6: Update or Deploy Application

The automated deployment script (`deploy.sh`) works for **both fresh deployments AND updates**. It's idempotent, meaning it's safe to run multiple times.

#### Automated Update (Recommended)

```bash
cd ~/kirby

# Pull latest changes
git pull origin main

# Run automated deployment
./deploy.sh
```

The script will:
- ✅ Detect existing `.env` file (won't overwrite)
- ✅ Rebuild Docker images
- ✅ Start all services
- ✅ Run migrations on both databases (production + training)
- ✅ Sync configurations
- ✅ Verify everything is working

**Expected Output:**
```bash
[✓] .env file already exists
[✓] Docker is installed
[✓] Docker Compose is installed
[✓] Docker images built
[✓] Services started
[✓] Database is ready
[✓] Production migrations completed
[✓] Production starlistings: 8
[✓] Training database already exists
[✓] Training migrations completed
[✓] Training starlistings: 24
[✓] Deployment Complete!
```

#### Verify Update

```bash
# Check services are running
docker compose ps

# Check API health
curl http://localhost:8000/health

# Check production database
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 8

# Check training database
docker compose exec timescaledb psql -U kirby -d kirby_training -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 24

# Check collector logs
docker compose logs -f collector
```

#### Quick Update (Code Changes Only)

If you only changed application code (no database/config changes):

```bash
cd ~/kirby
git pull origin main
docker compose down
docker compose up -d --build
docker compose logs -f
```

#### Rollback on Failure

If an update fails:

```bash
# Rollback to previous commit
cd ~/kirby
git log --oneline -5  # Find the commit hash
git checkout <previous-commit-hash>

# Redeploy
./deploy.sh

# Or manually rebuild
docker compose down
docker compose up -d --build
```

#### Manual Update (Advanced)

<details>
<summary>Click to expand manual update steps</summary>

```bash
cd ~/kirby

# Pull latest changes
git pull origin main

# Stop services
docker compose stop

# Rebuild images
docker compose build --no-cache

# Start database only
docker compose up -d timescaledb
sleep 10

# Run migrations on both databases
docker compose exec collector alembic upgrade head
docker compose exec collector python -m scripts.migrate_training_db

# Sync configurations
docker compose exec collector python -m scripts.sync_config
docker compose exec collector python -m scripts.sync_training_config

# Start all services
docker compose up -d

# Verify
docker compose ps
docker compose logs -f collector
```

</details>

**Important Notes**:
- Use `./deploy.sh` for all updates - it's safe and idempotent
- Check logs after update to verify services started correctly
- If collector or API shows errors, check database migrations ran successfully
- Training database is now included in all deployments automatically

---

## 8. Security Hardening

### Step 8.1: Configure Firewall (UFW)

```bash
# Enable UFW
sudo ufw enable

# Allow SSH (IMPORTANT: Do this first!)
sudo ufw allow 22/tcp

# Allow API (if exposing to public)
sudo ufw allow 8000/tcp

# Deny PostgreSQL from external access (keep it internal)
sudo ufw deny 5432/tcp

# Check status
sudo ufw status
```

### Step 8.2: Change SSH Port (Optional but Recommended)

```bash
sudo nano /etc/ssh/sshd_config

# Change Port 22 to a different port (e.g., 2222)
Port 2222

# Restart SSH
sudo systemctl restart sshd

# Update firewall
sudo ufw allow 2222/tcp
sudo ufw delete allow 22/tcp
```

### Step 8.3: Disable Password Authentication (If Using SSH Keys)

```bash
sudo nano /etc/ssh/sshd_config

# Set these values:
PasswordAuthentication no
PubkeyAuthentication yes

# Restart SSH
sudo systemctl restart sshd
```

### Step 8.4: Set Up Fail2Ban

```bash
# Install fail2ban
sudo apt install -y fail2ban

# Copy default config
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# Edit config
sudo nano /etc/fail2ban/jail.local

# Enable SSH protection (find [sshd] section):
[sshd]
enabled = true
port = 2222  # Change if you changed SSH port
maxretry = 3

# Restart fail2ban
sudo systemctl restart fail2ban
sudo systemctl enable fail2ban

# Check status
sudo fail2ban-client status
```

### Step 8.5: Secure Docker

The Dockerfile already runs the application as a non-root user (`kirby`), which is a security best practice.

### Step 8.6: Regular Updates

Set up automatic security updates:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 9. Troubleshooting

### Issue: Services Won't Start

```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Check Docker daemon
sudo systemctl status docker

# Restart Docker
sudo systemctl restart docker
docker compose up -d
```

### Issue: Can't Connect to Database

```bash
# Check if TimescaleDB is running
docker compose ps timescaledb

# Check database logs
docker compose logs timescaledb

# Test connection
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT 1;"

# Verify password in .env matches
cat .env | grep POSTGRES_PASSWORD
```

### Issue: Collector Not Collecting Data

```bash
# Check collector logs
docker compose logs collector | tail -100

# Common issues:
# 1. No starlistings configured - run sync_config.py
# 2. WebSocket connection failed - check internet connectivity
# 3. Database connection failed - check DATABASE_URL

# Restart collector
docker compose restart collector
docker compose logs -f collector
```

### Issue: API Not Responding

```bash
# Check if API is running
docker compose ps api

# Check API logs
docker compose logs api

# Test locally
curl http://localhost:8000/health

# Restart API
docker compose restart api
```

### Issue: Out of Disk Space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up Docker
docker system prune -a --volumes  # CAREFUL: This removes unused data

# Check database size
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT pg_size_pretty(pg_database_size('kirby'));"
```

### Issue: High Memory Usage

```bash
# Check container stats
docker stats

# If database is using too much memory, adjust shared_buffers:
docker compose exec timescaledb psql -U kirby -d kirby -c "SHOW shared_buffers;"

# Restart with limited memory (edit docker-compose.yml):
# Add under timescaledb service:
#   deploy:
#     resources:
#       limits:
#         memory: 1G
```

### Issue: "python: command not found" When Running Backfill

**Symptom**: You get `python: command not found` or `bash: python: command not found` when trying to run the backfill script.

**Cause**: You're trying to run the script directly on the Ubuntu host system, which doesn't have a `python` command (only `python3`).

**Solution**: Use `docker compose exec collector` to run the script **inside** the Docker container:

```bash
# ❌ Wrong - tries to run on host system
python -m scripts.backfill --coin=BTC --days=1

# ❌ Also wrong - still on host
python3 -m scripts.backfill --coin=BTC --days=1

# ✅ Correct - runs inside Docker container
docker compose exec collector python -m scripts.backfill --coin=BTC --days=1
```

**Why**: The Docker container (based on `python:3.13-slim`) has Python installed, but your Ubuntu host may not have `python` symlinked to `python3`.

**Alternative for Local Development**: If you're running locally without Docker:
```bash
# On Ubuntu/Debian host (outside Docker)
python3 -m scripts.backfill --coin=BTC --days=1
```

### Reset Everything (Nuclear Option)

```bash
# Stop and remove all containers, volumes, and images
docker compose down -v
docker system prune -a

# Start fresh
docker compose up -d
docker compose exec collector alembic upgrade head
docker compose exec collector python -m scripts.sync_config
```

---

## Useful Commands

```bash
# View all logs
docker compose logs -f

# Restart specific service
docker compose restart collector

# Stop all services
docker compose stop

# Start all services
docker compose start

# Rebuild after code changes
docker compose build && docker compose up -d

# Execute command in container
docker compose exec collector python scripts/test_full_system.py

# Access database shell
docker compose exec timescaledb psql -U kirby -d kirby

# Check service health
docker compose ps

# View resource usage
docker stats
```

---

## Production Checklist

Before going live, ensure:

- [ ] Changed default PostgreSQL password
- [ ] Configured firewall (UFW)
- [ ] Set up SSL/TLS for API (if public-facing)
- [ ] Configured log rotation
- [ ] Set up automated backups
- [ ] Enabled fail2ban
- [ ] Tested database restore from backup
- [ ] Monitored services for 24 hours
- [ ] Documented your specific configuration
- [ ] Set up alerting/monitoring (optional: Grafana, Prometheus)

---

## Next Steps

1. **Add More Trading Pairs**: Edit `config/starlistings.yaml` and re-run sync script
2. **Set Up Monitoring**: Consider Grafana + Prometheus for metrics
3. **Domain & SSL**: Use Nginx as reverse proxy with Let's Encrypt SSL
4. **Horizontal Scaling**: Add more collector instances for different exchanges
5. **Data Analysis**: Build dashboards using the collected data

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/oakwoodgates/kirby/issues
- Check logs first: `docker compose logs`
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues

---

## License

See [LICENSE](LICENSE) file for details.

---

**Last Updated**: October 26, 2025
**Version**: 1.0.0
