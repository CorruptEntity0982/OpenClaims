# Lattice EC2 Deployment Guide

This guide will walk you through deploying the Lattice application on an AWS EC2 instance with HTTPS enabled using your domain `lattice.soldeck.com`.

## Prerequisites

- AWS Account with EC2 access
- Domain name (soldeck.com) with access to DNS settings
- SSH key pair for EC2 access
- Required API keys (AWS, OpenAI)

## Table of Contents

1. [EC2 Instance Setup](#1-ec2-instance-setup)
2. [DNS Configuration](#2-dns-configuration)
3. [Server Initial Setup](#3-server-initial-setup)
4. [Install Required Software](#4-install-required-software)
5. [Clone and Configure Application](#5-clone-and-configure-application)
6. [Setup Nginx Reverse Proxy](#6-setup-nginx-reverse-proxy)
7. [SSL Certificate Setup](#7-ssl-certificate-setup)
8. [Deploy Application](#8-deploy-application)
9. [Verify Deployment](#9-verify-deployment)
10. [Maintenance & Monitoring](#10-maintenance--monitoring)

---

## 1. EC2 Instance Setup

### 1.1 Launch EC2 Instance

1. Go to AWS EC2 Console
2. Click "Launch Instance"
3. **Configuration:**
   - **Name:** `lattice-production`
   - **AMI:** Ubuntu Server 22.04 LTS (Free tier eligible)
   - **Instance Type:** 
     - Minimum: `t3.medium` (2 vCPU, 4GB RAM)
     - Recommended: `t3.large` (2 vCPU, 8GB RAM) for better Neo4j performance
   - **Key Pair:** Create new or use existing SSH key pair (download and save it!)
   - **Network Settings:**
     - Create new security group or use existing
     - Allow SSH (port 22) from your IP
     - Allow HTTP (port 80) from anywhere (0.0.0.0/0)
     - Allow HTTPS (port 443) from anywhere (0.0.0.0/0)
   - **Storage:** 30-50 GB gp3 SSD (depending on expected data volume)

4. Click "Launch Instance"
5. Wait for instance state to be "Running"
6. Note down the **Public IPv4 address** (e.g., `54.123.45.67`)

### 1.2 Security Group Configuration

Ensure your security group has these inbound rules:

| Type  | Protocol | Port Range | Source    | Description           |
|-------|----------|------------|-----------|-----------------------|
| SSH   | TCP      | 22         | Your IP   | SSH access            |
| HTTP  | TCP      | 80         | 0.0.0.0/0 | HTTP traffic          |
| HTTPS | TCP      | 443        | 0.0.0.0/0 | HTTPS traffic         |

---

## 2. DNS Configuration

### 2.1 Create A Record for Subdomain

1. Log in to your domain registrar or DNS provider (where soldeck.com is hosted)
2. Navigate to DNS settings for `soldeck.com`
3. Add an **A Record:**
   - **Host/Name:** `lattice`
   - **Type:** `A`
   - **Value/Points to:** Your EC2 Public IPv4 address (from step 1.1)
   - **TTL:** 300 (5 minutes) or default
4. Save the record

**DNS propagation can take 5-60 minutes. You can check propagation using:**
```bash
# On your local machine
dig lattice.soldeck.com
# or
nslookup lattice.soldeck.com
```

---

## 3. Server Initial Setup

### 3.1 Connect to EC2 Instance

On your local machine:

```bash
# Set correct permissions for your key file
chmod 400 /path/to/your-key-pair.pem

# SSH into the instance
ssh -i /path/to/your-key-pair.pem ubuntu@lattice.soldeck.com
# or use the IP directly if DNS isn't propagated yet:
# ssh -i /path/to/your-key-pair.pem ubuntu@54.123.45.67
```

### 3.2 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.3 Set up Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 4. Install Required Software

### 4.1 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Log out and log back in for group changes to take effect
exit
```

Then SSH back in:
```bash
ssh -i /path/to/your-key-pair.pem ubuntu@lattice.soldeck.com
```

Verify installation:
```bash
docker --version
docker compose version
```

### 4.2 Install Nginx

```bash
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx
```

### 4.3 Install Certbot (for SSL)

```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 4.4 Install Git

```bash
sudo apt install git -y
```

---

## 5. Clone and Configure Application

### 5.1 Clone Repository

```bash
cd ~
# Clone your repository (replace with your actual git URL)
git clone <your-repository-url> lattice
cd lattice
```

**If your repo is private, you'll need to set up authentication:**
```bash
# Option 1: Using Personal Access Token
git clone https://<token>@github.com/your-username/lattice.git

# Option 2: Using SSH (recommended)
# First, generate SSH key on EC2 and add to GitHub
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
# Copy this public key and add it to GitHub Settings > SSH Keys
git clone git@github.com:your-username/lattice.git
```

### 5.2 Configure Environment Variables

```bash
cd ~/lattice

# Create production environment file
cp .env.production.example .env.production

# Edit with your actual values
nano .env.production
```

Fill in all the required values:
```env
POSTGRES_PASSWORD=your_secure_postgres_password_here
NEO4J_PASSWORD=your_secure_neo4j_password_here
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_s3_bucket_name
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
```

Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`.

Set proper permissions:
```bash
chmod 600 .env.production
```

---

## 6. Setup Nginx Reverse Proxy

### 6.1 Configure Nginx

```bash
# Copy the nginx configuration
sudo cp ~/lattice/nginx-reverse-proxy.conf /etc/nginx/sites-available/lattice

# Create symbolic link to enable the site
sudo ln -s /etc/nginx/sites-available/lattice /etc/nginx/sites-enabled/

# Remove default nginx site
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t
```

**Note:** The SSL certificate paths in the config don't exist yet. We'll generate them in the next step.

### 6.2 Temporarily Modify Config for Certbot

We need to comment out SSL lines temporarily to get the certificate:

```bash
sudo nano /etc/nginx/sites-available/lattice
```

Comment out these lines in the HTTPS server block by adding `#` at the start:
```nginx
#    ssl_certificate /etc/letsencrypt/live/lattice.soldeck.com/fullchain.pem;
#    ssl_certificate_key /etc/letsencrypt/live/lattice.soldeck.com/privkey.pem;
```

Save and test:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. SSL Certificate Setup

### 7.1 Obtain SSL Certificate

```bash
# Make sure DNS is propagated first!
# Test with: dig lattice.soldeck.com

# Create directory for certbot challenge
sudo mkdir -p /var/www/certbot

# Obtain certificate
sudo certbot certonly --webroot \
  -w /var/www/certbot \
  -d lattice.soldeck.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive
```

If successful, you'll see:
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/lattice.soldeck.com/fullchain.pem
Key is saved at: /etc/letsencrypt/live/lattice.soldeck.com/privkey.pem
```

### 7.2 Enable SSL in Nginx

```bash
# Uncomment the SSL lines we commented earlier
sudo nano /etc/nginx/sites-available/lattice
```

Remove the `#` from:
```nginx
    ssl_certificate /etc/letsencrypt/live/lattice.soldeck.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lattice.soldeck.com/privkey.pem;
```

Save, test, and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 7.3 Set Up Auto-Renewal

```bash
# Test renewal process
sudo certbot renew --dry-run

# Certbot automatically installs a cron job, verify it:
sudo systemctl status certbot.timer
```

---

## 8. Deploy Application

### 8.1 Build and Start Containers

```bash
cd ~/lattice

# Build and start all services
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

This will:
- Build the backend, frontend, and worker images
- Start PostgreSQL, Redis, Neo4j
- Start the application services

### 8.2 Check Container Status

```bash
docker compose -f docker-compose.prod.yml ps
```

All services should show "Up" or "healthy" status.

### 8.3 View Logs

```bash
# View all logs
docker compose -f docker-compose.prod.yml logs

# View specific service logs
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs frontend

# Follow logs in real-time
docker compose -f docker-compose.prod.yml logs -f
```

### 8.4 Run Database Migrations

```bash
# Run Alembic migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 9. Verify Deployment

### 9.1 Check Services

1. **Frontend:** https://lattice.soldeck.com
   - Should load your React application
   - Check browser console for errors

2. **Backend API:** https://lattice.soldeck.com/api/health
   - Should return a health check response

3. **API Docs:** https://lattice.soldeck.com/docs
   - Should show FastAPI Swagger documentation

4. **Neo4j Browser:** http://lattice.soldeck.com:7474
   - Only if you opened port 7474 in security group
   - Not recommended for production (security risk)

### 9.2 Test Functionality

Test core features:
- Upload a document
- Verify processing
- Check patient data retrieval

### 9.3 Check SSL Certificate

```bash
# Check certificate details
echo | openssl s_client -servername lattice.soldeck.com -connect lattice.soldeck.com:443 2>/dev/null | openssl x509 -noout -dates
```

---

## 10. Maintenance & Monitoring

### 10.1 Useful Commands

```bash
# Check system resources
htop
docker stats

# View docker logs
docker compose -f docker-compose.prod.yml logs -f [service_name]

# Restart a service
docker compose -f docker-compose.prod.yml restart [service_name]

# Stop all services
docker compose -f docker-compose.prod.yml down

# Start all services
docker compose -f docker-compose.prod.yml up -d

# Update application (pull latest code and rebuild)
cd ~/lattice
git pull
docker compose -f docker-compose.prod.yml up -d --build

# Clean up old images
docker system prune -a
```

### 10.2 Backup Strategy

**Database Backup:**
```bash
# Backup PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U postgres lattice > backup_$(date +%Y%m%d).sql

# Backup Neo4j
docker compose -f docker-compose.prod.yml exec neo4j neo4j-admin database dump neo4j --to-path=/data
```

**Automated Backups:**
Create a cron job:
```bash
crontab -e
```

Add daily backup at 2 AM:
```cron
0 2 * * * cd ~/lattice && docker compose -f docker-compose.prod.yml exec postgres pg_dump -U postgres lattice > ~/backups/lattice_$(date +\%Y\%m\%d).sql
```

### 10.3 Monitoring

**Install monitoring tools:**
```bash
# Install htop for resource monitoring
sudo apt install htop -y

# Check disk space
df -h

# Check memory usage
free -h

# Check docker resource usage
docker stats
```

**Log rotation:**
Docker automatically rotates logs, but you can configure it in `/etc/docker/daemon.json`:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### 10.4 Security Best Practices

1. **Keep system updated:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Limit SSH access to specific IPs in security group**

3. **Use strong passwords for all services**

4. **Regularly rotate API keys and credentials**

5. **Monitor application logs for suspicious activity**

6. **Set up CloudWatch or similar monitoring**

7. **Enable AWS backup for EC2 instance (snapshots)**

### 10.5 Troubleshooting

**Issue: Can't connect to website**
- Check DNS: `dig lattice.soldeck.com`
- Check nginx: `sudo systemctl status nginx`
- Check nginx logs: `sudo tail -f /var/log/nginx/error.log`
- Check security group allows ports 80 and 443
- Check if Docker containers are running: `docker ps`

**Issue: SSL certificate errors**
- Verify certificate: `sudo certbot certificates`
- Check nginx config: `sudo nginx -t`
- Renew certificate: `sudo certbot renew`

**Issue: Application errors**
- Check logs: `docker compose -f docker-compose.prod.yml logs`
- Check environment variables: `cat .env.production`
- Verify all external services (AWS, OpenAI) are accessible
- Check available disk space: `df -h`

**Issue: Out of memory**
- Increase instance size
- Check for memory leaks in logs
- Restart services: `docker compose -f docker-compose.prod.yml restart`

**Issue: Database connection errors**
- Check if PostgreSQL is running: `docker ps | grep postgres`
- Check connection string in .env.production
- View PostgreSQL logs: `docker compose -f docker-compose.prod.yml logs postgres`

---

## Quick Reference

### Essential Files
- **Production compose:** `docker-compose.prod.yml`
- **Environment:** `.env.production`
- **Nginx config:** `/etc/nginx/sites-available/lattice`
- **SSL certificates:** `/etc/letsencrypt/live/lattice.soldeck.com/`

### Essential Commands
```bash
# Application directory
cd ~/lattice

# Start application
docker compose -f docker-compose.prod.yml up -d

# Stop application
docker compose -f docker-compose.prod.yml down

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart nginx
sudo systemctl restart nginx

# Update application
git pull && docker compose -f docker-compose.prod.yml up -d --build
```

### Support URLs
- Frontend: https://lattice.soldeck.com
- API Health: https://lattice.soldeck.com/api/health
- API Docs: https://lattice.soldeck.com/docs

---

## Conclusion

Your Lattice application should now be running securely on EC2 with HTTPS! 

If you encounter any issues during deployment, refer to the Troubleshooting section or check the logs for specific error messages.

For production deployments, consider:
- Setting up CloudWatch monitoring
- Implementing log aggregation (ELK stack or similar)
- Creating automated backups
- Setting up CI/CD pipeline
- Implementing rate limiting
- Adding a CDN (CloudFront) for better performance
