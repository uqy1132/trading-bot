import json
import os
import numpy as np
from datetime import datetime, date
from config.settings import MODAL_TOTAL, RISK_PER_TRADE, MAX_DD_HARIAN, MAX_DD_TOTAL

JOURNAL_FILE    = "logs/trade_journal.json"
KS_OVERRIDE_FILE = "logs/ks_override.json"
KURS_DEFAULT    = 16_200

def hitung_ukuran_posisi(entry: float, stop_loss: float,
                          modal: float = None, leverage: int = 1,
                          kurs: float = KURS_DEFAULT,
                          risk_override: float = None) -> dict:
    if modal is None:
        modal = MODAL_TOTAL

    risk_rate  = risk_override if risk_override else RISK_PER_TRADE
    modal_usdt = modal / kurs
    risk_usdt  = modal_usdt * risk_rate
    risk_idr   = modal * risk_rate
    jarak_sl   = abs(entry - stop_loss)

    if jarak_sl == 0:
        return {"error": "Stop loss tidak boleh sama dengan entry"}

    sl_pct        = (jarak_sl / entry) * 100
    ukuran        = risk_usdt / jarak_sl
    exposure_usdt = ukuran * entry
    margin_usdt   = exposure_usdt / leverage
    margin_idr    = margin_usdt * kurs
    pct_modal     = (margin_idr / modal) * 100

    if margin_usdt > modal_usdt:
        return {
            "error": f"Margin ${margin_usdt:.2f} melebihi modal ${modal_usdt:.2f}.",
            "saran": f"Leverage minimal: {int(np.ceil(exposure_usdt / modal_usdt))}x"
        }

    return {
        "ukuran"       : round(ukuran, 6),
        "exposure_usdt": round(exposure_usdt, 2),
        "margin_usdt"  : round(margin_usdt, 2),
        "margin_idr"   : round(margin_idr, 0),
        "nilai_posisi" : round(margin_idr, 0),
        "pct_modal"    : round(pct_modal, 2),
        "risk_usdt"    : round(risk_usdt, 2),
        "risk_rupiah"  : round(risk_idr, 0),
        "modal_usdt"   : round(modal_usdt, 2),
        "jarak_sl_pct" : round(sl_pct, 2),
        "leverage"     : leverage,
        "kurs"         : kurs
    }

def equity_curve_sizing(base_risk: float = 0.015) -> dict:
    try:
        from paper_trading.tracker import statistik_paper
        stats = statistik_paper()
    except:
        return {"risk_pct": base_risk, "mode": "NORMAL",
                "alasan": "Data tidak tersedia"}

    win_rate = stats.get("win_rate", 55)
    drawdown = stats.get("max_drawdown", 0)
    total    = stats.get("total", 0)

    if total < 5:
        return {"risk_pct": base_risk, "mode": "NORMAL",
                "alasan": f"Data belum cukup ({total} trade)"}

    if drawdown < -10 or win_rate < 40:
        risk   = base_risk * 0.33
        mode   = "MINIMAL"
        alasan = f"Performa buruk (DD:{drawdown:.1f}%, WR:{win_rate:.1f}%)"
    elif drawdown < -5 or win_rate < 50:
        risk   = base_risk * 0.5
        mode   = "REDUCED"
        alasan = f"Performa melemah (DD:{drawdown:.1f}%, WR:{win_rate:.1f}%)"
    else:
        risk   = base_risk
        mode   = "NORMAL"
        alasan = f"Performa bagus (DD:{drawdown:.1f}%, WR:{win_rate:.1f}%)"

    return {
        "risk_pct": round(risk, 4),
        "mode"    : mode,
        "alasan"  : alasan,
        "win_rate": win_rate,
        "drawdown": drawdown
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
    return {"status": "OK",
            "pesan": f"Drawdown {drawdown*100:.1f}% — Masih aman.",
            "lanjut": True}

def hitung_ekuitas() -> dict:
    """
    Hitung ekuitas saat ini berdasarkan histori PnL di jurnal.
    Digunakan oleh kill switch untuk tahu apakah sudah melewati batas drawdown.
    """
    jurnal = load_jurnal()
    closed = [t for t in jurnal
              if t.get("status") == "CLOSED" and t.get("harga_keluar")]

    def pnl_usdt(t) -> float:
        entry  = float(t.get("entry", 0))
        hk     = float(t.get("harga_keluar", entry))
        ukuran = float(t.get("ukuran", 0))
        aksi   = t.get("aksi", "BUY")
        if entry <= 0 or ukuran <= 0:
            return 0.0
        return (hk - entry) * ukuran if aksi in ("BUY", "LONG") else (entry - hk) * ukuran

    total_pnl_usdt = sum(pnl_usdt(t) for t in closed)
    modal_sekarang = MODAL_TOTAL + total_pnl_usdt * KURS_DEFAULT

    # Drawdown total
    dd_total = max(0.0, (MODAL_TOTAL - modal_sekarang) / MODAL_TOTAL * 100) if MODAL_TOTAL > 0 else 0

    # Drawdown hari ini
    today = str(date.today())
    closed_today = [t for t in closed if (t.get("tanggal_tutup") or "").startswith(today)]
    pnl_today    = sum(pnl_usdt(t) for t in closed_today)
    modal_pagi   = modal_sekarang - pnl_today * KURS_DEFAULT
    dd_hari      = max(0.0, (modal_pagi - modal_sekarang) / modal_pagi * 100) if modal_pagi > 0 else 0

    return {
        "modal_awal"    : MODAL_TOTAL,
        "modal_sekarang": round(modal_sekarang, 0),
        "dd_total_pct"  : round(dd_total, 2),
        "dd_hari_pct"   : round(dd_hari, 2),
        "pnl_total_usdt": round(total_pnl_usdt, 4),
        "pnl_hari_usdt" : round(pnl_today, 4),
        "jumlah_trade"  : len(closed),
    }

def set_ks_override(jam: int = 24):
    """Override kill switch secara manual selama N jam (default 24 jam)."""
    from datetime import timedelta
    os.makedirs("logs", exist_ok=True)
    expires = (datetime.now() + timedelta(hours=jam)).isoformat()
    with open(KS_OVERRIDE_FILE, "w") as f:
        json.dump({"expires": expires, "set_at": datetime.now().isoformat()}, f)

def clear_ks_override():
    if os.path.exists(KS_OVERRIDE_FILE):
        os.remove(KS_OVERRIDE_FILE)

def cek_ks_override() -> bool:
    """Return True jika override masih aktif."""
    if not os.path.exists(KS_OVERRIDE_FILE):
        return False
    try:
        with open(KS_OVERRIDE_FILE) as f:
            data = json.load(f)
        if datetime.now() < datetime.fromisoformat(data["expires"]):
            return True
    except Exception:
        pass
    clear_ks_override()
    return False


def status_kill_switch() -> dict:
    """
    Status kill switch berdasarkan ekuitas nyata dari jurnal.
    Dipanggil sebelum setiap trade baru untuk memblokir jika drawdown melewati batas.
    """
    # Cek manual override dulu
    if cek_ks_override():
        ekuitas = hitung_ekuitas()
        with open(KS_OVERRIDE_FILE) as f:
            ov = json.load(f)
        return {
            "status" : "OK",
            "lanjut" : True,
            "pesan"  : f"Override aktif hingga {ov['expires'][:16].replace('T',' ')} — gunakan dengan bijak!",
            **ekuitas,
        }

    ekuitas  = hitung_ekuitas()
    dd_total = ekuitas["dd_total_pct"]
    dd_hari  = ekuitas["dd_hari_pct"]

    if dd_total >= MAX_DD_TOTAL * 100:
        return {
            "status" : "STOP",
            "lanjut" : False,
            "pesan"  : f"Total drawdown {dd_total:.1f}% melebihi batas {MAX_DD_TOTAL*100:.0f}% — sistem dihentikan!",
            **ekuitas,
        }
    if dd_hari >= MAX_DD_HARIAN * 100:
        return {
            "status" : "PAUSE",
            "lanjut" : False,
            "pesan"  : f"Loss harian {dd_hari:.1f}% melebihi batas {MAX_DD_HARIAN*100:.0f}% — stop hari ini.",
            **ekuitas,
        }
    return {
        "status" : "OK",
        "lanjut" : True,
        "pesan"  : "Kondisi aman untuk trading.",
        **ekuitas,
    }

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
        # Normalisasi stop_loss → sl (field lama pakai stop_loss)
        if "sl" not in t:
            t["sl"] = t.get("stop_loss", 0) or 0
    return data

def catat_trade(symbol, aksi, entry, sl, target_1, target_2,
                ukuran, leverage=1, catatan="", kondisi=None) -> dict:
    os.makedirs("logs", exist_ok=True)
    jurnal = load_jurnal()

    # Kill switch — blokir trade baru jika drawdown melewati batas
    ks = status_kill_switch()
    if not ks["lanjut"]:
        return {"error": f"🚫 Kill Switch {ks['status']}: {ks['pesan']}"}

    # Cek duplikat — tolak jika symbol yang sama masih OPEN
    duplikat = [t for t in jurnal if t["symbol"] == symbol and t["status"] == "OPEN"]
    if duplikat:
        d = duplikat[0]
        return {"error": f"Trade {symbol} sudah ada (ID #{d['id']}, {d['aksi']} @ {d['entry']}). Tutup dulu sebelum buka posisi baru."}
    trade  = {
        "id"            : len(jurnal) + 1,
        "tanggal"       : str(date.today()),
        "symbol"        : symbol,
        "aksi"          : aksi,
        "entry"         : entry,
        "sl"            : sl,
        "stop_loss"     : sl,
        "target_1"      : target_1,
        "target_2"      : target_2,
        "ukuran"        : ukuran,
        "leverage"      : leverage,
        "catatan"       : catatan,
        "status"        : "OPEN",
        "harga_keluar"  : None,
        "pnl_pct"       : None,
        "hasil"         : None,
        "tanggal_tutup" : None,
        "rsi_entry"     : kondisi.get("rsi") if kondisi else None,
        "adx_entry"     : kondisi.get("adx") if kondisi else None,
        "btc_trend_entry": kondisi.get("btc_trend") if kondisi else None,
        "skor_entry"    : kondisi.get("skor") if kondisi else None,
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
            t["status"]       = "CLOSED"
            t["hasil"]        = status
            t["harga_keluar"] = harga_keluar
            t["pnl_pct"]      = round(pnl_pct, 2)
            t["tanggal_tutup"]= datetime.now().strftime("%Y-%m-%d %H:%M")
            target = t
            break
    with open(JOURNAL_FILE, "w") as f:
        json.dump(jurnal, f, indent=2, ensure_ascii=False)
    return target or {}

def statistik_jurnal() -> dict:
    jurnal     = load_jurnal()
    closed     = [t for t in jurnal if t.get("status") == "CLOSED"
                  and t.get("pnl_pct") is not None]
    open_count = len([t for t in jurnal if t.get("status") == "OPEN"])

    if not closed:
        return {"total": 0, "win": 0, "loss": 0, "win_rate": 0,
                "total_pnl": 0, "avg_win": 0, "avg_loss": 0,
                "profit_factor": 0, "open": open_count}

    wins       = [t for t in closed if t.get("hasil") == "WIN"]
    losses     = [t for t in closed if t.get("hasil") == "LOSS"]
    total_pnl  = sum(t["pnl_pct"] for t in closed)
    avg_win    = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss   = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    gross_win  = sum(t["pnl_pct"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 1

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
    jurnal = load_jurnal()
    for t in jurnal:
        if t["id"] == trade_id and t["status"] == "OPEN":
            entry    = float(t["entry"])
            sl       = float(t.get("sl") or t.get("stop_loss", 0))
            jarak_sl = abs(entry - sl)
            profit   = abs(harga_sekarang - entry)
            if profit >= jarak_sl:
                t["stop_loss"] = entry
                t["sl"]        = entry
                t["catatan"]   = t.get("catatan", "") + " | SL → break-even"
                simpan_jurnal(jurnal)
                return {"status": "OK", "pesan": f"SL digeser ke {entry}"}
            return {"status": "BELUM",
                    "pesan": f"Butuh +{jarak_sl:.4f}, sekarang +{profit:.4f}"}
    return {"status": "ERROR", "pesan": "Trade tidak ditemukan"}

def partial_takeprofit(trade_id: int, harga_tp1: float) -> dict:
    jurnal = load_jurnal()
    for t in jurnal:
        if t["id"] == trade_id and t["status"] == "OPEN":
            ukuran_awal = float(t["ukuran"])
            ukuran_sisa = round(ukuran_awal * 0.5, 6)
            entry       = float(t["entry"])
            pnl_partial = (harga_tp1 - entry) * (ukuran_awal * 0.5)
            t["ukuran"]  = ukuran_sisa
            t["catatan"] = (t.get("catatan", "") +
                            f" | Partial TP @ {harga_tp1} "
                            f"({ukuran_awal*0.5:.4f} unit, "
                            f"PnL: +{pnl_partial:.2f})")
            simpan_jurnal(jurnal)
            return {"status": "OK",
                    "pesan": f"Sisa: {ukuran_sisa} unit",
                    "pnl_partial": round(pnl_partial, 2)}
    return {"status": "ERROR", "pesan": "Trade tidak ditemukan"}

def simpan_jurnal(jurnal: list):
    os.makedirs("logs", exist_ok=True)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(jurnal, f, indent=2, ensure_ascii=False)

SKIP_FILE = "logs/skipped.json"

def load_skipped() -> list:
    if not os.path.exists(SKIP_FILE):
        return []
    with open(SKIP_FILE) as f:
        return json.load(f)

def catat_skip(symbol: str, timeframe: str, sinyal: str,
               grade: str, skor: int, harga: float, alasan: str = "") -> dict:
    os.makedirs("logs", exist_ok=True)
    skipped = load_skipped()
    entry = {
        "id"       : len(skipped) + 1,
        "tanggal"  : datetime.now().strftime("%Y-%m-%d %H:%M"),
        "symbol"   : symbol,
        "timeframe": timeframe,
        "sinyal"   : sinyal,
        "grade"    : grade,
        "skor"     : skor,
        "harga"    : harga,
        "alasan"   : alasan,
    }
    skipped.append(entry)
    with open(SKIP_FILE, "w") as f:
        json.dump(skipped, f, indent=2, ensure_ascii=False)
    return entry