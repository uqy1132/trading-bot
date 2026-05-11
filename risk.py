import json
import os
import numpy as np
from datetime import datetime, date
from config.settings import MODAL_TOTAL, RISK_PER_TRADE, MAX_DD_HARIAN, MAX_DD_TOTAL

JOURNAL_FILE = "logs/trade_journal.json"

KURS_DEFAULT = 16_200  # IDR per USDT, update sesuai kondisi pasar

def hitung_ukuran_posisi(entry: float, stop_loss: float,
                          modal: float = None, leverage: int = 1,
                          kurs: float = KURS_DEFAULT) -> dict:
    if modal is None:
        modal = MODAL_TOTAL

    # ── Konversi modal IDR → USDT ─────────────────────
    modal_usdt  = modal / kurs
    risk_usdt   = modal_usdt * RISK_PER_TRADE
    risk_idr    = modal * RISK_PER_TRADE

    jarak_sl    = abs(entry - stop_loss)
    if jarak_sl == 0:
        return {"error": "Stop loss tidak boleh sama dengan entry"}

    sl_pct      = (jarak_sl / entry) * 100

    # ── Ukuran posisi (leverage TIDAK di sini) ────────
    # Ukuran = berapa unit aset yang dibeli
    # Risk sudah fixed = 1.5% modal, SL menentukan ukuran
    ukuran      = risk_usdt / jarak_sl

    # ── Margin & exposure ─────────────────────────────
    exposure_usdt = ukuran * entry              # total nilai posisi
    margin_usdt   = exposure_usdt / leverage   # modal yang dikunci
    margin_idr    = margin_usdt * kurs

    # ── % modal yang dipakai (berbasis margin) ────────
    pct_modal   = (margin_idr / modal) * 100

    # Validasi — margin tidak boleh melebihi modal
    if margin_usdt > modal_usdt:
        return {
            "error"    : f"Margin ${margin_usdt:.2f} melebihi modal ${modal_usdt:.2f}. "
                         f"Naikkan leverage atau perkecil posisi.",
            "saran"    : f"Leverage minimal yang dibutuhkan: "
                         f"{int(np.ceil(exposure_usdt / modal_usdt))}x"
        }

    return {
        "ukuran"       : round(ukuran, 6),
        "exposure_usdt": round(exposure_usdt, 2),
        "margin_usdt"  : round(margin_usdt, 2),
        "margin_idr"   : round(margin_idr, 0),
        "nilai_posisi" : round(margin_idr, 0),   # alias untuk dashboard
        "pct_modal"    : round(pct_modal, 2),
        "risk_usdt"    : round(risk_usdt, 2),
        "risk_rupiah"  : round(risk_idr, 0),
        "modal_usdt"   : round(modal_usdt, 2),
        "jarak_sl_pct" : round(sl_pct, 2),
        "leverage"     : leverage,
        "kurs"         : kurs
    }

def cek_kill_switch(modal_awal: float, modal_sekarang: float) -> dict:
    drawdown = (modal_awal - modal_sekarang) / modal_awal
    if drawdown >= MAX_DD_TOTAL:
        return {"status": "STOP_TOTAL",
                "pesan": f"DRAWDOWN {drawdown*100:.1f}% — Sistem dihentikan!",
                "lanjut": False}
    elif drawdown >= MAX_DD_HARIAN:
        return {"status": "PAUSE_HARI",
                "pesan": f"Loss harian {drawdown*100:.1f}% — Trading stop hari ini.",
                "lanjut": False}
    else:
        return {"status": "OK",
                "pesan": f"Drawdown {drawdown*100:.1f}% — Masih aman.",
                "lanjut": True}

def load_jurnal() -> list:
    if not os.path.exists(JOURNAL_FILE):
        return []
    with open(JOURNAL_FILE) as f:
        data = json.load(f)
    for i, t in enumerate(data):
        if "status" not in t:
            t["status"] = "CLOSED" if t.get("hasil") and t["hasil"] != "OPEN" else "OPEN"
        if "harga_keluar" not in t:
            t["harga_keluar"] = None
        if "pnl_pct" not in t:
            t["pnl_pct"] = None
        if "tanggal_tutup" not in t:
            t["tanggal_tutup"] = None
        if "leverage" not in t:
            t["leverage"] = 1
        if "catatan" not in t:
            t["catatan"] = ""
        if "id" not in t:
            t["id"] = i + 1
        if "target_1" not in t:
            t["target_1"] = t.get("target", 0)
        if "target_2" not in t:
            t["target_2"] = 0
    return data

def catat_trade(symbol, aksi, entry, sl, target_1, target_2, ukuran, leverage=1, catatan="", kondisi=None) -> dict:
    os.makedirs("logs", exist_ok=True)
    jurnal = load_jurnal()
    trade = {
        "id": len(jurnal) + 1,
        "tanggal": str(date.today()),
        "symbol": symbol,
        "aksi": aksi,
        "entry": entry,
        "stop_loss": sl,
        "target_1": target_1,
        "target_2": target_2,
        "ukuran": ukuran,
        "leverage": leverage,
        "catatan": catatan,
        "status": "OPEN",
        "harga_keluar": None,
        "pnl_pct": None,
        "hasil": None,
        "tanggal_tutup": None,
        # Kondisi saat entry — untuk pembelajaran
        "rsi_entry": kondisi.get("rsi", None) if kondisi else None,
        "adx_entry": kondisi.get("adx", None) if kondisi else None,
        "btc_trend_entry": kondisi.get("btc_trend", None) if kondisi else None,
        "skor_entry": kondisi.get("skor", None) if kondisi else None,
    }
    jurnal.append(trade)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(jurnal, f, indent=2, ensure_ascii=False)
    return trade

def tutup_trade(trade_id: int, harga_keluar: float, status: str) -> dict:
    jurnal = load_jurnal()
    target = None
    for t in jurnal:
        if t["id"] == trade_id:
            pnl_raw = (harga_keluar - t["entry"]) / t["entry"]
            pnl_pct = pnl_raw * 100 * t["leverage"]
            if t["aksi"] in ["SELL", "SHORT"]:
                pnl_pct = -pnl_pct
            t["status"]        = "CLOSED"
            t["hasil"]         = status
            t["harga_keluar"]  = harga_keluar
            t["pnl_pct"]       = round(pnl_pct, 2)
            t["tanggal_tutup"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            target = t
            break
    with open(JOURNAL_FILE, "w") as f:
        json.dump(jurnal, f, indent=2, ensure_ascii=False)
    return target or {}

def statistik_jurnal() -> dict:
    jurnal = load_jurnal()
    closed = [t for t in jurnal if t.get("status") == "CLOSED" and t.get("pnl_pct") is not None]
    open_count = len([t for t in jurnal if t.get("status") == "OPEN"])
    if not closed:
        return {"total": 0, "win": 0, "loss": 0, "win_rate": 0,
                "total_pnl": 0, "avg_win": 0, "avg_loss": 0,
                "profit_factor": 0, "open": open_count}
    wins      = [t for t in closed if t.get("hasil") == "WIN"]
    losses    = [t for t in closed if t.get("hasil") == "LOSS"]
    total_pnl = sum(t["pnl_pct"] for t in closed)
    avg_win   = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss  = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    gross_win = sum(t["pnl_pct"] for t in wins) if wins else 0
    gross_loss= abs(sum(t["pnl_pct"] for t in losses)) if losses else 1
    return {
        "total"        : len(closed),
        "open"         : open_count,
        "win"          : len(wins),
        "loss"         : len(losses),
        "win_rate"     : round(len(wins) / len(closed) * 100, 1),
        "total_pnl"    : round(total_pnl, 2),
        "avg_win"      : round(avg_win, 2),
        "avg_loss"     : round(avg_loss, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else 0
    }

def geser_breakeven(trade_id: int, harga_sekarang: float) -> dict:
    """Geser stop loss ke entry (break-even) saat profit sudah +1R"""
    jurnal = load_jurnal()
    for t in jurnal:
        if t["id"] == trade_id and t["status"] == "OPEN":
            entry = float(t["entry"])
            sl    = float(t["stop_loss"])
            jarak_sl = abs(entry - sl)
            profit   = abs(harga_sekarang - entry)

            if profit >= jarak_sl:  # Sudah profit +1R
                t["stop_loss"]  = entry  # Geser ke entry
                t["catatan"]    = (t.get("catatan", "") + " | SL digeser ke break-even")
                simpan_jurnal(jurnal)
                return {"status": "OK", "pesan": f"SL digeser ke break-even: {entry}"}
            else:
                return {"status": "BELUM", "pesan": f"Profit belum cukup. Butuh +{jarak_sl:.4f}, sekarang +{profit:.4f}"}
    return {"status": "ERROR", "pesan": "Trade tidak ditemukan"}

def partial_takeprofit(trade_id: int, harga_tp1: float) -> dict:
    """Catat partial TP — tutup 50% posisi di Target 1"""
    jurnal = load_jurnal()
    for t in jurnal:
        if t["id"] == trade_id and t["status"] == "OPEN":
            ukuran_awal = float(t["ukuran"])
            ukuran_sisa = round(ukuran_awal * 0.5, 6)
            entry       = float(t["entry"])

            pnl_partial = (harga_tp1 - entry) * (ukuran_awal * 0.5)
            t["ukuran"]  = ukuran_sisa
            t["catatan"] = (t.get("catatan", "") +
                           f" | Partial TP @ {harga_tp1} ({ukuran_awal*0.5:.4f} unit, PnL: +{pnl_partial:.2f})")
            simpan_jurnal(jurnal)
            return {
                "status": "OK",
                "pesan": f"Partial TP dicatat. Sisa posisi: {ukuran_sisa} unit",
                "pnl_partial": round(pnl_partial, 2)
            }
    return {"status": "ERROR", "pesan": "Trade tidak ditemukan"}

def simpan_jurnal(jurnal: list):
    """Helper untuk simpan jurnal"""
    os.makedirs("logs", exist_ok=True)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(jurnal, f, indent=2, ensure_ascii=False)