# pgAdmin - Database GUI for Kirby

> **pgAdmin** is a feature-rich, web-based PostgreSQL/TimescaleDB administration tool integrated into the Kirby project via Docker Compose.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Local Development Usage](#local-development-usage)
- [Digital Ocean (Remote Server) Usage](#digital-ocean-remote-server-usage)
- [First-Time Setup](#first-time-setup)
- [Common Tasks](#common-tasks)
- [Query Examples](#query-examples)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

---

## Quick Start

### Start pgAdmin (Local)

```bash
# Start all services including pgAdmin
docker compose up -d

# Or just start pgAdmin
docker compose up -d pgadmin
```

**Access pgAdmin:**
- URL: http://localhost:5050
- Email: `admin@kirby.local` (default, configured in .env)
- Password: `admin` (default, **change this in production!**)

---

## Local Development Usage

### Step 1: Configure Environment Variables

Edit your `.env` file:

```bash
# pgAdmin Configuration
PGADMIN_EMAIL=admin@kirby.local
PGADMIN_PASSWORD=your_secure_password  # Change this!
PGADMIN_PORT=5050
```

### Step 2: Start Services

```bash
docker compose up -d
```

### Step 3: Access pgAdmin

1. Open your browser: **http://localhost:5050**
2. Login with credentials from `.env` file
   - Email: `admin@kirby.local`
   - Password: `your_secure_password`

### Step 4: Connect to Database

See [First-Time Setup](#first-time-setup) below for detailed connection instructions.

---

## Digital Ocean (Remote Server) Usage

### Method 1: SSH Tunnel (Recommended - Secure)

This is the **most secure** method as it doesn't expose pgAdmin to the internet.

#### Setup SSH Tunnel

**From your local machine (Windows PowerShell/CMD or Mac/Linux terminal):**

```bash
# Create SSH tunnel to forward remote port 5050 to local port 5050
ssh -L 5050:localhost:5050 your-user@your-server-ip
```

**Example:**
```bash
ssh -L 5050:localhost:5050 kirby@165.232.123.45
```

#### Access pgAdmin

1. **Keep the SSH connection open**
2. Open your browser: **http://localhost:5050**
3. Login with pgAdmin credentials
4. Connect to database (see [First-Time Setup](#first-time-setup))

#### Windows Users (Alternative - PuTTY)

If using PuTTY:

1. Session: Enter `your-server-ip`
2. Connection → SSH → Tunnels:
   - Source port: `5050`
   - Destination: `localhost:5050`
   - Click "Add"
3. Open connection and login
4. Access http://localhost:5050 in browser

---

### Method 2: Expose Port (Less Secure - Use Firewall!)

**Warning:** Only use this if you configure a firewall to restrict access!

#### On Digital Ocean Server

```bash
# 1. Ensure pgAdmin is running
cd ~/kirby
docker compose up -d pgadmin

# 2. Verify pgAdmin is listening
docker compose ps pgadmin

# 3. Configure UFW firewall (IMPORTANT!)
sudo ufw allow from YOUR_LOCAL_IP to any port 5050
# Replace YOUR_LOCAL_IP with your actual IP (find at https://whatismyip.com)

# Example:
sudo ufw allow from 203.0.113.45 to any port 5050

# 4. Reload firewall
sudo ufw reload
```

#### Update docker-compose.yml

Change the pgAdmin port binding to expose externally:

```yaml
pgadmin:
  ports:
    - "5050:80"  # Change from localhost:5050 to 5050:80
```

Restart pgAdmin:
```bash
docker compose up -d pgadmin
```

#### Access pgAdmin

1. Open browser: **http://YOUR_SERVER_IP:5050**
2. Login with pgAdmin credentials

**Important:** This method exposes pgAdmin to the internet. Always:
- Use a strong password
- Restrict access via firewall (UFW)
- Consider using a VPN instead

---

## First-Time Setup

After accessing pgAdmin for the first time, you need to register the database server.

### Add New Server

1. **In pgAdmin, right-click** "Servers" → "Register" → "Server"

2. **General Tab:**
   - Name: `Kirby TimescaleDB`

3. **Connection Tab:**
   - Host name/address: `timescaledb`
   - Port: `5432`
   - Maintenance database: `kirby`
   - Username: `kirby` (or your POSTGRES_USER from .env)
   - Password: (your POSTGRES_PASSWORD from .env)
   - Save password: Check this box

4. **Click "Save"**

### For Remote Server (SSH Tunnel)

If connecting through SSH tunnel, use the same settings:
- Host: `timescaledb` (Docker internal network name)
- Port: `5432`

The SSH tunnel forwards the web interface, but pgAdmin connects to the database through Docker's internal network.

---

## Common Tasks

### Browse Tables

1. Expand: **Servers** → **Kirby TimescaleDB** → **Databases** → **kirby** → **Schemas** → **public** → **Tables**
2. Right-click a table → **View/Edit Data** → **All Rows**

**Tables in Kirby:**
- `candles` - OHLCV candle data
- `funding_rates` - Funding rate data with price context
- `open_interest` - Open interest data
- `starlistings` - Trading pair configurations
- `exchanges` - Exchange definitions
- `coins` - Cryptocurrency definitions
- `quote_currencies` - Quote currency definitions
- `market_types` - Market type definitions
- `intervals` - Time interval definitions

### Run a Query

1. Click **Tools** → **Query Tool**
2. Write your SQL query
3. Press **F5** or click the **Execute** button (▶)

**Example:**
```sql
SELECT COUNT(*) FROM candles;
```

### Export Data

1. Right-click a table → **View/Edit Data** → **All Rows**
2. Click **Download** button (disk icon)
3. Choose format: CSV, JSON, etc.

### View Table Structure

1. Expand to **Tables**
2. Click on a table name
3. View tabs:
   - **Columns**: Column definitions
   - **Constraints**: Primary keys, foreign keys
   - **Indexes**: Table indexes
   - **Statistics**: Table size, row count

### Monitor Database Size

```sql
-- Database size
SELECT pg_size_pretty(pg_database_size('kirby'));

-- Table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size('public.' || tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.' || tablename) DESC;
```

---

## Query Examples

### Check Data Freshness

```sql
-- Latest candle data per starlisting
SELECT
    s.id,
    e.name AS exchange,
    c.symbol || '/' || q.symbol AS pair,
    i.name AS interval,
    MAX(ca.time) AS latest_candle,
    NOW() - MAX(ca.time) AS data_age
FROM starlistings s
JOIN exchanges e ON s.exchange_id = e.id
JOIN coins c ON s.coin_id = c.id
JOIN quote_currencies q ON s.quote_currency_id = q.id
JOIN intervals i ON s.interval_id = i.id
LEFT JOIN candles ca ON ca.starlisting_id = s.id
WHERE s.active = true
GROUP BY s.id, e.name, c.symbol, q.symbol, i.name
ORDER BY e.name, pair, i.name;
```

### Recent Candles for BTC 1m

```sql
SELECT
    time,
    open,
    high,
    low,
    close,
    volume
FROM candles c
JOIN starlistings s ON c.starlisting_id = s.id
JOIN coins co ON s.coin_id = co.id
JOIN quote_currencies q ON s.quote_currency_id = q.id
JOIN intervals i ON s.interval_id = i.id
WHERE co.symbol = 'BTC'
  AND q.symbol = 'USD'
  AND i.name = '1m'
ORDER BY time DESC
LIMIT 100;
```

### Funding Rates with Price Context

```sql
SELECT
    time,
    funding_rate,
    premium,
    mark_price,
    index_price,
    oracle_price,
    next_funding_time
FROM funding_rates fr
JOIN starlistings s ON fr.starlisting_id = s.id
JOIN coins c ON s.coin_id = c.id
WHERE c.symbol = 'BTC'
ORDER BY time DESC
LIMIT 100;
```

### Open Interest Over Time

```sql
SELECT
    time,
    open_interest,
    notional_value,
    day_base_volume,
    day_notional_volume
FROM open_interest oi
JOIN starlistings s ON oi.starlisting_id = s.id
JOIN coins c ON s.coin_id = c.id
WHERE c.symbol = 'BTC'
ORDER BY time DESC
LIMIT 100;
```

### Total Records by Table

```sql
SELECT
    'candles' AS table_name,
    COUNT(*) AS record_count
FROM candles
UNION ALL
SELECT 'funding_rates', COUNT(*) FROM funding_rates
UNION ALL
SELECT 'open_interest', COUNT(*) FROM open_interest
UNION ALL
SELECT 'starlistings', COUNT(*) FROM starlistings;
```

### Data Collection Rate (Candles per Day)

```sql
SELECT
    DATE(time) AS date,
    COUNT(*) AS candles
FROM candles
WHERE time >= NOW() - INTERVAL '7 days'
GROUP BY DATE(time)
ORDER BY date DESC;
```

---

## Troubleshooting

### Cannot Connect to pgAdmin

**Problem:** Browser shows "This site can't be reached"

**Solutions:**
1. Check pgAdmin is running:
   ```bash
   docker compose ps pgadmin
   ```

2. Check port 5050 is accessible:
   ```bash
   # Local
   curl http://localhost:5050

   # Should return HTML
   ```

3. Check logs:
   ```bash
   docker compose logs pgadmin
   ```

4. Restart pgAdmin:
   ```bash
   docker compose restart pgadmin
   ```

### Invalid Username/Password

**Problem:** Cannot login to pgAdmin

**Solutions:**
1. Check `.env` file for correct credentials
2. Reset pgAdmin password:
   ```bash
   # Stop pgAdmin
   docker compose stop pgadmin

   # Remove pgAdmin data (will reset all settings)
   docker volume rm kirby_pgadmin_data

   # Start pgAdmin (will recreate with current .env values)
   docker compose up -d pgadmin
   ```

### Cannot Connect to Database

**Problem:** pgAdmin shows "Unable to connect to server"

**Solutions:**
1. Verify hostname is `timescaledb` (not `localhost` or IP)
2. Verify port is `5432`
3. Check database credentials match `.env` file
4. Test database from command line:
   ```bash
   docker compose exec timescaledb psql -U kirby -d kirby
   ```

### SSH Tunnel Disconnected

**Problem:** Connection drops when accessing via SSH tunnel

**Solutions:**
1. Keep SSH connection alive by adding to `~/.ssh/config` (local machine):
   ```
   Host your-server-ip
       ServerAliveInterval 60
       ServerAliveCountMax 3
   ```

2. Or use screen/tmux on the server:
   ```bash
   # On local machine
   ssh your-user@your-server-ip -L 5050:localhost:5050

   # Keep terminal open
   ```

### Slow Query Performance

**Problem:** Queries take a long time

**Solutions:**
1. Add `LIMIT` to queries:
   ```sql
   SELECT * FROM candles ORDER BY time DESC LIMIT 1000;
   ```

2. Use time filters:
   ```sql
   SELECT * FROM candles
   WHERE time >= NOW() - INTERVAL '1 day';
   ```

3. Check indexes are being used:
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM candles WHERE time >= NOW() - INTERVAL '1 day';
   ```

---

## Security Notes

### Development vs Production

**Development (localhost):**
- Default password is acceptable
- Expose only to localhost (127.0.0.1)
- No firewall needed

**Production (Digital Ocean):**
- **Always use SSH tunnel** (recommended)
- If exposing port:
  - Use strong password (20+ characters)
  - Restrict access via UFW firewall
  - Consider IP whitelisting only
  - Use VPN if possible
  - Monitor access logs

### Change Default Password

**In `.env` file:**
```bash
PGADMIN_EMAIL=your-email@example.com
PGADMIN_PASSWORD=your-very-secure-password-here
```

**Then recreate pgAdmin:**
```bash
docker compose stop pgadmin
docker volume rm kirby_pgadmin_data
docker compose up -d pgadmin
```

### Restrict Access via Firewall (Production)

```bash
# Allow only your IP
sudo ufw allow from YOUR_IP to any port 5050

# Check rules
sudo ufw status

# Remove rule if needed
sudo ufw delete allow from YOUR_IP to any port 5050
```

### Best Practices

1. **Use SSH tunnels** for remote access (most secure)
2. **Never expose pgAdmin to 0.0.0.0:5050** without firewall
3. **Use strong passwords** (minimum 20 characters)
4. **Enable 2FA on your SSH keys** when accessing servers
5. **Audit access logs** regularly
6. **Keep pgAdmin updated** (pull latest Docker image)
7. **Limit user permissions** (create read-only users if needed)

---

## pgAdmin Alternatives

If pgAdmin doesn't meet your needs, consider:

- **DBeaver** - Universal database tool (desktop app, free)
- **TablePlus** - Modern, native UI (paid, macOS/Windows/Linux)
- **DataGrip** - JetBrains database IDE (paid)
- **psql** - Command-line PostgreSQL client (already available in Docker)

---

## Additional Resources

- [pgAdmin Documentation](https://www.pgadmin.org/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [Kirby API Documentation](../README.md)

---

**Last Updated:** November 3, 2025
