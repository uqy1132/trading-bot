import sys
sys.path.append("C:\\TradingBot")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import schedule
import time
from datetime import datetime

from config.settings import MODAL_TOTAL, CRYPTO_WATCHLIST
from risk import (cek_kill_switch, catat_trade, load_jurnal,
                  hitung_ukuran_posisi, statistik_jurnal)
from data.crypto_data import get_ohlcv
from data.market_context import get_full_market_context
from strategies.indicators import analisa_lengkap, hitung_skor_sinyal
from strategies.combined_signal import skor_gabungan
from agent import analisa_dengan_groq
from notifications.discord_alert import (
    alert_sinyal, alert_market_context,
    alert_scan_result, kirim_discord
)
from execution.order_manager import (
    kirim_order, update_virtual_positions,
    cek_posisi_aktif, ringkasan_virtual
)

# ════════════════════════════════════════════════════════
# HELPER
# ════════════════════════════════════════════════════════

def get_modal_sekarang() -> float:
    stats   = statistik_jurnal()
    pnl_pct = stats.get("total_pnl", 0) / 100
    return MODAL_TOTAL * (1 + pnl_pct)

# ════════════════════════════════════════════════════════
# 1. SCAN & ALERT (tanpa auto eksekusi)
# ════════════════════════════════════════════════════════

def scan_dan_alert():
    print(f"\n{'='*50}")
    print(f"🤖 Auto-scan: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    ctx = get_full_market_context()
    alert_market_context(ctx)
    print(f"BTC: {ctx['btc']['trend']} | F&G: {ctx['fear_greed']['value']}")

    hasil_scan  = []
    sinyal_kuat = []

    for symbol in CRYPTO_WATCHLIST:
        try:
            print(f"Scanning {symbol}...")
            df      = get_ohlcv(symbol, "4h", 200)
            analisa = analisa_lengkap(df, symbol)
            scoring = hitung_skor_sinyal(df, symbol, market_context=ctx)

            hasil_scan.append({
                "aset"  : symbol,
                "sinyal": analisa["konsensus"],
                "rsi"   : analisa["rsi"],
                "adx"   : analisa["adx"]
            })

            print(f"  {symbol}: {analisa['konsensus']} | "
                  f"Skor: {scoring['skor']} | Grade: {scoring['grade']}")

            if scoring["layak_trade"] or scoring["skor"] >= 8:
                print(f"  ✅ Sinyal kuat — kirim ke AI...")
                keputusan = analisa_dengan_groq(
                    analisa, scoring=scoring, market_context=ctx
                )

                if (keputusan.get("keputusan") != "HOLD" and
                        keputusan.get("keyakinan", 0) >= 7 and
                        keputusan.get("entry") and
                        keputusan.get("stop_loss")):

                    sizing = hitung_ukuran_posisi(
                        keputusan["entry"], keputusan["stop_loss"]
                    )
                    alert_sinyal(symbol, keputusan, scoring, sizing)
                    sinyal_kuat.append(symbol)
                    print(f"  🔔 Alert Discord terkirim: {symbol}")

        except Exception as e:
            print(f"  ❌ Error {symbol}: {e}")

    alert_scan_result(hasil_scan)

    if sinyal_kuat:
        print(f"\n🎯 Sinyal kuat: {', '.join(sinyal_kuat)}")
    else:
        print(f"\n⏸️ Tidak ada sinyal kuat")

    print(f"✅ Scan selesai: {datetime.now().strftime('%H:%M')}")

# ════════════════════════════════════════════════════════
# 2. AUTO TRADE (virtual — paper trading otomatis)
# ════════════════════════════════════════════════════════

def auto_trade_loop():
    """
    Pipeline otomatis penuh dengan virtual execution.
    Scan → filter → sizing → kirim virtual order → catat jurnal.
    """
    print(f"\n🤖 Auto trade loop: {datetime.now().strftime('%H:%M')}")

    # Cek kill switch
    kill = cek_kill_switch(MODAL_TOTAL, get_modal_sekarang())
    if not kill["lanjut"]:
        kirim_discord(f"⛔ {kill['pesan']}")
        print(f"⛔ Kill switch aktif: {kill['pesan']}")
        return

    # Cek posisi aktif — max 3
    posisi_aktif = cek_posisi_aktif()
    if len(posisi_aktif) >= 3:
        print(f"⏸️ Max posisi tercapai ({len(posisi_aktif)}/3) — skip")
        return

    # Cek kondisi pasar
    ctx = get_full_market_context()
    if not ctx["boleh_trading"]:
        kirim_discord("⏸️ Kondisi pasar tidak ideal — skip auto trade")
        return

    slot_tersedia = 3 - len(posisi_aktif)
    trade_masuk   = 0

    for symbol in CRYPTO_WATCHLIST:
        if trade_masuk >= slot_tersedia:
            break

        # Skip kalau sudah ada posisi di aset ini
        if any(p["symbol"] == symbol for p in posisi_aktif):
            print(f"  ⏭️ {symbol} sudah ada posisi aktif")
            continue

        try:
            df        = get_ohlcv(symbol, "4h", 200)
            hasil     = analisa_lengkap(df, symbol)
            skor_tk   = hitung_skor_sinyal(df, symbol, market_context=ctx)
            scoring   = skor_gabungan(skor_tk, df, hasil["konsensus"])

            print(f"  {symbol}: skor={scoring['skor']} "
                  f"layak={scoring['layak_trade']}")

            if not scoring["layak_trade"]:
                continue

            keputusan = analisa_dengan_groq(hasil, scoring, ctx)

            if (keputusan.get("keputusan") == "HOLD" or
                    keputusan.get("keyakinan", 0) < 7 or
                    not keputusan.get("entry") or
                    not keputusan.get("stop_loss")):
                continue

            # Hitung sizing dengan quant multiplier
            sizing_mult = scoring.get("sizing_mult", 1.0)
            sizing = hitung_ukuran_posisi(
                keputusan["entry"],
                keputusan["stop_loss"],
                leverage=2
            )

            if "error" in sizing:
                print(f"  ❌ Sizing error: {sizing['error']}")
                continue

            # Sesuaikan ukuran dengan quant multiplier
            ukuran_final = round(sizing["ukuran"] * sizing_mult, 6)

            # Eksekusi virtual order
            order = kirim_order(
                symbol   = symbol,
                aksi     = keputusan["keputusan"],
                ukuran   = ukuran_final,
                entry    = keputusan["entry"],
                sl       = keputusan["stop_loss"],
                tp1      = keputusan.get("target_1", 0),
                leverage = 2
            )

            if order["status"] == "OK":
                # Catat ke jurnal manual juga
                kondisi = {
                    "rsi"      : hasil.get("rsi"),
                    "adx"      : hasil.get("adx"),
                    "btc_trend": ctx.get("btc", {}).get("trend"),
                    "skor"     : scoring.get("skor"),
                    "leverage" : 2
                }
                catat_trade(
                    symbol   = symbol,
                    aksi     = keputusan["keputusan"],
                    entry    = keputusan["entry"],
                    sl       = keputusan["stop_loss"],
                    target_1 = keputusan.get("target_1", 0),
                    target_2 = keputusan.get("target_2", 0),
                    ukuran   = ukuran_final,
                    leverage = 2,
                    catatan  = f"AUTO | Skor:{scoring['skor']} | "
                               f"Keyakinan:{keputusan.get('keyakinan')}/10 | "
                               f"SizingMult:{sizing_mult}",
                    kondisi  = kondisi
                )
                trade_masuk += 1
                print(f"  ✅ Virtual order masuk: {symbol} "
                      f"{keputusan['keputusan']} @ {order['fill_price']}")

        except Exception as e:
            print(f"  ❌ Error {symbol}: {e}")

    if trade_masuk == 0:
        print("  ⏸️ Tidak ada trade yang masuk siklus ini")

# ════════════════════════════════════════════════════════
# 3. MONITOR POSISI VIRTUAL
# ════════════════════════════════════════════════════════

def monitor_posisi():
    """
    Cek posisi virtual tiap jam — apakah SL atau TP sudah kena.
    """
    closed = update_virtual_positions()
    if closed:
        print(f"📊 {len(closed)} posisi virtual ditutup otomatis")

# ════════════════════════════════════════════════════════
# 4. LAPORAN & MONITORING
# ════════════════════════════════════════════════════════

def ringkasan_harian():
    stats  = statistik_jurnal()
    jurnal = load_jurnal()
    open_t = [t for t in jurnal if t.get("status") == "OPEN"]
    virt   = ringkasan_virtual()

    pesan = (
        f"📊 **Ringkasan Harian**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 PnL Journal: `{stats['total_pnl']:+.2f}%`\n"
        f"🏆 Win Rate: `{stats['win_rate']}%` "
        f"({stats['win']}W / {stats['loss']}L)\n"
        f"📂 Posisi Open: `{len(open_t)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Virtual Trades: `{virt['total']}` closed\n"
        f"📈 Virtual PnL: `{virt.get('total_pnl', 0):+.4f} USDT`\n"
        f"🎯 Target Bulanan: 4-5%"
    )
    kirim_discord(pesan)

def cek_drawdown_alert():
    stats = statistik_jurnal()
    if stats["total_pnl"] <= -3:
        kirim_discord(
            f"⚠️ **DRAWDOWN WARNING**\n"
            f"Drawdown: `{stats['total_pnl']:+.2f}%`\n"
            f"Mendekati batas harian!\n"
            f"Pertimbangkan pause trading."
        )

# ════════════════════════════════════════════════════════
# 5. MAIN SCHEDULER
# ════════════════════════════════════════════════════════

def jalankan_scheduler():
    print("🚀 Scheduler dimulai...")
    print(f"📅 Auto-scan + auto-trade setiap 4 jam")
    print(f"🔍 Monitor posisi setiap 1 jam")

    # Auto trade + scan tiap 4 jam
    schedule.every(4).hours.do(auto_trade_loop)
    schedule.every(4).hours.do(scan_dan_alert)

    # Monitor posisi tiap 1 jam
    schedule.every(1).hours.do(monitor_posisi)

    # Cek drawdown tiap 1 jam
    schedule.every(1).hours.do(cek_drawdown_alert)

    # Laporan harian
    schedule.every().day.at("08:00").do(ringkasan_harian)
    schedule.every().day.at("08:00").do(scan_dan_alert)
    schedule.every().day.at("12:00").do(scan_dan_alert)
    schedule.every().day.at("16:00").do(scan_dan_alert)
    schedule.every().day.at("20:00").do(scan_dan_alert)

    # Langsung jalankan sekali saat start
    print("\n▶️ Menjalankan scan pertama...")
    scan_dan_alert()
    auto_trade_loop()

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    jalankan_scheduler()