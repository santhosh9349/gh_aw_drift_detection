#!/bin/bash
# User data script for internal web server
# Purpose: Install and configure nginx with HTTPS for connectivity testing
# Note: Client dashboard application deployment is out of scope

set -e

# Update system packages
echo "=== Updating system packages ==="
yum update -y

# Install nginx web server
echo "=== Installing nginx ==="
yum install -y nginx openssl

# Generate self-signed certificate for HTTPS testing
echo "=== Generating self-signed certificate ==="
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/nginx.key \
  -out /etc/nginx/ssl/nginx.crt \
  -subj "/C=US/ST=State/L=City/O=DevOps Team/OU=AWS Infrastructure/CN=internal-dashboard"

# Set proper permissions
chmod 600 /etc/nginx/ssl/nginx.key
chmod 644 /etc/nginx/ssl/nginx.crt

# Configure nginx for HTTPS
echo "=== Configuring nginx for HTTPS ==="
cat > /etc/nginx/conf.d/https.conf <<'EOF'
server {
    listen 443 ssl;
    server_name _;
    
    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    
    location / {
        return 200 'Internal Web Server - Ready for Dashboard Deployment\nHostname: $hostname\nServer IP: $server_addr\nClient IP: $remote_addr\nTimestamp: $time_iso8601\n';
        add_header Content-Type text/plain;
    }
    
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}

# Redirect any HTTP requests to HTTPS (for clarity)
server {
    listen 80;
    server_name _;
    
    location / {
        return 200 'HTTPS only - connect to port 443\n';
        add_header Content-Type text/plain;
    }
}
EOF

# Enable and start nginx
echo "=== Starting nginx service ==="
systemctl enable nginx
systemctl start nginx

# Verify nginx is running
if systemctl is-active --quiet nginx; then
    echo "=== SUCCESS: nginx is running ==="
else
    echo "=== ERROR: nginx failed to start ==="
    journalctl -u nginx -n 50
    exit 1
fi

# Create a simple status file for troubleshooting
cat > /var/www/html/status.txt <<EOF
Web Server Status
=================
Deployed: $(date)
OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)
Nginx Version: $(nginx -v 2>&1)
Private IP: $(hostname -I | awk '{print $1}')

Security Configuration:
- HTTPS: Port 443 (enabled)
- HTTP: Port 80 (informational only)
- SSH: Disabled per organizational policy
- Management: AWS Systems Manager Session Manager

Network Configuration:
- VPC: Dev VPC (172.0.0.0/16)
- Subnet: Private subnet (no public IP)
- Connectivity: Transit Gateway mesh to all internal VPCs

Ready for client dashboard deployment.
EOF

echo "=== User data script completed successfully ==="
