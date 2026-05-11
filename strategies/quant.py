import sys
sys.path.append("C:\\TradingBot")

import numpy as np
import pandas as pd
from scipy import stats

# ── Hurst Exponent ───────────────────────────────────
def hitung_hurst(series: pd.Series, max_lag: int = 20) -> float:
    lags = range(2, max_lag)
    tau  = [np.std(np.subtract(series[lag:].values, series[:-lag].values)) for lag in lags]
    try:
        reg = np.polyfit(np.log(list(lags)), np.log(tau), 1)
        return round(reg[0], 3)
    except:
        return 0.5

# ── Z-Score ──────────────────────────────────────────
def hitung_zscore(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    df = df.copy()
    df["zscore"]       = (df["close"] - df["close"].rolling(window).mean()) / df["close"].rolling(window).std()
    df["zscore_upper"] = 2.0
    df["zscore_lower"] = -2.0
    return df

# ── Kalman Filter Signal ─────────────────────────────
def sinyal_kalman(df: pd.DataFrame) -> dict:
    prices = df["close"].values.astype(float)
    n      = len(prices)

    # Simple Kalman Filter
    Q = 1e-5   # process noise
    R = 0.01   # measurement noise
    P = 1.0
    x = prices[0]

    estimates = []
    for z in prices:
        P = P + Q
        K = P / (P + R)
        x = x + K * (z - x)
        P = (1 - K) * P
        estimates.append(x)

    kalman_est = np.array(estimates)
    residual   = prices - kalman_est
    zscore     = round((residual[-1] - residual[-20:].mean()) / (residual[-20:].std() + 1e-8), 2)

    if zscore < -1.5:
        sinyal = "LONG"
    elif zscore > 1.5:
        sinyal = "SHORT"
    else:
        sinyal = "HOLD"

    return {
        "sinyal": sinyal,
        "zscore": zscore,
        "detail": f"Kalman z={zscore} → {sinyal}"
    }

# ── Regime Detection (tanpa HMM library) ─────────────
def deteksi_regime_hmm(df: pd.DataFrame) -> dict:
    """
    Deteksi regime pasar tanpa hmmlearn.
    Pakai kombinasi: volatilitas, trend, dan momentum.
    """
    returns   = df["close"].pct_change().dropna()
    vol_20    = returns.rolling(20).std().iloc[-1] * 100
    vol_50    = returns.rolling(50).std().iloc[-1] * 100 if len(returns) >= 50 else vol_20
    hurst     = hitung_hurst(df["close"])

    # Trend check
    ema20 = df["close"].ewm(span=20).mean().iloc[-1]
    ema50 = df["close"].ewm(span=50).mean().iloc[-1]
    harga = df["close"].iloc[-1]

    # Momentum 14 hari
    ret_14d = (df["close"].iloc[-1] / df["close"].iloc[-15] - 1) * 100 if len(df) >= 15 else 0

    if harga > ema20 > ema50 and ret_14d > 0:
        regime = "BULL"
    elif harga < ema20 < ema50 and ret_14d < 0:
        regime = "BEAR"
    else:
        regime = "SIDEWAYS"

    vol_ratio = round(vol_20 / vol_50, 2) if vol_50 > 0 else 1.0

    return {
        "regime"      : regime,
        "hurst"       : round(hurst, 3),
        "vol_kini"    : round(vol_20, 2),
        "vol_ratio"   : vol_ratio,
        "aman_trading": regime != "BEAR",
        "rekomendasi" : (
            "✅ Regime BULL — kondisi bagus untuk BUY" if regime == "BULL" else
            "❌ Regime BEAR — hindari BUY, fokus SELL/SHORT" if regime == "BEAR" else
            "⚠️ Regime SIDEWAYS — selektif, tunggu konfirmasi"
        )
    }

# ── GARCH Volatility (simplified) ────────────────────
def fit_garch(returns: pd.Series) -> dict:
    """
    Simplified GARCH-like volatility forecasting.
    Pakai EWMA sebagai proxy GARCH(1,1).
    """
    vol_ewma    = returns.ewm(span=10).std().iloc[-1] * 100
    vol_hist    = returns.rolling(30).std().iloc[-1] * 100 if len(returns) >= 30 else vol_ewma
    vol_ratio   = vol_ewma / vol_hist if vol_hist > 0 else 1.0

    if vol_ewma > 5:
        vol_state = "HIGH"
        aman      = False
        sizing    = 0.5
    elif vol_ewma < 2:
        vol_state = "LOW"
        aman      = True
        sizing    = 1.2
    else:
        vol_state = "NORMAL"
        aman      = True
        sizing    = 1.0

    return {
        "vol_forecast"     : round(vol_ewma, 2),
        "vol_state"        : vol_state,
        "aman_trading"     : aman,
        "rekomendasi_sizing": sizing
    }

# ── Multi Factor Score ────────────────────────────────
def multi_factor_score(df: pd.DataFrame) -> dict:
    returns = df["close"].pct_change().dropna()

    momentum  = (df["close"].iloc[-1] / df["close"].iloc[-20] - 1) * 100 if len(df) >= 20 else 0
    vol       = returns.rolling(14).std().iloc[-1] * 100
    trend_str = abs(df["close"].iloc[-1] - df["close"].ewm(span=50).mean().iloc[-1]) / df["close"].iloc[-1] * 100

    skor = 0
    if momentum > 5:   skor += 2
    elif momentum > 0: skor += 1
    if vol < 3:        skor += 1
    if trend_str > 2:  skor += 1

    return {
        "momentum_14d": round(momentum, 2),
        "volatilitas" : round(vol, 2),
        "trend_strength": round(trend_str, 2),
        "skor_total"  : skor
    }

# ── Quant Analisis Lengkap ────────────────────────────
def quant_analisis(df: pd.DataFrame, symbol: str) -> dict:
    returns  = df["close"].pct_change().dropna()
    regime   = deteksi_regime_hmm(df)
    garch    = fit_garch(returns)
    kalman   = sinyal_kalman(df)
    df_z     = hitung_zscore(df)
    zscore   = round(df_z["zscore"].iloc[-1], 2)

    if zscore < -2:
        sinyal_z = "STRONG BUY"
    elif zscore < -1:
        sinyal_z = "BUY"
    elif zscore > 2:
        sinyal_z = "STRONG SELL"
    elif zscore > 1:
        sinyal_z = "SELL"
    else:
        sinyal_z = "HOLD"

    return {
        "symbol"       : symbol,
        "regime"       : regime,
        "garch"        : garch,
        "kalman"       : kalman,
        "sinyal_zscore": {"zscore": zscore, "sinyal": sinyal_z},
        "rekomendasi"  : sinyal_z,
        "alasan"       : f"Regime: {regime['regime']} | Vol: {garch['vol_state']} | Z: {zscore} | Kalman: {kalman['sinyal']}"
    }

# ── Momentum Ranking ─────────────────────────────────
def hitung_momentum_ranking(data_dict: dict) -> pd.DataFrame:
    rows = []
    for symbol, df in data_dict.items():
        try:
            ret_14d = (df["close"].iloc[-1] / df["close"].iloc[-15] - 1) * 100 if len(df) >= 15 else 0
            ret_1d  = (df["close"].iloc[-1] / df["close"].iloc[-2]  - 1) * 100 if len(df) >= 2  else 0
            vol_14d = df["close"].pct_change().rolling(14).std().iloc[-1] * 100
            mom_score = ret_14d / (vol_14d + 0.01)

            rows.append({
                "symbol"        : symbol,
                "return_14d"    : round(ret_14d, 2),
                "return_1d"     : round(ret_1d, 2),
                "volatilitas_14d": round(vol_14d, 2),
                "momentum_score": round(mom_score, 2)
            })
        except:
            pass

    df_rank = pd.DataFrame(rows).sort_values("momentum_score", ascending=False)
    df_rank["rank"] = range(1, len(df_rank) + 1)

    def get_sinyal(rank, total):
        if rank <= 2:   return "LONG (Top)"
        if rank >= total - 1: return "SHORT (Bottom)"
        return "HOLD"

    total = len(df_rank)
    df_rank["sinyal"] = df_rank["rank"].apply(lambda r: get_sinyal(r, total))
    return df_rank.reset_index(drop=True)

# ── Pairs Trading ────────────────────────────────────
def hitung_spread_zscore(df1: pd.DataFrame, df2: pd.DataFrame,
                          window: int = 30):
    p1 = df1["close"].values
    p2 = df2["close"].values
    n  = min(len(p1), len(p2))
    p1, p2 = p1[-n:], p2[-n:]

    slope, intercept, _, _, _ = stats.linregress(p2, p1)
    hedge_ratio = round(slope, 4)
    spread      = p1 - hedge_ratio * p2

    spread_s    = pd.Series(spread)
    mean_s      = spread_s.rolling(window).mean()
    std_s       = spread_s.rolling(window).std()
    zscore_s    = (spread_s - mean_s) / (std_s + 1e-8)

    df_spread = pd.DataFrame({
        "spread"      : spread_s.values,
        "zscore_spread": zscore_s.values
    })
    return df_spread, hedge_ratio

def sinyal_pairs(df1, df2, sym1, sym2) -> dict:
    try:
        from scipy.stats import pearsonr
        n   = min(len(df1), len(df2))
        p1  = df1["close"].values[-n:]
        p2  = df2["close"].values[-n:]
        cor, pvalue = pearsonr(p1, p2)

        if abs(cor) < 0.7:
            return {
                "sinyal": "SKIP",
                "alasan": f"Korelasi {cor:.2f} terlalu rendah (butuh > 0.7)"
            }

        df_spread, hedge = hitung_spread_zscore(df1, df2)
        zscore = round(df_spread["zscore_spread"].iloc[-1], 2)

        if zscore < -2:
            sinyal = "LONG SPREAD"
            aksi   = f"BUY {sym1}, SELL {sym2}"
        elif zscore > 2:
            sinyal = "SHORT SPREAD"
            aksi   = f"SELL {sym1}, BUY {sym2}"
        else:
            sinyal = "HOLD"
            aksi   = "Tunggu z-score keluar dari range ±2"

        return {
            "sinyal"     : sinyal,
            "zscore"     : zscore,
            "pvalue"     : round(pvalue, 4),
            "hedge_ratio": hedge,
            "aksi"       : aksi,
            "detail"     : f"Korelasi: {cor:.2f} | Hedge ratio: {hedge} | Z-score: {zscore}"
        }
    except Exception as e:
        return {"sinyal": "SKIP", "alasan": str(e)}

# ── Kelly Criterion ──────────────────────────────────
def kelly_sizing(win_rate: float, avg_win: float, avg_loss: float,
                  modal_usdt: float) -> dict:
    if avg_loss == 0:
        return {"kelly_full": 0, "kelly_half": 0, "kelly_final": 0,
                "rekomendasi": "Avg loss tidak boleh 0"}

    b     = avg_win / avg_loss
    kelly = win_rate - ((1 - win_rate) / b)
    kelly = max(0, kelly)

    kelly_full = round(kelly * 100, 2)
    kelly_half = round(kelly_full / 2, 2)
    kelly_final= min(kelly_half, 10.0)

    return {
        "kelly_full" : kelly_full,
        "kelly_half" : kelly_half,
        "kelly_final": kelly_final,
        "rekomendasi": f"Pakai {kelly_final}% modal per trade (Half Kelly untuk keamanan)"
    }