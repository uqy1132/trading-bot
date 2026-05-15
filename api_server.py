"""
Trading Bot API Server
Jembatan antara React frontend dan Python bot.
Jalankan: uvicorn api_server:app --reload --port 8000
"""
import sys, os
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

# Pastikan direktori runtime ada (penting di cloud deployment)
for _d in ("logs", "config"):
    os.makedirs(os.path.join(_ROOT, _d), exist_ok=True)

import urllib3
urllib3.disable_warnings()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
import traceback, os, threading, time


def _scheduler_loop():
    """Background thread — jalankan auto-update TP/SL setiap jam."""
    time.sleep(60)  # tunggu 1 menit setelah startup baru mulai
    while True:
        try:
            from execution.order_manager import update_virtual_positions
            update_virtual_positions()
        except Exception as e:
            print(f"[scheduler] virtual positions: {e}")
        try:
            from paper_trading.tracker import update_paper_positions
            update_paper_positions()
        except Exception as e:
            print(f"[scheduler] paper positions: {e}")
        time.sleep(3600)  # interval 1 jam


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler")
    t.start()
    print("[startup] Scheduler thread berjalan.")
    yield


app = FastAPI(title="Trading Bot API", version="1.0.0", lifespan=lifespan)

# CORS — izinkan semua origin (localhost + public URL via tunnel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class _APIKeyMiddleware(BaseHTTPMiddleware):
    """Opsional auth — aktif hanya jika API_KEY diset di .env."""
    async def dispatch(self, request: Request, call_next):
        required = os.getenv("API_KEY", "")
        if required and request.url.path.startswith("/api/"):
            key = (request.headers.get("X-API-Key")
                   or request.query_params.get("api_key", ""))
            if key != required:
                return JSONResponse({"error": "Unauthorized — sertakan X-API-Key header"}, 403)
        return await call_next(request)

app.add_middleware(_APIKeyMiddleware)

# ── Import bot modules ────────────────────────────────
try:
    from data.crypto_data import (get_ohlcv, get_ticker, get_open_interest,
                                  get_exchange_auth, get_auth_exchange_name)
    from data.market_context import get_full_market_context
    from strategies.indicators import (analisa_lengkap, hitung_skor_sinyal,
                                       hitung_semua_indikator,
                                       analisa_multi_timeframe,
                                       hitung_entry_sl_tp)
    from strategies.combined_signal import skor_gabungan
    from strategies.smc import analisa_smc
    from strategies.quant import (multi_factor_score, deteksi_regime_hmm,
                                  fit_garch, sinyal_kalman,
                                  hitung_momentum_ranking,
                                  sinyal_kalman_pairs, kalman_pairs_series)
    from agent import analisa_dengan_groq
    from risk import (hitung_ukuran_posisi, catat_trade, tutup_trade,
                      load_jurnal, statistik_jurnal, equity_curve_sizing,
                      catat_skip, load_skipped,
                      partial_takeprofit, geser_breakeven,
                      status_kill_switch, hitung_ekuitas,
                      set_ks_override, clear_ks_override)
    from execution.order_manager import (kirim_order_virtual, kirim_order_live,
                                          tutup_posisi_live, load_virtual_positions,
                                          update_virtual_positions, ringkasan_virtual)
    from config.settings import LIVE_MODE as _LIVE_MODE
    from backtest.engine import backtest_strategi
    from config.settings import (MODAL_TOTAL, CRYPTO_WATCHLIST, TARGET_BULANAN,
                                  RISK_PER_TRADE, MAX_DD_HARIAN, MAX_DD_TOTAL)
    from paper_trading.tracker import (
        catat_paper_trade, tutup_paper_trade, statistik_paper,
        load_paper_trades, load_paper_config, init_paper_trading
    )
    BOT_READY = True
    print("✅ Bot modules loaded successfully")
except Exception as e:
    BOT_READY = False
    print(f"⚠️ Bot modules not fully loaded: {e}")
    MODAL_TOTAL     = 3_000_000
    TARGET_BULANAN  = 0.04
    RISK_PER_TRADE  = 0.015
    MAX_DD_HARIAN   = 0.03
    MAX_DD_TOTAL    = 0.15
    CRYPTO_WATCHLIST = ["BTC/USDT","ETH/USDT","SOL/USDT",
                        "XRP/USDT","AVAX/USDT","BNB/USDT"]

# ════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════

class CatatTradeRequest(BaseModel):
    symbol   : str
    aksi     : str
    entry    : float
    sl       : float
    target_1 : float
    target_2 : float
    ukuran   : float
    leverage : int   = 2
    catatan  : str   = ""

class TutupTradeRequest(BaseModel):
    harga_keluar : float
    hasil        : str   # WIN / LOSS / BREAKEVEN

class SkipTradeRequest(BaseModel):
    symbol    : str
    timeframe : str
    sinyal    : str
    grade     : str
    skor      : int
    harga     : float
    alasan    : str = ""

class HargaRequest(BaseModel):
    harga : float

class EksekusiRequest(BaseModel):
    symbol   : str
    aksi     : str
    ukuran   : float
    entry    : float
    sl       : float
    tp1      : float
    tp2      : float = 0
    leverage : int   = 2

class TutupPosisiRequest(BaseModel):
    aksi   : str
    ukuran : float

class BacktestRequest(BaseModel):
    symbol    : str
    timeframe : str
    limit     : int = 500

class QuantRequest(BaseModel):
    symbol    : str
    timeframe : str = "4h"

class PairsRequest(BaseModel):
    sym1      : str
    sym2      : str
    timeframe : str = "4h"

# ════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "bot_ready": BOT_READY,
            "modal": MODAL_TOTAL, "watchlist": CRYPTO_WATCHLIST}

# ════════════════════════════════════════════════════════
# MARKET CONTEXT
# ════════════════════════════════════════════════════════

@app.get("/api/market-context")
def market_context():
    try:
        ctx = get_full_market_context()
        btc = ctx.get("btc", {})
        fg  = ctx.get("fear_greed", {})
        fr  = ctx.get("funding_rate", {})
        return {
            "btcPrice"     : btc.get("harga", 0),
            "btcChange"    : btc.get("change_24h", 0),
            "trend"        : btc.get("trend", "SIDEWAYS"),
            "btcRsi"       : btc.get("rsi", 50),
            "fearGreed"    : fg.get("value", 50),
            "fearGreedLabel": fg.get("label", "Neutral"),
            "fundingRate"  : fr.get("funding_rate", 0),
            "fundingSignal": fr.get("sinyal", "NETRAL"),
            "bolehTrading" : ctx.get("boleh_trading", True),
            "warnings"     : ctx.get("warnings", []),
            "modal"        : MODAL_TOTAL,
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# ANALISA
# ════════════════════════════════════════════════════════

@app.get("/api/analisa/{symbol:path}/{timeframe}")
def analisa(symbol: str, timeframe: str, leverage: int = 2):
    try:
        symbol_decoded = symbol.replace("_", "/")
        tf_map = {"1H": "1h", "4H": "4h", "1D": "1d"}
        tf = tf_map.get(timeframe, timeframe.lower())

        df       = get_ohlcv(symbol_decoded, tf, 200)
        df_ind   = hitung_semua_indikator(df.copy())
        hasil    = analisa_lengkap(df, symbol_decoded)

        ctx      = get_full_market_context()
        oi_data  = get_open_interest(symbol_decoded)
        ctx["open_interest"] = oi_data

        # MTF diambil SEBELUM scoring agar bisa ikut dinilai
        mtf_data = analisa_multi_timeframe(symbol_decoded)
        skor_tk  = hitung_skor_sinyal(df, symbol_decoded,
                                      market_context=ctx, mtf_data=mtf_data)
        scoring  = skor_gabungan(skor_tk, df, hasil["konsensus"])
        keputusan= analisa_dengan_groq(hasil, scoring=scoring, market_context=ctx)

        # Entry/SL/TP dihitung algoritmik — LLM hanya tentukan BUY/SELL/HOLD
        algo  = hitung_entry_sl_tp(df, keputusan.get("keputusan", "HOLD"))

        # Size pakai level algoritmik
        sizing = {}
        if algo["sl"] > 0:
            sizing = hitung_ukuran_posisi(algo["entry"], algo["sl"], leverage=leverage)

        # Candle data untuk chart
        candles = []
        for i, row in df_ind.tail(100).iterrows():
            candles.append({
                "time"      : str(i),
                "open"      : row["open"],
                "high"      : row["high"],
                "low"       : row["low"],
                "close"     : row["close"],
                "volume"    : row["volume"],
                "ema20"     : row.get("ema_20", row["close"]),
                "ema50"     : row.get("ema_50", row["close"]),
                "bbU"       : row.get("bb_upper", row["close"]),
                "bbL"       : row.get("bb_lower", row["close"]),
                "macd"      : float(row.get("macd", 0) or 0),
                "macdSignal": float(row.get("macd_signal", 0) or 0),
                "macdHist"  : float(row.get("macd_hist", 0) or 0),
            })

        # RSI data
        rsi_data = [
            {"time": str(i), "rsi": row.get("rsi", 50)}
            for i, row in df_ind.tail(100).iterrows()
        ]

        return {
            "symbol"   : symbol_decoded,
            "timeframe": timeframe,
            "harga"    : hasil["harga"],
            "rsi"      : hasil["rsi"],
            "adx"      : hasil["adx"],
            "konsensus": hasil["konsensus"],
            "scoring"  : {
                "grade"      : scoring.get("grade", "B"),
                "score"      : scoring.get("skor", 0),
                "max"        : scoring.get("skor_max", 22),
                "layakTrade" : scoring.get("layak_trade", False),
                "factors"    : [
                    {"label": k, "score": v}
                    for k, v in scoring.get("detail", {}).items()
                ],
            },
            "aiDecision": {
                "action"    : keputusan.get("keputusan", "HOLD"),
                "confidence": keputusan.get("keyakinan", 0),
                "entry"     : algo["entry"],
                "sl"        : algo["sl"],
                "tp1"       : algo["tp1"],
                "tp2"       : algo["tp2"],
                "rr"        : algo["rr"],
                "reason"    : keputusan.get("alasan", ""),
                "risk"      : keputusan.get("risiko", "MEDIUM"),
            },
            "mtf": [
                {
                    "tf"    : tf_name,
                    "signal": data.get("sinyal", "HOLD"),
                    "rsi"   : data.get("rsi", 50),
                    "peran" : data.get("peran", tf_name),
                }
                for tf_name, data in mtf_data.get("detail", {}).items()
            ],
            "sizing": {
                "ukuran"      : sizing.get("ukuran", 0),
                "nilaiIDR"    : sizing.get("nilai_posisi", 0),
                "marginUSDT"  : sizing.get("margin_usdt", 0),
                "maxLossIDR"  : sizing.get("risk_rupiah", 0),
                "maxLossUSDT" : sizing.get("risk_usdt", 0),
                "pctModal"    : sizing.get("pct_modal", 0),
                "leverage"    : leverage,
            },
            "candles"      : candles,
            "rsiData"      : rsi_data,
            "openInterest" : {
                "value"    : oi_data.get("value", 0),
                "changePct": oi_data.get("change_pct", 0),
                "trend"    : oi_data.get("trend", "UNKNOWN"),
            },
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# SCAN
# ════════════════════════════════════════════════════════

@app.get("/api/scan")
def scan(tf: str = "4H"):
    try:
        tf_map = {"1H": "1h", "4H": "4h", "1D": "1d"}
        timeframe = tf_map.get(tf, "4h")
        ctx    = get_full_market_context()
        hasil  = []
        for symbol in CRYPTO_WATCHLIST:
            try:
                ticker  = get_ticker(symbol)
                df      = get_ohlcv(symbol, timeframe, 200)
                analisa = analisa_lengkap(df, symbol)
                oi_data = get_open_interest(symbol)
                ctx_sym = {**ctx, "open_interest": oi_data}
                skor_tk = hitung_skor_sinyal(df, symbol, market_context=ctx_sym)
                scoring = skor_gabungan(skor_tk, df, analisa["konsensus"])
                hasil.append({
                    "symbol"      : symbol,
                    "signal"      : analisa["konsensus"],
                    "rsi"         : analisa["rsi"],
                    "adx"         : analisa["adx"],
                    "price"       : ticker.get("harga", analisa["harga"]),
                    "change"      : ticker.get("change_24h", 0),
                    "skor"        : scoring["skor"],
                    "skor_max"    : scoring["skor_max"],
                    "grade"       : scoring["grade"],
                    "layak"       : scoring["layak_trade"],
                    "arah"        : scoring["arah"],
                    "mom_grade"   : scoring.get("mom_grade", "NETRAL"),
                    "roc_20"      : scoring.get("roc_20", 0),
                    "in_momentum" : scoring.get("in_momentum", False),
                })
            except Exception as e:
                hasil.append({
                    "symbol": symbol, "signal": "ERROR",
                    "rsi": 50, "adx": 0, "price": 0, "change": 0,
                    "skor": 0, "skor_max": 14, "grade": "-",
                    "layak": False, "arah": "WAIT",
                    "error": str(e)
                })
        mom_order = {"HOT": 0, "WARM": 1, "NETRAL": 2, "BEARISH": 3}
        hasil.sort(key=lambda x: (
            not x.get("layak", False),
            mom_order.get(x.get("mom_grade", "NETRAL"), 2),
            -(x.get("skor", 0)),
        ))
        return {"results": hasil, "timeframe": tf}
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# JURNAL
# ════════════════════════════════════════════════════════

@app.get("/api/jurnal")
def get_jurnal():
    try:
        jurnal = load_jurnal()
        return {
            "open"  : [t for t in jurnal if t.get("status") == "OPEN"],
            "closed": [t for t in jurnal if t.get("status") == "CLOSED"],
            "total" : len(jurnal),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/catat-trade")
def post_catat_trade(body: CatatTradeRequest):
    try:
        trade = catat_trade(
            symbol   = body.symbol,
            aksi     = body.aksi,
            entry    = body.entry,
            sl       = body.sl,
            target_1 = body.target_1,
            target_2 = body.target_2,
            ukuran   = body.ukuran,
            leverage = body.leverage,
            catatan  = body.catatan,
        )
        if "error" in trade:
            raise HTTPException(409, trade["error"])
        return {"success": True, "trade": trade}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/tutup-trade/{trade_id}")
def post_tutup_trade(trade_id: int, body: TutupTradeRequest):
    try:
        closed = tutup_trade(trade_id, body.harga_keluar, body.hasil)
        return {"success": True, "trade": closed}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/partial-tp/{trade_id}")
def post_partial_tp(trade_id: int):
    try:
        jurnal = load_jurnal()
        trade  = next((t for t in jurnal if t["id"] == trade_id), None)
        if not trade:
            raise HTTPException(404, "Trade tidak ditemukan")
        result = partial_takeprofit(trade_id, float(trade.get("target_1", 0)))
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/breakeven/{trade_id}")
def post_breakeven(trade_id: int, body: HargaRequest):
    try:
        result = geser_breakeven(trade_id, body.harga)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/skip-trade")
def post_skip_trade(body: SkipTradeRequest):
    try:
        record = catat_skip(
            symbol=body.symbol, timeframe=body.timeframe,
            sinyal=body.sinyal, grade=body.grade,
            skor=body.skor, harga=body.harga, alasan=body.alasan,
        )
        return {"success": True, "record": record}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/skipped")
def get_skipped():
    try:
        return {"skipped": load_skipped()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/price/{symbol:path}")
def get_price_endpoint(symbol: str):
    try:
        sym    = symbol.replace("_", "/")
        ticker = get_ticker(sym)
        return {"symbol": sym, "price": ticker["harga"], "change": ticker["change_24h"]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/settings")
def get_settings():
    import os
    try:
        ks = status_kill_switch()
    except Exception:
        ks = {"status": "OK", "lanjut": True, "pesan": "-",
              "dd_hari_pct": 0, "dd_total_pct": 0}
    return {
        "modal"        : MODAL_TOTAL,
        "riskPct"      : round(RISK_PER_TRADE * 100, 2),
        "targetBulanan": round(TARGET_BULANAN * 100, 1),
        "maxDdHarian"  : round(MAX_DD_HARIAN * 100, 1),
        "maxDdTotal"   : round(MAX_DD_TOTAL * 100, 1),
        "watchlist"    : CRYPTO_WATCHLIST,
        "discordOk"    : bool(os.getenv("DISCORD_WEBHOOK_URL")),
        "botReady"     : BOT_READY,
        "liveMode"     : _LIVE_MODE,
        "killSwitch"   : {
            "status"    : ks.get("status", "OK"),
            "lanjut"    : ks.get("lanjut", True),
            "pesan"     : ks.get("pesan", "-"),
            "ddHari"    : ks.get("dd_hari_pct", 0),
            "ddTotal"   : ks.get("dd_total_pct", 0),
        },
    }

@app.post("/api/test-discord")
def test_discord():
    try:
        from notifications.discord_alert import kirim_discord
        ok = kirim_discord(
            "✅ Test koneksi Discord dari Trading Bot Dashboard berhasil!",
            title="🔧 Test Discord"
        )
        return {"success": ok}
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# PERFORMA
# ════════════════════════════════════════════════════════

@app.get("/api/performa")
def get_performa():
    try:
        stats  = statistik_jurnal()
        jurnal = load_jurnal()
        closed = [t for t in jurnal if t.get("status") == "CLOSED"]

        # Equity curve
        modal  = MODAL_TOTAL
        equity = [{"day": "Start", "equity": modal}]
        for t in closed:
            pnl   = t.get("pnl_pct", 0) or 0
            modal = modal * (1 + pnl / 100)
            equity.append({
                "day"   : t.get("tanggal_tutup", "")[:10],
                "equity": round(modal, 0)
            })

        eq_mode = equity_curve_sizing()

        # PnL distribution
        pnl_vals = [t.get("pnl_pct", 0) or 0 for t in closed]
        _dist_buckets = [
            ("<-5%",    lambda x: x < -5),
            ("-5~-3%",  lambda x: -5 <= x < -3),
            ("-3~-1%",  lambda x: -3 <= x < -1),
            ("-1~1%",   lambda x: -1 <= x < 1),
            ("1~3%",    lambda x: 1 <= x < 3),
            ("3~5%",    lambda x: 3 <= x < 5),
            (">5%",     lambda x: x >= 5),
        ]
        pnl_dist = [
            {"bucket": label, "count": sum(1 for p in pnl_vals if fn(p))}
            for label, fn in _dist_buckets
        ]

        return {
            "totalTrade"   : stats["total"],
            "winRate"      : stats["win_rate"],
            "totalPnL"     : stats["total_pnl"],
            "profitFactor" : stats["profit_factor"],
            "avgWin"       : stats["avg_win"],
            "avgLoss"      : stats["avg_loss"],
            "openTrades"   : stats["open"],
            "bestTrade"    : max((t.get("pnl_pct", 0) or 0 for t in closed), default=0),
            "worstTrade"   : min((t.get("pnl_pct", 0) or 0 for t in closed), default=0),
            "equityCurve"  : equity,
            "equityMode"   : eq_mode,
            "modal"        : MODAL_TOTAL,
            "pnlDist"      : pnl_dist,
            "targetBulanan": round(TARGET_BULANAN * 100, 1),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# KALKULATOR
# ════════════════════════════════════════════════════════

@app.get("/api/kalkulator")
def kalkulator(entry: float, sl: float, tp1: float = 0, tp2: float = 0,
               leverage: int = 2, kurs: float = 16200, risk_pct: float = 1.5):
    try:
        sizing = hitung_ukuran_posisi(
            entry    = entry,
            stop_loss= sl,
            leverage = leverage,
            kurs     = kurs,
            risk_override= risk_pct / 100
        )
        if "error" in sizing:
            return {"error": sizing["error"]}

        ukuran   = sizing["ukuran"]
        profit1  = ukuran * abs(tp1 - entry) if tp1 else 0
        profit2  = ukuran * abs(tp2 - entry) if tp2 else 0
        max_loss = sizing["risk_usdt"]
        rr1      = profit1 / max_loss if max_loss > 0 and profit1 > 0 else 0
        rr2      = profit2 / max_loss if max_loss > 0 and profit2 > 0 else 0

        return {
            **sizing,
            "profit1_usdt": round(profit1, 2),
            "profit1_idr" : round(profit1 * kurs, 0),
            "profit2_usdt": round(profit2, 2),
            "profit2_idr" : round(profit2 * kurs, 0),
            "rr1"         : round(rr1, 2),
            "rr2"         : round(rr2, 2),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# BACKTEST
# ════════════════════════════════════════════════════════

@app.post("/api/backtest")
def post_backtest(body: BacktestRequest):
    try:
        tf_map = {"1H": "1h", "4H": "4h", "1D": "1d"}
        tf     = tf_map.get(body.timeframe, body.timeframe.lower())
        hasil  = backtest_strategi(body.symbol, tf, body.limit)

        if "error" in hasil:
            return {"error": hasil["error"]}

        # Konversi equity list → [{day, equity}] untuk chart
        equity_raw = hasil.get("equity", [])
        equity_chart = [
            {"day": str(i), "equity": round(float(v), 2)}
            for i, v in enumerate(equity_raw)
        ]

        # Konversi trades DataFrame → list dengan field yang sesuai frontend
        trades_list = []
        if "trades" in hasil:
            df_tr = hasil["trades"]
            if hasattr(df_tr, "to_dict"):
                for row in df_tr.to_dict("records"):
                    trades_list.append({
                        "tanggal_entry": row.get("tanggal_masuk", ""),
                        "symbol"       : body.symbol,
                        "aksi"         : row.get("arah", ""),
                        "entry"        : row.get("entry", 0),
                        "exit"         : row.get("keluar", 0),
                        "pnl"          : row.get("pnl_pct", 0),   # % untuk formatPct
                        "pnl_usdt"     : row.get("pnl_usdt", 0),
                        "hasil"        : row.get("hasil", ""),
                        "metode"       : row.get("metode", ""),
                    })

        return {
            "symbol"       : body.symbol,
            "timeframe"    : body.timeframe,
            "totalTrade"   : hasil["total_trade"],
            "win"          : hasil["win"],
            "loss"         : hasil["loss"],
            "winRate"      : hasil["win_rate"],
            "profitFactor" : hasil["profit_factor"],
            "sharpe"       : hasil["sharpe"],
            "maxDrawdown"  : hasil["max_drawdown"],
            "returnTotal"  : hasil["return_total"],
            "modalAwal"    : hasil["modal_awal"],
            "modalAkhir"   : hasil["modal_akhir"],
            "equity"       : equity_chart,
            "trades"       : trades_list[:50],
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# QUANT
# ════════════════════════════════════════════════════════

@app.get("/api/quant/{symbol:path}/{timeframe}")
def quant_analisa(symbol: str, timeframe: str):
    try:
        sym = symbol.replace("_", "/")
        tf_map = {"1H": "1h", "4H": "4h", "1D": "1d"}
        tf  = tf_map.get(timeframe, timeframe.lower())
        df  = get_ohlcv(sym, tf, 300)

        mfs    = multi_factor_score(df)
        regime = deteksi_regime_hmm(df)
        garch  = fit_garch(df["close"].pct_change().dropna())
        kalman = sinyal_kalman(df)

        # Z-score series untuk chart
        from strategies.quant import hitung_zscore
        df_z     = hitung_zscore(df)
        zscore_data = [
            {"time": str(i), "zscore": row["zscore"]}
            for i, row in df_z.tail(100).iterrows()
        ]

        return {
            "symbol"     : sym,
            "skortTotal" : mfs["skor_total"],
            "keputusan"  : mfs["keputusan"],
            "regime"     : {
                "state"     : regime["regime"],
                "probBull"  : regime["prob_bull"],
                "rekomendasi": regime["rekomendasi"],
                "amanTrading": regime["aman_trading"],
            },
            "garch"      : {
                "volForecast": garch["vol_forecast"],
                "volState"   : garch["vol_state"],
                "amanTrading": garch["aman_trading"],
                "sizingMult" : garch["rekomendasi_sizing"],
            },
            "kalman"     : {
                "sinyal" : kalman["sinyal"],
                "zscore" : kalman["zscore"],
                "detail" : kalman["detail"],
            },
            "zscoreData" : zscore_data,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

@app.get("/api/smc/{symbol:path}/{timeframe}")
def smc_analysis(symbol: str, timeframe: str = "1h"):
    try:
        tf_map = {"15M": "15m", "30M": "30m", "1H": "1h", "2H": "2h", "4H": "4h", "1D": "1d"}
        tf = tf_map.get(timeframe.upper(), timeframe.lower())
        from data.crypto_data import ambil_data_ohlcv
        df = ambil_data_ohlcv(symbol, tf, limit=200)
        if df is None or len(df) < 50:
            raise HTTPException(status_code=400, detail="Data tidak cukup")
        from strategies.indicators import hitung_semua_indikator
        df = hitung_semua_indikator(df)
        result = analisa_smc(df, symbol=symbol)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/momentum")
def momentum_ranking(tf: str = "4H"):
    try:
        tf_map = {"1H": "1h", "4H": "4h", "1D": "1d"}
        timeframe = tf_map.get(tf, "4h")
        data_dict = {}
        for symbol in CRYPTO_WATCHLIST:
            try:
                data_dict[symbol] = get_ohlcv(symbol, timeframe, 100)
            except:
                pass

        from strategies.quant import hitung_momentum_ranking
        ranking = hitung_momentum_ranking(data_dict)
        rows = ranking.to_dict("records")
        # Normalisasi nama field agar cocok dengan frontend
        for r in rows:
            r["momentum"] = r.pop("momentum_score", r.get("momentum", 0))
        return {"ranking": rows, "timeframe": tf}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/pairs/{sym1:path}/{sym2:path}")
def pairs_analisa(sym1: str, sym2: str, tf: str = "4H"):
    try:
        s1 = sym1.replace("_", "/")
        s2 = sym2.replace("_", "/")
        tf_map = {"1H": "1h", "4H": "4h", "1D": "1d"}
        timeframe = tf_map.get(tf, "4h")

        df1    = get_ohlcv(s1, timeframe, 300)
        df2    = get_ohlcv(s2, timeframe, 300)
        sinyal = sinyal_kalman_pairs(df1, df2, s1, s2)

        spread_df, hedge = kalman_pairs_series(df1, df2), 0
        spread_data = []
        try:
            from strategies.quant import hitung_spread_zscore
            result, hedge = hitung_spread_zscore(df1, df2)
            spread_data = [
                {"time": str(i), "zscore": row["zscore_spread"]}
                for i, row in result.tail(100).iterrows()
            ]
        except:
            pass

        return {
            "sym1"       : s1,
            "sym2"       : s2,
            "sinyal"     : sinyal.get("sinyal", "HOLD"),
            "aksi"       : sinyal.get("aksi", "-"),
            "zscore"     : sinyal.get("zscore", 0),
            "pvalue"     : sinyal.get("pvalue", 1),
            "hedgeRatio" : sinyal.get("hedge_ratio", 0),
            "detail"     : sinyal.get("detail", "-"),
            "spreadData" : spread_data,
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# WATCHLIST
# ════════════════════════════════════════════════════════

@app.get("/api/watchlist")
def get_watchlist():
    return {"symbols": CRYPTO_WATCHLIST, "modal": MODAL_TOTAL}

# ════════════════════════════════════════════════════════
# KILL SWITCH
# ════════════════════════════════════════════════════════

@app.get("/api/kill-switch")
def get_kill_switch():
    try:
        return status_kill_switch()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/reset-kill-switch")
def post_reset_kill_switch():
    """Override kill switch selama 24 jam. Gunakan hanya jika yakin situasi aman."""
    try:
        set_ks_override(24)
        return {"success": True, "message": "Kill switch di-override selama 24 jam"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/clear-kill-switch-override")
def post_clear_ks_override():
    """Hapus override — kembalikan kill switch ke mode normal."""
    try:
        clear_ks_override()
        return {"success": True, "message": "Override dihapus"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# ORDER EXECUTION
# ════════════════════════════════════════════════════════

@app.post("/api/eksekusi-order")
def post_eksekusi_order(body: EksekusiRequest):
    """
    Eksekusi order ke exchange.
    LIVE_MODE=false → virtual (simulasi).
    LIVE_MODE=true  → order nyata via CCXT.
    Kill switch dicek sebelum eksekusi.
    """
    try:
        # Kill switch check sebelum eksekusi
        ks = status_kill_switch()
        if not ks["lanjut"]:
            raise HTTPException(403, f"Kill Switch {ks['status']}: {ks['pesan']}")

        if _LIVE_MODE:
            result = kirim_order_live(
                symbol   = body.symbol,
                aksi     = body.aksi,
                ukuran   = body.ukuran,
                sl       = body.sl,
                tp1      = body.tp1,
                tp2      = body.tp2 or None,
                leverage = body.leverage,
            )
        else:
            result = kirim_order_virtual(
                symbol   = body.symbol,
                aksi     = body.aksi,
                ukuran   = body.ukuran,
                entry    = body.entry,
                sl       = body.sl,
                tp1      = body.tp1,
                leverage = body.leverage,
            )

        if result["status"] == "ERROR":
            raise HTTPException(400, result["error"])

        return {"success": True, "mode": result.get("mode", "VIRTUAL"), **result}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/tutup-posisi/{symbol:path}")
def post_tutup_posisi(symbol: str, body: TutupPosisiRequest):
    """Tutup posisi live. Hanya berlaku saat LIVE_MODE=true."""
    try:
        if not _LIVE_MODE:
            raise HTTPException(400, "LIVE_MODE=false — endpoint ini hanya untuk eksekusi live")
        result = tutup_posisi_live(symbol.replace("_", "/"), body.aksi, body.ukuran)
        if result["status"] == "ERROR":
            raise HTTPException(400, result["error"])
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/virtual-positions")
def get_virtual_positions():
    """Daftar posisi virtual/live — open dan closed (20 terakhir)."""
    try:
        positions  = load_virtual_positions()
        open_pos   = [p for p in positions if p.get("status") == "OPEN"]
        closed_pos = [p for p in positions if p.get("status") == "CLOSED"][-20:]
        ringkasan  = ringkasan_virtual()
        return {
            "open"     : open_pos,
            "closed"   : closed_pos,
            "ringkasan": ringkasan,
            "live_mode": _LIVE_MODE,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/update-virtual")
def post_update_virtual():
    """Cek posisi virtual vs harga live — tutup yang sudah kena TP/SL."""
    try:
        closed = update_virtual_positions()
        return {"success": True, "closed_count": len(closed), "closed": closed}
    except Exception as e:
        raise HTTPException(500, str(e))

# ════════════════════════════════════════════════════════
# DISCORD NOTIFICATIONS
# ════════════════════════════════════════════════════════

class DiscordAnalisaRequest(BaseModel):
    symbol      : str
    timeframe   : str
    action      : str
    confidence  : int
    entry       : float
    sl          : float
    tp1         : float
    tp2         : float
    rr          : float
    reason      : str
    grade       : str
    score       : float
    max         : float
    ukuran      : float
    maxLossIDR  : float
    nilaiIDR    : float

class DiscordScanRequest(BaseModel):
    results     : list
    timeframe   : str

@app.post("/api/discord/analisa")
def discord_analisa(body: DiscordAnalisaRequest):
    try:
        from notifications.discord_alert import kirim_discord
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⏸️"}.get(body.action, "⚪")
        stars = "⭐" * min(body.confidence, 10)
        pesan = f"""
{emoji} **SINYAL TRADING — {body.symbol}** {emoji}
━━━━━━━━━━━━━━━━━━━━━━━━
**Aksi:** `{body.action}` | **Timeframe:** `{body.timeframe}`
**Keyakinan:** {stars} ({body.confidence}/10)
━━━━━━━━━━━━━━━━━━━━━━━━
💰 **Entry:** `${body.entry:,.2f}`
🛑 **Stop Loss:** `${body.sl:,.2f}`
🎯 **TP1:** `${body.tp1:,.2f}` · **TP2:** `${body.tp2:,.2f}`
⚖️ **R:R:** `1:{body.rr:.2f}`
━━━━━━━━━━━━━━━━━━━━━━━━
🏆 **Grade:** `{body.grade}` — Skor {body.score:.0f}/{body.max:.0f}
📦 **Sizing:** {body.ukuran:.4f} unit | Modal: Rp {body.nilaiIDR:,.0f}
⚠️ **Max Loss:** Rp {body.maxLossIDR:,.0f}
━━━━━━━━━━━━━━━━━━━━━━━━
💬 {body.reason}
"""
        color = 0x00ff88 if body.action == "BUY" else 0xff4444 if body.action == "SELL" else 0x888888
        ok = kirim_discord(pesan, title=f"🤖 Analisa {body.symbol}", color=color)
        return {"success": ok}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/discord/scan")
def discord_scan(body: DiscordScanRequest):
    try:
        from notifications.discord_alert import kirim_discord
        hasil = body.results
        buys  = [r for r in hasil if r.get("signal") == "BUY"]
        sells = [r for r in hasil if r.get("signal") == "SELL"]

        if not buys and not sells:
            ok = kirim_discord(
                "Tidak ada sinyal kuat — semua HOLD saat ini.",
                title=f"📡 Scan {body.timeframe} Selesai", color=0x888888
            )
            return {"success": ok}

        lines = [f"**📡 Hasil Scan {body.timeframe}**\n"]
        if buys:
            lines.append("**🟢 BUY:**")
            for r in buys:
                lines.append(f"- `{r['symbol']}` | RSI: {r.get('rsi', 0):.0f} | ADX: {r.get('adx', 0):.0f} | ${r.get('price', 0):,.2f}")
        if sells:
            lines.append("\n**🔴 SELL:**")
            for r in sells:
                lines.append(f"- `{r['symbol']}` | RSI: {r.get('rsi', 0):.0f} | ADX: {r.get('adx', 0):.0f} | ${r.get('price', 0):,.2f}")

        ok = kirim_discord(
            "\n".join(lines),
            title=f"📡 Scan — {len(buys)} BUY · {len(sells)} SELL",
            color=0x00ff88 if buys else 0xff4444
        )
        return {"success": ok}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ════════════════════════════════════════════════════════
# PAPER TRADING
# ════════════════════════════════════════════════════════

class PaperTradeRequest(BaseModel):
    symbol   : str
    aksi     : str
    entry    : float
    sl       : float
    target_1 : float
    target_2 : float
    ukuran   : float   = 0
    leverage : int     = 2
    skor     : int     = 0
    keyakinan: int     = 0
    catatan  : str     = ""

class TutupPaperRequest(BaseModel):
    harga_keluar : float
    hasil        : str   # WIN / LOSS / BREAKEVEN

@app.get("/api/paper-stats")
def get_paper_stats():
    try:
        stats  = statistik_paper()
        config = load_paper_config()
        trades = load_paper_trades()
        return {
            "stats" : stats,
            "config": config,
            "open"  : [t for t in trades if t.get("status") == "OPEN"],
            "closed": [t for t in trades if t.get("status") == "CLOSED"][-20:],
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/paper-trade")
def post_paper_trade(body: PaperTradeRequest):
    try:
        init_paper_trading()
        trade = catat_paper_trade(
            symbol    = body.symbol,
            aksi      = body.aksi,
            entry     = body.entry,
            sl        = body.sl,
            target_1  = body.target_1,
            target_2  = body.target_2,
            ukuran    = body.ukuran,
            leverage  = body.leverage,
            skor      = body.skor,
            keyakinan = body.keyakinan,
            catatan   = body.catatan,
        )
        if "error" in trade:
            raise HTTPException(409, trade["error"])
        return {"success": True, "trade": trade}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/paper-trade/tutup/{trade_id}")
def post_tutup_paper(trade_id: int, body: TutupPaperRequest):
    try:
        result = tutup_paper_trade(trade_id, body.harga_keluar, body.hasil)
        return {"success": True, "trade": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/paper-reset")
def reset_paper():
    """Reset sesi paper trading (hapus file, mulai baru)."""
    try:
        import os
        from paper_trading.tracker import PAPER_FILE, PAPER_CONFIG
        for f in (PAPER_FILE, PAPER_CONFIG):
            if os.path.exists(f):
                os.remove(f)
        init_paper_trading()
        return {"success": True, "message": "Paper trading direset"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ════════════════════════════════════════════════════════
# WALLET & EXCHANGE POSITIONS
# ════════════════════════════════════════════════════════

@app.get("/api/wallet")
def get_wallet():
    """Saldo USDT dan coin lain dari exchange (butuh API key di .env)."""
    try:
        ex       = get_exchange_auth()
        balance  = ex.fetch_balance()
        exchange = get_auth_exchange_name()

        coins = {}
        for coin in balance.get("total", {}):
            if coin in ("free", "used", "total", "info", "datetime", "timestamp"):
                continue
            total = float(balance["total"].get(coin, 0) or 0)
            if total > 0:
                coins[coin] = {
                    "free" : round(float(balance["free"].get(coin, 0) or 0), 6),
                    "used" : round(float(balance["used"].get(coin, 0) or 0), 6),
                    "total": round(total, 6),
                }

        usdt = coins.get("USDT", {"free": 0, "used": 0, "total": 0})
        return {
            "exchange"   : exchange,
            "live_mode"  : _LIVE_MODE,
            "usdt_total" : usdt["total"],
            "usdt_free"  : usdt["free"],
            "usdt_used"  : usdt["used"],
            "coins"      : coins,
        }
    except Exception as e:
        raise HTTPException(503, f"Gagal konek ke exchange: {e}")


@app.get("/api/posisi-exchange")
def get_posisi_exchange():
    """Posisi terbuka nyata di exchange (butuh API key di .env)."""
    try:
        ex        = get_exchange_auth()
        exchange  = get_auth_exchange_name()
        positions = ex.fetch_positions()

        open_pos = []
        for pos in (positions or []):
            contracts = float(pos.get("contracts", 0) or 0)
            if contracts <= 0:
                continue
            open_pos.append({
                "symbol"          : pos.get("symbol", ""),
                "side"            : pos.get("side", ""),
                "contracts"       : contracts,
                "entryPrice"      : float(pos.get("entryPrice", 0) or 0),
                "unrealizedPnl"   : round(float(pos.get("unrealizedPnl", 0) or 0), 4),
                "leverage"        : float(pos.get("leverage", 1) or 1),
                "liquidationPrice": float(pos.get("liquidationPrice", 0) or 0),
                "percentage"      : round(float(pos.get("percentage", 0) or 0), 2),
                "marginMode"      : pos.get("marginMode", "cross"),
                "notional"        : round(float(pos.get("notional", 0) or 0), 2),
            })

        return {
            "exchange" : exchange,
            "positions": open_pos,
            "count"    : len(open_pos),
        }
    except Exception as e:
        raise HTTPException(503, f"Gagal konek ke exchange: {e}")


# ════════════════════════════════════════════════════════
# SERVE REACT FRONTEND (production build)
# Harus di paling bawah — setelah semua route /api/* didefinisikan
# ════════════════════════════════════════════════════════
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as _FileResponse

_dist = _Path(__file__).parent / "frontend" / "dist"
if _dist.exists():
    # Static assets (JS, CSS, images, fonts)
    if (_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """SPA fallback — semua route non-/api/* dikembalikan ke index.html."""
        index = _dist / "index.html"
        return _FileResponse(str(index))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
