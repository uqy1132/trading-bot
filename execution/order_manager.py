import sys
sys.path.append("C:\\TradingBot")

import json, os
from datetime import datetime
from data.crypto_data import get_ohlcv
from notifications.discord_alert import kirim_discord

VIRTUAL_POSITIONS_FILE = "logs/virtual_positions.json"
os.makedirs("logs", exist_ok=True)

def load_virtual_positions() -> list:
    if not os.path.exists(VIRTUAL_POSITIONS_FILE):
        return []
    with open(VIRTUAL_POSITIONS_FILE) as f:
        return json.load(f)

def simpan_virtual_positions(positions: list):
    with open(VIRTUAL_POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2, ensure_ascii=False)

def kirim_order(symbol, aksi, ukuran, entry, sl, tp1, leverage=2) -> dict:
    """
    Virtual order — simulasi eksekusi tanpa exchange nyata.
    Pakai harga real dari market untuk fill price.
    """
    try:
        # Ambil harga real sebagai fill price
        df         = get_ohlcv(symbol, "1h", 2)
        fill_price = float(df["close"].iloc[-1])

        # Simulasi slippage 0.05%
        if aksi in ["BUY", "LONG"]:
            fill_price = fill_price * 1.0005
        else:
            fill_price = fill_price * 0.9995

        order_id = f"VIRTUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        posisi = {
            "order_id"  : order_id,
            "symbol"    : symbol,
            "aksi"      : aksi,
            "ukuran"    : ukuran,
            "entry_plan": entry,
            "fill_price": round(fill_price, 4),
            "stop_loss" : sl,
            "take_profit": tp1,
            "leverage"  : leverage,
            "status"    : "OPEN",
            "waktu"     : datetime.now().strftime("%Y-%m-%d %H:%M"),
            "pnl_usdt"  : 0
        }

        # Simpan posisi virtual
        positions = load_virtual_positions()
        positions.append(posisi)
        simpan_virtual_positions(positions)

        slippage = abs(fill_price - entry) / entry * 100
        kirim_discord(
            f"🤖 **VIRTUAL ORDER TEREKSEKUSI**\n"
            f"**{symbol}** {aksi} {ukuran:.4f} unit\n"
            f"Fill: `${fill_price:,.4f}` (plan: ${entry:,.4f})\n"
            f"SL: `${sl:,.4f}` | TP: `${tp1:,.4f}`\n"
            f"Slippage: {slippage:.3f}% | Leverage: {leverage}x\n"
            f"ID: `{order_id}`"
        )

        return {"status": "OK", "order_id": order_id,
                "fill_price": fill_price, "posisi": posisi}

    except Exception as e:
        kirim_discord(f"❌ Virtual order gagal: {symbol} — {e}")
        return {"status": "ERROR", "error": str(e)}

def update_virtual_positions():
    """
    Cek semua posisi virtual — apakah sudah kena SL atau TP.
    Jalankan ini tiap jam dari scheduler.
    """
    positions = load_virtual_positions()
    if not positions:
        return []

    closed_now = []

    for pos in positions:
        if pos["status"] != "OPEN":
            continue

        try:
            df    = get_ohlcv(pos["symbol"], "1h", 2)
            harga = float(df["close"].iloc[-1])

            hit_sl = False
            hit_tp = False

            if pos["aksi"] in ["BUY", "LONG"]:
                hit_sl = harga <= pos["stop_loss"]
                hit_tp = harga >= pos["take_profit"]
                pnl    = (harga - pos["fill_price"]) * pos["ukuran"] * pos["leverage"]
            else:
                hit_sl = harga >= pos["stop_loss"]
                hit_tp = harga <= pos["take_profit"]
                pnl    = (pos["fill_price"] - harga) * pos["ukuran"] * pos["leverage"]

            if hit_tp or hit_sl:
                hasil        = "WIN" if hit_tp else "LOSS"
                pos["status"]= "CLOSED"
                pos["hasil"] = hasil
                pos["harga_keluar"]  = harga
                pos["pnl_usdt"]      = round(pnl, 4)
                pos["waktu_tutup"]   = datetime.now().strftime("%Y-%m-%d %H:%M")

                emoji = "🟢" if hit_tp else "🔴"
                kirim_discord(
                    f"{emoji} **VIRTUAL POSITION CLOSED**\n"
                    f"**{pos['symbol']}** {pos['aksi']}\n"
                    f"Hasil: **{hasil}** | Harga: `${harga:,.4f}`\n"
                    f"PnL: `{'+' if pnl > 0 else ''}{pnl:.4f} USDT`\n"
                    f"ID: `{pos['order_id']}`"
                )
                closed_now.append(pos)

        except Exception as e:
            print(f"Error update {pos['symbol']}: {e}")

    simpan_virtual_positions(positions)
    return closed_now

def cek_posisi_aktif() -> list:
    positions = load_virtual_positions()
    return [p for p in positions if p["status"] == "OPEN"]

def tutup_semua_posisi():
    """Emergency close semua virtual positions."""
    positions = load_virtual_positions()
    count     = 0
    for pos in positions:
        if pos["status"] == "OPEN":
            pos["status"]      = "CLOSED"
            pos["hasil"]       = "MANUAL_CLOSE"
            pos["waktu_tutup"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            count += 1
    simpan_virtual_positions(positions)
    kirim_discord(f"🚨 Emergency close — {count} virtual posisi ditutup!")

def ringkasan_virtual() -> dict:
    """Statistik semua virtual trades."""
    positions = load_virtual_positions()
    closed    = [p for p in positions if p["status"] == "CLOSED"]
    open_pos  = [p for p in positions if p["status"] == "OPEN"]

    if not closed:
        return {"total": 0, "open": len(open_pos),
                "win": 0, "loss": 0, "total_pnl": 0}

    wins      = [p for p in closed if p["hasil"] == "WIN"]
    losses    = [p for p in closed if p["hasil"] == "LOSS"]
    total_pnl = sum(p.get("pnl_usdt", 0) for p in closed)

    return {
        "total"    : len(closed),
        "open"     : len(open_pos),
        "win"      : len(wins),
        "loss"     : len(losses),
        "win_rate" : round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_pnl": round(total_pnl, 4)
    }