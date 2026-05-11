import yfinance as yf
import pandas as pd
from config.settings import IDX_WATCHLIST

def get_saham_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    saham = yf.Ticker(ticker)
    df = saham.history(period=period, interval=interval)
    df.index = pd.to_datetime(df.index)
    df.columns = [c.lower() for c in df.columns]
    return df[["open", "high", "low", "close", "volume"]]

def get_info_saham(ticker: str) -> dict:
    saham = yf.Ticker(ticker)
    info = saham.info
    return {
        "nama": info.get("longName", ticker),
        "sektor": info.get("sector", "-"),
        "harga": info.get("currentPrice", 0)
    }

if __name__ == "__main__":
    print("=== Data BBCA 1 bulan terakhir ===")
    df = get_saham_ohlcv("BBCA.JK", period="1mo")
    print(df.tail(5))