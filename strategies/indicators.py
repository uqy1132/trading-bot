import pandas as pd
import ta

def hitung_semua_indikator(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_20"]  = ta.trend.ema_indicator(df["close"], window=20)
    df["ema_50"]  = ta.trend.ema_indicator(df["close"], window=50)
    df["ema_200"] = ta.trend.ema_indicator(df["close"], window=200)
    df["adx"]     = ta.trend.adx(df["high"], df["low"], df["close"], window=14)
    df["rsi"]     = ta.momentum.rsi(df["close"], window=14)
    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()
    df["atr"]         = ta.volatility.average_true_range(df["high"], df["low"], df["close"])
    df["vol_sma20"]   = df["volume"].rolling(20).mean()
    df["vol_ratio"]   = df["volume"] / df["vol_sma20"]
    
    kolom_penting = ["ema_20", "ema_50", "rsi", "adx", "bb_upper", "bb_lower", "atr", "vol_ratio"]
    df = df.dropna(subset=kolom_penting)
    return df


def analisa_lengkap(df: pd.DataFrame, symbol: str) -> dict:
    df = hitung_semua_indikator(df)
    
    # Cek data cukup
    if len(df) < 3:
        return {"symbol": symbol, "error": "Data tidak cukup", "konsensus": "HOLD / TUNGGU"}
    
    baris = df.iloc[-1]
    baris_prev = df.iloc[-2]

    # Trend Following
    ema_cross_up = baris_prev["ema_20"] < baris_prev["ema_50"] and baris["ema_20"] > baris["ema_50"]
    tren_kuat = baris["adx"] > 25

    # Mean Reversion
    oversold   = baris["rsi"] < 32 and baris["close"] <= baris["bb_lower"] * 1.005
    overbought = baris["rsi"] > 68 and baris["close"] >= baris["bb_upper"] * 0.995

    # Breakout
    resistance = df["high"].rolling(20).max().iloc[-2]
    breakout   = baris["close"] > resistance and baris["vol_ratio"] > 2.0

    # Konsensus
    buy_count = sum([ema_cross_up and tren_kuat, oversold, breakout])
    sell_count = sum([overbought])

    if buy_count >= 2:
        konsensus = "BUY"
    elif sell_count >= 1:
        konsensus = "SELL"
    else:
        konsensus = "HOLD / TUNGGU"

    return {
        "symbol": symbol,
        "harga": baris["close"],
        "rsi": round(baris["rsi"], 1),
        "adx": round(baris["adx"], 1),
        "konsensus": konsensus,
        "atr": round(baris["atr"], 4),
        "sinyal_detail": {
            "ema_cross_up": ema_cross_up,
            "tren_kuat": tren_kuat,
            "oversold": oversold,
            "overbought": overbought,
            "breakout": breakout
        }
    }

if __name__ == "__main__":
    import sys
    sys.path.append("C:\\TradingBot")
    from data.crypto_data import get_ohlcv
    
    df = get_ohlcv("BTC/USDT", "4h", 200)
    print(f"Data diterima: {len(df)} baris")
    
    hasil = analisa_lengkap(df, "BTC/USDT")
    print(f"Hasil: {hasil}")
    
    if "error" in hasil:
        print(f"Error: {hasil['error']}")
    else:
        print("=== Analisa BTC/USDT ===")
        print(f"Harga  : ${hasil['harga']:,.2f}")
        print(f"RSI    : {hasil['rsi']}")
        print(f"ADX    : {hasil['adx']}")
        print(f"Sinyal : {hasil['konsensus']}")
        print(f"Detail : {hasil['sinyal_detail']}")

def analisa_multi_timeframe(symbol: str) -> dict:
    """
    Konfirmasi sinyal di 3 timeframe: 1d (bias) → 4h (setup) → 1h (entry)
    """
    import sys
    sys.path.append("C:\\TradingBot")
    from data.crypto_data import get_ohlcv

    hasil_tf = {}
    timeframes = {"1d": "Bias", "4h": "Setup", "1h": "Entry"}

    for tf, peran in timeframes.items():
        try:
            df = get_ohlcv(symbol, tf, 200)
            h = analisa_lengkap(df, symbol)
            hasil_tf[tf] = {
                "peran": peran,
                "sinyal": h["konsensus"],
                "rsi": h["rsi"],
                "adx": h["adx"],
                "harga": h["harga"]
            }
        except Exception as e:
            hasil_tf[tf] = {"peran": peran, "sinyal": "ERROR", "error": str(e)}

    # Hitung konfirmasi
    sinyal_list = [hasil_tf[tf]["sinyal"] for tf in timeframes]
    buy_count  = sum(1 for s in sinyal_list if s == "BUY")
    sell_count = sum(1 for s in sinyal_list if "SELL" in s)

    if buy_count >= 2:
        konfirmasi = "BUY CONFIRMED"
        kekuatan = "KUAT" if buy_count == 3 else "SEDANG"
    elif sell_count >= 2:
        konfirmasi = "SELL CONFIRMED"
        kekuatan = "KUAT" if sell_count == 3 else "SEDANG"
    else:
        konfirmasi = "NO SIGNAL"
        kekuatan = "LEMAH"

    return {
        "symbol": symbol,
        "konfirmasi": konfirmasi,
        "kekuatan": kekuatan,
        "detail": hasil_tf
    }

def deteksi_market_structure(df: pd.DataFrame) -> dict:
    """
    Deteksi Higher High/Lower Low untuk tentukan struktur tren
    HH + HL = Uptrend (struktur bullish)
    LH + LL = Downtrend (struktur bearish)
    """
    if len(df) < 10:
        return {"struktur": "UNKNOWN", "detail": "Data tidak cukup"}

    # Ambil 10 candle terakhir
    recent = df.tail(20)
    highs  = recent["high"].values
    lows   = recent["low"].values

    # Cari swing high dan swing low
    swing_highs = []
    swing_lows  = []

    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            swing_lows.append(lows[i])

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"struktur": "SIDEWAYS", "detail": "Tidak cukup swing point"}

    # Cek Higher High / Lower Low
    hh = swing_highs[-1] > swing_highs[-2]  # Higher High
    hl = swing_lows[-1]  > swing_lows[-2]   # Higher Low
    lh = swing_highs[-1] < swing_highs[-2]  # Lower High
    ll = swing_lows[-1]  < swing_lows[-2]   # Lower Low

    if hh and hl:
        struktur = "UPTREND"
        detail   = "HH + HL — struktur bullish"
    elif lh and ll:
        struktur = "DOWNTREND"
        detail   = "LH + LL — struktur bearish"
    elif hh and ll:
        struktur = "VOLATILE"
        detail   = "HH + LL — pasar volatile/tidak jelas"
    else:
        struktur = "SIDEWAYS"
        detail   = "Struktur sideways"

    return {
        "struktur": struktur,
        "detail": detail,
        "last_swing_high": round(swing_highs[-1], 4),
        "last_swing_low": round(swing_lows[-1], 4)
    }
    
def hitung_entry_sl_tp(df: pd.DataFrame, sinyal: str,
                       rr1: float = 1.5, rr2: float = 2.5) -> dict:
    """
    Hitung entry, SL, TP secara algoritmik dari swing high/low + ATR.
    Deterministik — tidak bergantung pada LLM untuk angka harga.
    """
    df = hitung_semua_indikator(df)
    if len(df) < 3:
        return {"entry": 0, "sl": 0, "tp1": 0, "tp2": 0, "jarak_pct": 0, "rr": 0, "atr": 0}

    baris  = df.iloc[-1]
    entry  = float(baris["close"])
    atr    = float(baris["atr"]) if baris["atr"] > 0 else entry * 0.01
    upper  = sinyal.upper()
    is_buy  = any(k in upper for k in ("BUY", "LONG"))
    is_sell = any(k in upper for k in ("SELL", "SHORT"))

    if not is_buy and not is_sell:
        return {"entry": round(entry, 6), "sl": 0, "tp1": 0, "tp2": 0,
                "jarak_pct": 0, "rr": 0, "atr": round(atr, 6)}

    if is_buy:
        swing_low = float(df["low"].tail(20).min())
        sl = max(swing_low - 0.3 * atr, entry * 0.95)   # cap 5% below
        sl = min(sl, entry - 0.5 * atr)                  # at least 0.5 ATR below
        jarak = entry - sl
        tp1 = entry + jarak * rr1
        tp2 = entry + jarak * rr2
    else:
        swing_high = float(df["high"].tail(20).max())
        sl = min(swing_high + 0.3 * atr, entry * 1.05)   # cap 5% above
        sl = max(sl, entry + 0.5 * atr)                   # at least 0.5 ATR above
        jarak = sl - entry
        tp1 = entry - jarak * rr1
        tp2 = entry - jarak * rr2

    jarak_pct = (jarak / entry) * 100 if entry > 0 else 0

    return {
        "entry"     : round(entry, 6),
        "sl"        : round(sl, 6),
        "tp1"       : round(tp1, 6),
        "tp2"       : round(tp2, 6),
        "jarak_pct" : round(jarak_pct, 2),
        "rr"        : round(rr2, 1),
        "atr"       : round(atr, 6),
    }


def hitung_skor_sinyal(df: pd.DataFrame, symbol: str,
                       market_context: dict = None, mtf_data: dict = None) -> dict:
    """
    Scoring system — setiap sinyal punya bobot.
    Total skor menentukan kualitas setup SEBELUM tanya AI.
    
    Swing trading focus: cari setup kuat, bukan sinyal cepat.
    """
    df = hitung_semua_indikator(df)
    if len(df) < 3:
        return {"skor": 0, "grade": "NO TRADE", "detail": {}}

    baris      = df.iloc[-1]
    baris_prev = df.iloc[-2]
    skor       = 0
    detail     = {}

    # ── 1. Trend Structure (bobot tinggi) ─────────────
    ms = deteksi_market_structure(df)
    if ms["struktur"] == "UPTREND":
        skor += 3
        detail["market_structure"] = f"+3 (UPTREND — HH+HL)"
    elif ms["struktur"] == "DOWNTREND":
        skor -= 3
        detail["market_structure"] = f"-3 (DOWNTREND — LH+LL)"
    else:
        detail["market_structure"] = f"0 (SIDEWAYS)"

    # ── 2. EMA Alignment ──────────────────────────────
    if baris["close"] > baris["ema_20"] > baris["ema_50"]:
        skor += 2
        detail["ema_alignment"] = "+2 (Harga > EMA20 > EMA50 — bullish)"
    elif baris["close"] < baris["ema_20"] < baris["ema_50"]:
        skor -= 2
        detail["ema_alignment"] = "-2 (Harga < EMA20 < EMA50 — bearish)"
    else:
        detail["ema_alignment"] = "0 (EMA tidak aligned)"

    # ── 3. ADX — kekuatan tren (direction-aware) ─────
    adx_val  = baris["adx"]
    ema_bull = baris["close"] > baris["ema_20"] > baris["ema_50"]
    ema_bear = baris["close"] < baris["ema_20"] < baris["ema_50"]

    if adx_val > 30:
        if ema_bull:
            skor += 2
            detail["adx"] = f"+2 (ADX {adx_val:.1f} — uptrend sangat kuat)"
        elif ema_bear:
            skor -= 2
            detail["adx"] = f"-2 (ADX {adx_val:.1f} — downtrend kuat, hindari long)"
        else:
            skor += 1
            detail["adx"] = f"+1 (ADX {adx_val:.1f} — tren kuat, arah belum jelas)"
    elif adx_val > 20:
        if ema_bull:
            skor += 1
            detail["adx"] = f"+1 (ADX {adx_val:.1f} — uptrend cukup)"
        elif ema_bear:
            skor -= 1
            detail["adx"] = f"-1 (ADX {adx_val:.1f} — downtrend sedang)"
        else:
            detail["adx"] = f"0 (ADX {adx_val:.1f} — tren lemah/sideways)"
    else:
        detail["adx"] = f"0 (ADX {adx_val:.1f} — tidak ada tren)"

    # ── 4. RSI — momentum ────────────────────────────
    if 45 <= baris["rsi"] <= 60:
        skor += 2
        detail["rsi"] = f"+2 (RSI {baris['rsi']:.1f} — momentum sehat)"
    elif baris["rsi"] < 35:
        skor += 1
        detail["rsi"] = f"+1 (RSI {baris['rsi']:.1f} — oversold, potensi reversal)"
    elif baris["rsi"] > 70:
        skor -= 2
        detail["rsi"] = f"-2 (RSI {baris['rsi']:.1f} — overbought, hindari beli)"
    else:
        detail["rsi"] = f"0 (RSI {baris['rsi']:.1f} — netral)"

    # ── 5. MACD ───────────────────────────────────────
    macd_v    = baris.get("macd", 0) or 0
    macd_s    = baris.get("macd_signal", 0) or 0
    macd_h    = baris.get("macd_hist", 0) or 0
    macd_h_p  = baris_prev.get("macd_hist", 0) or 0

    if macd_v > macd_s and macd_h > 0 and macd_h > macd_h_p:
        skor += 2
        detail["macd"] = f"+2 (MACD bullish crossover, histogram naik)"
    elif macd_v > macd_s and macd_h > 0:
        skor += 1
        detail["macd"] = f"+1 (MACD di atas signal line)"
    elif macd_v < macd_s and macd_h < 0 and macd_h < macd_h_p:
        skor -= 2
        detail["macd"] = f"-2 (MACD bearish crossover, histogram turun)"
    elif macd_v < macd_s:
        skor -= 1
        detail["macd"] = f"-1 (MACD di bawah signal line)"
    else:
        detail["macd"] = f"0 (MACD netral)"

    # ── 6. Volume konfirmasi ──────────────────────────
    if baris["vol_ratio"] > 1.5:
        skor += 2
        detail["volume"] = f"+2 (Volume {baris['vol_ratio']:.1f}x rata-rata — konfirmasi kuat)"
    elif baris["vol_ratio"] > 1.0:
        skor += 1
        detail["volume"] = f"+1 (Volume {baris['vol_ratio']:.1f}x — cukup)"
    else:
        detail["volume"] = f"0 (Volume {baris['vol_ratio']:.1f}x — lemah)"

    # ── 6. Bollinger Band posisi ──────────────────────
    bb_range = baris["bb_upper"] - baris["bb_lower"]
    bb_pos   = (baris["close"] - baris["bb_lower"]) / bb_range if bb_range > 0 else 0.5

    if 0.4 <= bb_pos <= 0.7:
        skor += 1
        detail["bollinger"] = f"+1 (Harga di tengah BB — ruang gerak bagus)"
    elif bb_pos < 0.2:
        skor += 1
        detail["bollinger"] = f"+1 (Harga di lower BB — potensi bounce)"
    elif bb_pos > 0.9:
        skor -= 1
        detail["bollinger"] = f"-1 (Harga di upper BB — risiko reversal)"
    else:
        detail["bollinger"] = f"0 (Posisi BB netral)"

    # ── 8. Open Interest (opsional, kalau tersedia) ───
    oi_data = market_context.get("open_interest", {}) if market_context else {}
    oi_trend = oi_data.get("trend", "UNKNOWN") if oi_data else "UNKNOWN"
    oi_change = oi_data.get("change_pct", 0) if oi_data else 0

    if oi_trend == "RISING" and oi_change > 3:
        skor += 2
        detail["open_interest"] = f"+2 (OI naik {oi_change:.1f}% — posisi baru masuk, trend kuat)"
    elif oi_trend == "RISING":
        skor += 1
        detail["open_interest"] = f"+1 (OI naik {oi_change:.1f}% — konfirmasi trend)"
    elif oi_trend == "FALLING" and oi_change < -3:
        skor -= 1
        detail["open_interest"] = f"-1 (OI turun {oi_change:.1f}% — posisi ditutup, trend melemah)"
    elif oi_trend != "UNKNOWN":
        detail["open_interest"] = f"0 (OI stabil)"

    # ── 7. Konteks pasar (BTC + F&G + Funding) ───────
    if market_context:
        btc_trend = market_context.get("btc", {}).get("trend", "UNKNOWN")
        fg_value  = market_context.get("fear_greed", {}).get("value", 50)
        fr_status = market_context.get("funding_rate", {}).get("status", "normal")

        if btc_trend == "UPTREND":
            skor += 2
            detail["btc_context"] = "+2 (BTC uptrend — altcoin ikut)"
        elif btc_trend == "DOWNTREND":
            skor -= 3
            detail["btc_context"] = "-3 (BTC downtrend — SANGAT berbahaya long altcoin)"
        else:
            detail["btc_context"] = "0 (BTC sideways)"

        if fg_value <= 25:
            skor += 2
            detail["fear_greed"] = f"+2 (Extreme Fear {fg_value} — peluang beli terbaik)"
        elif fg_value >= 80:
            skor -= 2
            detail["fear_greed"] = f"-2 (Extreme Greed {fg_value} — hindari beli)"
        elif fg_value <= 40:
            skor += 1
            detail["fear_greed"] = f"+1 (Fear {fg_value} — kondisi bagus untuk beli)"
        else:
            detail["fear_greed"] = f"0 (F&G {fg_value} — netral)"

        if fr_status == "extreme_long":
            skor -= 2
            detail["funding_rate"] = "-2 (Funding terlalu tinggi — potensi long squeeze)"
        elif fr_status == "extreme_short":
            skor += 1
            detail["funding_rate"] = "+1 (Funding negatif — potensi short squeeze)"
        else:
            detail["funding_rate"] = "0 (Funding normal)"

    # ── Multi-Timeframe konfirmasi ────────────────────
    if mtf_data:
        konfirmasi = mtf_data.get("konfirmasi", "NO SIGNAL")
        kekuatan   = mtf_data.get("kekuatan", "LEMAH")
        if konfirmasi == "BUY CONFIRMED":
            pts = 3 if kekuatan == "KUAT" else 2
            skor += pts
            detail["mtf"] = f"+{pts} (MTF BUY CONFIRMED — {kekuatan})"
        elif konfirmasi == "SELL CONFIRMED":
            pts = 3 if kekuatan == "KUAT" else 2
            skor -= pts
            detail["mtf"] = f"-{pts} (MTF SELL CONFIRMED — {kekuatan})"
        else:
            skor -= 1
            detail["mtf"] = "-1 (MTF: sinyal tidak konsisten antar TF)"

    # ── Grade final ───────────────────────────────────
    skor_max = (21 if market_context else 14) + (3 if mtf_data else 0)

    if skor >= 10:
        grade = "A — STRONG BUY"
    elif skor >= 7:
        grade = "B — BUY"
    elif skor >= 4:
        grade = "C — WEAK/WAIT"
    elif skor <= -4:
        grade = "D — AVOID/SHORT"
    else:
        grade = "C — HOLD/WAIT"

    return {
        "skor": skor,
        "skor_max": skor_max,
        "grade": grade,
        "detail": detail,
        "layak_trade": skor >= 7,
        "arah": "BUY" if skor >= 7 else "SHORT" if skor <= -4 else "WAIT"
    }