#!/bin/bash
cd /home/user/TradingBot
source venv/bin/activate
python scheduler.py >> logs/scheduler.log 2>&1 &
streamlit run dashboard.py --server.port 8501 --server.headless true >> logs/dashboard.log 2>&1 &
echo "✅ Bot started!"