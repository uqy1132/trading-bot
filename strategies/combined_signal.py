import sys
sys.path.append("C:\\TradingBot")

import pandas as pd
import numpy as np
from strategies.quant import (
    deteksi_regime_hmm, fit_garch, sinyal_kalman, multi_factor_score
)

def filter_quant(df: pd.DataFrame, sinyal_teknikal: str) -> dict:
    """
    Jalankan quant filter terhadap sinyal teknikal.
    Kembalikan: apakah sinyal valid + alasan + sizing multiplier.
    """
    returns = df["close"].pct_change().dropna()

    # 1. HMM Regime
    try:
        regime = deteksi_regime_hmm(df)
    except Exception:
        regime = {"regime": "UNKNOWN", "aman_trading": True,
                  "rekomendasi": "Regime tidak bisa dihitung"}

    # 2. GARCH Volatility
    try:
        garch = fit_garch(returns)
    except Exception:
        garch = {"vol_state": "NORMAL", "aman_trading": True,
                 "rekomendasi_sizing": 1.0}

    # 3. Kalman Z-Score
    try:
        kalman = sinyal_kalman(df)
    except Exception:
        kalman = {"sinyal": "HOLD", "zscore": 0, "detail": "-"}

    # ── Logika filter ────────────────────────────────────
    lolos      = True
    penalti    = 0
    bonus      = 0
    alasan     = []
    sizing_mult= garch.get("rekomendasi_sizing", 1.0)

    # Filter 1: Regime
    if regime["regime"] == "BEAR" and "BUY" in sinyal_teknikal:
        lolos   = False
        penalti += 3
        alasan.append("❌ Regime BEAR — sinyal BUY ditolak")
    elif regime["regime"] == "BULL" and "BUY" in sinyal_teknikal:
        bonus  += 2
        alasan.append("✅ Regime BULL — mendukung BUY")
    elif regime["regime"] == "UNKNOWN":
        alasan.append("⚠️ Regime tidak terdeteksi — hati-hati")

    # Filter 2: GARCH volatilitas ekstrem
    if not garch.get("aman_trading", True):
        lolos      = False
        penalti   += 2
        sizing_mult = 0.5
        alasan.append(f"❌ Volatilitas HIGH ({garch.get('vol_forecast', 0):.1f}%) — sizing dikurangi 50%")
    elif garch["vol_state"] == "LOW":
        bonus  += 1
        alasan.append(f"✅ Volatilitas rendah — kondisi ideal")

    # Filter 3: Kalman Z-Score konfirmasi
    if kalman["sinyal"] == "LONG" and "BUY" in sinyal_teknikal:
        bonus  += 2
        alasan.append(f"✅ Kalman konfirmasi LONG (z={kalman['zscore']})")
    elif kalman["sinyal"] == "SHORT" and "SELL" in sinyal_teknikal:
        bonus  += 2
        alasan.append(f"✅ Kalman konfirmasi SHORT (z={kalman['zscore']})")
    elif kalman["sinyal"] != "HOLD" and kalman["sinyal"] not in sinyal_teknikal:
        penalti += 1
        alasan.append(f"⚠️ Kalman berlawanan ({kalman['sinyal']}) — keyakinan berkurang")

    skor_quant = bonus - penalti

    return {
        "lolos"       : lolos,
        "skor_quant"  : skor_quant,
        "sizing_mult" : round(sizing_mult, 2),
        "regime"      : regime["regime"],
        "vol_state"   : garch["vol_state"],
        "kalman"      : kalman["sinyal"],
        "alasan"      : alasan,
        "ringkasan"   : "PASS ✅" if lolos else "FILTERED ❌"
    }


def skor_gabungan(skor_teknikal: dict, df: pd.DataFrame,
                   sinyal: str) -> dict:
    """
    Gabungkan skor teknikal + quant menjadi skor final.
    
    skor_teknikal: output dari hitung_skor_sinyal()
    """
    quant = filter_quant(df, sinyal)

    skor_final    = skor_teknikal["skor"] + quant["skor_quant"]
    skor_max_baru = skor_teknikal["skor_max"] + 5

    # Recalculate grade
    if skor_final >= 13:
        grade = "A+ (Sangat Kuat)"
    elif skor_final >= 10:
        grade = "A (Kuat)"
    elif skor_final >= 7:
        grade = "B (Cukup)"
    elif skor_final >= 4:
        grade = "C (Lemah)"
    else:
        grade = "D (Hindari)"

    layak = quant["lolos"] and skor_final >= 7

    return {
        "skor"        : skor_final,
        "skor_max"    : skor_max_baru,
        "skor_teknikal": skor_teknikal["skor"],
        "skor_quant"  : quant["skor_quant"],
        "grade"       : grade,
        "layak_trade" : layak,
        "sizing_mult" : quant["sizing_mult"],
        "quant_filter": quant,
        "detail"      : {
            **skor_teknikal.get("detail", {}),
            "Quant Regime"  : f"{quant['regime']} ({'+' if quant['skor_quant'] >= 0 else ''}{quant['skor_quant']} poin)",
            "Quant Vol"     : quant["vol_state"],
            "Quant Kalman"  : quant["kalman"],
            "Quant Filter"  : quant["ringkasan"]
        }
    }