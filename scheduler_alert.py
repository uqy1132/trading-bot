"""
Auto Alert Scanner
Scan semua pair di watchlist setiap N jam.
Kalau ada sinyal layak trade → kirim Discord otomatis.

Jalankan: python scheduler_alert.py
"""
import sys, time, traceback, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config.settings import CRYPTO_WATCHLIST
from data.crypto_data import get_ohlcv, get_open_interest, get_ticker
from data.market_context import get_full_market_context
from strategies.indicators import analisa_lengkap, hitung_skor_sinyal
from strategies.combined_signal import skor_gabungan
from notifications.discord_alert import kirim_discord
from execution.order_manager import update_virtual_positions
from paper_trading.tracker import update_paper_positions

INTERVAL_JAM   = 4      # Scan setiap 4 jam
MIN_SKOR       = 7      # Minimum skor untuk kirim alert
TIMEFRAME      = "4h"   # Timeframe utama untuk scan
ALERT_CACHE    = "logs/alert_cache.json"  # Cache duplikat alert

def format_harga(h: float) -> str:
    if h >= 1000:
        return f"${h:,.2f}"
    elif h >= 1:
        return f"${h:,.4f}"
    return f"${h:,.6f}"

# ── Alert cache (anti-duplikat Discord) ──────────────────────────────────────

def load_cache() -> dict:
    if not os.path.exists(ALERT_CACHE):
        return {}
    with open(ALERT_CACHE) as f:
        return json.load(f)

def simpan_cache(cache: dict):
    os.makedirs("logs", exist_ok=True)
    with open(ALERT_CACHE, "w") as f:
        json.dump(cache, f)

def sudah_dikirim(cache: dict, symbol: str, action: str) -> bool:
    """True jika sinyal ini sudah dikirim dalam interval terakhir."""
    key = f"{symbol}_{action}"
    if key not in cache:
        return False
    last = datetime.fromisoformat(cache[key])
    jam_lalu = (datetime.now() - last).total_seconds() / 3600
    return jam_lalu < INTERVAL_JAM

# ── TP/SL monitor ────────────────────────────────────────────────────────────

def monitor_open_trades():
    """Cek open trade vs harga live, kirim alert Discord kalau TP/SL tersentuh."""
    try:
        from risk import load_jurnal
        jurnal = load_jurnal()
    except Exception as e:
        print(f"[!] Gagal load jurnal: {e}")
        return

    open_trades = [t for t in jurnal if t.get("status") == "OPEN"]
    if not open_trades:
        return

    print(f"\n--- Monitor {len(open_trades)} open trade ---")
    for trade in open_trades:
        try:
            ticker = get_ticker(trade["symbol"])
            harga  = float(ticker.get("harga", 0))
            entry  = float(trade["entry"])
            sl     = float(trade.get("sl") or trade.get("stop_loss", 0))
            tp1    = float(trade.get("target_1", 0))
            tp2    = float(trade.get("target_2", 0))
            aksi   = trade["aksi"]

            tipe = None
            if aksi in ("BUY", "LONG"):
                if sl > 0 and harga <= sl:
                    tipe = "SL_HIT"
                elif tp2 > 0 and harga >= tp2:
                    tipe = "TP2_HIT"
                elif tp1 > 0 and harga >= tp1:
                    tipe = "TP1_HIT"
            else:
                if sl > 0 and harga >= sl:
                    tipe = "SL_HIT"
                elif tp2 > 0 and harga <= tp2:
                    tipe = "TP2_HIT"
                elif tp1 > 0 and harga <= tp1:
                    tipe = "TP1_HIT"

            if tipe:
                map_tipe = {
                    "SL_HIT" : ("🔴", "STOP LOSS TERSENTUH"),
                    "TP1_HIT": ("🟡", "TARGET 1 TERCAPAI"),
                    "TP2_HIT": ("🟢", "TARGET 2 TERCAPAI"),
                }
                emoji, label = map_tipe[tipe]
                pnl_pct = ((harga - entry) / entry) * 100 * trade.get("leverage", 1)
                if aksi in ("SELL", "SHORT"):
                    pnl_pct = -pnl_pct

                pesan = (
                    f"{emoji} **{label}**\n"
                    f"**{trade['symbol']}** {aksi} @ {format_harga(entry)}\n"
                    f"Harga: `{format_harga(harga)}` | PnL estimasi: `{pnl_pct:+.1f}%`\n"
                    f"→ Tutup posisi manual via dashboard."
                )
                kirim_discord(pesan)
                print(f"  ✅ Alert {tipe} → {trade['symbol']}")
            else:
                live_pnl = ((harga - entry) / entry) * 100 * trade.get("leverage", 1)
                if aksi in ("SELL", "SHORT"):
                    live_pnl = -live_pnl
                print(f"  {trade['symbol']} {aksi}: harga {format_harga(harga)}, PnL {live_pnl:+.1f}%")

        except Exception as e:
            print(f"  [!] {trade['symbol']}: {e}")

def scan_sekali() -> list[dict]:
    """Scan semua pair, return list sinyal yang layak."""
    print(f"\n{'='*50}")
    print(f"Auto Scan — {time.strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")

    try:
        ctx = get_full_market_context()
        btc_trend = ctx.get("btc", {}).get("trend", "UNKNOWN")
        print(f"BTC Trend : {btc_trend}")
        print(f"F&G       : {ctx.get('fear_greed', {}).get('value', '?')}")
    except Exception as e:
        print(f"[!] Gagal ambil market context: {e}")
        ctx = {}

    sinyal_kuat = []

    for symbol in CRYPTO_WATCHLIST:
        try:
            df       = get_ohlcv(symbol, TIMEFRAME, 200)
            oi_data  = get_open_interest(symbol)
            ctx_sym  = {**ctx, "open_interest": oi_data}
            hasil    = analisa_lengkap(df, symbol)
            skor_tk  = hitung_skor_sinyal(df, symbol, market_context=ctx_sym)
            scoring  = skor_gabungan(skor_tk, df, hasil["konsensus"])

            skor  = scoring["skor"]
            grade = scoring["grade"]
            layak = scoring["layak_trade"]
            arah  = scoring["arah"]

            status = "✅ SINYAL" if layak else "   -"
            print(f"{status} {symbol:12s} | {arah:5s} | Grade: {grade:18s} | Skor: {skor:3d}")

            if layak and arah in ("BUY", "SHORT"):
                sinyal_kuat.append({
                    "symbol": symbol,
                    "action": arah,
                    "grade" : grade,
                    "skor"  : skor,
                    "skor_max": scoring["skor_max"],
                    "rsi"   : hasil["rsi"],
                    "adx"   : hasil["adx"],
                    "harga" : hasil["harga"],
                    "konsensus": hasil["konsensus"],
                    "oi_trend" : oi_data.get("trend", "?"),
                    "oi_change": oi_data.get("change_pct", 0),
                })

        except Exception as e:
            print(f"   ERROR {symbol}: {e}")

    return sinyal_kuat

def kirim_alert(sinyal_list: list[dict]):
    """Format dan kirim sinyal ke Discord — skip duplikat."""
    cache = load_cache()

    # Filter: hanya kirim sinyal yang belum dikirim dalam interval terakhir
    sinyal_baru = [s for s in sinyal_list
                   if not sudah_dikirim(cache, s["symbol"], s["action"])]

    if not sinyal_list:
        print("\nTidak ada sinyal layak — tidak ada Discord yang dikirim.")
        return

    if not sinyal_baru:
        print(f"\nSemua {len(sinyal_list)} sinyal sudah dikirim sebelumnya — skip Discord.")
        return

    pesan  = f"🤖 **AUTO SCAN · {time.strftime('%d/%m %H:%M')} WIB**\n"
    pesan += f"Ditemukan **{len(sinyal_baru)}** sinyal baru:\n\n"

    for s in sinyal_baru:
        emoji = "🟢" if s["action"] == "BUY" else "🔴"
        oi_info = ""
        if s["oi_trend"] not in ("UNKNOWN", "?"):
            arrow = "↑" if s["oi_trend"] == "RISING" else "↓" if s["oi_trend"] == "FALLING" else "→"
            oi_info = f" | OI {arrow} {s['oi_change']:+.1f}%"

        pesan += (
            f"{emoji} **{s['symbol']}** — `{s['action']}`\n"
            f"   Grade: `{s['grade']}` | Score: `{s['skor']}/{s['skor_max']}`\n"
            f"   Harga: `{format_harga(s['harga'])}` | RSI: `{s['rsi']}` | ADX: `{s['adx']}`{oi_info}\n\n"
        )

    pesan += "_Buka dashboard untuk analisa lengkap & entry point._"

    try:
        kirim_discord(pesan)
        print(f"\n✅ Alert Discord terkirim — {len(sinyal_baru)} sinyal baru")
        # Update cache hanya untuk sinyal yang berhasil dikirim
        for s in sinyal_baru:
            cache[f"{s['symbol']}_{s['action']}"] = datetime.now().isoformat()
        simpan_cache(cache)
    except Exception as e:
        print(f"\n[!] Gagal kirim Discord: {e}")

def main():
    print(f"🤖 Auto Alert Scanner aktif")
    print(f"   Interval  : setiap {INTERVAL_JAM} jam")
    print(f"   Timeframe : {TIMEFRAME}")
    print(f"   Watchlist : {len(CRYPTO_WATCHLIST)} pair")
    print(f"   Min skor  : {MIN_SKOR}")

    while True:
        try:
            update_virtual_positions()  # auto-close virtual/live order yang kena TP/SL
            update_paper_positions()    # auto-close paper trade yang kena TP/SL
            monitor_open_trades()       # cek open trade jurnal vs TP/SL
            sinyal = scan_sekali()
            kirim_alert(sinyal)
        except Exception as e:
            print(f"\n[!] Error scan: {e}")
            traceback.print_exc()

        waktu_berikut = time.strftime('%H:%M', time.localtime(time.time() + INTERVAL_JAM * 3600))
        print(f"\nScan berikutnya pukul {waktu_berikut} ({INTERVAL_JAM} jam lagi)...")
        time.sleep(INTERVAL_JAM * 3600)

if __name__ == "__main__":
    main()
