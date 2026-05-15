import requests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.crypto_data import get_ohlcv
from strategies.indicators import hitung_semua_indikator

def get_fear_greed() -> dict:
    """Ambil Fear & Greed Index dari API gratis"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = r.json()["data"][0]
        return {
            "value": int(data["value"]),
            "label": data["value_classification"],
            "status": "OK"
        }
    except Exception as e:
        return {"value": 50, "label": "Unknown", "status": f"Error: {e}"}

def get_btc_context() -> dict:
    """Analisa kondisi BTC sebagai market leader"""
    try:
        df = get_ohlcv("BTC/USDT", "4h", 200)
        df = hitung_semua_indikator(df)

        if len(df) < 3:
            raise ValueError("Data tidak cukup")

        baris = df.iloc[-1]

        if baris["close"] > baris["ema_50"] and baris["ema_20"] > baris["ema_50"]:
            trend = "UPTREND"
        elif baris["close"] < baris["ema_50"] and baris["ema_20"] < baris["ema_50"]:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        if trend == "UPTREND":
            rekomendasi = "AMAN — BTC uptrend, altcoin boleh long"
        elif trend == "DOWNTREND":
            rekomendasi = "HATI-HATI — BTC downtrend, hindari long altcoin"
        else:
            rekomendasi = "NETRAL — BTC sideways, selektif dalam entry"

        return {
            "harga"      : round(float(baris["close"]), 2),
            "trend"      : trend,
            "rsi"        : round(float(baris["rsi"]), 1),
            "adx"        : round(float(baris["adx"]), 1),
            "rekomendasi": rekomendasi,
            "status"     : "OK"
        }
    except Exception as e:
        return {
            "harga"      : 0,
            "trend"      : "UNKNOWN",
            "rsi"        : 0,
            "adx"        : 0,
            "rekomendasi": "Tidak bisa cek BTC",
            "status"     : str(e)
        }

def get_funding_rate(symbol: str = "BTC/USDT") -> dict:
    """Ambil funding rate dari Binance USDT-M Futures"""
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    try:
        sym = symbol.replace("/", "").replace(":USDT", "")  # → BTCUSDT
        r = requests.get(
            f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}",
            timeout=5, verify=False
        )
        data = r.json()
        fr = float(data["lastFundingRate"]) * 100
        return {
            "symbol": symbol,
            "funding_rate": round(fr, 4),
            "status": "extreme_long" if fr > 0.1 else "extreme_short" if fr < -0.05 else "normal",
            "sinyal": "BEARISH" if fr > 0.1 else "BULLISH" if fr < -0.05 else "NETRAL"
        }
    except Exception as e:
        return {"funding_rate": 0, "status": "normal", "sinyal": "NETRAL", "error": str(e)}

def get_funding_semua() -> list:
    """Cek funding rate semua aset watchlist"""
    from config.settings import CRYPTO_WATCHLIST
    hasil = []
    for sym in CRYPTO_WATCHLIST:
        fr = get_funding_rate(sym)
        hasil.append({
            "symbol": sym,
            "funding_rate": fr["funding_rate"],
            "sinyal": fr["sinyal"],
            "status": fr["status"]
        })
    return hasil

def get_full_market_context() -> dict:
    fg  = get_fear_greed()
    btc = get_btc_context()
    fr  = get_funding_rate("BTC/USDT")

    boleh_trading = True
    warnings = []

    if btc["trend"] == "DOWNTREND":
        warnings.append("BTC sedang downtrend — hindari long altcoin")
        boleh_trading = False

    if fg["value"] >= 80:
        warnings.append(f"Extreme Greed ({fg['value']}) — pasar overbought, hati-hati long")
    elif fg["value"] <= 20:
        warnings.append(f"Extreme Fear ({fg['value']}) — potensi reversal up")

    if fr["status"] == "extreme_long":
        warnings.append(f"Funding Rate tinggi ({fr['funding_rate']}%) — terlalu banyak long, potensi reversal down")
        boleh_trading = False
    elif fr["status"] == "extreme_short":
        warnings.append(f"Funding Rate negatif ({fr['funding_rate']}%) — terlalu banyak short, potensi short squeeze")

    return {
        "btc": btc,
        "fear_greed": fg,
        "funding_rate": fr,
        "boleh_trading": boleh_trading,
        "warnings": warnings
    }

