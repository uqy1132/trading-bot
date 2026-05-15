import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json, os
from datetime import datetime
from data.crypto_data import get_ohlcv
from notifications.discord_alert import kirim_discord

VIRTUAL_POSITIONS_FILE = "logs/virtual_positions.json"
os.makedirs("logs", exist_ok=True)

# Konstanta fee Bybit Futures
TAKER_FEE = 0.00055   # 0.055% per sisi
MAKER_FEE = 0.00020   # 0.020% per sisi

def hitung_pnl_bersih(aksi, entry, keluar, ukuran, leverage, fee_type="taker"):
    """
    Hitung PnL dengan fee dan slippage sudah diperhitungkan.
    Ini yang membuat backtest dan paper trading akurat.
    """
    fee_rate = TAKER_FEE if fee_type == "taker" else MAKER_FEE

    # PnL kotor
    if aksi in ["BUY", "LONG"]:
        pnl_kotor = (keluar - entry) * ukuran
    else:
        pnl_kotor = (entry - keluar) * ukuran

    # Biaya entry dan exit
    nilai_entry = entry * ukuran
    nilai_exit  = keluar * ukuran
    fee_entry   = nilai_entry * fee_rate
    fee_exit    = nilai_exit  * fee_rate
    total_fee   = fee_entry + fee_exit

    # Funding rate estimate (8 jam sekali, ~0.01% per hari)
    funding_cost = nilai_entry * 0.0001

    pnl_bersih = pnl_kotor - total_fee - funding_cost

    return {
        "pnl_kotor"    : round(pnl_kotor, 4),
        "fee_entry"    : round(fee_entry, 4),
        "fee_exit"     : round(fee_exit, 4),
        "total_fee"    : round(total_fee, 4),
        "funding_cost" : round(funding_cost, 4),
        "pnl_bersih"   : round(pnl_bersih, 4),
        "fee_pct_pnl"  : round(total_fee / abs(pnl_kotor) * 100, 1) if pnl_kotor != 0 else 0
    }

def update_trailing_stop(posisi: dict, harga_kini: float) -> dict:
    """
    Geser SL otomatis mengikuti harga.
    - Breakeven: saat profit >= 1R, SL geser ke entry
    - Trailing: saat profit >= 2R, SL mengikuti harga - 1R
    """
    entry    = posisi["fill_price"]
    sl       = posisi["stop_loss"]
    jarak_sl = abs(entry - sl)

    if posisi["aksi"] in ["BUY", "LONG"]:
        profit    = harga_kini - entry
        r_multiple = profit / jarak_sl if jarak_sl > 0 else 0

        if r_multiple >= 2.0:
            # Trailing: SL mengikuti harga - 1R
            new_sl = harga_kini - jarak_sl
            if new_sl > posisi["stop_loss"]:
                posisi["stop_loss"] = round(new_sl, 4)
                posisi["trailing"]  = True

        elif r_multiple >= 1.0:
            # Breakeven: SL ke entry
            if posisi["stop_loss"] < entry:
                posisi["stop_loss"] = entry
                posisi["breakeven"] = True
    else:
        profit    = entry - harga_kini
        r_multiple = profit / jarak_sl if jarak_sl > 0 else 0

        if r_multiple >= 2.0:
            new_sl = harga_kini + jarak_sl
            if new_sl < posisi["stop_loss"]:
                posisi["stop_loss"] = round(new_sl, 4)
                posisi["trailing"]  = True

        elif r_multiple >= 1.0:
            if posisi["stop_loss"] > entry:
                posisi["stop_loss"] = entry
                posisi["breakeven"] = True

    return posisi

def update_virtual_positions():
    positions = load_virtual_positions()
    closed_now = []

    for pos in positions:
        if pos["status"] != "OPEN":
            continue
        try:
            df    = get_ohlcv(pos["symbol"], "1h", 2)
            harga = float(df["close"].iloc[-1])

            # Update trailing stop dulu
            pos = update_trailing_stop(pos, harga)

            # Cek SL/TP
            if pos["aksi"] in ["BUY", "LONG"]:
                hit_sl = harga <= pos["stop_loss"]
                hit_tp = harga >= pos["take_profit"]
                pnl    = hitung_pnl_bersih(
                    pos["aksi"], pos["fill_price"], harga,
                    pos["ukuran"], pos["leverage"]
                )["pnl_bersih"]
            else:
                hit_sl = harga >= pos["stop_loss"]
                hit_tp = harga <= pos["take_profit"]
                pnl    = hitung_pnl_bersih(
                    pos["aksi"], pos["fill_price"], harga,
                    pos["ukuran"], pos["leverage"]
                )["pnl_bersih"]

            if hit_tp or hit_sl:
                hasil = "WIN" if hit_tp else "LOSS"
                pos.update({
                    "status"     : "CLOSED",
                    "hasil"      : hasil,
                    "harga_keluar": harga,
                    "pnl_usdt"   : pnl,
                    "waktu_tutup": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                emoji = "🟢" if hit_tp else "🔴"
                trailing_info = " | 🎯 Trailing SL" if pos.get("trailing") else ""
                kirim_discord(
                    f"{emoji} **VIRTUAL CLOSED**\n"
                    f"**{pos['symbol']}** {pos['aksi']}\n"
                    f"Hasil: **{hasil}** | Harga: `${harga:,.4f}`\n"
                    f"PnL bersih: `{'+' if pnl > 0 else ''}{pnl:.4f} USDT`{trailing_info}"
                )
                closed_now.append(pos)

        except Exception as e:
            print(f"Error update {pos['symbol']}: {e}")

    simpan_virtual_positions(positions)
    return closed_now

def load_virtual_positions() -> list:
    if not os.path.exists(VIRTUAL_POSITIONS_FILE):
        return []
    with open(VIRTUAL_POSITIONS_FILE) as f:
        return json.load(f)

def simpan_virtual_positions(positions: list):
    with open(VIRTUAL_POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2, ensure_ascii=False)

def kirim_order_virtual(symbol, aksi, ukuran, entry, sl, tp1, leverage=2) -> dict:
    """
    Virtual order — simulasi eksekusi tanpa exchange nyata.
    Digunakan saat LIVE_MODE=false (default).
    """
    try:
        df         = get_ohlcv(symbol, "1h", 2)
        fill_price = float(df["close"].iloc[-1])

        # Simulasi slippage 0.05%
        fill_price = fill_price * (1.0005 if aksi in ("BUY", "LONG") else 0.9995)

        order_id = f"VIRTUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        posisi = {
            "order_id"   : order_id,
            "symbol"     : symbol,
            "aksi"       : aksi,
            "ukuran"     : ukuran,
            "entry_plan" : entry,
            "fill_price" : round(fill_price, 6),
            "stop_loss"  : sl,
            "take_profit": tp1,
            "leverage"   : leverage,
            "status"     : "OPEN",
            "mode"       : "VIRTUAL",
            "waktu"      : datetime.now().strftime("%Y-%m-%d %H:%M"),
            "pnl_usdt"   : 0,
        }

        positions = load_virtual_positions()
        positions.append(posisi)
        simpan_virtual_positions(positions)

        slippage = abs(fill_price - entry) / entry * 100
        kirim_discord(
            f"🤖 **VIRTUAL ORDER TEREKSEKUSI**\n"
            f"**{symbol}** {aksi} {ukuran:.6f} unit\n"
            f"Fill: `${fill_price:,.6f}` (plan: `${entry:,.6f}`)\n"
            f"SL: `${sl:,.6f}` | TP: `${tp1:,.6f}`\n"
            f"Slippage: {slippage:.3f}% | Leverage: {leverage}x\n"
            f"ID: `{order_id}`"
        )
        return {"status": "OK", "order_id": order_id,
                "fill_price": fill_price, "posisi": posisi, "mode": "VIRTUAL"}

    except Exception as e:
        kirim_discord(f"❌ Virtual order gagal: {symbol} — {e}")
        return {"status": "ERROR", "error": str(e)}


def kirim_order_live(symbol, aksi, ukuran, sl, tp1, tp2=None, leverage=2) -> dict:
    """
    Eksekusi order NYATA ke exchange via CCXT.
    Membutuhkan LIVE_MODE=true dan API key terkonfigurasi di config/.env.
    Alur: set leverage → market order entry → SL order → TP order.
    """
    from config.settings import LIVE_MODE
    if not LIVE_MODE:
        return {"status": "ERROR",
                "error": "LIVE_MODE=false — set LIVE_MODE=true di config/.env untuk eksekusi nyata"}

    from data.crypto_data import get_exchange_auth, _fmt_symbol
    try:
        ex  = get_exchange_auth()
    except Exception as e:
        return {"status": "ERROR", "error": f"Auth gagal: {e}"}

    sym        = _fmt_symbol(symbol)
    side       = "buy" if aksi in ("BUY", "LONG") else "sell"
    close_side = "sell" if side == "buy" else "buy"

    try:
        # 1. Set leverage
        try:
            ex.set_leverage(leverage, sym)
        except Exception:
            pass  # beberapa exchange tidak support atau sudah terset

        # 2. Market order entry
        order      = ex.create_order(sym, "market", side, ukuran)
        fill_price = float(order.get("average") or order.get("price") or 0)
        order_id   = order.get("id", "")

        sl_placed  = False
        tp_placed  = False

        # 3. Stop Loss order (reduceOnly)
        try:
            ex.create_order(sym, "stop_market", close_side, ukuran,
                            params={"stopPrice": sl, "reduceOnly": True})
            sl_placed = True
        except Exception as e_sl:
            print(f"[!] SL order gagal ({symbol}): {e_sl}")

        # 4. Take Profit order (reduceOnly)
        try:
            ex.create_order(sym, "take_profit_market", close_side, ukuran,
                            params={"stopPrice": tp1, "reduceOnly": True})
            tp_placed = True
        except Exception as e_tp:
            print(f"[!] TP order gagal ({symbol}): {e_tp}")

        # Simpan sebagai virtual position untuk tracking
        posisi = {
            "order_id"   : order_id,
            "symbol"     : symbol,
            "aksi"       : aksi,
            "ukuran"     : ukuran,
            "fill_price" : round(fill_price, 6),
            "stop_loss"  : sl,
            "take_profit": tp1,
            "leverage"   : leverage,
            "status"     : "OPEN",
            "mode"       : "LIVE",
            "waktu"      : datetime.now().strftime("%Y-%m-%d %H:%M"),
            "pnl_usdt"   : 0,
            "sl_placed"  : sl_placed,
            "tp_placed"  : tp_placed,
        }
        positions = load_virtual_positions()
        positions.append(posisi)
        simpan_virtual_positions(positions)

        warn = ""
        if not sl_placed:
            warn += "\n⚠️ **SL order GAGAL dipasang — pasang manual segera!**"
        if not tp_placed:
            warn += "\n⚠️ TP order gagal — keluar manual saat TP tercapai."

        kirim_discord(
            f"⚡ **LIVE ORDER TEREKSEKUSI**\n"
            f"**{symbol}** {aksi} {ukuran:.6f} unit\n"
            f"Fill: `${fill_price:,.6f}` | SL: `${sl}` | TP1: `${tp1}`\n"
            f"Leverage: {leverage}x | ID: `{order_id}`{warn}",
            title="⚡ Live Order", color=0xFFAA00
        )
        return {"status": "OK", "order_id": order_id, "fill_price": fill_price,
                "sl_placed": sl_placed, "tp_placed": tp_placed, "mode": "LIVE"}

    except Exception as e:
        kirim_discord(f"❌ **LIVE ORDER GAGAL**: {symbol} {aksi} — {e}",
                      title="🚨 Order Error", color=0xFF0000)
        return {"status": "ERROR", "error": str(e)}


def tutup_posisi_live(symbol, aksi, ukuran) -> dict:
    """
    Tutup posisi live dengan market order berlawanan (reduceOnly).
    Juga membatalkan semua order pending (SL/TP) yang masih terbuka.
    """
    from config.settings import LIVE_MODE
    if not LIVE_MODE:
        return {"status": "ERROR", "error": "LIVE_MODE=false"}

    from data.crypto_data import get_exchange_auth, _fmt_symbol
    try:
        ex  = get_exchange_auth()
    except Exception as e:
        return {"status": "ERROR", "error": f"Auth gagal: {e}"}

    sym        = _fmt_symbol(symbol)
    close_side = "sell" if aksi in ("BUY", "LONG") else "buy"

    try:
        # Batalkan semua order pending dulu
        try:
            ex.cancel_all_orders(sym)
        except Exception:
            pass

        order      = ex.create_order(sym, "market", close_side, ukuran,
                                      params={"reduceOnly": True})
        fill_price = float(order.get("average") or order.get("price") or 0)

        kirim_discord(
            f"🔒 **POSISI DITUTUP (LIVE)**\n"
            f"**{symbol}** {aksi} — Exit @ `${fill_price:,.6f}`",
            title="🔒 Close Position", color=0x888888
        )
        return {"status": "OK", "fill_price": fill_price, "order_id": order.get("id", "")}

    except Exception as e:
        kirim_discord(f"❌ **TUTUP POSISI GAGAL**: {symbol} — {e}",
                      title="🚨 Close Error", color=0xFF0000)
        return {"status": "ERROR", "error": str(e)}

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