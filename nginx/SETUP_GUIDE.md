# Nginx Reverse Proxy Setup Guide

## Overview

This guide sets up Nginx as a reverse proxy to provide a single entry point for your Sea Level Dashboard.

**Before:**
- Dashboard: `http://5.102.231.16:30887/`
- API: `http://5.102.231.16:30886/api/`

**After:**
- Dashboard: `http://5.102.231.16/`
- API: `http://5.102.231.16/api/`
- API Docs: `http://5.102.231.16/docs`

---

## Installation (Ubuntu/Debian)

```bash
# Update packages
sudo apt update

# Install Nginx
sudo apt install nginx -y

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Check status
sudo systemctl status nginx
```

---

## Configuration

### Step 1: Copy Configuration File

```bash
# Copy the config file to Nginx sites-available
sudo cp nginx.conf /etc/nginx/sites-available/sea-level-dashboard

# Create symlink to sites-enabled
sudo ln -s /etc/nginx/sites-available/sea-level-dashboard /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default
```

### Step 2: Test Configuration

```bash
# Test for syntax errors
sudo nginx -t

# Expected output:
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Step 3: Reload Nginx

```bash
sudo systemctl reload nginx
```

---

## Firewall Configuration

```bash
# Allow HTTP traffic on port 80
sudo ufw allow 80/tcp

# Allow HTTPS traffic on port 443 (for future SSL)
sudo ufw allow 443/tcp

# Optionally, block direct access to backend ports from outside
sudo ufw deny 30886/tcp
sudo ufw deny 30887/tcp

# Check firewall status
sudo ufw status
```

---

## Verification

### Test the URLs:

```bash
# Test frontend (should show dashboard)
curl -I http://5.102.231.16/

# Test API health
curl http://5.102.231.16/api/health

# Test API stations
curl http://5.102.231.16/api/stations

# Test API docs
curl -I http://5.102.231.16/docs
```

---

## Adding SSL (HTTPS) with Let's Encrypt

If you have a domain name, you can add free SSL:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com

# Certbot will automatically update Nginx config for HTTPS
# Certificate auto-renewal is set up automatically
```

---

## Troubleshooting

### Check Nginx logs:
```bash
# Access log
sudo tail -f /var/log/nginx/access.log

# Error log
sudo tail -f /var/log/nginx/error.log
```

### Common Issues:

1. **502 Bad Gateway**: Backend service not running
   ```bash
   # Check if backend is running
   curl http://127.0.0.1:30886/health
   ```

2. **504 Gateway Timeout**: Backend taking too long
   - Increase `proxy_read_timeout` in nginx.conf

3. **Connection refused**: Check firewall and services
   ```bash
   sudo ufw status
   sudo systemctl status nginx
   ```

---

## Client URLs After Setup

| Purpose | URL |
|---------|-----|
| **Web Dashboard** | `http://5.102.231.16/` |
| **API Base** | `http://5.102.231.16/api/` |
| **API Documentation** | `http://5.102.231.16/docs` |
| **Health Check** | `http://5.102.231.16/api/health` |

### Example API Calls:

```bash
# Get stations
curl "http://5.102.231.16/api/stations"

# Get data for Haifa
curl "http://5.102.231.16/api/data?station=Haifa&start_date=2025-01-01&end_date=2025-01-07"

# Get batch data
curl "http://5.102.231.16/api/data/batch?stations=Haifa,Ashdod&start_date=2025-01-01&end_date=2025-01-07"

# Get sea forecast
curl "http://5.102.231.16/api/sea-forecast"
```

---

## Windows Alternative (if not using Linux)

If your server runs Windows, you can use **IIS** with URL Rewrite module or install Nginx for Windows:

1. Download Nginx for Windows: https://nginx.org/en/download.html
2. Extract to `C:\nginx`
3. Copy `nginx.conf` to `C:\nginx\conf\nginx.conf`
4. Run: `C:\nginx\nginx.exe`

Or consider using **Caddy** (simpler configuration):
```
:80 {
    reverse_proxy /api/* localhost:30886
    reverse_proxy /* localhost:30887
}
```
