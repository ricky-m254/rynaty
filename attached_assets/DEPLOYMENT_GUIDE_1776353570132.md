# Deployment Guide

## Prerequisites

- Ubuntu 20.04+ server (or similar)
- PostgreSQL 12+
- Redis 6+
- Python 3.9+
- Nginx
- SSL certificate (Let's Encrypt)

## Server Setup

### 1. System Dependencies

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y redis-server
sudo apt install -y nginx
sudo apt install -y git
sudo apt install -y build-essential libpq-dev
```

### 2. PostgreSQL Setup

```bash
sudo -u postgres psql

CREATE DATABASE schoolsaas;
CREATE USER schoolsaas WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE schoolsaas TO schoolsaas;
ALTER DATABASE schoolsaas OWNER TO schoolsaas;

\q
```

### 3. Redis Setup

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify
redis-cli ping  # Should return PONG
```

### 4. Project Setup

```bash
# Create directory
sudo mkdir -p /var/www/schoolsaas
sudo chown $USER:$USER /var/www/schoolsaas
cd /var/www/schoolsaas

# Clone your project
git clone https://github.com/yourusername/schoolsaas.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Environment file
cp .env.example .env
nano .env  # Edit with production values
```

### 5. Django Setup

```bash
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser
```

### 6. Gunicorn Setup

Create `/etc/systemd/system/gunicorn.service`:

```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/schoolsaas
ExecStart=/var/www/schoolsaas/venv/bin/gunicorn \
    --access-logfile - \
    --workers 4 \
    --bind unix:/var/www/schoolsaas/gunicorn.sock \
    config.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### 7. Celery Setup

Create `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Celery Service
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
EnvironmentFile=/var/www/schoolsaas/.env
WorkingDirectory=/var/www/schoolsaas
ExecStart=/var/www/schoolsaas/venv/bin/celery \
    -A config multi start worker1 \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/log/celery/%n.log
ExecStop=/var/www/schoolsaas/venv/bin/celery \
    -A config multi stop worker1 \
    --pidfile=/var/run/celery/%n.pid
ExecReload=/var/www/schoolsaas/venv/bin/celery \
    -A config multi restart worker1 \
    --pidfile=/var/run/celery/%n.pid

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/celerybeat.service`:

```ini
[Unit]
Description=Celery Beat Service
After=network.target redis.service

[Service]
User=www-data
Group=www-data
EnvironmentFile=/var/www/schoolsaas/.env
WorkingDirectory=/var/www/schoolsaas
ExecStart=/var/www/schoolsaas/venv/bin/celery \
    -A config beat \
    --logfile=/var/log/celery/beat.log \
    --pidfile=/var/run/celery/beat.pid

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/run/celery /var/log/celery
sudo chown -R www-data:www-data /var/run/celery /var/log/celery

sudo systemctl start celery
sudo systemctl enable celery
sudo systemctl start celerybeat
sudo systemctl enable celerybeat
```

### 8. Nginx Setup

Create `/etc/nginx/sites-available/schoolsaas`:

```nginx
server {
    listen 80;
    server_name yourdomain.com *.yourdomain.com;
    
    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/schoolsaas;
    }
    
    location /media/ {
        root /var/www/schoolsaas;
    }
    
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/schoolsaas/gunicorn.sock;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/schoolsaas /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

### 9. SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d *.yourdomain.com

# Auto-renewal test
sudo certbot renew --dry-run
```

### 10. Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

## Monitoring

### Log Files

```bash
# Django logs
tail -f /var/www/schoolsaas/logs/django.log

# Gunicorn logs
sudo journalctl -u gunicorn -f

# Celery logs
sudo tail -f /var/log/celery/worker1.log

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Health Checks

```bash
# Check services
sudo systemctl status gunicorn
sudo systemctl status celery
sudo systemctl status celerybeat
sudo systemctl status redis
sudo systemctl status nginx

# Check Celery workers
cd /var/www/schoolsaas
source venv/bin/activate
celery -A config inspect active
```

## Updates

```bash
cd /var/www/schoolsaas
source venv/bin/activate

git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

sudo systemctl restart gunicorn
sudo systemctl restart celery
sudo systemctl restart celerybeat
```

## Backup

### Database Backup

```bash
# Create backup script
sudo tee /usr/local/bin/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/schoolsaas"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump -U schoolsaas schoolsaas > $BACKUP_DIR/schoolsaas_$DATE.sql
gzip $BACKUP_DIR/schoolsaas_$DATE.sql
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

sudo chmod +x /usr/local/bin/backup-db.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /usr/local/bin/backup-db.sh" | sudo crontab -
```

## Troubleshooting

### Gunicorn not starting

```bash
# Check logs
sudo journalctl -u gunicorn -n 50

# Test manually
cd /var/www/schoolsaas
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 config.wsgi:application
```

### Celery not processing tasks

```bash
# Check workers
celery -A config inspect active
celery -A config inspect scheduled

# Restart
sudo systemctl restart celery
sudo systemctl restart celerybeat
```

### Database connection issues

```bash
# Test connection
sudo -u www-data psql -U schoolsaas -d schoolsaas -c "SELECT 1"

# Check PostgreSQL status
sudo systemctl status postgresql
```
