import schedule
import time
import sys
sys.path.append("C:\\TradingBot")

from data.crypto_data import get_ohlcv
from strategies.indicators import analisa_lengkap
from agent import analisa_dengan_groq
from risk import hitung_ukuran_posisi, cek_kill_switch, catat_trade
from config.settings import CRYPTO_WATCHLIST, MODAL_TOTAL

def scan_crypto():
    """Scan semua crypto dalam watchlist"""
    print("\n" + "="*50)
    print("Scanning crypto...")
    print("="*50)

    for symbol in CRYPTO_WATCHLIST:
        try:
            print(f"\nAnalisa {symbol}...")
            df = get_ohlcv(symbol, timeframe="4h", limit=200)
            analisa = analisa_lengkap(df, symbol)

            print(f"Harga: {analisa['harga']} | RSI: {analisa['rsi']} | Sinyal: {analisa['konsensus']}")

            # Hanya proses jika ada sinyal jelas
            if analisa["konsensus"] != "HOLD / TUNGGU":
                print(f"Sinyal ditemukan! Kirim ke AI...")
                keputusan = analisa_dengan_groq(analisa)

                print(f"AI: {keputusan['keputusan']} | Keyakinan: {keputusan['keyakinan']}/10")

                if keputusan["keputusan"] != "HOLD" and keputusan["keyakinan"] >= 7:
                    if keputusan["entry"] and keputusan["stop_loss"]:
                        sizing = hitung_ukuran_posisi(
                            keputusan["entry"],
                            keputusan["stop_loss"]
                        )
                        print(f"Ukuran posisi: {sizing['ukuran']} | Nilai: Rp {sizing['nilai_posisi']:,.0f}")
                        catat_trade(
                            symbol,
                            keputusan["keputusan"],
                            keputusan["entry"],
                            keputusan["stop_loss"],
                            keputusan["target_1"],
                            sizing["ukuran"]
                        )
            else:
                print(f"Sinyal lemah — skip")

        except Exception as e:
            print(f"Error {symbol}: {e}")

def jalankan_bot():
    """Fungsi utama"""
    print("\n" + "="*50)
    print("Trading Bot Aktif")
    print("="*50)

    # Cek kill switch
    kill = cek_kill_switch(MODAL_TOTAL, MODAL_TOTAL)
    if not kill["lanjut"]:
        print(kill["pesan"])
        return

    scan_crypto()
    print("\nScan selesai. Menunggu jadwal berikutnya...")

if __name__ == "__main__":
    print("Bot dimulai...")
    jalankan_bot()

    # Jadwal otomatis setiap 4 jam
    schedule.every(4).hours.do(jalankan_bot)

    while True:
        schedule.run_pending()
        time.sleep(60)