import json
from groq import Groq
from config.settings import GROQ_API_KEY, MODAL_TOTAL, RISK_PER_TRADE

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Kamu adalah Trading AI Agent spesialis Swing Trading Crypto.
Fokus: setup berkualitas tinggi, bukan kuantitas trade.
Target: 4-5% per bulan, max drawdown 10%.

Scoring system dan sistem algoritmik sudah menentukan arah dan level harga.
Tugasmu adalah:
1. Konfirmasi apakah setup layak berdasarkan data yang diberikan
2. Berikan keyakinan 1-10 berdasarkan kualitas setup
3. Berikan alasan singkat dalam 2 kalimat mengapa setup ini bagus/buruk
4. Tentukan risiko: LOW/MEDIUM/HIGH

ATURAN WAJIB — TIDAK BOLEH DILANGGAR:
- Keputusanmu HARUS SESUAI dengan SINYAL TEKNIKAL yang diberikan
  * Sinyal SELL/OVERBOUGHT → keputusan SELL atau SHORT, BUKAN BUY
  * Sinyal BUY/OVERSOLD   → keputusan BUY, BUKAN SELL
  * Sinyal HOLD           → keputusan HOLD
- Kalau grade C atau D → keputusan HOLD, keyakinan max 4
- Entry, SL, dan TP dihitung otomatis oleh sistem — JANGAN output angka harga

Respons WAJIB JSON murni tanpa markdown:
{
  "keputusan": "BUY/SELL/SHORT/HOLD",
  "keyakinan": 1-10,
  "alasan": "max 2 kalimat fokus ke kualitas setup",
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

    konsensus = data_pasar.get("konsensus", "HOLD / TUNGGU")

    prompt = f"""
Setup swing trading untuk dikonfirmasi:

Aset: {data_pasar['symbol']}
Harga sekarang: {data_pasar['harga']}
RSI: {data_pasar['rsi']} | ADX: {data_pasar['adx']} | ATR: {data_pasar['atr']}

⚠️ SINYAL TEKNIKAL (WAJIB IKUTI): {konsensus}
Keputusanmu HARUS sesuai sinyal di atas. Jika SELL/OVERBOUGHT → jangan BUY.
{scoring_txt}
{konteks_pasar}

Riwayat bot: {konteks_jurnal}
Modal: Rp {MODAL_TOTAL:,} | Risk per trade: {RISK_PER_TRADE*100}%

Evaluasi kualitas setup dan berikan keputusan. Entry/SL/TP dihitung otomatis oleh sistem.
Kalau grade C/D → HOLD. Ikuti arah sinyal teknikal.
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