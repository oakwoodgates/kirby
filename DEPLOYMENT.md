# Kirby Deployment Guide

This guide covers deploying Kirby to production environments, with focus on Digital Ocean deployment.

## Table of Contents

1. [Local Development](#local-development)
2. [Digital Ocean Droplet](#digital-ocean-droplet)
3. [Digital Ocean App Platform](#digital-ocean-app-platform)
4. [Production Checklist](#production-checklist)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

- Python 3.11+
- Docker Desktop (Windows/Mac) or Docker + Docker Compose (Linux)
- Poetry

### Setup

```bash
# Clone and install
git clone <repo-url>
cd kirby
poetry install
poetry shell

# Start database
docker-compose up -d

# Run migrations
alembic upgrade head

# Seed data
python scripts/seed_database.py

# Test collectors
bash -c "PYTHONPATH=. python scripts/test_collectors.py"
```

### Development Workflow

```bash
# Start API (auto-reload)
uvicorn src.api.main:app --reload --port 8000

# Run collectors in separate terminal
PYTHONPATH=. python scripts/test_collectors.py

# Run backfill
python scripts/run_backfill.py

# View logs
docker logs -f kirby_timescaledb

# Access database
docker exec -it kirby_timescaledb psql -U kirby_user -d kirby
```

---

## Digital Ocean Droplet

### Recommended Droplet Specs

| Listings | RAM | vCPU | Disk | Monthly Cost |
|----------|-----|------|------|--------------|
| 2-10 | 4GB | 2 | 80GB | $24/mo |
| 10-50 | 8GB | 4 | 160GB | $48/mo |
| 50-100 | 16GB | 8 | 320GB | $96/mo |

### Initial Server Setup

```bash
# 1. Create droplet
# - Ubuntu 24.04 LTS
# - Choose region closest to exchanges (US East for Hyperliquid)
# - Add SSH key

# 2. SSH into droplet
ssh root@your-droplet-ip

# 3. Update system
apt update && apt upgrade -y

# 4. Install Docker
apt install -y docker.io docker-compose

# 5. Install Python 3.11 and Poetry
apt install -y python3.11 python3.11-venv python3-pip
curl -sSL https://install.python-poetry.org | python3 -

# 6. Add poetry to PATH
export PATH="/root/.local/bin:$PATH"
echo 'export PATH="/root/.local/bin:$PATH"' >> ~/.bashrc

# 7. Create non-root user (recommended)
useradd -m -s /bin/bash kirby
usermod -aG docker kirby
su - kirby
```

### Application Deployment

```bash
# 1. Clone repository
cd /opt
git clone <repo-url> kirby
cd kirby
chown -R kirby:kirby /opt/kirby

# 2. Configure environment
cp .env .env.production
nano .env.production

# Update these values:
# - DATABASE_URL (use production credentials)
# - LOG_LEVEL=WARNING
# - LOG_FORMAT=json
# - ENVIRONMENT=production

# 3. Install dependencies
poetry install --no-dev --no-root

# 4. Start database
docker-compose up -d

# Wait for database to be ready
sleep 10

# 5. Run migrations
poetry run alembic upgrade head

# 6. Seed initial data
poetry run python scripts/seed_database.py

# 7. Run initial backfill (optional, can take time)
# For 30 days of data:
poetry run python scripts/run_backfill.py
```

### Systemd Services

Create systemd services for automatic startup and restart.

#### Collector Service

```bash
# Create service file
sudo nano /etc/systemd/system/kirby-collectors.service
```

```ini
[Unit]
Description=Kirby Data Collectors
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=kirby
WorkingDirectory=/opt/kirby
Environment="PATH=/home/kirby/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/kirby"
ExecStart=/home/kirby/.local/bin/poetry run python scripts/test_collectors.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### API Service (Phase 5)

```bash
sudo nano /etc/systemd/system/kirby-api.service
```

```ini
[Unit]
Description=Kirby API Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=kirby
WorkingDirectory=/opt/kirby
Environment="PATH=/home/kirby/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/kirby/.local/bin/poetry run gunicorn src.api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable kirby-collectors
sudo systemctl enable kirby-api

# Start services
sudo systemctl start kirby-collectors
sudo systemctl start kirby-api

# Check status
sudo systemctl status kirby-collectors
sudo systemctl status kirby-api

# View logs
sudo journalctl -u kirby-collectors -f
sudo journalctl -u kirby-api -f
```

### Nginx Reverse Proxy (Optional)

```bash
# Install nginx
sudo apt install -y nginx

# Create config
sudo nano /etc/nginx/sites-available/kirby
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # API endpoints
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8000/api/v1/health;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;
    limit_req zone=api_limit burst=20 nodelay;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/kirby /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup SSL with Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Firewall Configuration

```bash
# Install UFW
sudo apt install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (if using nginx)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow API directly (if not using nginx)
sudo ufw allow 8000/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## Digital Ocean App Platform

For easier scaling and management, use DO App Platform.

### Architecture

- **Web Service**: FastAPI (auto-scaling, load balanced)
- **Worker Service**: Data collectors (fixed instance count)
- **Database**: Managed TimescaleDB (separate)

### Setup

1. **Create Managed Database**

```bash
# Via DO Console:
# - Create Database → TimescaleDB
# - Plan: 4GB RAM, 2 vCPU ($60/mo)
# - Region: Same as app
# - Enable automatic backups
```

2. **Create App Spec** (`app.yaml`)

```yaml
name: kirby
region: nyc

# Database (managed)
databases:
  - engine: PG
    name: kirby-db
    version: "15"
    production: true

# API Service
services:
  - name: api
    github:
      repo: your-org/kirby
      branch: main
      deploy_on_push: true
    build_command: poetry install --no-dev
    run_command: gunicorn src.api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
    environment_slug: python
    instance_count: 2
    instance_size_slug: basic-xs  # 1 vCPU, 1GB RAM
    http_port: 8080
    health_check:
      http_path: /api/v1/health
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
        value: ${kirby-db.DATABASE_URL}
      - key: ENVIRONMENT
        value: production
      - key: LOG_LEVEL
        value: INFO

# Collector Worker
workers:
  - name: collectors
    github:
      repo: your-org/kirby
      branch: main
    build_command: poetry install --no-dev
    run_command: python scripts/test_collectors.py
    environment_slug: python
    instance_count: 1
    instance_size_slug: basic-xxs  # 0.5 vCPU, 512MB RAM
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
        value: ${kirby-db.DATABASE_URL}
      - key: ENVIRONMENT
        value: production
```

3. **Deploy**

```bash
# Install doctl
snap install doctl
doctl auth init

# Deploy app
doctl apps create --spec app.yaml

# Update app
doctl apps update <app-id> --spec app.yaml

# View logs
doctl apps logs <app-id> --type run
```

---

## Production Checklist

### Pre-Deployment

- [ ] Update `.env` with production values
- [ ] Set `LOG_LEVEL=WARNING` or `INFO`
- [ ] Set `LOG_FORMAT=json`
- [ ] Configure `CORS_ORIGINS` with allowed domains
- [ ] Review rate limiting settings
- [ ] Test database migrations on staging
- [ ] Run backfill for initial data

### Security

- [ ] Use strong database passwords (32+ chars)
- [ ] Enable database SSL connections
- [ ] Configure firewall (UFW or DO cloud firewall)
- [ ] Set up SSH key authentication (disable password auth)
- [ ] Enable automatic security updates
- [ ] Use non-root user for application
- [ ] Restrict Docker socket access
- [ ] Set up fail2ban for SSH

### Monitoring

- [ ] Configure log aggregation (optional: Grafana Loki, ELK)
- [ ] Set up database backups (daily, retained 7 days)
- [ ] Monitor disk usage alerts (<80%)
- [ ] Monitor memory usage alerts
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
- [ ] Configure alerts (Discord webhook, email)

### Performance

- [ ] Enable TimescaleDB compression policies
- [ ] Set up retention policies (optional: drop data >1 year)
- [ ] Optimize PostgreSQL settings for workload
- [ ] Configure connection pooling limits
- [ ] Enable query logging for slow queries (>1s)

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check database connection
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT 1"

# Check collector status
sudo systemctl status kirby-collectors

# Check disk usage
df -h

# Check memory usage
free -h

# Check Docker containers
docker ps
docker stats
```

### Database Maintenance

```bash
# Backup database
docker exec kirby_timescaledb pg_dump -U kirby_user kirby > backup_$(date +%Y%m%d).sql

# Restore database
cat backup_20251024.sql | docker exec -i kirby_timescaledb psql -U kirby_user kirby

# Vacuum analyze (monthly)
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "VACUUM ANALYZE;"

# Check table sizes
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check compression stats
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT * FROM timescaledb_information.compressed_chunk_stats;
"
```

### Log Management

```bash
# View collector logs (systemd)
sudo journalctl -u kirby-collectors -f

# View API logs
sudo journalctl -u kirby-api -f

# View last 100 lines
sudo journalctl -u kirby-collectors -n 100

# View logs from last hour
sudo journalctl -u kirby-collectors --since "1 hour ago"

# Search logs
sudo journalctl -u kirby-collectors | grep ERROR

# Rotate logs (prevent disk fill)
sudo nano /etc/systemd/journald.conf
# Set: SystemMaxUse=1G
sudo systemctl restart systemd-journald
```

### Backfill Management

```bash
# Check backfill job status
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT
    id,
    listing_id,
    data_type,
    status,
    records_fetched,
    start_date,
    end_date,
    created_at
FROM backfill_job
ORDER BY created_at DESC
LIMIT 10;
"

# Retry failed backfill jobs
python scripts/run_backfill.py --retry-failed
```

---

## Troubleshooting

### Collectors Not Running

```bash
# Check service status
sudo systemctl status kirby-collectors

# View logs
sudo journalctl -u kirby-collectors -n 50

# Restart service
sudo systemctl restart kirby-collectors

# Check database connection
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT 1"

# Test collector manually
cd /opt/kirby
poetry run python scripts/test_collectors.py
```

### High Memory Usage

```bash
# Check memory usage
free -h
docker stats

# Check PostgreSQL connections
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT count(*) FROM pg_stat_activity;
"

# Reduce connection pool size in .env
DB_POOL_MAX_SIZE=10  # Down from 20
DB_POOL_MIN_SIZE=5   # Down from 10

# Restart services
sudo systemctl restart kirby-collectors
sudo systemctl restart kirby-api
```

### Database Connection Errors

```bash
# Check container status
docker ps

# Check PostgreSQL logs
docker logs kirby_timescaledb --tail 100

# Test connection
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT version();"

# Restart database
docker-compose restart

# Check disk space (database may refuse connections if disk full)
df -h
```

### Slow Queries

```bash
# Enable query logging
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();
"

# View slow queries
docker logs kirby_timescaledb | grep "duration:"

# Check missing indexes
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexname NOT LIKE 'pg_toast%';
"
```

### Disk Space Issues

```bash
# Check disk usage
df -h

# Check database size
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT pg_size_pretty(pg_database_size('kirby'));
"

# Check table sizes
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size('public.'||tablename))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.'||tablename) DESC;
"

# Manual compression
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
SELECT compress_chunk(i.show_chunks)
FROM show_chunks('candle', older_than => INTERVAL '7 days') AS i;
"

# Delete old data (if needed)
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "
DELETE FROM candle WHERE timestamp < NOW() - INTERVAL '90 days';
"
```

---

## Updating the Application

```bash
# On the server
cd /opt/kirby

# Backup database first
docker exec kirby_timescaledb pg_dump -U kirby_user kirby > backup_pre_update.sql

# Pull latest code
git pull origin main

# Update dependencies
poetry install --no-dev

# Run any new migrations
poetry run alembic upgrade head

# Restart services
sudo systemctl restart kirby-collectors
sudo systemctl restart kirby-api

# Check status
sudo systemctl status kirby-collectors
sudo systemctl status kirby-api

# Monitor logs for errors
sudo journalctl -u kirby-collectors -f
```

---

## Backup & Disaster Recovery

### Automated Backups

```bash
# Create backup script
sudo nano /opt/kirby/scripts/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/kirby/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker exec kirby_timescaledb pg_dump -U kirby_user kirby | gzip > $BACKUP_DIR/kirby_$DATE.sql.gz

# Upload to S3 (optional)
# aws s3 cp $BACKUP_DIR/kirby_$DATE.sql.gz s3://your-bucket/backups/

# Delete old backups
find $BACKUP_DIR -name "kirby_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: kirby_$DATE.sql.gz"
```

```bash
# Make executable
chmod +x /opt/kirby/scripts/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
```

```cron
0 2 * * * /opt/kirby/scripts/backup.sh >> /var/log/kirby-backup.log 2>&1
```

### Recovery

```bash
# Stop services
sudo systemctl stop kirby-collectors
sudo systemctl stop kirby-api

# Restore database
gunzip -c /opt/kirby/backups/kirby_20251024_020000.sql.gz | docker exec -i kirby_timescaledb psql -U kirby_user kirby

# Run migrations (in case of version mismatch)
cd /opt/kirby
poetry run alembic upgrade head

# Restart services
sudo systemctl start kirby-collectors
sudo systemctl start kirby-api
```

---

## Support

For issues or questions:
- GitHub Issues: [your-repo/issues]
- Documentation: [ARCHITECTURE.md](ARCHITECTURE.md), [README.md](README.md)
- Logs: `sudo journalctl -u kirby-collectors -f`