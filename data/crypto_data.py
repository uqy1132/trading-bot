import ssl
import ccxt
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

ssl._create_default_https_context = ssl._create_unverified_context

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def _make_session():
    session = requests.Session()
    session.mount('https://', SSLAdapter())
    session.verify = False
    return session

# Exchange configs — dicoba urut sampai ada yang berhasil
_EXCHANGE_FACTORIES = [
    ("okx",    lambda: ccxt.okx({"enableRateLimit": True, "options": {"defaultType": "swap"}})),
    ("gateio", lambda: ccxt.gateio({"enableRateLimit": True, "options": {"defaultType": "swap"}})),
    ("mexc",   lambda: ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})),
]

_exchange_cache: ccxt.Exchange | None = None
_exchange_name: str = ""

def get_exchange() -> ccxt.Exchange:
    """
    Auto-pilih exchange pertama yang bisa diakses dari jaringan ini.
    OKX → Gate.io → MEXC. Hasil di-cache agar tidak perlu retry setiap call.
    """
    global _exchange_cache, _exchange_name
    if _exchange_cache is not None:
        return _exchange_cache

    import urllib3
    urllib3.disable_warnings()

    last_err = None
    for name, factory in _EXCHANGE_FACTORIES:
        try:
            ex = factory()
            ex.session = _make_session()
            # quick connectivity test — ambil 2 candle BTC
            sym = "BTC/USDT:USDT"
            ex.fetch_ohlcv(sym, "1h", limit=2)
            _exchange_cache = ex
            _exchange_name = name
            print(f"[crypto_data] Menggunakan exchange: {name}")
            return ex
        except Exception as e:
            print(f"[crypto_data] {name} gagal: {e}")
            last_err = e

    raise ConnectionError(f"Semua exchange gagal. Error terakhir: {last_err}")

def _fmt_symbol(symbol: str) -> str:
    """Konversi BTC/USDT → BTC/USDT:USDT (format CCXT unified perpetual)."""
    if ":" not in symbol:
        base = symbol.split("/")[0]
        return f"{base}/USDT:USDT"
    return symbol

def get_ohlcv(symbol: str, timeframe: str = "4h", limit: int = 200) -> pd.DataFrame:
    import urllib3
    urllib3.disable_warnings()

    exchange = get_exchange()
    sym = _fmt_symbol(symbol)
    ohlcv = exchange.fetch_ohlcv(sym, timeframe, limit=limit)

    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df

def get_ticker(symbol: str) -> dict:
    import urllib3
    urllib3.disable_warnings()

    exchange = get_exchange()
    sym = _fmt_symbol(symbol)
    ticker = exchange.fetch_ticker(sym)

    return {
        "symbol"    : symbol,
        "harga"     : ticker.get("last") or ticker.get("close") or 0,
        "change_24h": ticker.get("percentage") or 0,
        "volume_24h": ticker.get("quoteVolume") or ticker.get("baseVolume") or 0,
    }


def get_all_tickers() -> list:
    """Fetch semua perpetual swap USDT, filter by volume."""
    import urllib3; urllib3.disable_warnings()
    exchange = get_exchange()

    # Load markets agar symbol list tersedia
    if not exchange.markets:
        exchange.load_markets()

    # Ambil simbol swap USDT yang aktif
    swap_symbols = [
        m["symbol"] for m in exchange.markets.values()
        if m.get("type") == "swap"
        and m.get("quote") == "USDT"
        and m.get("active", True)
    ]

    if not swap_symbols:
        return []

    tickers = exchange.fetch_tickers(swap_symbols)

    result = []
    for sym, t in tickers.items():
        change = t.get("percentage") or 0
        last   = t.get("last") or 0
        if last == 0:
            continue
        vol = t.get("quoteVolume") or t.get("baseVolume") or 0
        clean = sym.replace(":USDT", "")
        result.append({
            "symbol"    : clean,
            "price"     : last,
            "change_24h": round(change, 2),
            "volume_24h": round(vol, 0),
        })
    return sorted(result, key=lambda x: x["change_24h"], reverse=True)


def get_open_interest(symbol: str) -> dict:
    """Ambil Open Interest dan tren-nya (naik/turun) dari exchange."""
    import urllib3
    urllib3.disable_warnings()
    try:
        exchange = get_exchange()
        sym = _fmt_symbol(symbol)
        # Coba ambil history untuk bisa hitung tren
        try:
            hist = exchange.fetch_open_interest_history(sym, timeframe="1d", limit=3)
            if hist and len(hist) >= 2:
                oi_now  = float(hist[-1].get("openInterestAmount", 0) or 0)
                oi_prev = float(hist[-2].get("openInterestAmount", 0) or 0)
                change_pct = (oi_now - oi_prev) / oi_prev * 100 if oi_prev > 0 else 0
                trend = "RISING" if change_pct > 2 else "FALLING" if change_pct < -2 else "STABLE"
                return {
                    "value"     : round(oi_now, 2),
                    "change_pct": round(change_pct, 2),
                    "trend"     : trend,
                    "status"    : "OK",
                }
        except Exception:
            pass
        # Fallback: hanya nilai sekarang
        oi = exchange.fetch_open_interest(sym)
        oi_val = float(oi.get("openInterestAmount", 0) or 0)
        return {"value": round(oi_val, 2), "change_pct": 0, "trend": "UNKNOWN", "status": "OK"}
    except Exception as e:
        return {"value": 0, "change_pct": 0, "trend": "UNKNOWN", "status": f"Error: {e}"}


_auth_exchange_cache: "ccxt.Exchange | None" = None
_auth_exchange_name: str = ""

def get_exchange_auth() -> ccxt.Exchange:
    """
    Exchange dengan API key — untuk eksekusi order nyata.
    Prioritas: OKX → Gate.io → MEXC (sesuai dengan key yang tersedia).
    """
    global _auth_exchange_cache, _auth_exchange_name
    if _auth_exchange_cache is not None:
        return _auth_exchange_cache

    import urllib3
    urllib3.disable_warnings()

    from config.settings import (OKX_API_KEY, OKX_SECRET, OKX_PASSPHRASE,
                                  GATE_API_KEY, GATE_SECRET,
                                  MEXC_API_KEY, MEXC_SECRET)

    candidates = []
    if OKX_API_KEY and OKX_SECRET:
        candidates.append(("okx", lambda: ccxt.okx({
            "apiKey": OKX_API_KEY, "secret": OKX_SECRET,
            "password": OKX_PASSPHRASE,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })))
    if GATE_API_KEY and GATE_SECRET:
        candidates.append(("gateio", lambda: ccxt.gateio({
            "apiKey": GATE_API_KEY, "secret": GATE_SECRET,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })))
    if MEXC_API_KEY and MEXC_SECRET:
        candidates.append(("mexc", lambda: ccxt.mexc({
            "apiKey": MEXC_API_KEY, "secret": MEXC_SECRET,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })))

    if not candidates:
        raise ValueError(
            "Tidak ada API key exchange. Tambahkan OKX_API_KEY + OKX_SECRET + OKX_PASSPHRASE "
            "(atau GATE_API_KEY + GATE_SECRET) ke config/.env"
        )

    last_err = None
    for name, factory in candidates:
        try:
            ex = factory()
            ex.session = _make_session()
            ex.fetch_balance()   # verifikasi auth berhasil
            _auth_exchange_cache = ex
            _auth_exchange_name  = name
            print(f"[auth] Exchange terpilih: {name}")
            return ex
        except Exception as e:
            print(f"[auth] {name} gagal: {e}")
            last_err = e

    raise ConnectionError(f"Autentikasi ke semua exchange gagal. Error: {last_err}")


def get_auth_exchange_name() -> str:
    return _auth_exchange_name


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()

    print("=== Test koneksi exchange ===")
    df = get_ohlcv("BTC/USDT", "4h", 5)
    print(f"Exchange terpilih: {_exchange_name}")
    print("Data BTC/USDT (4H) — 5 candle terakhir:")
    print(df.tail())

    ticker = get_ticker("BTC/USDT")
    print(f"\nHarga BTC sekarang: ${ticker['harga']:,.2f}")
    print(f"Perubahan 24H: {ticker['change_24h']:.2f}%")
