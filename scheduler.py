import sys
sys.path.append("C:\\TradingBot")

import urllib3
urllib3.disable_warnings()
sys.path.append('.')

print("=== Bot Starting ===")
print(f"Python version: {sys.version}")

try:
    print("Importing scheduler...")
    from scheduler import scan_dan_alert
    print("Import OK, running scan...")
    scan_dan_alert()
    print("=== Scan Complete ===")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

import schedule
import time
from datetime import datetime

from config.settings import MODAL_TOTAL, CRYPTO_WATCHLIST
from risk import (cek_kill_switch, catat_trade, load_jurnal,
                  hitung_ukuran_posisi, statistik_jurnal,
                  equity_curve_sizing)
from data.crypto_data import get_ohlcv
from data.market_context import get_full_market_context
from strategies.indicators import analisa_lengkap, hitung_skor_sinyal
from strategies.combined_signal import skor_gabungan
from strategies.correlation import cek_over_exposure
from agent import analisa_dengan_groq
from notifications.discord_alert import (
    alert_sinyal, alert_market_context,
    alert_scan_result, kirim_discord
)
from execution.order_manager import (
    kirim_order, update_virtual_positions,
    cek_posisi_aktif, ringkasan_virtual
)

def get_modal_sekarang() -> float:
    stats   = statistik_jurnal()
    pnl_pct = stats.get("total_pnl", 0) / 100
    return MODAL_TOTAL * (1 + pnl_pct)

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
                    print(f"  🔔 Alert Discord: {symbol}")

        except Exception as e:
            print(f"  ❌ Error {symbol}: {e}")

    alert_scan_result(hasil_scan)
    if sinyal_kuat:
        print(f"\n🎯 Sinyal kuat: {', '.join(sinyal_kuat)}")
    else:
        print(f"\n⏸️ Tidak ada sinyal kuat")
    print(f"✅ Scan selesai: {datetime.now().strftime('%H:%M')}")

def auto_trade_loop():
    print(f"\n🤖 Auto trade: {datetime.now().strftime('%H:%M')}")

    # 1. Kill switch
    kill = cek_kill_switch(MODAL_TOTAL, get_modal_sekarang())
    if not kill["lanjut"]:
        kirim_discord(f"⛔ {kill['pesan']}")
        return

    # 2. Max posisi
    posisi_aktif = cek_posisi_aktif()
    if len(posisi_aktif) >= 3:
        print(f"⏸️ Max posisi ({len(posisi_aktif)}/3)")
        return

    # 3. Kondisi pasar
    ctx = get_full_market_context()
    if not ctx["boleh_trading"]:
        kirim_discord("⏸️ Kondisi pasar tidak ideal")
        return

    # 4. Equity curve sizing
    eq_sizing = equity_curve_sizing()
    print(f"📊 Equity Mode: {eq_sizing['mode']} | Risk: {eq_sizing['risk_pct']*100:.2f}%")
    if eq_sizing["mode"] != "NORMAL":
        kirim_discord(
            f"📊 **Equity Curve Adjustment**\n"
            f"Mode: `{eq_sizing['mode']}`\n"
            f"Risk: `{eq_sizing['risk_pct']*100:.2f}%`\n"
            f"{eq_sizing['alasan']}"
        )

    slot_tersedia = 3 - len(posisi_aktif)
    trade_masuk   = 0

    for symbol in CRYPTO_WATCHLIST:
        if trade_masuk >= slot_tersedia:
            break

        if any(p["symbol"] == symbol for p in posisi_aktif):
            print(f"  ⏭️ {symbol} sudah open")
            continue

        # 5. Cek korelasi
        korelasi = cek_over_exposure(
            symbol_baru  = symbol,
            posisi_aktif = posisi_aktif,
            watchlist    = CRYPTO_WATCHLIST
        )
        if not korelasi["aman"]:
            print(f"  ⚠️ Skip {symbol}: {korelasi['alasan']}")
            continue

        try:
            df      = get_ohlcv(symbol, "4h", 200)
            hasil   = analisa_lengkap(df, symbol)
            skor_tk = hitung_skor_sinyal(df, symbol, market_context=ctx)
            scoring = skor_gabungan(skor_tk, df, hasil["konsensus"])

            print(f"  {symbol}: skor={scoring['skor']} layak={scoring['layak_trade']}")

            if not scoring["layak_trade"]:
                continue

            keputusan = analisa_dengan_groq(hasil, scoring, ctx)

            if (keputusan.get("keputusan") == "HOLD" or
                    keputusan.get("keyakinan", 0) < 7 or
                    not keputusan.get("entry") or
                    not keputusan.get("stop_loss")):
                continue

            sizing_mult = scoring.get("sizing_mult", 1.0)
            sizing = hitung_ukuran_posisi(
                keputusan["entry"],
                keputusan["stop_loss"],
                leverage     = 2,
                risk_override= eq_sizing["risk_pct"]
            )

            if "error" in sizing:
                print(f"  ❌ Sizing: {sizing['error']}")
                continue

            ukuran_final = round(sizing["ukuran"] * sizing_mult, 6)

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
                    catatan  = (f"AUTO | Skor:{scoring['skor']} | "
                                f"AI:{keputusan.get('keyakinan')}/10 | "
                                f"EqMode:{eq_sizing['mode']} | "
                                f"SizeMult:{sizing_mult}"),
                    kondisi  = kondisi
                )
                trade_masuk += 1
                print(f"  ✅ Order: {symbol} {keputusan['keputusan']} "
                      f"@ {order['fill_price']}")

        except Exception as e:
            print(f"  ❌ Error {symbol}: {e}")

    if trade_masuk == 0:
        print("  ⏸️ Tidak ada trade siklus ini")

def monitor_posisi():
    closed = update_virtual_positions()
    if closed:
        print(f"📊 {len(closed)} posisi ditutup otomatis")

def ringkasan_harian():
    stats  = statistik_jurnal()
    jurnal = load_jurnal()
    open_t = [t for t in jurnal if t.get("status") == "OPEN"]
    virt   = ringkasan_virtual()
    kirim_discord(
        f"📊 **Ringkasan Harian**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 PnL: `{stats['total_pnl']:+.2f}%`\n"
        f"🏆 Win Rate: `{stats['win_rate']}%` "
        f"({stats['win']}W/{stats['loss']}L)\n"
        f"📂 Open: `{len(open_t)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Virtual: `{virt['total']}` closed | "
        f"PnL: `{virt.get('total_pnl', 0):+.4f} USDT`"
    )

def cek_drawdown_alert():
    stats = statistik_jurnal()
    if stats["total_pnl"] <= -3:
        kirim_discord(
            f"⚠️ **DRAWDOWN WARNING**\n"
            f"Drawdown: `{stats['total_pnl']:+.2f}%`"
        )

def jalankan_scheduler():
    print("🚀 Scheduler dimulai...")

    schedule.every(4).hours.do(auto_trade_loop)
    schedule.every(4).hours.do(scan_dan_alert)
    schedule.every(1).hours.do(monitor_posisi)
    schedule.every(1).hours.do(cek_drawdown_alert)
    schedule.every().day.at("08:00").do(ringkasan_harian)
    schedule.every().day.at("08:00").do(scan_dan_alert)
    schedule.every().day.at("12:00").do(scan_dan_alert)
    schedule.every().day.at("16:00").do(scan_dan_alert)
    schedule.every().day.at("20:00").do(scan_dan_alert)

    print("▶️ Scan pertama...")
    scan_dan_alert()
    auto_trade_loop()

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        print("🚀 Single Run (GitHub Actions)")
        scan_dan_alert()
        auto_trade_loop()
        monitor_posisi()
    else:
        jalankan_scheduler()