#!/bin/bash
# Update bot setelah push perubahan dari laptop
set -e
cd /app
git pull
source venv/bin/activate
pip install -r requirements.txt --quiet
cd frontend && npm install --silent && npm run build && cd ..
sudo systemctl restart tradingbot tradingbot-scheduler
echo "✅ Bot diupdate dan direstart!"
