import json
from groq import Groq
from config.settings import GROQ_API_KEY, MODAL_TOTAL, RISK_PER_TRADE

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Kamu adalah Trading AI Agent spesialis Swing Trading Crypto.
Fokus: setup berkualitas tinggi, bukan kuantitas trade.
Target: 4-5% per bulan, max drawdown 10%.

Tugasmu BUKAN mengulang analisa — scoring system sudah menentukan arah.
Tugasmu adalah:
1. Tentukan entry yang presisi (bukan asal harga sekarang)
2. Hitung stop loss yang logis (di bawah support / swing low)
3. Hitung 2 target profit dengan R:R minimal 1:2
4. Berikan keyakinan 1-10 berdasarkan kualitas setup

Aturan ketat:
- Kalau grade C atau D → keputusan HOLD, keyakinan max 4
- Kalau grade A atau B → tentukan entry/SL/TP yang presisi
- R:R minimal 1:2, idealnya 1:3
- Stop loss harus di level yang logis, bukan asal -1%

Respons WAJIB JSON murni tanpa markdown:
{
  "keputusan": "BUY/SELL/SHORT/HOLD",
  "keyakinan": 1-10,
  "entry": harga,
  "stop_loss": harga,
  "target_1": harga,
  "target_2": harga,
  "rr_ratio": angka,
  "ukuran_posisi_pct": persen modal max 10,
  "alasan": "max 2 kalimat fokus ke setup",
  "risiko": "LOW/MEDIUM/HIGH"
}"""

def load_konteks_jurnal() -> str:
    import os
    JOURNAL_FILE = "logs/trade_journal.json"
    if not os.path.exists(JOURNAL_FILE):
        return "Belum ada riwayat trade."

    with open(JOURNAL_FILE) as f:
        jurnal = json.load(f)

    closed = [t for t in jurnal if t.get("status") == "CLOSED"]
    if not closed:
        return "Belum ada trade selesai."

    total    = len(closed)
    win      = sum(1 for t in closed if t.get("hasil") == "WIN")
    win_rate = round(win / total * 100, 1)

    # Cek aset mana yang buruk
    from collections import defaultdict
    per_aset = defaultdict(lambda: {"total": 0, "win": 0})
    for t in closed:
        per_aset[t["symbol"]]["total"] += 1
        if t.get("hasil") == "WIN":
            per_aset[t["symbol"]]["win"] += 1

    aset_buruk = [
        sym for sym, data in per_aset.items()
        if data["total"] >= 2 and data["win"] / data["total"] < 0.4
    ]

    trade_terakhir = closed[-3:] if len(closed) >= 3 else closed
    ringkasan = " | ".join([
        f"{t['symbol']} {t['aksi']} → {t.get('hasil','?')} ({t.get('pnl_pct', 0):+.1f}%)"
        for t in trade_terakhir
    ])

    konteks = f"Performa: {total} trade, win rate {win_rate}%, 3 terakhir: {ringkasan}"
    if aset_buruk:
        konteks += f". PERHATIAN: win rate rendah di {', '.join(aset_buruk)} — lebih selektif"

    return konteks

def analisa_dengan_groq(data_pasar: dict, scoring: dict = None, market_context: dict = None) -> dict:
    konteks_jurnal = load_konteks_jurnal()

    # Konteks pasar
    konteks_pasar = ""
    if market_context:
        btc = market_context.get("btc", {})
        fg  = market_context.get("fear_greed", {})
        fr  = market_context.get("funding_rate", {})
        konteks_pasar = (
            f"\nKonteks Pasar:"
            f"\n- BTC: ${btc.get('harga','?'):,} | Trend: {btc.get('trend','?')} | RSI: {btc.get('rsi','?')}"
            f"\n- Fear & Greed: {fg.get('value','?')} ({fg.get('label','?')})"
            f"\n- Funding Rate BTC: {fr.get('funding_rate','?')}% ({fr.get('sinyal','?')})"
        )

    # Scoring context
    scoring_txt = ""
    if scoring:
        scoring_txt = (
            f"\nScoring System:"
            f"\n- Skor: {scoring['skor']}/{scoring['skor_max']}"
            f"\n- Grade: {scoring['grade']}"
            f"\n- Layak Trade: {'YA' if scoring['layak_trade'] else 'TIDAK'}"
            f"\n- Arah yang direkomendasikan: {scoring.get('arah', scoring.get('grade', 'UNKNOWN'))}"
            f"\n- Detail skor: {json.dumps(scoring['detail'], ensure_ascii=False)}"
        )

    prompt = f"""
Setup swing trading untuk dikonfirmasi:

Aset: {data_pasar['symbol']}
Harga sekarang: {data_pasar['harga']}
RSI: {data_pasar['rsi']} | ADX: {data_pasar['adx']} | ATR: {data_pasar['atr']}
{scoring_txt}
{konteks_pasar}

Riwayat bot: {konteks_jurnal}
Modal: Rp {MODAL_TOTAL:,} | Risk per trade: {RISK_PER_TRADE*100}%

Tentukan entry presisi, SL di level support logis, dan 2 target dengan R:R minimal 1:2.
Kalau grade C/D → HOLD.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ],
        max_tokens=800
    )

    teks = response.choices[0].message.content.strip()
    if "```" in teks:
        teks = teks.split("```")[1]
        if teks.startswith("json"):
            teks = teks[4:]

    return json.loads(teks)