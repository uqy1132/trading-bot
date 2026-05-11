import pandas as pd
import numpy as np
from data.crypto_data import get_ohlcv

def hitung_korelasi(watchlist: list, timeframe: str = "4h",
                     limit: int = 100) -> pd.DataFrame:
    """
    Hitung matriks korelasi return antar semua aset.
    Nilai mendekati 1.0 = bergerak sangat mirip.
    """
    returns = {}
    for symbol in watchlist:
        try:
            df = get_ohlcv(symbol, timeframe, limit)
            returns[symbol] = df["close"].pct_change().dropna()
        except:
            pass

    df_returns = pd.DataFrame(returns)
    return df_returns.corr()

def cek_over_exposure(symbol_baru: str, posisi_aktif: list,
                       watchlist: list, threshold: float = 0.8) -> dict:
    """
    Cek apakah menambah posisi di symbol_baru akan
    menyebabkan over-exposure karena korelasi tinggi.

    threshold: 0.8 = tolak kalau korelasi > 80%
    """
    if not posisi_aktif:
        return {"aman": True, "alasan": "Tidak ada posisi aktif"}

    simbol_aktif = [p["symbol"] for p in posisi_aktif]

    # Hitung korelasi
    semua_simbol = list(set([symbol_baru] + simbol_aktif))
    try:
        corr_matrix = hitung_korelasi(semua_simbol)
    except:
        return {"aman": True, "alasan": "Korelasi tidak bisa dihitung"}

    # Cek korelasi symbol_baru dengan setiap posisi aktif
    konflik = []
    for sym_aktif in simbol_aktif:
        if symbol_baru not in corr_matrix or sym_aktif not in corr_matrix:
            continue
        corr = corr_matrix.loc[symbol_baru, sym_aktif]
        if abs(corr) >= threshold:
            konflik.append({
                "symbol"  : sym_aktif,
                "korelasi": round(corr, 3)
            })

    if konflik:
        konflik_str = ", ".join([f"{k['symbol']}({k['korelasi']})"
                                  for k in konflik])
        return {
            "aman"   : False,
            "alasan" : f"Korelasi tinggi dengan: {konflik_str}",
            "konflik": konflik
        }

    return {
        "aman"   : True,
        "alasan" : "Korelasi aman — tidak ada over-exposure",
        "konflik": []
    }