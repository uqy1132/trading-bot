import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from data.crypto_data import get_ohlcv
from strategies.indicators import hitung_semua_indikator

FEE_RATE    = 0.0004   # 0.04% taker per sisi (OKX/Gate)
SLIPPAGE    = 0.0003   # 0.03% slippage per sisi
SKOR_MIN    = 7        # sama dengan threshold layak_trade di live analisa
WARMUP      = 60       # candle awal yang dilewati agar indikator stabil
TP_RR       = 1.5      # target 1.5R — lebih realistis, WR lebih tinggi vs 2.5R
ALLOW_SHORT = False    # crypto cenderung bullish, short sering rugi


def _skor_inline(df: pd.DataFrame, i: int) -> int:
    """
    Replika hitung_skor_sinyal tanpa market_context/MTF
    (tidak tersedia di data historis).
    Skor max = 14 (vs 21+ di live yang punya konteks pasar).
    """
    baris      = df.iloc[i]
    baris_prev = df.iloc[i - 1]
    skor = 0

    # 1. Market structure — last 20 bars
    start = max(0, i - 19)
    highs = df["high"].values[start : i + 1]
    lows  = df["low"].values[start : i + 1]
    sh = [highs[j] for j in range(1, len(highs) - 1)
          if highs[j] > highs[j - 1] and highs[j] > highs[j + 1]]
    sl_pts = [lows[j] for j in range(1, len(lows) - 1)
              if lows[j] < lows[j - 1] and lows[j] < lows[j + 1]]
    if len(sh) >= 2 and len(sl_pts) >= 2:
        if sh[-1] > sh[-2] and sl_pts[-1] > sl_pts[-2]:    # HH + HL
            skor += 3
        elif sh[-1] < sh[-2] and sl_pts[-1] < sl_pts[-2]:  # LH + LL
            skor -= 3

    # 2. EMA alignment
    close, e20, e50 = float(baris["close"]), float(baris["ema_20"]), float(baris["ema_50"])
    if close > e20 > e50:
        skor += 2
    elif close < e20 < e50:
        skor -= 2

    # 3. ADX — direction-aware
    adx  = float(baris["adx"])
    bull = close > e20 > e50
    bear = close < e20 < e50
    if adx > 30:
        skor += 2 if bull else (-2 if bear else 1)
    elif adx > 20:
        skor += 1 if bull else (-1 if bear else 0)

    # 4. RSI
    rsi = float(baris["rsi"])
    if 45 <= rsi <= 60:   skor += 2
    elif rsi < 35:         skor += 1
    elif rsi > 70:         skor -= 2

    # 5. MACD
    mh  = float(baris.get("macd_hist",   0) or 0)
    mhp = float(baris_prev.get("macd_hist", 0) or 0)
    mv  = float(baris.get("macd",         0) or 0)
    ms  = float(baris.get("macd_signal",  0) or 0)
    if   mv > ms and mh > 0 and mh > mhp:   skor += 2
    elif mv > ms and mh > 0:                 skor += 1
    elif mv < ms and mh < 0 and mh < mhp:   skor -= 2
    elif mv < ms:                            skor -= 1

    # 6. Volume
    vr = float(baris["vol_ratio"])
    if   vr > 1.5:  skor += 2
    elif vr > 1.0:  skor += 1

    # 7. Bollinger Band position
    bb_range = float(baris["bb_upper"]) - float(baris["bb_lower"])
    if bb_range > 0:
        bb_pos = (close - float(baris["bb_lower"])) / bb_range
        if   0.4 <= bb_pos <= 0.7:  skor += 1
        elif bb_pos < 0.2:           skor += 1
        elif bb_pos > 0.9:           skor -= 1

    return skor


def _konsensus_inline(df: pd.DataFrame, i: int) -> str:
    """Replika logika konsensus analisa_lengkap di candle ke-i.

    SELL dipersyaratkan lebih ketat: selain overbought, EMA juga harus bearish
    (close < ema_50) agar tidak short di tengah uptrend.
    """
    baris      = df.iloc[i]
    baris_prev = df.iloc[i - 1]

    close = float(baris["close"])
    e20   = float(baris["ema_20"])
    e50   = float(baris["ema_50"])
    adx   = float(baris["adx"])

    ema_cross_up = (float(baris_prev["ema_20"]) < float(baris_prev["ema_50"]) and e20 > e50)
    tren_kuat    = adx > 25
    oversold     = float(baris["rsi"]) < 32 and close <= float(baris["bb_lower"]) * 1.005

    # Breakout: close > 20-bar high (tidak termasuk candle sekarang) + volume tinggi
    resistance = float(df["high"].values[max(0, i - 20) : i].max()) if i > 0 else 0.0
    breakout   = close > resistance and float(baris["vol_ratio"]) > 2.0

    # SELL: overbought + EMA bearish — hindari short di aset yang masih uptrend
    overbought    = float(baris["rsi"]) > 68 and close >= float(baris["bb_upper"]) * 0.995
    ema_bearish   = close < e50 and e20 < e50

    buy_count  = sum([ema_cross_up and tren_kuat, oversold, breakout])
    sell_signal = overbought and ema_bearish

    if buy_count >= 1:   return "BUY"   # skor >= 7 jadi filter kualitas utama
    if sell_signal:      return "SELL"
    return "HOLD"


def backtest_strategi(symbol: str, timeframe: str = "4h", limit: int = 500) -> dict:
    try:
        df = get_ohlcv(symbol, timeframe, limit)
        df = hitung_semua_indikator(df)

        if len(df) < WARMUP + 10:
            return {"error": "Data tidak cukup untuk backtest"}

        modal          = 1000.0
        modal_awal     = modal
        risk_per_trade = 0.015
        trades         = []
        equity         = [modal]
        posisi         = None

        skor_prev = 0  # track skor candle sebelumnya untuk deteksi fresh signal

        for i in range(WARMUP, len(df)):
            baris = df.iloc[i]

            if posisi is None:
                skor  = _skor_inline(df, i)
                close = float(baris["close"])
                e50   = float(baris["ema_50"])

                # Momentum filter — hanya masuk saat aset sedang in-momentum
                if i >= 20:
                    roc_20    = float(df["close"].iloc[i] / df["close"].iloc[i - 20] - 1) * 100
                    vol_14    = float(df["close"].pct_change().iloc[max(0, i - 14) : i].std()) * 100
                    mom_ratio = roc_20 / max(vol_14, 0.1)
                    in_mom    = roc_20 > 2 and mom_ratio > 0.3
                else:
                    in_mom = False

                # Fresh signal: skor baru saja melewati threshold + dalam momentum
                fresh_buy  = skor >= SKOR_MIN and skor_prev < SKOR_MIN and close > e50 and in_mom
                fresh_sell = False  # ALLOW_SHORT = False, crypto bullish bias

                skor_prev = skor

                if not fresh_buy and not fresh_sell:
                    continue

                entry = float(baris["close"])
                atr   = float(baris["atr"]) if float(baris["atr"]) > 0 else entry * 0.01

                if fresh_buy:
                    swing_low = float(df["low"].values[max(0, i - 20) : i].min())
                    sl        = max(swing_low - 0.3 * atr, entry * 0.95)
                    sl        = min(sl, entry - 0.5 * atr)
                    jarak     = entry - sl
                    if jarak <= 0:
                        continue
                    tp        = entry + jarak * TP_RR
                    entry_eff = entry * (1 + SLIPPAGE)
                    posisi = {
                        "entry": entry, "entry_eff": entry_eff,
                        "sl": sl, "tp": tp,
                        "ukuran": (modal * risk_per_trade) / jarak,
                        "arah": "BUY", "skor": skor,
                        "tanggal_masuk": str(df.index[i]),
                    }

                else:  # fresh_sell
                    swing_high = float(df["high"].values[max(0, i - 20) : i].max())
                    sl         = min(swing_high + 0.3 * atr, entry * 1.05)
                    sl         = max(sl, entry + 0.5 * atr)
                    jarak      = sl - entry
                    if jarak <= 0:
                        continue
                    tp         = entry - jarak * TP_RR
                    entry_eff  = entry * (1 - SLIPPAGE)
                    posisi = {
                        "entry": entry, "entry_eff": entry_eff,
                        "sl": sl, "tp": tp,
                        "ukuran": (modal * risk_per_trade) / jarak,
                        "arah": "SELL", "skor": skor,
                        "tanggal_masuk": str(df.index[i]),
                    }

            else:
                # Update skor_prev selama posisi terbuka agar fresh-signal bekerja setelah exit
                skor_prev = _skor_inline(df, i)

                harga  = float(baris["close"])
                hasil  = None
                keluar = None
                pnl    = None

                if posisi["arah"] == "BUY":
                    if harga <= posisi["sl"]:
                        hasil      = "LOSS"
                        keluar     = posisi["sl"]
                        keluar_eff = keluar * (1 - SLIPPAGE)
                        pnl        = (keluar_eff - posisi["entry_eff"]) * posisi["ukuran"]
                    elif harga >= posisi["tp"]:
                        hasil      = "WIN"
                        keluar     = posisi["tp"]
                        keluar_eff = keluar * (1 - SLIPPAGE)
                        pnl        = (keluar_eff - posisi["entry_eff"]) * posisi["ukuran"]
                else:
                    if harga >= posisi["sl"]:
                        hasil      = "LOSS"
                        keluar     = posisi["sl"]
                        keluar_eff = keluar * (1 + SLIPPAGE)
                        pnl        = (posisi["entry_eff"] - keluar_eff) * posisi["ukuran"]
                    elif harga <= posisi["tp"]:
                        hasil      = "WIN"
                        keluar     = posisi["tp"]
                        keluar_eff = keluar * (1 + SLIPPAGE)
                        pnl        = (posisi["entry_eff"] - keluar_eff) * posisi["ukuran"]

                if pnl is not None:
                    fee  = (posisi["entry_eff"] + keluar_eff) * posisi["ukuran"] * FEE_RATE
                    pnl -= fee

                if hasil:
                    modal  += pnl
                    pnl_pct = (pnl / (modal - pnl)) * 100
                    trades.append({
                        "tanggal_masuk" : posisi["tanggal_masuk"],
                        "tanggal_keluar": str(df.index[i]),
                        "arah"          : posisi["arah"],
                        "skor"          : posisi["skor"],
                        "entry"         : round(posisi["entry"], 4),
                        "keluar"        : round(keluar, 4),
                        "hasil"         : hasil,
                        "pnl_pct"       : round(pnl_pct, 2),
                        "pnl_usdt"      : round(pnl, 4),
                    })
                    equity.append(modal)
                    posisi = None

        total = len(trades)
        if total == 0:
            return {"error": (
                f"Tidak ada trade — tidak ada setup yang memenuhi skor ≥{SKOR_MIN}. "
                "Coba timeframe 1d atau tambah limit candle (≥500)."
            )}

        df_trades     = pd.DataFrame(trades)
        win           = len(df_trades[df_trades["hasil"] == "WIN"])
        loss          = total - win
        win_rate      = round(win / total * 100, 1)
        wins_pnl      = df_trades[df_trades["hasil"] == "WIN"]["pnl_usdt"].sum()
        losses_pnl    = abs(df_trades[df_trades["hasil"] == "LOSS"]["pnl_usdt"].sum())
        profit_factor = round(wins_pnl / losses_pnl, 2) if losses_pnl > 0 else 999.0
        returns       = df_trades["pnl_pct"].values
        sharpe        = (round(float(np.mean(returns)) / float(np.std(returns)) * np.sqrt(252), 2)
                         if float(np.std(returns)) > 0 else 0.0)
        equity_arr    = np.array(equity)
        peak          = np.maximum.accumulate(equity_arr)
        drawdown      = ((equity_arr - peak) / peak) * 100
        max_dd        = round(float(drawdown.min()), 2)
        return_total  = round(((modal - modal_awal) / modal_awal) * 100, 2)

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
        }

    except Exception as e:
        return {"error": str(e)}
