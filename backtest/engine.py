import sys
sys.path.append("C:\\TradingBot")

import pandas as pd
import numpy as np
from data.crypto_data import get_ohlcv
from strategies.indicators import hitung_semua_indikator

ASET_CONFIG = {
    "BTC/USDT":  {"adx_min": 18, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 3.0},
    "ETH/USDT":  {"adx_min": 20, "rsi_min": 40, "rsi_max": 63, "vol_min": 1.0, "rr": 2.5},
    "SOL/USDT":  {"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
    "BNB/USDT":  {"adx_min": 18, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 3.0},
    "XRP/USDT":  {"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
    "ADA/USDT":  {"adx_min": 18, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
    "AVAX/USDT": {"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
    "DOT/USDT":  {"adx_min": 18, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
    "HYPE/USDT": {"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.0},
    "TRX/USDT":  {"adx_min": 18, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 3.0},
    "MATIC/USDT":{"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
    "LINK/USDT": {"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5},
}

# Vol multiplier per timeframe — daily lebih longgar dari 4h
TF_VOL_MULTIPLIER = {
    "1h": 1.3,
    "4h": 1.1,
    "1d": 0.9,  # Daily: volume jarang spike tinggi
}

def backtest_strategi(symbol: str, timeframe: str = "4h", limit: int = 500) -> dict:
    try:
        df = get_ohlcv(symbol, timeframe, limit)
        df = hitung_semua_indikator(df)

        if len(df) < 10:
            return {"error": "Data tidak cukup untuk backtest"}

        # Ambil config untuk aset ini
        cfg = ASET_CONFIG.get(symbol, {"adx_min": 20, "rsi_min": 40, "rsi_max": 65, "vol_min": 1.0, "rr": 2.5})

        # Sesuaikan vol_min berdasarkan timeframe
        vol_multiplier = TF_VOL_MULTIPLIER.get(timeframe, 1.0)
        vol_min_adjusted = cfg["vol_min"] * vol_multiplier
        
        modal          = 1000.0
        modal_awal     = modal
        risk_per_trade = 0.015
        trades         = []
        equity         = [modal]
        posisi         = None

        for i in range(3, len(df)):
            baris       = df.iloc[i]
            baris_prev  = df.iloc[i-1]
            baris_prev2 = df.iloc[i-2]

            if posisi is None:

                # ── Strategi 1: Pullback ke EMA20 dalam uptrend ──────
                uptrend = baris["close"] > baris["ema_50"] and baris["ema_20"] > baris["ema_50"]
                pullback_ema20 = (
                baris_prev["low"] <= baris_prev["ema_20"] * 1.005 and
                baris["close"] > baris["ema_20"] and
                baris["rsi"] > cfg["rsi_min"] and baris["rsi"] < cfg["rsi_max"] and
                baris["adx"] > cfg["adx_min"] and
                baris["vol_ratio"] > vol_min_adjusted
                )

                if uptrend and pullback_ema20:
                    entry = baris["close"]
                    sl    = baris["ema_50"] * 0.995
                    tp    = entry + (entry - sl) * cfg["rr"]
                    risk_usdt = modal * risk_per_trade
                    jarak = entry - sl
                    if jarak > 0:
                        ukuran = risk_usdt / jarak
                        posisi = {
                            "entry": entry, "sl": sl, "tp": tp,
                            "ukuran": ukuran, "arah": "BUY",
                            "metode": "Pullback EMA20",
                            "tanggal_masuk": str(df.index[i])
                        }
                        continue

                # ── Strategi 2: RSI Oversold Bounce ──────────────────
                rsi_bounce = (
                    baris_prev2["rsi"] < 35 and
                    baris_prev["rsi"] < 35 and
                    baris["rsi"] > baris_prev["rsi"] and
                    baris["close"] > baris["bb_lower"] and
                    baris["close"] > baris["ema_50"]
                )

                if rsi_bounce:
                    entry = baris["close"]
                    sl    = baris["bb_lower"] * 0.99
                    tp    = entry + (entry - sl) * cfg["rr"]
                    risk_usdt = modal * risk_per_trade
                    jarak = entry - sl
                    if jarak > 0:
                        ukuran = risk_usdt / jarak
                        posisi = {
                            "entry": entry, "sl": sl, "tp": tp,
                            "ukuran": ukuran, "arah": "BUY",
                            "metode": "RSI Bounce",
                            "tanggal_masuk": str(df.index[i])
                        }
                        continue

                # ── Strategi 3: SELL — Downtrend + Overbought ────────
                downtrend    = baris["close"] < baris["ema_50"] and baris["ema_20"] < baris["ema_50"]
                rsi_over     = baris["rsi"] > 68
                macd_negatif = baris["macd_hist"] < 0

                if downtrend and rsi_over and macd_negatif:
                    entry = baris["close"]
                    sl    = baris["bb_upper"] * 1.005
                    tp    = entry - (sl - entry) * cfg["rr"]
                    risk_usdt = modal * risk_per_trade
                    jarak = sl - entry
                    if jarak > 0:
                        ukuran = risk_usdt / jarak
                        posisi = {
                            "entry": entry, "sl": sl, "tp": tp,
                            "ukuran": ukuran, "arah": "SELL",
                            "metode": "Overbought Reversal",
                            "tanggal_masuk": str(df.index[i])
                        }

            elif posisi:
                harga  = baris["close"]
                hasil  = None
                keluar = None

                if posisi["arah"] == "BUY":
                    if harga <= posisi["sl"]:
                        hasil  = "LOSS"
                        keluar = posisi["sl"]
                        pnl    = (posisi["sl"] - posisi["entry"]) * posisi["ukuran"]
                    elif harga >= posisi["tp"]:
                        hasil  = "WIN"
                        keluar = posisi["tp"]
                        pnl    = (posisi["tp"] - posisi["entry"]) * posisi["ukuran"]
                else:
                    if harga >= posisi["sl"]:
                        hasil  = "LOSS"
                        keluar = posisi["sl"]
                        pnl    = (posisi["entry"] - posisi["sl"]) * posisi["ukuran"]
                    elif harga <= posisi["tp"]:
                        hasil  = "WIN"
                        keluar = posisi["tp"]
                        pnl    = (posisi["entry"] - posisi["tp"]) * posisi["ukuran"]

                if hasil:
                    modal   += pnl
                    pnl_pct  = (pnl / (modal - pnl)) * 100
                    trades.append({
                        "tanggal_masuk" : posisi["tanggal_masuk"],
                        "tanggal_keluar": str(df.index[i]),
                        "arah"    : posisi["arah"],
                        "metode"  : posisi["metode"],
                        "entry"   : round(posisi["entry"], 4),
                        "keluar"  : round(keluar, 4),
                        "hasil"   : hasil,
                        "pnl_pct" : round(pnl_pct, 2),
                        "pnl_usdt": round(pnl, 4)
                    })
                    equity.append(modal)
                    posisi = None

        total = len(trades)
        if total == 0:
            return {"error": "Tidak ada trade — coba ganti timeframe ke 1d atau tambah candle"}

        df_trades     = pd.DataFrame(trades)
        win           = len(df_trades[df_trades["hasil"] == "WIN"])
        loss          = total - win
        win_rate      = round(win / total * 100, 1)
        wins_pnl      = df_trades[df_trades["hasil"] == "WIN"]["pnl_usdt"].sum()
        losses_pnl    = abs(df_trades[df_trades["hasil"] == "LOSS"]["pnl_usdt"].sum())
        profit_factor = round(wins_pnl / losses_pnl, 2) if losses_pnl > 0 else 999
        returns       = df_trades["pnl_pct"].values
        sharpe        = round(np.mean(returns) / np.std(returns) * np.sqrt(252), 2) if np.std(returns) > 0 else 0
        equity_arr    = np.array(equity)
        peak          = np.maximum.accumulate(equity_arr)
        drawdown      = ((equity_arr - peak) / peak) * 100
        max_dd        = round(drawdown.min(), 2)
        return_total  = round(((modal - modal_awal) / modal_awal) * 100, 2)

        per_metode = df_trades.groupby("metode").apply(lambda x: pd.Series({
            "total"    : len(x),
            "win"      : len(x[x["hasil"] == "WIN"]),
            "win_rate" : round(len(x[x["hasil"] == "WIN"]) / len(x) * 100, 1),
            "pnl_total": round(x["pnl_usdt"].sum(), 2)
        })).reset_index()

        return {
            "total_trade"  : total,
            "win"          : win,
            "loss"         : loss,
            "win_rate"     : win_rate,
            "profit_factor": profit_factor,
            "sharpe"       : sharpe,
            "max_drawdown" : max_dd,
            "return_total" : return_total,
            "modal_awal"   : modal_awal,
            "modal_akhir"  : round(modal, 2),
            "equity"       : equity,
            "trades"       : df_trades,
            "per_metode"   : per_metode
        }

    except Exception as e:
        return {"error": str(e)}