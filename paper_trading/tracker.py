import sys
sys.path.append("C:\\TradingBot")

import json
import os
from datetime import datetime, date, timedelta
import numpy as np

PAPER_FILE    = "logs/paper_trading.json"
PAPER_CONFIG  = "logs/paper_config.json"
MODAL_AWAL    = 3_000_000  # IDR
KURS          = 16_200

os.makedirs("logs", exist_ok=True)

def init_paper_trading():
    """Inisialisasi sesi paper trading baru."""
    if os.path.exists(PAPER_FILE):
        return load_paper_trades()

    config = {
        "mulai"       : str(date.today()),
        "target_selesai": str(date.today() + timedelta(days=30)),
        "modal_awal"  : MODAL_AWAL,
        "modal_sim"   : MODAL_AWAL,
        "aturan"      : {
            "min_skor"      : 10,
            "min_keyakinan" : 7,
            "max_posisi"    : 3,
            "risk_per_trade": 1.5
        }
    }
    with open(PAPER_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

    with open(PAPER_FILE, "w") as f:
        json.dump([], f)

    return []

def load_paper_trades() -> list:
    if not os.path.exists(PAPER_FILE):
        return []
    with open(PAPER_FILE) as f:
        return json.load(f)

def load_paper_config() -> dict:
    if not os.path.exists(PAPER_CONFIG):
        return {"modal_awal": MODAL_AWAL, "modal_sim": MODAL_AWAL,
                "mulai": str(date.today()),
                "target_selesai": str(date.today() + timedelta(days=30))}
    with open(PAPER_CONFIG) as f:
        return json.load(f)

def catat_paper_trade(symbol, aksi, entry, sl, target_1, target_2,
                       ukuran, leverage, skor, keyakinan, catatan="") -> dict:
    """Catat paper trade baru."""
    trades = load_paper_trades()
    config = load_paper_config()

    # Cek max posisi
    open_count = len([t for t in trades if t["status"] == "OPEN"])
    if open_count >= config.get("aturan", {}).get("max_posisi", 3):
        return {"error": f"Max {config['aturan']['max_posisi']} posisi bersamaan sudah tercapai"}

    # Hitung sizing
    modal_usdt = config["modal_sim"] / KURS
    risk_usdt  = modal_usdt * 0.015
    jarak_sl   = abs(entry - sl)
    ukuran_sim = risk_usdt / jarak_sl if jarak_sl > 0 else 0

    trade = {
        "id"         : len(trades) + 1,
        "tanggal"    : datetime.now().strftime("%Y-%m-%d %H:%M"),
        "symbol"     : symbol,
        "aksi"       : aksi,
        "entry"      : entry,
        "stop_loss"  : sl,
        "target_1"   : target_1,
        "target_2"   : target_2,
        "ukuran"     : round(ukuran_sim, 6),
        "leverage"   : leverage,
        "skor_entry" : skor,
        "keyakinan"  : keyakinan,
        "catatan"    : catatan,
        "status"     : "OPEN",
        "harga_keluar": None,
        "pnl_usdt"   : None,
        "pnl_pct_modal": None,
        "hasil"      : None,
        "tanggal_tutup": None,
        "durasi_jam" : None
    }
    trades.append(trade)

    with open(PAPER_FILE, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)

    return trade

def tutup_paper_trade(trade_id: int, harga_keluar: float, hasil: str) -> dict:
    """Tutup paper trade dan update modal simulasi."""
    trades = load_paper_trades()
    config = load_paper_config()
    target = None

    for t in trades:
        if t["id"] == trade_id and t["status"] == "OPEN":
            # Hitung PnL
            if t["aksi"] in ["BUY", "LONG"]:
                pnl_usdt = (harga_keluar - t["entry"]) * t["ukuran"]
            else:
                pnl_usdt = (t["entry"] - harga_keluar) * t["ukuran"]

            pnl_idr        = pnl_usdt * KURS
            pnl_pct_modal  = (pnl_idr / config["modal_sim"]) * 100

            # Hitung durasi
            masuk = datetime.strptime(t["tanggal"], "%Y-%m-%d %H:%M")
            durasi_jam = round((datetime.now() - masuk).total_seconds() / 3600, 1)

            t["status"]       = "CLOSED"
            t["hasil"]        = hasil
            t["harga_keluar"] = harga_keluar
            t["pnl_usdt"]     = round(pnl_usdt, 4)
            t["pnl_idr"]      = round(pnl_idr, 0)
            t["pnl_pct_modal"]= round(pnl_pct_modal, 2)
            t["tanggal_tutup"]= datetime.now().strftime("%Y-%m-%d %H:%M")
            t["durasi_jam"]   = durasi_jam
            target = t

            # Update modal simulasi
            config["modal_sim"] = round(config["modal_sim"] + pnl_idr, 0)
            break

    with open(PAPER_FILE, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
    with open(PAPER_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

    return target or {}

def statistik_paper() -> dict:
    """Hitung semua metrik performa paper trading."""
    trades = load_paper_trades()
    config = load_paper_config()
    closed = [t for t in trades if t["status"] == "CLOSED"]
    open_t = [t for t in trades if t["status"] == "OPEN"]

    if not closed:
        return {
            "total": 0, "open": len(open_t), "win": 0, "loss": 0,
            "win_rate": 0, "total_pnl_idr": 0, "total_pnl_pct": 0,
            "profit_factor": 0, "avg_win_idr": 0, "avg_loss_idr": 0,
            "max_drawdown": 0, "sharpe": 0, "modal_awal": config["modal_awal"],
            "modal_sim": config["modal_sim"], "hari_berjalan": 0,
            "lulus": False, "evaluasi": []
        }

    wins   = [t for t in closed if t["hasil"] == "WIN"]
    losses = [t for t in closed if t["hasil"] == "LOSS"]

    total_pnl_idr = sum(t.get("pnl_idr", 0) for t in closed)
    total_pnl_pct = (total_pnl_idr / config["modal_awal"]) * 100

    gross_win  = sum(t.get("pnl_idr", 0) for t in wins) if wins else 0
    gross_loss = abs(sum(t.get("pnl_idr", 0) for t in losses)) if losses else 1

    # Drawdown
    modal_running = config["modal_awal"]
    peak          = modal_running
    max_dd        = 0
    for t in closed:
        modal_running += t.get("pnl_idr", 0)
        peak           = max(peak, modal_running)
        dd             = (peak - modal_running) / peak * 100
        max_dd         = max(max_dd, dd)

    # Sharpe (sederhana)
    pnls   = [t.get("pnl_pct_modal", 0) for t in closed]
    sharpe = (np.mean(pnls) / np.std(pnls) * np.sqrt(252)) if len(pnls) > 1 and np.std(pnls) > 0 else 0

    # Hari berjalan
    mulai       = datetime.strptime(config["mulai"], "%Y-%m-%d").date()
    hari_jalan  = (date.today() - mulai).days
    hari_sisa   = max(0, 30 - hari_jalan)

    win_rate      = len(wins) / len(closed) * 100 if closed else 0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 0

    # Kriteria lulus
    kriteria = {
        "Win Rate ≥ 55%"      : win_rate >= 55,
        "Profit Factor ≥ 1.3" : profit_factor >= 1.3,
        "Max Drawdown < 15%"  : max_dd < 15,
        "Return > 0%"         : total_pnl_pct > 0,
        "Min 10 Trade"        : len(closed) >= 10
    }
    lulus = all(kriteria.values())

    return {
        "total"          : len(closed),
        "open"           : len(open_t),
        "win"            : len(wins),
        "loss"           : len(losses),
        "win_rate"       : round(win_rate, 1),
        "total_pnl_idr"  : round(total_pnl_idr, 0),
        "total_pnl_pct"  : round(total_pnl_pct, 2),
        "profit_factor"  : round(profit_factor, 2),
        "avg_win_idr"    : round(gross_win / len(wins), 0) if wins else 0,
        "avg_loss_idr"   : round(gross_loss / len(losses), 0) if losses else 0,
        "max_drawdown"   : round(max_dd, 2),
        "sharpe"         : round(float(sharpe), 2),
        "modal_awal"     : config["modal_awal"],
        "modal_sim"      : config["modal_sim"],
        "hari_berjalan"  : hari_jalan,
        "hari_sisa"      : hari_sisa,
        "lulus"          : lulus,
        "kriteria"       : kriteria,
        "evaluasi"       : []
    }

def tutup_paper_trade(trade_id, harga_keluar, hasil):
    from execution.order_manager import hitung_pnl_bersih

    trades = load_paper_trades()
    config = load_paper_config()

    for t in trades:
        if t["id"] == trade_id and t["status"] == "OPEN":
            # Hitung PnL bersih dengan fee
            pnl_detail = hitung_pnl_bersih(
                aksi     = t["aksi"],
                entry    = t["fill_price"],
                keluar   = harga_keluar,
                ukuran   = t["ukuran"],
                leverage = t["leverage"]
            )

            pnl_idr = pnl_detail["pnl_bersih"] * KURS
            pnl_pct = (pnl_idr / config["modal_sim"]) * 100

            masuk = datetime.strptime(t["tanggal"], "%Y-%m-%d %H:%M")
            durasi = round((datetime.now() - masuk).total_seconds() / 3600, 1)

            t.update({
                "status"       : "CLOSED",
                "hasil"        : hasil,
                "harga_keluar" : harga_keluar,
                "pnl_kotor"    : pnl_detail["pnl_kotor"],
                "total_fee"    : pnl_detail["total_fee"],
                "pnl_bersih"   : pnl_detail["pnl_bersih"],
                "pnl_idr"      : round(pnl_idr, 0),
                "pnl_pct_modal": round(pnl_pct, 2),
                "tanggal_tutup": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "durasi_jam"   : durasi
            })

            config["modal_sim"] = round(config["modal_sim"] + pnl_idr, 0)
            break

    with open(PAPER_FILE, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
    with open(PAPER_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

    return t

def laporan_mingguan() -> dict:
    """Buat laporan evaluasi mingguan."""
    trades = load_paper_trades()
    seminggu_lalu = datetime.now() - timedelta(days=7)

    trade_minggu = [
        t for t in trades
        if t["status"] == "CLOSED" and
        datetime.strptime(t["tanggal_tutup"], "%Y-%m-%d %H:%M") >= seminggu_lalu
    ]

    if not trade_minggu:
        return {"pesan": "Belum ada trade closed minggu ini"}

    wins   = [t for t in trade_minggu if t["hasil"] == "WIN"]
    losses = [t for t in trade_minggu if t["hasil"] == "LOSS"]
    pnl    = sum(t.get("pnl_idr", 0) for t in trade_minggu)

    return {
        "periode"     : f"{seminggu_lalu.date()} s/d {date.today()}",
        "total_trade" : len(trade_minggu),
        "win"         : len(wins),
        "loss"        : len(losses),
        "win_rate"    : round(len(wins) / len(trade_minggu) * 100, 1),
        "pnl_idr"     : round(pnl, 0),
        "pnl_pct"     : round(pnl / 3_000_000 * 100, 2),
        "avg_durasi"  : round(np.mean([t.get("durasi_jam", 0) for t in trade_minggu]), 1)
    }