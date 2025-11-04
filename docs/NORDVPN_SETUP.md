# NordVPN Integration with Kirby

> **Purpose**: Enable local Docker containers to access geo-restricted exchange APIs (like Binance) through NordVPN for training data backfills.

---

## Table of Contents

- [Overview](#overview)
- [Why NordVPN Integration?](#why-nordvpn-integration)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Usage](#usage)
- [Testing & Verification](#testing--verification)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [FAQ](#faq)

---

## Overview

Kirby uses a **VPN sidecar container pattern** to route specific Docker services through NordVPN. This allows the `collector-training` service to access geo-restricted APIs like Binance without affecting:
- Your host system's network connection
- Production data collection (runs on separate `collector` service)
- Other Docker services (API, pgAdmin, TimescaleDB)

**Architecture:**
```
┌──────────────────────────────────────────────────┐
│  Docker Compose                                  │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────────┐     ┌──────────────────┐   │
│  │  VPN Container │◄────┤ Collector        │   │
│  │  (NordVPN)     │     │  Training        │   │
│  │  ┌──────────┐  │     │                  │   │
│  │  │ NordLynx │  │     │  (network_mode:  │   │
│  │  │WireGuard │  │     │   service:vpn)   │   │
│  │  └──────────┘  │     └──────────────────┘   │
│  └────────┬───────┘                             │
│           │                                     │
│           └─► Internet (via VPN)                │
│              Appears as US IP                   │
│                                                  │
│  ┌────────────────┐     ┌──────────────────┐   │
│  │  Collector     │────►│  TimescaleDB     │   │
│  │  (Production)  │     │                  │   │
│  └────────────────┘     └──────────────────┘   │
│        ▲                                        │
│        │                                        │
│        └─ Direct connection (no VPN)            │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Why NordVPN Integration?

### The Problem

Some cryptocurrency exchanges (notably Binance) restrict API access from certain geographic regions:
- **Binance**: Blocks US IPs and other restricted countries
- **Bybit**: Various regional restrictions
- **Other exchanges**: May have geo-blocks

### The Solution

**VPN Sidecar Container** allows you to:
- ✅ Access geo-restricted exchanges for **training data** backfills
- ✅ Keep **production data collection** running without VPN (faster, more reliable)
- ✅ Run backfills **locally** instead of managing a separate overseas server
- ✅ Export training data and upload to your training server
- ✅ No changes to your host system or Windows network settings

### Why Not Just Use NordVPN Windows Client?

❌ **Docker Desktop doesn't inherit Windows VPN connections**
- Docker runs in WSL2 or Hyper-V with its own network stack
- Container traffic bypasses Windows VPN routing tables
- Would require complex workarounds (wsl-vpnkit, manual routing)

✅ **VPN Sidecar Container is the proper solution**
- Docker-native approach
- Clean isolation
- Well-tested with 1000+ GitHub stars
- Production-ready

---

## Prerequisites

### Required

1. **NordVPN Subscription** (active account)
   - Any plan works (monthly, yearly)
   - Free trials acceptable for testing

2. **Docker Desktop** running on Windows
   - Version 4.0+ recommended
   - WSL2 backend enabled (default)

3. **Kirby Project** set up and working
   - Training database created (`kirby_training`)
   - Migrations run successfully

### Optional but Recommended

- **Admin/PowerShell access** for testing network connectivity
- **Patience** - First-time VPN setup takes ~30 minutes with testing

---

## Setup Instructions

### Step 1: Generate NordVPN Access Token

1. **Visit NordVPN Account Portal**:
   - Go to: https://my.nordaccount.com
   - Log in with your NordVPN credentials

2. **Navigate to Access Token Section**:
   - Click **Services** in sidebar
   - Click **NordVPN**
   - Scroll to **Access Token** section
   - Click **Generate new token**

3. **Choose Token Duration**:
   - **30 days** - Recommended for testing
   - **Non-expiring** - Better for production (requires re-authentication if revoked)

4. **Copy Token**:
   - Click **Copy** button
   - Save token somewhere safe temporarily
   - **IMPORTANT**: Token is shown only once! If you lose it, generate a new one.

**Example Token Format**:
```
abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```
(50+ character alphanumeric string)

---

### Step 2: Update Your Local .env File

1. **Open your .env file** (in project root):
   ```bash
   # If using VS Code
   code .env

   # Or edit manually
   notepad .env
   ```

2. **Add NordVPN Configuration** (copy your token):
   ```bash
   # NordVPN Configuration
   NORDVPN_TOKEN=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
   NORDVPN_COUNTRY=United_States
   NORDVPN_TECHNOLOGY=NordLynx
   ```

3. **Adjust Country if Needed**:
   - **For Binance**: Use `United_States`, `United_Kingdom`, `Canada`, `Netherlands`, etc.
   - **Format**: No spaces! Use underscores: `United_States` not `United States`
   - **Full list**: https://nordvpn.com/servers/

4. **Save the file**

**Security Note**: Never commit your `.env` file to Git! It's already in `.gitignore`.

---

### Step 3: Verify Docker Compose Configuration

The VPN services have already been added to `docker-compose.yml`. Let's verify:

```bash
# Check VPN service exists
docker compose config --services | grep vpn
# Should output: vpn

# Check collector-training service exists
docker compose config --services | grep collector-training
# Should output: collector-training
```

If services don't appear, ensure you have the latest code:
```bash
git pull origin main
```

---

### Step 4: Start VPN Container

1. **Start only the VPN service**:
   ```bash
   docker compose up -d vpn
   ```

2. **Watch VPN connection logs**:
   ```bash
   docker compose logs -f vpn
   ```

3. **Wait for successful connection**:
   ```
   ✅ Look for these messages:
   [INFO] Connecting to NordVPN...
   [INFO] Connected to NordVPN! (us9876.nordvpn.com)
   [INFO] Connection established
   ```

   This typically takes **10-30 seconds** on first connection.

4. **Stop watching logs**: Press `Ctrl+C` (logs keep running in background)

---

### Step 5: Verify VPN Connection

1. **Check VPN container is healthy**:
   ```bash
   docker compose ps vpn
   ```

   **Expected output:**
   ```
   NAME        STATUS                    HEALTH
   kirby-vpn   Up 2 minutes (healthy)    healthy
   ```

2. **Verify IP address changed**:
   ```bash
   docker compose exec vpn curl -s https://ipinfo.io/json
   ```

   **Expected output** (example for US connection):
   ```json
   {
     "ip": "123.45.67.89",
     "city": "New York",
     "region": "New York",
     "country": "US",
     "org": "AS174 NordVPN"
   }
   ```

   **Verify**:
   - ✅ `country` should match your `NORDVPN_COUNTRY` setting
   - ✅ `org` should mention NordVPN
   - ✅ `ip` should NOT be your real IP

3. **Test Binance API access**:
   ```bash
   docker compose exec vpn curl -s https://api.binance.com/api/v3/ping
   ```

   **Expected output**:
   ```json
   {}
   ```

   **If you see an error instead**, Binance may have blocked that specific NordVPN server. Try a different country in `.env` and restart VPN.

---

### Step 6: Test Database Connectivity from VPN Network

This verifies that containers using `network_mode: service:vpn` can still reach your TimescaleDB database.

```bash
# Test database connection through VPN network
docker compose run --rm collector-training psql postgresql://kirby:YOUR_PASSWORD@timescaledb:5432/kirby_training -c "SELECT 1;"
```

**Replace `YOUR_PASSWORD`** with your actual `POSTGRES_PASSWORD` from `.env`.

**Expected output**:
```
 ?column?
----------
        1
(1 row)
```

If this fails, see [Troubleshooting](#troubleshooting) section.

---

## Usage

### Running Training Data Backfills

Now that VPN is set up, you can backfill training data from Binance (or other geo-restricted exchanges):

#### Example 1: Backfill 7 Days of BTC Training Data

```bash
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=7
```

**What happens**:
1. Docker starts `collector-training` container
2. Container routes all traffic through VPN
3. Connects to Binance API (appears as US IP)
4. Downloads 7 days of historical data for BTC across all training starlistings
5. Stores data in `kirby_training` database
6. Container exits automatically (`--rm` removes it after completion)

#### Example 2: Backfill Multiple Coins

```bash
# Backfill BTC (7 days)
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=7

# Backfill SOL (7 days)
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=SOL --days=7

# Backfill ETH (7 days)
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=ETH --days=7
```

#### Example 3: Backfill Longer Timeframe

```bash
# Backfill 90 days (3 months)
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=90

# Backfill 365 days (1 year)
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=365
```

**Pro Tip**: For very long backfills (1+ year), consider breaking into chunks to avoid timeout issues:
```bash
# Backfill in 3-month chunks
docker compose run --rm collector-training python -m scripts.backfill_training --coin=BTC --days=90
docker compose run --rm collector-training python -m scripts.backfill_training --coin=BTC --days=90 --start-date=2024-08-01
# etc.
```

### Exporting Training Data

After backfilling, export the data for uploading to your training server:

```bash
# Export BTC 1m candles (last 30 days)
docker compose run --rm collector-training \
  python -m scripts.export_all \
  --coin=BTC --intervals=1m --days=30 --format=parquet
```

**Output location**: `exports/` directory in your project root

**Upload to training server**:
```bash
# Example using SCP
scp exports/merged_*.parquet user@training-server:/path/to/data/
```

### Checking VPN Status

```bash
# View VPN logs (live)
docker compose logs -f vpn

# Check VPN health status
docker compose ps vpn

# Verify current IP/location
docker compose exec vpn curl -s https://ipinfo.io/json

# Test specific API access
docker compose exec vpn curl -s https://api.binance.com/api/v3/ping
```

### Stopping VPN

```bash
# Stop VPN container
docker compose stop vpn

# Stop and remove VPN container
docker compose down vpn
```

**Note**: Stopping VPN won't affect your production `collector` service (it runs independently).

---

## Testing & Verification

### Full End-to-End Test

Run this complete test to verify everything works:

```bash
# 1. Start VPN
docker compose up -d vpn
sleep 30  # Wait for connection

# 2. Verify VPN connected
docker compose logs vpn | grep "Connected"

# 3. Check IP is from VPN country
docker compose exec vpn curl -s https://ipinfo.io/json | grep country

# 4. Test Binance API access
docker compose exec vpn curl -s https://api.binance.com/api/v3/ping

# 5. Run small training backfill (1 day, BTC only)
docker compose run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=1

# 6. Verify data was inserted
docker compose exec timescaledb psql -U kirby -d kirby_training \
  -c "SELECT COUNT(*) FROM candles WHERE created_at > NOW() - INTERVAL '5 minutes';"

# 7. Export data to verify export works
docker compose run --rm collector-training \
  python -m scripts.export_all --coin=BTC --intervals=1m --days=1 --format=csv
```

**Expected Results**:
- ✅ VPN shows "Connected" in logs
- ✅ IP location shows your chosen country (e.g., "US")
- ✅ Binance API returns `{}`
- ✅ Backfill completes without errors
- ✅ Database shows new candles inserted
- ✅ Export creates CSV file in `exports/` directory

---

## Troubleshooting

### Issue: VPN container won't start

**Symptoms**:
```
Error response from daemon: failed to create shim task
```

**Solutions**:

1. **Restart Docker Desktop**:
   - Right-click Docker Desktop icon → Quit Docker Desktop
   - Start Docker Desktop again
   - Wait for "Docker Desktop is running" status
   - Try again: `docker compose up -d vpn`

2. **Check Docker has required permissions**:
   - Run PowerShell/CMD as Administrator
   - Navigate to project directory
   - Run: `docker compose up -d vpn`

3. **Verify Docker Desktop settings**:
   - Docker Desktop → Settings → Resources → WSL Integration
   - Ensure your distro is enabled (if using WSL2)

---

### Issue: VPN connects but DNS not resolving

**Symptoms**:
```bash
$ docker compose exec vpn curl https://api.binance.com
curl: (6) Could not resolve host: api.binance.com
```

**Solutions**:

1. **Add explicit DNS servers to VPN service**:

   Edit `docker-compose.yml`, add to `vpn` service:
   ```yaml
   vpn:
     image: ghcr.io/bubuntux/nordvpn
     # ... existing config ...
     dns:
       - 1.1.1.1
       - 8.8.8.8
   ```

2. **Restart VPN**:
   ```bash
   docker compose restart vpn
   docker compose logs -f vpn
   ```

---

### Issue: "Token is invalid" error

**Symptoms**:
```
[ERROR] Token is invalid or expired
```

**Solutions**:

1. **Verify token is correct**:
   ```bash
   cat .env | grep NORDVPN_TOKEN
   ```
   - Check for typos
   - Ensure no spaces before/after token
   - Verify token is 50+ characters

2. **Generate new token**:
   - Visit https://my.nordaccount.com
   - Revoke old token (if still visible)
   - Generate new token
   - Update `.env` file
   - Restart VPN: `docker compose restart vpn`

3. **Verify NordVPN subscription is active**:
   - Log in to https://my.nordaccount.com
   - Check subscription status
   - If expired, renew subscription

---

### Issue: Collector-training can't connect to database

**Symptoms**:
```
asyncpg.exceptions.ConnectionDoesNotExistError: connection to server at "timescaledb" (172.x.x.x), port 5432 failed
```

**Root Cause**: When using `network_mode: service:vpn`, the container shares VPN's network namespace and may have DNS resolution issues.

**Solutions**:

1. **Verify both VPN and database are on same Docker network**:
   ```bash
   docker compose ps
   # Both 'vpn' and 'timescaledb' should show 'kirby-network'
   ```

2. **Test DNS resolution from VPN container**:
   ```bash
   docker compose exec vpn nslookup timescaledb
   ```

   If this fails, DNS is the issue. Add explicit DNS to VPN service (see DNS issue above).

3. **Alternative: Use IP address instead of hostname**:

   Get TimescaleDB IP:
   ```bash
   docker compose exec timescaledb hostname -i
   ```

   Update `.env`:
   ```bash
   # Replace 'timescaledb' with IP (example: 172.18.0.2)
   TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:password@172.18.0.2:5432/kirby_training
   ```

---

### Issue: Binance still blocks me (403 Forbidden)

**Symptoms**:
```bash
$ docker compose exec vpn curl https://api.binance.com/api/v3/ping
{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}
```

**Possible Causes**:
- Binance detected that specific NordVPN server IP
- Country choice still restricted by Binance

**Solutions**:

1. **Try different country**:
   ```bash
   # Edit .env
   NORDVPN_COUNTRY=Netherlands  # or United_Kingdom, Canada, etc.

   # Restart VPN
   docker compose restart vpn
   docker compose logs -f vpn
   ```

2. **Try different NordVPN technology**:
   ```bash
   # Edit .env
   NORDVPN_TECHNOLOGY=OpenVPN  # Instead of NordLynx

   # Restart VPN
   docker compose restart vpn
   ```

3. **Connect to specific server**:
   ```bash
   # Edit .env - replace NORDVPN_COUNTRY with specific server
   NORDVPN_CONNECT=us9876  # Get from nordvpn.com/servers

   # Restart VPN
   docker compose restart vpn
   ```

4. **Last resort: Use different exchange**:
   - Bybit has fewer restrictions
   - OKX works in many regions
   - Consider paid data API (CryptoCompare, Kaiko)

---

### Issue: VPN keeps disconnecting/reconnecting

**Symptoms**:
```
[INFO] Connection lost, reconnecting...
[INFO] Connected to NordVPN...
[INFO] Connection lost, reconnecting...
```

**Solutions**:

1. **Check your internet connection**:
   - Ensure stable internet (test with: `ping 8.8.8.8`)
   - VPN needs consistent connection

2. **Try different country/server**:
   - Some servers are more stable than others
   - US servers tend to be very stable
   - Try: `NORDVPN_COUNTRY=Canada` or `United_Kingdom`

3. **Switch to OpenVPN**:
   ```bash
   # Edit .env
   NORDVPN_TECHNOLOGY=OpenVPN

   # Restart VPN
   docker compose restart vpn
   ```

   OpenVPN is slower but sometimes more stable than NordLynx.

4. **Increase health check interval**:

   Edit `docker-compose.yml`, modify `vpn` service:
   ```yaml
   healthcheck:
     test: ["CMD-SHELL", "ping -c 1 1.1.1.1 || exit 1"]
     interval: 120s  # Changed from 60s
     timeout: 20s    # Changed from 10s
     retries: 5      # Changed from 3
   ```

---

### Issue: Backfill script hangs indefinitely

**Symptoms**:
- Script runs for very long time
- No progress output
- Can't Ctrl+C to stop

**Solutions**:

1. **Force stop the container**:
   ```bash
   # Find container ID
   docker ps

   # Force stop
   docker stop <container-id>
   ```

2. **Check database to see if data was inserted anyway**:
   ```bash
   docker compose exec timescaledb psql -U kirby -d kirby_training \
     -c "SELECT COUNT(*) FROM candles WHERE created_at > NOW() - INTERVAL '1 hour';"
   ```

   Data might have been stored even if script appears hung.

3. **Run with smaller time chunks**:
   ```bash
   # Instead of --days=365, break into chunks
   docker compose run --rm collector-training \
     python -m scripts.backfill_training --coin=BTC --days=30

   # Wait for completion, then continue
   docker compose run --rm collector-training \
     python -m scripts.backfill_training --coin=BTC --days=30 --start-date=2024-10-01
   ```

---

## Security Considerations

### Token Security

**DO**:
- ✅ Keep token in `.env` file (gitignored)
- ✅ Treat token like a password
- ✅ Use non-expiring tokens for production (easier management)
- ✅ Regenerate token if you suspect it's compromised

**DON'T**:
- ❌ Commit token to Git
- ❌ Share token publicly
- ❌ Use token on multiple machines simultaneously (may violate NordVPN TOS)
- ❌ Hardcode token in source code

### Network Isolation

The VPN sidecar pattern provides good isolation:
- ✅ Only `collector-training` uses VPN (production traffic unaffected)
- ✅ VPN container crashes don't affect other services
- ✅ Easy to disable VPN (stop container)
- ✅ No changes to host system networking

### Binance Terms of Service

**IMPORTANT**: Using VPN to bypass Binance geo-restrictions may violate their Terms of Service.

**Risks**:
- ⚠️ Account suspension
- ⚠️ Fund freezing
- ⚠️ API key revocation

**Mitigations**:
- Use only for **historical data** (not trading)
- Respect API rate limits
- Consider using Binance's official partners (Kaiko, CryptoCompare)
- Understand legal implications in your jurisdiction

**Our stance**: We provide this tool for technical learning and data collection. You are responsible for complying with exchange ToS and local laws.

### VPN Leak Protection

The bubuntux/nordvpn container includes built-in leak protection:
- ✅ Kill switch (iptables rules)
- ✅ IPv6 disabled (prevents leaks)
- ✅ DNS leak protection
- ✅ WebRTC leak protection

**Verify no leaks**:
```bash
# Check IP before VPN
curl https://ipinfo.io/json

# Check IP through VPN
docker compose exec vpn curl https://ipinfo.io/json

# IPs should be different!
```

---

## FAQ

### Q: Do I need NordVPN subscription for this to work?

**A**: Yes, you need an active NordVPN subscription. Any plan works (monthly, yearly). Free trials are acceptable for testing.

### Q: Can I use other VPN providers (ExpressVPN, Surfshark, etc.)?

**A**: Not with this exact setup. The `bubuntux/nordvpn` Docker container is specific to NordVPN. Other VPN providers would require different container images. However, the sidecar pattern works similarly for other VPNs - you'd just need to find/build a container for your provider.

### Q: Will this slow down my production data collection?

**A**: No! The production `collector` service runs independently without VPN. Only the `collector-training` service (used for backfills) routes through VPN. Your real-time Hyperliquid data collection is unaffected.

### Q: How much does VPN add to backfill time?

**A**: Minimal impact (~10-20% slower). VPN adds 10-30ms latency, but backfill speed is primarily limited by:
1. Exchange API rate limits (much bigger factor)
2. Database insert speed
3. Network bandwidth

For a 30-day backfill, expect similar completion time (with or without VPN).

### Q: Can I run backfills while production collector is running?

**A**: Yes! They use separate containers and don't interfere with each other. Both can run simultaneously. However, they share the same database pool, so very heavy concurrent usage might slow things down slightly.

### Q: Do I need to keep VPN running all the time?

**A**: No! You only need VPN running when:
- Running training backfills (`docker compose run collector-training ...`)
- Testing Binance API access

You can stop VPN when not in use:
```bash
docker compose stop vpn
```

### Q: What if my NordVPN token expires?

**A**: Token expiration depends on your choice during generation:
- **30-day tokens**: Expire automatically after 30 days
- **Non-expiring tokens**: Valid until you revoke them or subscription ends

When expired:
1. Generate new token from https://my.nordaccount.com
2. Update `.env` file
3. Restart VPN: `docker compose restart vpn`

### Q: Can I use this on Mac/Linux instead of Windows?

**A**: Yes! This setup is cross-platform. The Docker Compose configuration works identically on:
- ✅ Windows (Docker Desktop)
- ✅ macOS (Docker Desktop)
- ✅ Linux (Docker Engine or Docker Desktop)

Only difference: File paths use forward slashes (/) on Mac/Linux instead of backslashes (\) on Windows.

### Q: Is this approach production-ready?

**A**: For **training data backfills**: Yes, absolutely. Thousands of projects use this bubuntux/nordvpn container in production.

For **real-time data collection**: Not recommended. VPN adds latency and potential disconnection issues. Keep production collection on direct connections (like your Hyperliquid collector).

### Q: What happens if VPN disconnects during a long backfill?

**A**: The backfill script has built-in retry logic:
1. Script detects connection failure
2. Waits briefly
3. Retries the request
4. If repeated failures, script may exit with error

**Mitigation**: Run backfills in smaller chunks (7-30 days) rather than very long periods (1+ year).

### Q: Can I change VPN country without restarting?

**A**: No, you must restart the VPN container:
```bash
# Edit .env
nano .env  # Change NORDVPN_COUNTRY

# Restart VPN
docker compose restart vpn
docker compose logs -f vpn  # Verify new country
```

### Q: How do I know which NordVPN server I'm connected to?

**A**: Check the VPN logs:
```bash
docker compose logs vpn | grep "Connected"
```

Example output:
```
[INFO] Connected to NordVPN! (us9876.nordvpn.com)
```

Or check via IP info:
```bash
docker compose exec vpn curl -s https://ipinfo.io/json | grep org
# Output: "org": "AS174 NordVPN"
```

---

## Additional Resources

- **NordVPN Account Portal**: https://my.nordaccount.com
- **NordVPN Server List**: https://nordvpn.com/servers/
- **bubuntux/nordvpn Docker Image**: https://github.com/bubuntux/nordvpn
- **Kirby Training Data Guide**: [EXPORT.md](EXPORT.md)
- **Kirby Deployment Guide**: [DEPLOYMENT.md](../DEPLOYMENT.md)

---

**Last Updated**: 2025-11-04
**Version**: 1.0.0
