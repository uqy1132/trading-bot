#!/bin/bash
# =============================================================
# Trading Bot — Auto Setup Script untuk Oracle Cloud / Ubuntu VPS
# Jalankan: bash deploy.sh
# =============================================================

set -e
echo "🚀 Setup Trading Bot di VPS..."

# 1. Update sistem
sudo apt-get update -y && sudo apt-get upgrade -y

# 2. Install Python 3.11
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# 3. Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 4. Install git & nginx
sudo apt-get install -y git nginx

# 5. Buat direktori app
sudo mkdir -p /app
sudo chown $USER:$USER /app

# 6. Clone atau pull repo
if [ -d "/app/.git" ]; then
    echo "📦 Update repo..."
    cd /app && git pull
else
    echo "📦 Clone repo..."
    # Ganti URL di bawah dengan URL repo GitHub kamu
    git clone https://github.com/GANTI_DENGAN_USERNAME/TradingBot.git /app
fi

cd /app

# 7. Setup Python virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 8. Build frontend React
cd /app/frontend
npm install
npm run build
cd /app

# 9. Buat folder logs
mkdir -p logs

# 10. Setup systemd service untuk backend
sudo tee /etc/systemd/system/tradingbot.service > /dev/null <<EOF
[Unit]
Description=Trading Bot API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/app
Environment=PYTHONPATH=/app
EnvironmentFile=/app/config/.env
ExecStart=/app/venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 11. Setup systemd service untuk scheduler
sudo tee /etc/systemd/system/tradingbot-scheduler.service > /dev/null <<EOF
[Unit]
Description=Trading Bot Scheduler (Auto Alert + TP/SL update)
After=network.target tradingbot.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/app
Environment=PYTHONPATH=/app
EnvironmentFile=/app/config/.env
ExecStart=/app/venv/bin/python scheduler_alert.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# 12. Setup Nginx sebagai reverse proxy
sudo tee /etc/nginx/sites-available/tradingbot > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    # Gzip untuk performa lebih baik
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/tradingbot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 13. Enable dan start services
sudo systemctl daemon-reload
sudo systemctl enable tradingbot tradingbot-scheduler
sudo systemctl start tradingbot tradingbot-scheduler

echo ""
echo "✅ Setup selesai!"
echo ""
echo "📋 Cek status:"
echo "   sudo systemctl status tradingbot"
echo "   sudo systemctl status tradingbot-scheduler"
echo ""
echo "📋 Lihat log:"
echo "   sudo journalctl -u tradingbot -f"
echo ""
echo "🌐 Akses via IP publik VPS kamu di browser (port 80)"
