import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("config/.env")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def kirim_discord(pesan: str, title: str = "🤖 Trading Bot", color: int = 0x00ff00):
    """Kirim notifikasi ke Discord via webhook"""
    if not WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL tidak ditemukan di .env")
        return False

    embed = {
        "title": title,
        "description": pesan,
        "color": color,
        "footer": {"text": f"Trading Bot • {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
    }

    try:
        r = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, verify=False)
        if r.status_code == 204:
            print("✅ Discord alert terkirim")
            return True
        else:
            print(f"❌ Discord error: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Gagal kirim Discord: {e}")
        return False

def alert_sinyal(symbol, keputusan, scoring, sizing, quant_filter=None):
    """
    Kirim alert sinyal ke Discord dengan konteks quant.
    """
    emoji = {"BUY": "🟢", "SELL": "🔴", "SHORT": "🔴", "HOLD": "⏸️"}
    e = emoji.get(keputusan.get("keputusan", "HOLD"), "⚪")

    # Bagian quant (opsional)
    quant_section = ""
    if quant_filter:
        regime_emoji = "🟢" if quant_filter["regime"] == "BULL" else \
                       "🔴" if quant_filter["regime"] == "BEAR" else "🟡"
        vol_emoji    = "🔴" if quant_filter["vol_state"] == "HIGH" else \
                       "🟢" if quant_filter["vol_state"] == "LOW" else "🟡"
        quant_section = f"""
**📐 Quant Context:**
{regime_emoji} Regime: `{quant_filter['regime']}`
{vol_emoji} Volatilitas: `{quant_filter['vol_state']}`
📊 Kalman: `{quant_filter['kalman']}`
⚡ Sizing Multiplier: `{quant_filter['sizing_mult']}x`
"""

    pesan = f"""
{e} **SINYAL TRADING** {e}
━━━━━━━━━━━━━━━━━━━━━━━━
**Aset:** `{symbol}`
**Aksi:** {keputusan.get('keputusan', '-')}
**Keyakinan:** {'⭐' * keputusan.get('keyakinan', 0)} ({keputusan.get('keyakinan', 0)}/10)
━━━━━━━━━━━━━━━━━━━━━━━━
💰 **Entry:** `{keputusan.get('entry', '-')}`
🛑 **Stop Loss:** `{keputusan.get('stop_loss', '-')}`
🎯 **Target 1:** `{keputusan.get('target_1', '-')}`
🎯 **Target 2:** `{keputusan.get('target_2', '-')}`
⚖️ **R:R:** `1:{keputusan.get('rr_ratio', '-')}`
━━━━━━━━━━━━━━━━━━━━━━━━
🏆 **Skor:** {scoring.get('skor', '-')}/{scoring.get('skor_max', '-')} — {scoring.get('grade', '-')}
📦 **Sizing:** {sizing.get('ukuran', '-')} unit | Max loss: Rp {sizing.get('risk_rupiah', 0):,.0f}
💼 **Nilai:** Rp {sizing.get('nilai_posisi', 0):,.0f} ({sizing.get('pct_modal')}% modal)
⚠️ **Max Loss:** Rp {sizing.get('risk_rupiah', 0):,.0f}
{quant_section}
━━━━━━━━━━━━━━━━━━━━━━━━
💬 {keputusan.get('alasan')}
"""
    kirim_discord(pesan)

def alert_market_context(ctx: dict):
    """Kirim ringkasan kondisi pasar harian"""
    btc = ctx.get("btc", {})
    fg  = ctx.get("fear_greed", {})
    fr  = ctx.get("funding_rate", {})

    pesan = f"""
₿ **BTC:** ${btc.get('harga', 0):,} | Trend: {btc.get('trend')} | RSI: {btc.get('rsi')}
😱 **Fear & Greed:** {fg.get('value')} ({fg.get('label')})
📡 **Funding Rate:** {fr.get('funding_rate')}% ({fr.get('sinyal')})
✅ **Boleh Trading:** {'YA' if ctx.get('boleh_trading') else 'TIDAK'}
"""
    warnings = ctx.get("warnings", [])
    if warnings:
        pesan += "\n⚠️ **Warning:**\n" + "\n".join([f"- {w}" for w in warnings])

    return kirim_discord(pesan, title="📊 Market Context Update", color=0x0099ff)

def alert_scan_result(hasil_scan: list):
    """Kirim hasil scan semua aset"""
    buy_list  = [h for h in hasil_scan if h.get("sinyal") == "BUY"]
    sell_list = [h for h in hasil_scan if "SELL" in h.get("sinyal", "")]

    if not buy_list and not sell_list:
        return kirim_discord("Tidak ada sinyal kuat saat ini — semua HOLD", 
                           title="📡 Scan Selesai", color=0x808080)

    pesan = ""
    if buy_list:
        pesan += "**🟢 BUY SIGNALS:**\n"
        for h in buy_list:
            pesan += f"- `{h['aset']}` | RSI: {h['rsi']} | ADX: {h['adx']}\n"
    if sell_list:
        pesan += "\n**🔴 SELL SIGNALS:**\n"
        for h in sell_list:
            pesan += f"- `{h['aset']}` | RSI: {h['rsi']} | ADX: {h['adx']}\n"

    return kirim_discord(pesan, title=f"📡 Scan — {len(buy_list)} BUY, {len(sell_list)} SELL", 
                        color=0x00ff00 if buy_list else 0xff0000)

if __name__ == "__main__":
    print("Test Discord alert...")
    kirim_discord("✅ Bot trading aktif dan siap memantau pasar!", title="🤖 Bot Online")