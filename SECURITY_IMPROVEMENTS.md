# Docker Media Stack Security Improvements

## Overview
This document outlines the security improvements made to your Docker media stack configuration to ensure safe web accessibility while maintaining functionality.

## Critical Security Issues Fixed

### 1. **Exposed Credentials**
- **Issue**: VPN credentials and tokens were hardcoded in `.env` file
- **Fix**: Created `.env.example` template without sensitive data
- **Action Required**: 
  - Never commit `.env` to version control
  - Use a secrets management solution for production
  - Rotate all exposed credentials immediately

### 2. **HTTP vs HTTPS**
- **Issue**: All services used HTTP, exposing traffic
- **Fix**: Caddy now automatically provisions SSL certificates via Let's Encrypt
- **Benefits**: 
  - All traffic encrypted in transit
  - HSTS enabled to force HTTPS
  - Automatic certificate renewal

### 3. **Weak Authentication**
- **Issue**: Hardcoded secrets in Authelia configuration
- **Fix**: Secrets now use environment variables
- **Action Required**: Generate strong secrets using:
  ```bash
  # Generate secure random secrets
  openssl rand -hex 32  # For each secret in .env
  ```

### 4. **Docker Socket Exposure**
- **Issue**: Unrestricted Docker socket access
- **Fix**: 
  - Read-only mounts where possible
  - Security options applied
  - User namespacing recommended

### 5. **Direct Port Exposure**
- **Issue**: Services exposed directly to internet
- **Fix**: All services now behind reverse proxy with authentication

## Security Enhancements Implemented

### 1. **Network Segmentation**
Four isolated networks created:
- `frontend`: Public-facing services (Caddy)
- `backend`: Internal services (auth, management)
- `vpn`: VPN-protected services (*arr stack)
- `media`: Media servers

### 2. **Security Headers**
Added comprehensive security headers:
- HSTS (Strict-Transport-Security)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Content Security Policy
- Referrer Policy
- Permissions Policy

### 3. **Rate Limiting**
- Implemented on all endpoints
- 100 requests per minute per IP
- Protects against brute force attacks

### 4. **Container Security**
- `no-new-privileges`: Prevents privilege escalation
- `cap_drop: ALL`: Removes all capabilities by default
- `read_only`: Read-only root filesystem where possible
- User namespacing with PUID/PGID

### 5. **Authentication & Authorization**
- Two-factor authentication for admin services
- One-factor for media services
- Group-based access control
- Session management with timeout

### 6. **VPN Protection**
- All download/indexer services behind VPN
- Kill switch enabled
- DNS leak protection
- Malicious/surveillance blocking

## Deployment Guide

### 1. **Prepare Environment**
```bash
# Copy example environment file
cp .env.example .env

# Generate secure secrets
echo "AUTHELIA_SESSION_SECRET=$(openssl rand -hex 32)" >> .env
echo "AUTHELIA_JWT_SECRET=$(openssl rand -hex 32)" >> .env
echo "AUTHELIA_STORAGE_ENCRYPTION_KEY=$(openssl rand -hex 32)" >> .env
echo "AUTHELIA_OIDC_HMAC_SECRET=$(openssl rand -hex 32)" >> .env

# Edit .env and add your actual values
nano .env
```

### 2. **DNS Configuration**
Point these subdomains to your server:
- `auth.yourdomain.com`
- `homepage.yourdomain.com`
- `portainer.yourdomain.com`
- `jellyfin.yourdomain.com`
- `plex.yourdomain.com`
- `radarr.yourdomain.com`
- `sonarr.yourdomain.com`
- `prowlarr.yourdomain.com`
- `qbittorrent.yourdomain.com`
- `lidarr.yourdomain.com`
- `bazarr.yourdomain.com`

### 3. **Generate Authelia User Password**
```bash
# Install authelia-cli or use Docker
docker run authelia/authelia:latest authelia crypto hash generate argon2 --password 'your-secure-password'

# Add the hash to users_database.yml
```

### 4. **Deploy the Stack**
```bash
# Stop existing stack
docker-compose down

# Backup existing data
cp -r media-stack media-stack.backup

# Deploy secure configuration
docker-compose -f docker-compose-secure.yml up -d

# Check logs
docker-compose -f docker-compose-secure.yml logs -f
```

### 5. **Post-Deployment**
1. Access `https://auth.yourdomain.com` to set up 2FA
2. Configure SMTP in Authelia for email notifications
3. Update API keys in services for Homepage integration
4. Test VPN connectivity for download services

## Security Best Practices

### 1. **Regular Updates**
- Enable Watchtower for automatic updates
- Review security advisories regularly
- Test updates in staging first

### 2. **Backup Strategy**
- Regular automated backups of:
  - Configuration files
  - Authelia database
  - Service databases
- Store backups encrypted off-site

### 3. **Monitoring**
- Enable Authelia logging
- Monitor failed authentication attempts
- Set up alerts for suspicious activity
- Review Caddy access logs

### 4. **Access Control**
- Use strong, unique passwords
- Enable 2FA for all admin accounts
- Regularly review user access
- Remove unused accounts

### 5. **Network Security**
- Use Cloudflare for DDoS protection
- Configure firewall rules
- Limit source IPs if possible
- Use VPN for admin access

## Troubleshooting

### SSL Certificate Issues
```bash
# Check Caddy logs
docker logs caddy

# Manually request certificate
docker exec -it caddy caddy reload --config /etc/caddy/Caddyfile
```

### Authentication Problems
```bash
# Check Authelia logs
docker logs authelia

# Verify configuration
docker exec authelia authelia validate-config
```

### VPN Connectivity
```bash
# Check Gluetun health
docker exec gluetun /gluetun-entrypoint healthcheck

# View VPN logs
docker logs gluetun
```

## Additional Recommendations

1. **Hardware Security**
   - Enable hardware acceleration for media servers
   - Use dedicated GPU for transcoding
   - Consider hardware security keys for 2FA

2. **Advanced Security**
   - Implement fail2ban for IP blocking
   - Use WAF (Web Application Firewall)
   - Enable audit logging
   - Regular security scans

3. **Compliance**
   - Review data protection regulations
   - Implement data retention policies
   - Document security procedures
   - Regular security audits

## Support

For issues or questions:
1. Check service logs: `docker logs <service-name>`
2. Verify DNS resolution
3. Test connectivity without proxy
4. Review authentication rules

Remember: Security is an ongoing process. Regularly review and update your configuration based on new threats and best practices.