import sys
sys.path.append("C:\\TradingBot")

import pandas as pd
import numpy as np
from strategies.quant import (
    deteksi_regime_hmm, fit_garch, sinyal_kalman, multi_factor_score
)

def skor_momentum(df: pd.DataFrame) -> dict:
    """
    Risk-adjusted momentum score (Sharpe-like).
    HOT = return tinggi relatif terhadap volatilitas → aset layak dimasuki.
    """
    close = df["close"]
    n     = len(close)

    roc_5  = float((close.iloc[-1] / close.iloc[-6]  - 1) * 100) if n >= 6  else 0.0
    roc_14 = float((close.iloc[-1] / close.iloc[-15] - 1) * 100) if n >= 15 else 0.0
    roc_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if n >= 21 else 0.0

    vol_14    = float(close.pct_change().rolling(14).std().iloc[-1] * 100) if n >= 14 else 1.0
    vol_14    = max(vol_14, 0.1)
    mom_ratio = roc_14 / vol_14  # semakin tinggi = semakin momentum

    skor = 0
    if   roc_20 > 10:  skor += 3
    elif roc_20 > 5:   skor += 2
    elif roc_20 > 0:   skor += 1
    elif roc_20 < -5:  skor -= 2
    elif roc_20 < 0:   skor -= 1

    if   roc_5 > 3:   skor += 1
    elif roc_5 < -3:  skor -= 1

    if   mom_ratio > 1.5:  grade = "HOT"
    elif mom_ratio > 0.5:  grade = "WARM"
    elif mom_ratio > 0.0:  grade = "NETRAL"
    else:                  grade = "BEARISH"

    return {
        "skor"        : skor,
        "grade"       : grade,
        "roc_5"       : round(roc_5, 2),
        "roc_14"      : round(roc_14, 2),
        "roc_20"      : round(roc_20, 2),
        "mom_ratio"   : round(mom_ratio, 2),
        "in_momentum" : mom_ratio > 0.3 and roc_20 > 0,
    }


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
    lolos       = True
    penalti     = 0
    bonus       = 0
    alasan      = []
    sizing_mult = garch.get("rekomendasi_sizing", 1.0)
    skor_regime = 0
    skor_vol    = 0
    skor_kalman = 0

    # Filter 1: Regime — selalu beri penalti untuk BEAR
    if regime["regime"] == "BEAR":
        if "BUY" in sinyal_teknikal:
            lolos    = False
            penalti += 3
            skor_regime = -3
            alasan.append("❌ Regime BEAR — sinyal BUY ditolak")
        else:
            penalti += 1
            skor_regime = -1
            alasan.append("⚠️ Regime BEAR — hindari posisi long")
    elif regime["regime"] == "BULL":
        if "BUY" in sinyal_teknikal:
            bonus  += 2
            skor_regime = 2
            alasan.append("✅ Regime BULL — mendukung BUY")
        else:
            skor_regime = 0
    elif regime["regime"] == "UNKNOWN":
        alasan.append("⚠️ Regime tidak terdeteksi — hati-hati")

    # Filter 2: GARCH volatilitas ekstrem
    if not garch.get("aman_trading", True):
        lolos       = False
        penalti    += 2
        skor_vol    = -2
        sizing_mult = 0.5
        alasan.append(f"❌ Volatilitas HIGH ({garch.get('vol_forecast', 0):.1f}%) — sizing dikurangi 50%")
    elif garch["vol_state"] == "LOW":
        bonus   += 1
        skor_vol = 1
        alasan.append("✅ Volatilitas rendah — kondisi ideal")

    # Filter 3: Kalman Z-Score konfirmasi
    if kalman["sinyal"] == "LONG" and "BUY" in sinyal_teknikal:
        bonus      += 2
        skor_kalman = 2
        alasan.append(f"✅ Kalman konfirmasi LONG (z={kalman['zscore']})")
    elif kalman["sinyal"] == "SHORT" and "SELL" in sinyal_teknikal:
        bonus      += 2
        skor_kalman = 2
        alasan.append(f"✅ Kalman konfirmasi SHORT (z={kalman['zscore']})")
    elif kalman["sinyal"] != "HOLD" and kalman["sinyal"] not in sinyal_teknikal:
        penalti    += 1
        skor_kalman = -1
        alasan.append(f"⚠️ Kalman berlawanan ({kalman['sinyal']}) — keyakinan berkurang")

    skor_quant = bonus - penalti

    def fmt(v: int) -> str:
        return f"+{v}" if v >= 0 else str(v)

    return {
        "lolos"       : lolos,
        "skor_quant"  : skor_quant,
        "sizing_mult" : round(sizing_mult, 2),
        "regime"      : regime["regime"],
        "vol_state"   : garch["vol_state"],
        "kalman"      : kalman["sinyal"],
        "alasan"      : alasan,
        "ringkasan"   : "PASS ✅" if lolos else "FILTERED ❌",
        "skor_regime" : skor_regime,
        "skor_vol"    : skor_vol,
        "skor_kalman" : skor_kalman,
        "detail_quant": {
            "Quant Regime": f"{regime['regime']} ({fmt(skor_regime)} poin)",
            "Quant Vol"   : f"{garch['vol_state']} ({fmt(skor_vol)} poin)",
            "Quant Kalman": f"{kalman['sinyal']} ({fmt(skor_kalman)} poin)",
            "Quant Filter": "PASS ✅" if lolos else "FILTERED ❌",
        }
    }


def skor_gabungan(skor_teknikal: dict, df: pd.DataFrame,
                   sinyal: str) -> dict:
    """
    Gabungkan skor teknikal + momentum + quant menjadi skor final.
    Opsi 3: Momentum filter + Swing entry — hanya BUY aset yang sedang in-momentum.
    """
    quant = filter_quant(df, sinyal)
    mom   = skor_momentum(df)

    skor_final    = skor_teknikal["skor"] + quant["skor_quant"] + mom["skor"]
    skor_max_baru = skor_teknikal["skor_max"] + 5 + 4  # quant(5) + momentum(4)

    if   skor_final >= 14: grade = "A+"
    elif skor_final >= 11: grade = "A"
    elif skor_final >= 8:  grade = "B"
    elif skor_final >= 5:  grade = "C"
    else:                  grade = "D"

    # Layak: teknikal OK + quant lolos + aset sedang in-momentum
    layak = quant["lolos"] and skor_final >= 8 and mom["in_momentum"]

    return {
        "skor"          : skor_final,
        "skor_max"      : skor_max_baru,
        "skor_teknikal" : skor_teknikal["skor"],
        "skor_quant"    : quant["skor_quant"],
        "skor_momentum" : mom["skor"],
        "mom_grade"     : mom["grade"],
        "mom_ratio"     : mom["mom_ratio"],
        "roc_20"        : mom["roc_20"],
        "in_momentum"   : mom["in_momentum"],
        "grade"         : grade,
        "layak_trade"   : layak,
        "arah"          : "BUY" if layak else "WAIT",
        "sizing_mult"   : quant["sizing_mult"],
        "quant_filter"  : quant,
        "detail"        : {
            **skor_teknikal.get("detail", {}),
            **quant["detail_quant"],
            "Momentum"  : f"{mom['grade']} · ROC20={mom['roc_20']:+.1f}% · ratio={mom['mom_ratio']:.1f}",
        }
    }