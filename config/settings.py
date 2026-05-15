import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET  = os.getenv("BYBIT_SECRET_KEY", "")
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET     = os.getenv("BINANCE_SECRET_KEY")
BINANCE_TESTNET    = os.getenv("BINANCE_TESTNET", "true") == "true"
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY        = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# Exchange API keys — untuk eksekusi order nyata
OKX_API_KEY    = os.getenv("OKX_API_KEY", "")
OKX_SECRET     = os.getenv("OKX_SECRET", "")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
GATE_API_KEY   = os.getenv("GATE_API_KEY", "")
GATE_SECRET    = os.getenv("GATE_SECRET", "")
MEXC_API_KEY   = os.getenv("MEXC_API_KEY", "")
MEXC_SECRET    = os.getenv("MEXC_SECRET", "")

# LIVE_MODE=true → eksekusi order nyata ke exchange. Default false (virtual/paper)
LIVE_MODE = os.getenv("LIVE_MODE", "false").lower() == "true"

MODAL_TOTAL        = float(os.getenv("MODAL_TOTAL", 10_000_000))
RISK_PER_TRADE     = float(os.getenv("RISK_PER_TRADE", 0.015))
MAX_DD_HARIAN      = float(os.getenv("MAX_DRAWDOWN_HARIAN", 0.03))
MAX_DD_TOTAL       = float(os.getenv("MAX_DRAWDOWN_TOTAL", 0.15))
TARGET_BULANAN     = float(os.getenv("TARGET_BULANAN", 0.04))

CRYPTO_WATCHLIST = [
    "BTC/USDT",  "ETH/USDT",  "SOL/USDT",  "XRP/USDT",
    "BNB/USDT",  "AVAX/USDT", "LINK/USDT", "ADA/USDT",
    "DOT/USDT",  "NEAR/USDT", "APT/USDT",  "OP/USDT",
    "ARB/USDT",  "SUI/USDT",  "TRX/USDT",  "TON/USDT",
    "DOGE/USDT", "PEPE/USDT",
]

IDX_WATCHLIST = [
    "BBCA.JK", "BBRI.JK", "TLKM.JK",
    "ASII.JK", "BMRI.JK", "GOTO.JK"
]