# Kirby - Digital Ocean Deployment Guide

This guide will walk you through deploying the Kirby cryptocurrency data platform to Digital Ocean.

## Prerequisites

- Digital Ocean account
- SSH key added to your Digital Ocean account
- Git installed locally
- Access to the Kirby GitHub repository

## Architecture Overview

The deployment consists of 3 Docker containers:
- **TimescaleDB**: Time-series database for candle data
- **API**: FastAPI REST API server
- **Collectors**: WebSocket collectors for real-time data

## Step 1: Create Digital Ocean Droplet

### Option A: Using the Digital Ocean Web Interface

1. Log in to [Digital Ocean](https://cloud.digitalocean.com)
2. Click **Create** → **Droplets**
3. Choose configuration:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic
   - **CPU options**: Regular (2 GB RAM / 1 CPU minimum, **4 GB RAM / 2 CPU recommended**)
   - **Datacenter**: Choose closest to your location
   - **Authentication**: SSH keys (select your key)
   - **Hostname**: `kirby-production`
4. Click **Create Droplet**
5. Note your droplet's IP address

### Option B: Using doctl CLI

```bash
# Install doctl (if not already installed)
# macOS
brew install doctl

# Linux
cd ~
wget https://github.com/digitalocean/doctl/releases/download/v1.94.0/doctl-1.94.0-linux-amd64.tar.gz
tar xf doctl-1.94.0-linux-amd64.tar.gz
sudo mv doctl /usr/local/bin

# Authenticate
doctl auth init

# Create droplet
doctl compute droplet create kirby-production \
  --image ubuntu-22-04-x64 \
  --size s-2vcpu-4gb \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1)

# Get IP address
doctl compute droplet list
```

## Step 2: Initial Server Setup

SSH into your droplet:

```bash
ssh root@YOUR_DROPLET_IP
```

### Update system and install dependencies:

```bash
# Update package list
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Install Git
apt install git -y

# Create application user
useradd -m -s /bin/bash kirby
usermod -aG docker kirby

# Create app directory
mkdir -p /opt/kirby
chown kirby:kirby /opt/kirby
```

## Step 3: Clone Repository

Switch to kirby user and clone the repository:

```bash
# Switch to kirby user
su - kirby

# Clone repository
cd /opt/kirby
git clone https://github.com/oakwoodgates/kirby.git .

# Verify files
ls -la
```

## Step 4: Configure Environment

Create production environment file:

```bash
# Copy production template
cp .env.production .env

# Edit environment file
nano .env
```

Update the following values in `.env`:

```bash
# IMPORTANT: Change this password!
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD_HERE

# Optional: Adjust these if needed
API_PORT=8000
API_WORKERS=2
LOG_LEVEL=INFO
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

## Step 5: Deploy Application

Run the deployment script:

```bash
cd /opt/kirby
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

The script will:
1. Pull latest code
2. Build Docker images
3. Start containers
4. Run database migrations
5. Optionally seed the database
6. Verify services are running

**When prompted to seed the database, answer `y` (yes) on first deployment.**

## Step 6: Configure Firewall

Set up UFW firewall:

```bash
# Exit kirby user back to root
exit

# Configure firewall
ufw allow OpenSSH
ufw allow 8000/tcp  # API port
ufw --force enable

# Verify firewall status
ufw status
```

## Step 7: Verify Deployment

### Check container status:

```bash
su - kirby
cd /opt/kirby
docker compose -f docker/docker-compose.prod.yml --env-file .env ps
```

All containers should show status "Up".

### Check API health:

```bash
curl http://localhost:8000/api/v1/health
```

Should return:
```json
{
  "status": "ok",
  "timestamp": "..."
}
```

### Check database health:

```bash
curl http://localhost:8000/api/v1/health/database
```

Should return database stats with candle counts.

### Check multi-interval stats:

```bash
curl http://localhost:8000/api/v1/market/intervals/overview
```

Should return interval statistics for all listings.

## Step 8: Monitor Collectors

View collector logs to verify data collection:

```bash
cd /opt/kirby
docker compose -f docker/docker-compose.prod.yml --env-file .env logs -f collectors
```

You should see:
- WebSocket connections established
- Candle data being received for all intervals (1m, 15m, 4h, 1d)
- Data being stored to database

Press `Ctrl+C` to stop viewing logs.

## Step 9: Optional - Run Backfill

To backfill historical data:

```bash
# Enter API container
docker exec -it kirby_api bash

# Run backfill for last 30 days
python scripts/run_backfill.py \
  --listing-ids 1 2 \
  --data-types candles \
  --days 30

# Exit container
exit
```

## Step 10: Set Up Domain (Optional)

If you want to access the API via a domain name:

### Install Nginx:

```bash
# As root
apt install nginx -y

# Configure Nginx
nano /etc/nginx/sites-available/kirby
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
ln -s /etc/nginx/sites-available/kirby /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Allow HTTP through firewall
ufw allow 'Nginx Full'
```

### Add SSL with Let's Encrypt (Recommended):

```bash
apt install certbot python3-certbot-nginx -y
certbot --nginx -d api.yourdomain.com
```

## Management Commands

### View logs:

```bash
cd /opt/kirby

# All services
docker compose -f docker/docker-compose.prod.yml --env-file .env logs -f

# Specific service
docker compose -f docker/docker-compose.prod.yml --env-file .env logs -f api
docker compose -f docker/docker-compose.prod.yml --env-file .env logs -f collectors
docker compose -f docker/docker-compose.prod.yml --env-file .env logs -f timescaledb
```

### Restart services:

```bash
cd /opt/kirby

# Restart all
docker compose -f docker/docker-compose.prod.yml --env-file .env restart

# Restart specific service
docker compose -f docker/docker-compose.prod.yml --env-file .env restart collectors
```

### Stop services:

```bash
cd /opt/kirby
docker compose -f docker/docker-compose.prod.yml --env-file .env down
```

### Update deployment:

```bash
cd /opt/kirby
git pull origin main
./deploy/deploy.sh
```

### Access database:

```bash
docker exec -it kirby_timescaledb psql -U kirby_user -d kirby

# Example queries
SELECT interval, COUNT(*) FROM candle GROUP BY interval;
SELECT * FROM listing;
\q  # to exit
```

### Backup database:

```bash
docker exec kirby_timescaledb pg_dump -U kirby_user kirby > backup_$(date +%Y%m%d).sql
```

### Restore database:

```bash
docker exec -i kirby_timescaledb psql -U kirby_user kirby < backup_20241024.sql
```

## Monitoring

### Check disk usage:

```bash
df -h
docker system df
```

### Check memory usage:

```bash
free -h
docker stats --no-stream
```

### Set up automatic updates (Optional):

```bash
# Create update cron job
crontab -e

# Add this line to pull updates daily at 3 AM
0 3 * * * cd /opt/kirby && git pull origin main && ./deploy/deploy.sh > /tmp/kirby-deploy.log 2>&1
```

## Troubleshooting

### POSTGRES_PASSWORD variable not set:

If you see "POSTGRES_PASSWORD variable is not set" during deployment:

```bash
# 1. Ensure .env file exists in project root
cd /opt/kirby
ls -la .env

# 2. Check if password is set
cat .env | grep POSTGRES_PASSWORD
# Should show: POSTGRES_PASSWORD=your_actual_password

# 3. If it shows CHANGE_ME_TO_SECURE_PASSWORD, edit it:
nano .env
# Change the password to a real value, save and exit

# 4. Clean up and redeploy
docker compose -f docker/docker-compose.prod.yml --env-file .env down -v
./deploy/deploy.sh
```

**Note:** The deploy.sh script automatically uses `--env-file .env` to load environment variables correctly.

### API not responding:

```bash
# Check if container is running
docker ps

# Check API logs
cd /opt/kirby
docker compose -f docker/docker-compose.prod.yml --env-file .env logs api

# Restart API
docker compose -f docker/docker-compose.prod.yml --env-file .env restart api
```

### Collectors not collecting data:

```bash
# Check collector logs
cd /opt/kirby
docker compose -f docker/docker-compose.prod.yml --env-file .env logs collectors

# Common issues:
# - Network connectivity
# - Database connection
# - Invalid listing configuration

# Restart collectors
docker compose -f docker/docker-compose.prod.yml --env-file .env restart collectors
```

### Database connection issues:

```bash
# Check if database is running
docker ps | grep timescaledb

# Check database logs
cd /opt/kirby
docker compose -f docker/docker-compose.prod.yml --env-file .env logs timescaledb

# Test connection
docker exec kirby_timescaledb pg_isready -U kirby_user
```

### Out of disk space:

```bash
# Clean up Docker
docker system prune -a

# Remove old logs
journalctl --vacuum-time=7d
```

## Performance Tuning

### For 4GB RAM Droplet:

Default configuration should work well.

### For 8GB+ RAM Droplet:

Update `.env`:
```bash
API_WORKERS=4  # Increase API workers
```

Then redeploy:
```bash
./deploy/deploy.sh
```

## Security Recommendations

1. **Change default password**: Always use a strong, unique password for `POSTGRES_PASSWORD`
2. **Enable firewall**: Only open necessary ports (SSH, API)
3. **Regular updates**: Keep system and Docker images updated
4. **Use SSH keys**: Disable password authentication for SSH
5. **Enable SSL**: Use Let's Encrypt for HTTPS if using a domain
6. **Backup regularly**: Set up automated database backups
7. **Monitor logs**: Check logs regularly for suspicious activity

## Support

For issues or questions:
- Check logs first: `docker compose -f docker/docker-compose.prod.yml --env-file .env logs`
- Review this guide
- Check GitHub issues: https://github.com/oakwoodgates/kirby/issues

## Next Steps

After successful deployment:
1. Monitor collectors for 24 hours to ensure stable data collection
2. Set up monitoring/alerting (optional)
3. Configure automatic backups
4. Plan for scaling if needed

---

**Congratulations! Your Kirby instance is now running on Digital Ocean!**
