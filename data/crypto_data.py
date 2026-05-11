import ssl
import ccxt
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

# Fix SSL untuk Windows
ssl._create_default_https_context = ssl._create_unverified_context

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def get_exchange():
    exchange = ccxt.bybit({"enableRateLimit": True})
    # Inject session dengan SSL disabled
    session = requests.Session()
    session.mount('https://', SSLAdapter())
    session.verify = False
    exchange.session = session
    return exchange

def get_ohlcv(symbol: str, timeframe: str = "4h", limit: int = 200) -> pd.DataFrame:
    exchange = get_exchange()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df

def get_ticker(symbol: str) -> dict:
    exchange = get_exchange()
    ticker = exchange.fetch_ticker(symbol)
    return {
        "symbol": symbol,
        "harga": ticker["last"],
        "change_24h": ticker["percentage"],
        "volume_24h": ticker["quoteVolume"]
    }

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    
    df = get_ohlcv("BTC/USDT", "4h", 10)
    print("=== Data BTC/USDT (4H) — 10 candle terakhir ===")
    print(df.tail())
    
    ticker = get_ticker("BTC/USDT")
    print(f"\nHarga BTC sekarang: ${ticker['harga']:,.2f}")
    print(f"Perubahan 24H: {ticker['change_24h']:.2f}%")