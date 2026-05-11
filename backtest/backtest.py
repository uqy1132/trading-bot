import sys
sys.path.append("C:\\TradingBot")

import pandas as pd
from data.crypto_data import get_ohlcv
from strategies.indicators import hitung_semua_indikator

def backtest_strategi(symbol: str, timeframe: str = "4h", limit: int = 500):
    """
    Backtest sederhana berdasarkan sinyal RSI + EMA
    """
    print(f"\nBacktest {symbol} | Timeframe: {timeframe} | {limit} candle")
    
    df = get_ohlcv(symbol, timeframe, limit)
    df = hitung_semua_indikator(df)
    
    modal = 3_000_000  # Rp 3 juta
    modal_awal = modal
    risk_per_trade = 0.015
    trades = []
    posisi = None

    for i in range(2, len(df)):
        baris = df.iloc[i]
        baris_prev = df.iloc[i-1]

        # Entry BUY: EMA cross up + RSI < 60
        if posisi is None:
            ema_cross_up = baris_prev["ema_20"] < baris_prev["ema_50"] and baris["ema_20"] > baris["ema_50"]
            if ema_cross_up and baris["rsi"] < 60 and baris["adx"] > 20:
                entry = baris["close"]
                sl = entry - (baris["atr"] * 2)
                tp = entry + (baris["atr"] * 4)
                risk_rp = modal * risk_per_trade
                ukuran = risk_rp / (entry - sl)
                posisi = {"entry": entry, "sl": sl, "tp": tp, "ukuran": ukuran, "tipe": "BUY"}

        # Exit posisi
        elif posisi:
            harga = baris["close"]
            if harga <= posisi["sl"]:
                pnl = (posisi["sl"] - posisi["entry"]) * posisi["ukuran"]
                modal += pnl
                trades.append({"hasil": "LOSS", "pnl": pnl})
                posisi = None
            elif harga >= posisi["tp"]:
                pnl = (posisi["tp"] - posisi["entry"]) * posisi["ukuran"]
                modal += pnl
                trades.append({"hasil": "WIN", "pnl": pnl})
                posisi = None

    # Hasil
    total = len(trades)
    if total == 0:
        print("Tidak ada trade dalam periode ini.")
        return

    menang = sum(1 for t in trades if t["hasil"] == "WIN")
    kalah = total - menang
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = (menang / total) * 100
    return_pct = ((modal - modal_awal) / modal_awal) * 100

    print(f"\n=== Hasil Backtest ===")
    print(f"Total trade : {total}")
    print(f"Menang      : {menang} | Kalah: {kalah}")
    print(f"Win rate    : {win_rate:.1f}%")
    print(f"Total PnL   : Rp {total_pnl:,.0f}")
    print(f"Return      : {return_pct:.2f}%")
    print(f"Modal akhir : Rp {modal:,.0f}")

if __name__ == "__main__":
    backtest_strategi("BTC/USDT", "4h", 500)
    backtest_strategi("SOL/USDT", "4h", 500)
    backtest_strategi("ETH/USDT", "4h", 500)