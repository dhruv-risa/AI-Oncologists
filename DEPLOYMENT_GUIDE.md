# AI Oncologist - Deployment Guide for Managers

This guide provides step-by-step instructions for deploying the AI Oncologist application on any server or production environment.

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Environment Configuration (.env File)](#environment-configuration-env-file)
- [Step-by-Step Deployment](#step-by-step-deployment)
- [Post-Deployment Verification](#post-deployment-verification)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

---

## Overview

The AI Oncologist system consists of:
- **Backend**: FastAPI server (Python) running on port 8000
- **Frontend**: React dashboard (optional) running on port 5173
- **Database**: SQLite for data caching
- **External Services**:
  - Google Drive API (for document storage)
  - FHIR API (for EMR integration)
  - Risa Labs AI Service (for AI-powered data extraction)

**First Load Time**: 10-30 seconds (fetches from FHIR, uploads to Drive, extracts with AI)
**Subsequent Loads**: < 1 second (served from cache)

---

## System Requirements

### Software Requirements
- **Python**: Version 3.7 or higher
- **pip**: Python package manager
- **Node.js**: Version 16 or higher (only if deploying frontend)
- **npm**: Node package manager (only if deploying frontend)

### Hardware Requirements
- **CPU**: 2+ cores recommended
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB minimum (for dependencies and data cache)
- **Network**: Stable internet connection for API calls

### Operating System
- Linux (Ubuntu 20.04+, CentOS 7+, etc.)
- macOS 10.15+
- Windows Server 2016+ (with WSL recommended)

---

## Pre-Deployment Checklist

Before deployment, ensure you have:

- [ ] Server/machine with required specifications
- [ ] Google Cloud Project with Drive API enabled
- [ ] Google OAuth credentials (credentials.json file)
- [ ] Google authentication token (token.pickle file)
- [ ] FHIR API access credentials (if using)
- [ ] Server admin/sudo access (for installation)
- [ ] SSL certificate (for production HTTPS)

---

## Environment Configuration (.env File)

The `.env` file contains all sensitive configuration and credentials. This file MUST be created in the project root directory.

### Understanding the .env File Structure

```bash
# ============================================================================
# Google Drive Credentials
# ============================================================================
GOOGLE_CREDENTIALS_BASE64=<base64_encoded_credentials>
GOOGLE_TOKEN_BASE64=<base64_encoded_token>

# ============================================================================
# FHIR API Credentials (Optional - if using direct FHIR access)
# ============================================================================
RISALABS_USERNAME=your_username@example.com
RISALABS_PASSWORD=your_password
```

### What Each Variable Means

#### 1. GOOGLE_CREDENTIALS_BASE64 (Required)

**Purpose**: Base64-encoded version of your Google OAuth credentials file (`credentials.json`)

**What it does**: Allows the application to authenticate with Google Drive API to upload and manage PDF files

**How to generate**:

1. **Get credentials.json from Google Cloud Console**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable "Google Drive API":
     - Navigate to "APIs & Services" → "Library"
     - Search for "Google Drive API"
     - Click "Enable"
   - Create OAuth 2.0 Credentials:
     - Go to "APIs & Services" → "Credentials"
     - Click "Create Credentials" → "OAuth client ID"
     - Choose "Desktop app" as application type
     - Name it (e.g., "AI Oncologist PDF Uploader")
     - Click "Create"
   - Download the credentials file (it will be named something like `client_secret_xxx.json`)
   - Rename it to `credentials.json`

2. **Convert to Base64**:

   On Linux/macOS:
   ```bash
   base64 -i credentials.json -o credentials_base64.txt
   ```

   On Windows (PowerShell):
   ```powershell
   [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("credentials.json")) | Out-File credentials_base64.txt
   ```

3. **Add to .env**:
   - Open `credentials_base64.txt`
   - Copy the entire base64 string (it will be very long, possibly multiple lines)
   - Paste it as one continuous line after `GOOGLE_CREDENTIALS_BASE64=`
   - Remove any line breaks within the base64 string

**Example**:
```bash
GOOGLE_CREDENTIALS_BASE64=eyJpbnN0YWxsZWQiOnsiY2xpZW50X2lkIjoiOTYyMjE1MjI2NDE2LWZkZGZkMHJnaWFncms4dm1uNWY5am1oc2ZrY2dkb3AyLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwicHJvamVjdF9pZCI6InRydWUtd2ludGVyLTQ4MzcwNS12OCIsImF1dGhfdXJpIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLCJ0b2tlbl91cmkiOiJodHRwczovL29hdXRoMi5nb29nbGVhcGlzLmNvbS90b2tlbiIsImF1dGhfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6Imh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL29hdXRoMi92MS9jZXJ0cyIsImNsaWVudF9zZWNyZXQiOiJHT0NTUFgteW15ZGZKS2oxQ1lmaFFuYmRUODd0bUY2WEhFYiIsInJlZGlyZWN0X3VyaXMiOlsiaHR0cDovL2xvY2FsaG9zdCJdfX0=
```

#### 2. GOOGLE_TOKEN_BASE64 (Required)

**Purpose**: Base64-encoded version of your Google authentication token (`token.pickle`)

**What it does**: Contains the OAuth token that allows the application to access Google Drive without repeated login prompts

**How to generate**:

**IMPORTANT**: You must first create the `token.pickle` file through initial authentication before encoding it.

1. **Generate token.pickle** (First-time authentication):

   ```bash
   # Create a temporary Python script to authenticate
   python3 << 'EOF'
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive.file']

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

with open('token.pickle', 'wb') as token:
    pickle.dump(creds, token)
print("token.pickle created successfully!")
EOF
   ```

   - This will open a browser window
   - Login with your Google account
   - Grant permissions to access Google Drive
   - The `token.pickle` file will be created automatically

2. **Convert to Base64**:

   On Linux/macOS:
   ```bash
   base64 -i token.pickle -o token_base64.txt
   ```

   On Windows (PowerShell):
   ```powershell
   [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("token.pickle")) | Out-File token_base64.txt
   ```

3. **Add to .env**:
   - Open `token_base64.txt`
   - Copy the entire base64 string
   - Paste it as one continuous line after `GOOGLE_TOKEN_BASE64=`
   - Remove any line breaks within the base64 string

**Example**:
```bash
GOOGLE_TOKEN_BASE64=gAWV/AMAAAAAAACMGWdvb2dsZS5vYXV0aDIuY3JlZGVudGlhbHOUjAtDcmVkZW50aWFsc5STlCmBlH2UKIwFdG9rZW6UjP55YTI5LmEwQVVNV2dfS2hWcDJZbUhmN3ZnT3BDeHloeTRTNW8wcVZZc1FoZHdqVzNQWXRILXYwcFM2SERJRlVEek9PdnNPNjIxNU13V1JkLW1NME41U0lBMS0ta2NOTS01RW1mVXNGQW9XZ3lJWEFFMHp3SHJaazFZeE1uWGRqb2JrTEs3RnI3X1FEcmFiUUUyMEVwMmdPa2dLNGtZc2hsYTc0RF9hTExWQnRLM0VrYVhPQ0VTUUlNa0ktcF9NaFVnTmQxRGlsM241LTdTUUVhQ2dZS0FlRVNBUllTRlFIR1gyTWkxVGM3UC1CTFdYSG5RTEt3WDhpLTBnMDIwN5SMBmV4cGlyeZSMCGRhdGV0aW1llIwIZGF0ZXRpbWWUk5RDCgfqAQ8GIC4EE/+UhZRSlA==
```

#### 3. RISALABS_USERNAME and RISALABS_PASSWORD (Optional)

**Purpose**: Credentials for direct FHIR API access (if your deployment uses external FHIR)

**What it does**: Authenticates with the FHIR server to retrieve patient medical records

**How to set**:
```bash
RISALABS_USERNAME=your_username@example.com
RISALABS_PASSWORD=your_secure_password
```

**Note**: These are optional. The current system uses Risa Labs AI service which handles authentication internally. Only add these if you need direct FHIR access.

---

## Step-by-Step Deployment

### Step 1: Prepare the Server

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
# OR
sudo yum update -y  # CentOS/RHEL

# Install Python 3 and pip
sudo apt install python3 python3-pip -y  # Ubuntu/Debian
# OR
sudo yum install python3 python3-pip -y  # CentOS/RHEL

# Verify installation
python3 --version
pip3 --version
```

### Step 2: Transfer Project Files

Upload the entire project directory to your server using one of these methods:

**Option A: Using SCP (from your local machine)**
```bash
scp -r "/Users/dhruvsaraswat/Desktop/AI Oncologist" user@server-ip:/path/to/deployment/
```

**Option B: Using Git (if using version control)**
```bash
git clone <your-repository-url>
cd AI-Oncologist
```

**Option C: Using rsync**
```bash
rsync -avz "/Users/dhruvsaraswat/Desktop/AI Oncologist" user@server-ip:/path/to/deployment/
```

### Step 3: Create .env File

On the server, navigate to the project root and create the `.env` file:

```bash
cd "/path/to/AI Oncologist"

# Create .env file
nano .env
```

Paste the complete environment configuration:

```bash
# ============================================================================
# Google Drive Credentials
# ============================================================================
GOOGLE_CREDENTIALS_BASE64=<paste_your_base64_credentials_here>
GOOGLE_TOKEN_BASE64=<paste_your_base64_token_here>

# ============================================================================
# FHIR API Credentials (Optional)
# ============================================================================
# RISALABS_USERNAME=your_username@example.com
# RISALABS_PASSWORD=your_password
```

Save and exit (Ctrl+X, then Y, then Enter in nano).

**CRITICAL**: Verify there are no line breaks within the base64 strings!

### Step 4: Install Python Dependencies

```bash
# Navigate to project directory
cd "/path/to/AI Oncologist"

# Install required packages
pip3 install -r requirements.txt

# Verify installation
pip3 list | grep -E "fastapi|uvicorn|google"
```

Expected packages:
- fastapi
- uvicorn
- google-api-python-client
- google-auth-oauthlib
- requests
- python-dotenv
- pydantic

### Step 5: Test the Backend

```bash
# Start the backend server
python3 Backend/app.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Test the API** (open a new terminal):
```bash
curl http://localhost:8000/docs
```

You should see the Swagger UI documentation.

### Step 6: Set Up as a System Service (Production)

For production deployment, create a systemd service to keep the application running:

```bash
# Create service file
sudo nano /etc/systemd/system/ai-oncologist.service
```

Paste this configuration:

```ini
[Unit]
Description=AI Oncologist FastAPI Backend
After=network.target

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/path/to/AI Oncologist
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/AI Oncologist/Backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace**:
- `<your-username>` with the actual server username
- `/path/to/AI Oncologist` with the actual project path

**Enable and start the service**:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable ai-oncologist

# Start the service
sudo systemctl start ai-oncologist

# Check status
sudo systemctl status ai-oncologist
```

### Step 7: Configure Firewall (if applicable)

```bash
# Allow port 8000
sudo ufw allow 8000/tcp  # Ubuntu/Debian

# OR for CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### Step 8: Set Up Reverse Proxy with Nginx (Production - Optional but Recommended)

```bash
# Install Nginx
sudo apt install nginx -y  # Ubuntu/Debian

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/ai-oncologist
```

Paste this configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable the site**:

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/ai-oncologist /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Step 9: Set Up SSL Certificate (Production - Highly Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Certbot will automatically configure Nginx for HTTPS
```

### Step 10: Deploy Frontend (Optional)

If deploying the frontend dashboard:

```bash
# Navigate to frontend directory
cd "Frontend/Oncology Patient Dashboard 2"

# Install Node.js dependencies
npm install

# Create frontend .env file
nano .env
```

Add:
```bash
VITE_API_BASE_URL=https://your-domain.com  # Or http://localhost:8000 for local
```

**For production build**:
```bash
# Build the frontend
npm run build

# Serve with a static file server
npm install -g serve
serve -s dist -p 5173
```

**Or configure Nginx to serve the frontend**:

```nginx
server {
    listen 80;
    server_name your-frontend-domain.com;

    root /path/to/AI Oncologist/Frontend/Oncology Patient Dashboard 2/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Post-Deployment Verification

### 1. Check Backend Health

```bash
# Test API documentation
curl http://your-domain.com/docs

# Test patient endpoint (should return data)
curl -X POST http://your-domain.com/api/patient/all \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

### 2. Check Google Drive Integration

```bash
# Check logs for Google Drive authentication
sudo journalctl -u ai-oncologist -f

# Should see:
# "Using base64-encoded token from environment variable"
# "Successfully loaded credentials from environment variable"
# "Google Drive service authenticated successfully"
```

### 3. Test Data Pool (Cache)

```bash
# Check cached patients
curl http://your-domain.com/api/pool/patients

# Should return JSON list of cached patient MRNs
```

### 4. Monitor Logs

```bash
# View real-time logs
sudo journalctl -u ai-oncologist -f

# View last 100 lines
sudo journalctl -u ai-oncologist -n 100

# Check for errors
sudo journalctl -u ai-oncologist | grep -i error
```

---

## Troubleshooting

### Issue 1: "GOOGLE_CREDENTIALS_BASE64 not set" or authentication errors

**Cause**: .env file not loaded or base64 strings are incorrect

**Solution**:
```bash
# Check if .env file exists
ls -la /path/to/AI\ Oncologist/.env

# Verify .env file contents (check for line breaks in base64 strings)
cat /path/to/AI\ Oncologist/.env

# Ensure base64 strings are on single lines (no line breaks)
# Re-encode if necessary using the steps in "Environment Configuration" section
```

### Issue 2: "Permission denied" or "File not found" errors

**Cause**: Incorrect file permissions or paths

**Solution**:
```bash
# Fix permissions for entire project
chmod -R 755 /path/to/AI\ Oncologist

# Ensure .env is readable
chmod 644 /path/to/AI\ Oncologist/.env

# Verify Python can import modules
cd /path/to/AI\ Oncologist/Backend
python3 -c "from drive_uploader import authenticate_drive; print('Import successful')"
```

### Issue 3: "Token expired" or "Invalid credentials"

**Cause**: Google OAuth token has expired

**Solution**:
```bash
# Delete the old token and re-generate
rm token.pickle

# Run the authentication script again (from Step 2 of GOOGLE_TOKEN_BASE64 section)
# Then re-encode the new token.pickle to base64
# Update .env with new GOOGLE_TOKEN_BASE64 value

# Restart the service
sudo systemctl restart ai-oncologist
```

### Issue 4: Port 8000 already in use

**Cause**: Another service is using port 8000

**Solution**:
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process (replace PID with actual process ID)
sudo kill -9 <PID>

# Or change the port in Backend/app.py
nano Backend/app.py
# Change: uvicorn.run(app, host="0.0.0.0", port=8000)
# To: uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Issue 5: Service fails to start

**Cause**: Various issues with systemd service configuration

**Solution**:
```bash
# Check service status
sudo systemctl status ai-oncologist

# View detailed logs
sudo journalctl -u ai-oncologist -n 50

# Test running manually to see errors
cd /path/to/AI\ Oncologist
python3 Backend/app.py

# Common fixes:
# 1. Verify WorkingDirectory path in service file
# 2. Verify User has permissions
# 3. Check Python path: which python3
```

### Issue 6: Slow first load (10-30 seconds)

**This is NORMAL behavior!**

First load performs:
- FHIR API calls to fetch documents
- PDF combination and processing
- Google Drive uploads
- AI extraction with Claude

Subsequent loads are instant (< 1 second) due to caching.

**To verify caching is working**:
```bash
# First request (will be slow)
time curl -X POST http://localhost:8000/api/patient/all \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'

# Second request (should be fast)
time curl -X POST http://localhost:8000/api/patient/all \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

---

## Security Considerations

### 1. Protect the .env File

```bash
# Ensure .env is NOT committed to Git
echo ".env" >> .gitignore

# Set restrictive permissions
chmod 600 /path/to/AI\ Oncologist/.env

# Verify owner
chown <your-username>:<your-group> /path/to/AI\ Oncologist/.env
```

### 2. Use HTTPS in Production

- Always use SSL certificates (Let's Encrypt is free)
- Never expose port 8000 directly to the internet
- Use Nginx reverse proxy with SSL

### 3. Database Security

```bash
# Ensure database file has proper permissions
chmod 600 Backend/data_pool.db

# Regularly backup the database
cp Backend/data_pool.db /backup/location/data_pool_$(date +%Y%m%d).db
```

### 4. Google Drive Security

- PDFs are made **publicly accessible** by default
- Ensure compliance with HIPAA and PHI regulations
- Consider using restricted Google Drive folders
- Implement data retention policies

### 5. Access Control

- Implement authentication/authorization in production
- Use environment-specific credentials
- Rotate credentials regularly
- Monitor access logs

### 6. Network Security

```bash
# Allow only specific IPs (if applicable)
sudo ufw allow from <trusted-ip> to any port 8000

# Enable firewall
sudo ufw enable
```

---

## Production Checklist

Before going live:

- [ ] SSL certificate installed and working
- [ ] .env file configured with correct credentials
- [ ] All dependencies installed
- [ ] Firewall configured
- [ ] Reverse proxy (Nginx) set up
- [ ] Systemd service created and enabled
- [ ] Logs monitored for errors
- [ ] Test endpoints verified
- [ ] Data pool (cache) working correctly
- [ ] Google Drive authentication successful
- [ ] Backup procedures in place
- [ ] Security policies reviewed
- [ ] HIPAA compliance verified (if applicable)

---

## Support & Maintenance

### Regular Maintenance Tasks

1. **Monitor Logs**:
   ```bash
   sudo journalctl -u ai-oncologist -f
   ```

2. **Update Dependencies** (monthly):
   ```bash
   pip3 install --upgrade -r requirements.txt
   sudo systemctl restart ai-oncologist
   ```

3. **Backup Database** (weekly):
   ```bash
   cp Backend/data_pool.db /backup/location/data_pool_$(date +%Y%m%d).db
   ```

4. **Clear Cache** (if needed):
   ```bash
   curl -X DELETE http://localhost:8000/api/pool/clear
   ```

5. **Rotate Logs** (configure logrotate):
   ```bash
   sudo nano /etc/logrotate.d/ai-oncologist
   ```

### Getting Help

For issues not covered in this guide:

1. Check application logs: `sudo journalctl -u ai-oncologist -n 100`
2. Review the main [README.md](README.md) for detailed documentation
3. Test individual workflows using test endpoints (see README.md)
4. Check Google Cloud Console for API quota limits

---

## Quick Reference Commands

```bash
# Start service
sudo systemctl start ai-oncologist

# Stop service
sudo systemctl stop ai-oncologist

# Restart service
sudo systemctl restart ai-oncologist

# Check status
sudo systemctl status ai-oncologist

# View logs
sudo journalctl -u ai-oncologist -f

# Test API
curl http://localhost:8000/docs

# Clear cache
curl -X DELETE http://localhost:8000/api/pool/clear

# List cached patients
curl http://localhost:8000/api/pool/patients
```

---

**Version**: 1.0
**Last Updated**: 2026-01-20
**Document Type**: Deployment Guide for Production Environments
