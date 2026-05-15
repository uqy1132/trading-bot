import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from data.crypto_data import get_ohlcv
from strategies.indicators import hitung_semua_indikator
from strategies.smc import analisa_smc

FEE_RATE = 0.0004   # 0.04% taker per sisi (OKX/Gate)
SLIPPAGE = 0.0003   # 0.03% slippage per sisi
TP_RR    = 3.0      # Kevin Sailly 1:3
WARMUP   = 80       # candle awal yang dilewati agar OB detection stabil
COOLDOWN = 5        # candle jeda minimum antar evaluasi sinyal


def backtest_strategi(symbol: str, timeframe: str = "15m", limit: int = 500) -> dict:
    """
    Backtest strategi SMC / Order Block — Kevin Sailly style.
    Entry: price masuk zona OTE/OB (bullish)
    SL   : OB low
    TP   : entry + (entry - SL) * 3  → RR 1:3
    """
    try:
        tf_map = {"15M": "15m", "30M": "30m", "1H": "1h", "4H": "4h", "1D": "1d"}
        tf = tf_map.get(timeframe.upper(), timeframe.lower())

        df = get_ohlcv(symbol, tf, limit)
        df = hitung_semua_indikator(df)

        if len(df) < WARMUP + 20:
            return {"error": "Data tidak cukup untuk backtest"}

        modal          = 1000.0
        modal_awal     = modal
        risk_per_trade = 0.015
        trades         = []
        equity         = [modal]
        posisi         = None
        last_eval      = -COOLDOWN  # candle terakhir dievaluasi

        for i in range(WARMUP, len(df)):
            baris = df.iloc[i]
            high  = float(baris["high"])
            low   = float(baris["low"])
            close = float(baris["close"])

            # ── Cari sinyal (hanya saat tidak ada posisi terbuka) ────────────
            if posisi is None:
                if i - last_eval < COOLDOWN:
                    continue
                last_eval = i

                # SMC analysis pada window historis sampai candle ke-i
                window = df.iloc[max(0, i - 150): i + 1]
                try:
                    smc = analisa_smc(window)
                except Exception:
                    continue

                quality   = smc.get("entry_quality", "WAIT")
                near_bull = smc.get("nearest_bull_ob")

                if quality not in ("OPTIMAL", "VALID") or not near_bull:
                    continue

                # Konfirmasi RSI + EMA
                cl    = window["close"]
                delta = cl.diff()
                gain  = delta.clip(lower=0).rolling(14).mean()
                loss  = (-delta.clip(upper=0)).rolling(14).mean()
                rsi   = float(100 - 100 / (1 + (gain / (loss + 1e-8)).iloc[-1]))
                ema20 = float(cl.ewm(span=20).mean().iloc[-1])
                ema50 = float(cl.ewm(span=50).mean().iloc[-1])

                conf = 0
                if smc["in_bull_ote"]:  conf += 3
                elif smc["in_bull_ob"]: conf += 2
                if rsi < 45:            conf += 1
                if ema20 > ema50:       conf += 1
                if conf < 3:
                    continue

                # Hitung level entry / SL / TP
                ob_mid = near_bull["midpoint"]
                ob_sl  = near_bull["ob_low"]
                risk   = ob_mid - ob_sl
                if risk <= 0:
                    continue
                ob_tp = ob_mid + risk * TP_RR

                # Masuk di close candle (market order simulasi)
                entry     = close
                entry_eff = entry * (1 + SLIPPAGE)

                # SL tidak boleh lebih dari 8% di bawah entry (hindari sizing ekstrem)
                if (entry - ob_sl) / entry > 0.08:
                    continue

                ukuran = (modal * risk_per_trade) / (entry - ob_sl)
                if ukuran <= 0:
                    continue

                posisi = {
                    "entry"        : entry,
                    "entry_eff"    : entry_eff,
                    "sl"           : ob_sl,
                    "tp"           : ob_tp,
                    "ukuran"       : ukuran,
                    "quality"      : quality,
                    "conf"         : conf,
                    "tanggal_masuk": str(df.index[i]),
                }

            # ── Manage posisi terbuka ─────────────────────────────────────────
            else:
                hasil = keluar = pnl = keluar_eff = None

                if low <= posisi["sl"]:
                    hasil      = "LOSS"
                    keluar     = posisi["sl"]
                    keluar_eff = keluar * (1 - SLIPPAGE)
                    pnl        = (keluar_eff - posisi["entry_eff"]) * posisi["ukuran"]
                elif high >= posisi["tp"]:
                    hasil      = "WIN"
                    keluar     = posisi["tp"]
                    keluar_eff = keluar * (1 - SLIPPAGE)
                    pnl        = (keluar_eff - posisi["entry_eff"]) * posisi["ukuran"]

                if hasil:
                    fee   = (posisi["entry_eff"] + keluar_eff) * posisi["ukuran"] * FEE_RATE
                    pnl  -= fee
                    modal += pnl
                    pnl_pct = (pnl / (modal - pnl)) * 100
                    trades.append({
                        "tanggal_masuk" : posisi["tanggal_masuk"],
                        "tanggal_keluar": str(df.index[i]),
                        "arah"          : "BUY",
                        "skor"          : posisi["conf"],
                        "entry"         : round(posisi["entry"], 6),
                        "keluar"        : round(keluar, 6),
                        "hasil"         : hasil,
                        "pnl_pct"       : round(pnl_pct, 2),
                        "pnl_usdt"      : round(pnl, 4),
                        "metode"        : f"SMC-{posisi['quality']}",
                    })
                    equity.append(modal)
                    posisi = None

        total = len(trades)
        if total == 0:
            return {"error": (
                "Tidak ada trade — tidak ada setup SMC OTE/VALID yang ditemukan. "
                "Coba timeframe 15M atau tambah limit candle (≥500)."
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
