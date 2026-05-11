import os
from dotenv import load_dotenv

load_dotenv("config/.env")

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET  = os.getenv("BYBIT_SECRET_KEY", "")
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET     = os.getenv("BINANCE_SECRET_KEY")
BINANCE_TESTNET    = os.getenv("BINANCE_TESTNET", "true") == "true"
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY        = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

MODAL_TOTAL        = float(os.getenv("MODAL_TOTAL", 10_000_000))
RISK_PER_TRADE     = float(os.getenv("RISK_PER_TRADE", 0.015))
MAX_DD_HARIAN      = float(os.getenv("MAX_DRAWDOWN_HARIAN", 0.03))
MAX_DD_TOTAL       = float(os.getenv("MAX_DRAWDOWN_TOTAL", 0.15))

CRYPTO_WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "HYPE/USDT", "TRX/USDT"
]

IDX_WATCHLIST = [
    "BBCA.JK", "BBRI.JK", "TLKM.JK",
    "ASII.JK", "BMRI.JK", "GOTO.JK"
]