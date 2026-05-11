import sys
sys.path.append("C:\\TradingBot")

import streamlit as st
import pandas as pd
import json, os
from datetime import datetime
from data.crypto_data import get_ohlcv
from strategies.indicators import analisa_lengkap, hitung_semua_indikator, analisa_multi_timeframe, deteksi_market_structure
from agent import analisa_dengan_groq
from risk import (hitung_ukuran_posisi, catat_trade, tutup_trade,
                  load_jurnal, statistik_jurnal, cek_kill_switch,
                  geser_breakeven, partial_takeprofit)
from config.settings import CRYPTO_WATCHLIST as BIGCAP_WATCHLIST, MODAL_TOTAL
from data.market_context import get_full_market_context
from notifications.discord_alert import alert_sinyal, alert_market_context, alert_scan_result

os.makedirs("logs", exist_ok=True)

st.set_page_config(page_title="Trading Bot Dashboard", page_icon="🤖", layout="wide")
st.title("🤖 Trading Bot — Crypto Big Cap")

stats       = statistik_jurnal()
jurnal_all  = load_jurnal()
open_trades = [t for t in jurnal_all if t["status"] == "OPEN"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Modal",          f"Rp {MODAL_TOTAL:,.0f}")
c2.metric("🎯 Target Mingguan","4-5%")
c3.metric("📈 Total PnL",      f"{stats['total_pnl']:+.2f}%",
          delta="profit" if stats['total_pnl'] > 0 else "loss")
c4.metric("🏆 Win Rate",       f"{stats['win_rate']}%",
          delta=f"{stats['win']}W / {stats['loss']}L")
c5.metric("📂 Trade Open",     len(open_trades))

st.divider()

# === MARKET CONTEXT BAR ===
with st.spinner("Memuat kondisi pasar..."):
    ctx = get_full_market_context()

btc = ctx["btc"]
fg  = ctx["fear_greed"]
fr  = ctx.get("funding_rate", {"funding_rate": 0, "sinyal": "NETRAL", "status": "normal"})

fg_color  = "🟢" if fg["value"] >= 60 else "🔴" if fg["value"] <= 30 else "🟡"
btc_color = "🟢" if btc["trend"] == "UPTREND" else "🔴" if btc["trend"] == "DOWNTREND" else "🟡"
fr_color  = "🔴" if fr["status"] == "extreme_long" else "🟢" if fr["status"] == "extreme_short" else "🟡"

mc1, mc2, mc3, mc4 = st.columns(4)
mc1.metric("₿ BTC Trend",     f"{btc_color} {btc['trend']}", delta=f"${btc['harga']:,}")
mc2.metric("😱 Fear & Greed", f"{fg_color} {fg['value']}",  delta=fg["label"])
mc3.metric("📡 BTC RSI",      btc["rsi"])
mc4.metric("✅ Boleh Trading", "YA" if ctx["boleh_trading"] else "TIDAK",
           delta="Kondisi aman" if ctx["boleh_trading"] else "Tunggu dulu")

st.caption(f"**Funding Rate BTC:** {fr_color} {fr['funding_rate']}% — {fr['sinyal']}")

if ctx["warnings"]:
    for w in ctx["warnings"]:
        st.warning(f"⚠️ {w}")

st.divider()


tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🔍 Analisa & Sinyal",
    "📡 Scan 10 Big Cap",
    "📒 Jurnal Trade",
    "📊 Performa",
    "🧮 Kalkulator Posisi",
    "🧪 Backtest",
    "🧠 Learning Engine",
    "📐 Quant Analysis",
    "📝 Paper Trading"
])

# ════════════════════════════════════════════════════════
# TAB 1 — Analisa + Konfirmasi Manual
# ════════════════════════════════════════════════════════
with tab1:
    st.subheader("Analisa Detail — Konfirmasi Trade Manual")

    col_s1, col_s2, col_s3 = st.columns(3)
    symbol    = col_s1.selectbox("Aset", BIGCAP_WATCHLIST)
    timeframe = col_s2.selectbox("Timeframe", ["1h", "4h", "1d"])
    leverage  = col_s3.selectbox("Leverage", [1, 2, 3, 5], index=1)
    limit     = 200

    if st.button("🔍 Analisa Sekarang", type="primary"):
        with st.spinner(f"Mengambil data {symbol}..."):
            df     = get_ohlcv(symbol, timeframe, limit)
            df_ind = hitung_semua_indikator(df.copy())
            hasil  = analisa_lengkap(df, symbol)

        from strategies.indicators import hitung_skor_sinyal
        from strategies.combined_signal import skor_gabungan

        skor_teknikal = hitung_skor_sinyal(df, symbol, market_context=ctx)
        scoring       = skor_gabungan(skor_teknikal, df, hasil["konsensus"])

        with st.spinner("Meminta analisa AI..."):
            keputusan = analisa_dengan_groq(hasil, scoring=scoring, market_context=ctx)

        sizing = None
        if keputusan.get("entry") and keputusan.get("stop_loss"):
            sizing = hitung_ukuran_posisi(
                keputusan["entry"], keputusan["stop_loss"], leverage=leverage
            )

        # Simpan ke session state
        st.session_state["analisa_hasil"]    = hasil
        st.session_state["analisa_scoring"]  = scoring
        st.session_state["analisa_keputusan"]= keputusan
        st.session_state["analisa_sizing"]   = sizing
        st.session_state["analisa_symbol"]   = symbol
        st.session_state["analisa_leverage"] = leverage
        st.session_state["analisa_df_ind"]   = df_ind
        st.session_state["analisa_df"]       = df

    # Tampilkan hasil dari session state
    if "analisa_hasil" in st.session_state:
        hasil    = st.session_state["analisa_hasil"]
        scoring  = st.session_state["analisa_scoring"]
        keputusan= st.session_state["analisa_keputusan"]
        sizing   = st.session_state["analisa_sizing"]
        sym_used = st.session_state["analisa_symbol"]
        lev_used = st.session_state["analisa_leverage"]
        df_ind   = st.session_state["analisa_df_ind"]
        df_used  = st.session_state["analisa_df"]

        # Scoring
        st.divider()
        st.subheader("🎯 Scoring System")
        skor_pct    = min(max(scoring["skor"] / scoring["skor_max"], 0), 1)
        warna_grade = (
            "🟢" if scoring["skor"] >= 10 else
            "🟡" if scoring["skor"] >= 7  else
            "🔴" if scoring["skor"] <= -4 else "⏸️"
        )
        g1, g2, g3 = st.columns(3)
        g1.metric("Grade",       f"{warna_grade} {scoring['grade']}")
        g2.metric("Skor",        f"{scoring['skor']} / {scoring['skor_max']}")
        g3.metric("Layak Trade", "✅ YA" if scoring["layak_trade"] else "❌ TIDAK")
        st.progress(max(skor_pct, 0))
        with st.expander("📋 Detail Skor"):
            for faktor, nilai in scoring["detail"].items():
                st.caption(f"**{faktor}**: {nilai}")

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Harga", f"${hasil['harga']:,.4f}")
        m2.metric("RSI",   hasil['rsi'],
                  delta="Overbought" if hasil['rsi'] > 68 else ("Oversold" if hasil['rsi'] < 32 else "Netral"))
        m3.metric("ADX",   hasil['adx'],
                  delta="Tren Kuat" if hasil['adx'] > 25 else "Tren Lemah")
        warna = "🟢" if hasil['konsensus'] == "BUY" else ("🔴" if "SELL" in hasil['konsensus'] else "⏸️")
        m4.metric("Sinyal Teknikal", f"{warna} {hasil['konsensus']}")

        # Market Structure
        ms = deteksi_market_structure(df_ind)
        ms_color = "🟢" if ms["struktur"] == "UPTREND" else "🔴" if ms["struktur"] == "DOWNTREND" else "🟡"
        st.caption(f"**Market Structure:** {ms_color} {ms['struktur']} — {ms['detail']}")

        st.subheader("📈 Harga + EMA")
        st.line_chart(df_ind[["close", "ema_20", "ema_50"]].tail(100))

        ch1, ch2 = st.columns(2)
        with ch1:
            st.subheader("RSI")
            st.line_chart(df_ind["rsi"].tail(100))
        with ch2:
            st.subheader("Volume Ratio")
            st.bar_chart(df_ind["vol_ratio"].tail(100))

        st.subheader("Bollinger Bands")
        st.line_chart(df_ind[["close", "bb_upper", "bb_lower"]].tail(100))

        # Multi-Timeframe
        st.divider()
        st.subheader("🕐 Konfirmasi Multi-Timeframe")
        with st.spinner("Cek 3 timeframe..."):
            mtf = analisa_multi_timeframe(sym_used)
        mtf_color = "🟢" if "BUY" in mtf["konfirmasi"] else "🔴" if "SELL" in mtf["konfirmasi"] else "⏸️"
        st.metric("Konfirmasi MTF", f"{mtf_color} {mtf['konfirmasi']}", delta=f"Kekuatan: {mtf['kekuatan']}")
        mtf1, mtf2, mtf3 = st.columns(3)
        for col, (tf, data) in zip([mtf1, mtf2, mtf3], mtf["detail"].items()):
            sinyal = data.get("sinyal", "ERROR")
            icon   = "🟢" if sinyal == "BUY" else "🔴" if "SELL" in sinyal else "⏸️"
            col.metric(f"{data['peran']} ({tf})", f"{icon} {sinyal}",
                       delta=f"RSI: {data.get('rsi', '-')}")

        # AI
        st.divider()
        st.subheader("🤖 Analisa AI")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Keputusan AI", keputusan.get("keputusan", "-"))
        a2.metric("Keyakinan",    f"{keputusan.get('keyakinan', '-')}/10")
        a3.metric("Risiko",       keputusan.get("risiko", "-"))
        a4.metric("R:R Ratio",    f"1:{keputusan.get('rr_ratio', '-')}")
        st.info(f"💬 {keputusan.get('alasan', '-')}")

        if sizing:
            st.subheader("💼 Kalkulasi Posisi")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Entry",     f"${keputusan['entry']:,.4f}")
            s2.metric("Stop Loss", f"${keputusan['stop_loss']:,.4f}")
            s3.metric("Target 1",  f"${keputusan.get('target_1', 0):,.4f}")
            s4.metric("Target 2",  f"${keputusan.get('target_2', 0):,.4f}")
            st.info(
                f"📦 Ukuran: **{sizing['ukuran']} unit** | "
                f"Nilai: **Rp {sizing['nilai_posisi']:,.0f}** ({sizing['pct_modal']}% modal) | "
                f"Leverage: **{lev_used}x** | Max loss: **Rp {sizing['risk_rupiah']:,.0f}**"
            )

            st.divider()
            st.subheader("✅ Konfirmasi Trade")
            st.warning("⚠️ Trade hanya masuk jurnal setelah kamu klik **Ambil Trade Ini**.")
            catatan = st.text_input("Catatan (opsional)",
                                    placeholder="misal: breakout resistance 65k, volume 3x")
            col_btn1, col_btn2 = st.columns([1, 3])
            with col_btn1:
                if st.button("🚀 Ambil Trade Ini", type="primary"):
                    kondisi_entry = {
                        "rsi": hasil.get("rsi"),
                        "adx": hasil.get("adx"),
                        "btc_trend": ctx.get("btc", {}).get("trend"),
                        "skor": scoring.get("skor"),
                        "leverage": lev_used
                    }
                    trade = catat_trade(
                        symbol=sym_used, aksi=keputusan["keputusan"],
                        entry=keputusan["entry"], sl=keputusan["stop_loss"],
                        target_1=keputusan.get("target_1", 0),
                        target_2=keputusan.get("target_2", 0),
                        ukuran=sizing["ukuran"], leverage=lev_used,
                        catatan=catatan, kondisi=kondisi_entry
                    )
                    st.success(f"✅ Trade #{trade['id']} dicatat! Cek tab Jurnal Trade.")
                    alert_sinyal(sym_used, keputusan, scoring, sizing)
                    st.session_state.pop("analisa_hasil", None)
                    st.rerun()
            with col_btn2:
                if st.button("❌ Skip / Tidak Ambil"):
                    skip_file = "logs/skipped_trades.json"
                    skips = []
                    if os.path.exists(skip_file):
                        with open(skip_file) as f:
                            skips = json.load(f)
                    skips.append({
                        "waktu": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "symbol": sym_used,
                        "harga_skip": hasil["harga"],
                        "sinyal": hasil["konsensus"],
                        "keyakinan_ai": keputusan.get("keyakinan", "-"),
                        "entry_ai": keputusan.get("entry", "-"),
                        "target_ai": keputusan.get("target_1", "-"),
                        "hasil_akhir": "BELUM_DIEVALUASI"
                    })
                    with open(skip_file, "w") as f:
                        json.dump(skips, f, indent=2, ensure_ascii=False)
                    st.info("Trade di-skip dan dicatat untuk evaluasi.")
                    st.session_state.pop("analisa_hasil", None)
        else:
            st.warning("⏸️ Sinyal lemah — tidak ada rekomendasi trade.")

# ════════════════════════════════════════════════════════
# TAB 2 — Scan 10 Big Cap
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader("📡 Scan 10 Big Cap Crypto")
    tf_scan = st.selectbox("Timeframe", ["1h", "4h", "1d"], key="tf_scan")

    if st.button("🚀 Scan Semua", type="primary"):
        hasil_scan = []
        progress   = st.progress(0)
        status_txt = st.empty()

        for i, sym in enumerate(BIGCAP_WATCHLIST):
            status_txt.text(f"Scanning {sym}... ({i+1}/{len(BIGCAP_WATCHLIST)})")
            try:
                df = get_ohlcv(sym, tf_scan, 200)
                h  = analisa_lengkap(df, sym)
                hasil_scan.append({
                    "Aset": sym, "Harga": f"${h['harga']:,.4f}",
                    "RSI": h["rsi"], "ADX": h["adx"], "Sinyal": h["konsensus"]
                })
            except Exception as e:
                hasil_scan.append({"Aset": sym, "Harga": "-", "RSI": "-",
                                   "ADX": "-", "Sinyal": f"Error: {e}"})
            progress.progress((i + 1) / len(BIGCAP_WATCHLIST))

        status_txt.text("✅ Scan selesai!")
        scan_untuk_discord = [
            {"aset": r["Aset"], "sinyal": r["Sinyal"], 
             "rsi": r["RSI"], "adx": r["ADX"]} 
            for r in hasil_scan
        ]
        alert_scan_result(scan_untuk_discord)
        df_scan = pd.DataFrame(hasil_scan)
        buy_df  = df_scan[df_scan["Sinyal"] == "BUY"]
        sell_df = df_scan[df_scan["Sinyal"].str.contains("SELL", na=False)]
        hold_df = df_scan[~df_scan.index.isin(buy_df.index) & ~df_scan.index.isin(sell_df.index)]

        if not buy_df.empty:
            st.success(f"🟢 BUY — {len(buy_df)} aset")
            st.dataframe(buy_df, use_container_width=True)
        if not sell_df.empty:
            st.error(f"🔴 SELL — {len(sell_df)} aset")
            st.dataframe(sell_df, use_container_width=True)
        if not hold_df.empty:
            st.info(f"⏸️ HOLD — {len(hold_df)} aset")
            st.dataframe(hold_df, use_container_width=True)

# ════════════════════════════════════════════════════════
# TAB 3 — Jurnal Trade
# ════════════════════════════════════════════════════════
with tab3:
    st.subheader("📒 Jurnal Trade — Hanya dari Konfirmasi Manual")
    jurnal = load_jurnal()

    if not jurnal:
        st.info("Belum ada trade. Lakukan analisa lalu klik 'Ambil Trade Ini'.")
    else:
        open_list = [t for t in jurnal if t["status"] == "OPEN"]
        if open_list:
            st.subheader(f"📂 Trade Open ({len(open_list)})")
            for t in open_list:
                with st.expander(
                    f"#{t['id']} {t['symbol']} {t['aksi']} @ {t['entry']} — {t['tanggal']}"
                ):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Entry",     t["entry"])
                    col_b.metric("Stop Loss", t["stop_loss"])
                    col_c.metric("Target 1",  t["target_1"])
                    if t.get("catatan"):
                        st.caption(f"📝 {t['catatan']}")

                    st.markdown("**Tutup Trade:**")
                    tc1, tc2, tc3 = st.columns(3)
                    harga_keluar = tc1.number_input(
                        "Harga Keluar", value=float(t["entry"]), key=f"harga_{t['id']}"
                    )
                    hasil_trade = tc2.selectbox(
                        "Hasil", ["WIN", "LOSS", "BREAKEVEN"], key=f"hasil_{t['id']}"
                    )
                    with tc3:
                        st.write("")
                        st.write("")
                        if st.button(f"✅ Tutup #{t['id']}", key=f"tutup_{t['id']}"):
                            closed = tutup_trade(t["id"], harga_keluar, hasil_trade)
                            pnl    = closed.get("pnl_pct", 0)
                            st.success(f"{'🟢' if pnl > 0 else '🔴'} PnL: {pnl:+.2f}%")
                            st.rerun()

                    # Manajemen Posisi Aktif
                    st.markdown("**⚙️ Manajemen Posisi:**")
                    mp1, mp2 = st.columns(2)

                    with mp1:
                        harga_be = st.number_input(
                            "Harga sekarang (Break-even)",
                            value=float(t["entry"]),
                            key=f"be_{t['id']}"
                        )
                        if st.button(f"⚖️ Geser Break-even #{t['id']}", key=f"btn_be_{t['id']}"):
                            hasil_be = geser_breakeven(t["id"], harga_be)
                            if hasil_be["status"] == "OK":
                                st.success(hasil_be["pesan"])
                                st.rerun()
                            else:
                                st.warning(hasil_be["pesan"])

                    with mp2:
                        harga_ptp = st.number_input(
                            "Harga Partial TP",
                            value=float(t.get("target_1", t["entry"])),
                            key=f"ptp_{t['id']}"
                        )
                        if st.button(f"🎯 Partial TP 50% #{t['id']}", key=f"btn_ptp_{t['id']}"):
                            hasil_ptp = partial_takeprofit(t["id"], harga_ptp)
                            if hasil_ptp["status"] == "OK":
                                st.success(f"{hasil_ptp['pesan']} | PnL: +${hasil_ptp['pnl_partial']:,.2f}")
                                st.rerun()
                            else:
                                st.warning(hasil_ptp["pesan"])

        closed_list = [t for t in jurnal if t["status"] == "CLOSED"]
        if closed_list:
            st.divider()
            st.subheader(f"📋 Riwayat ({len(closed_list)})")
            df_closed = pd.DataFrame(closed_list)[[
                "id", "tanggal", "symbol", "aksi", "entry",
                "harga_keluar", "pnl_pct", "hasil", "leverage", "catatan"
            ]]
            st.dataframe(df_closed, use_container_width=True)

        # Skip Tracker
        skip_file = "logs/skipped_trades.json"
        if os.path.exists(skip_file):
            with open(skip_file) as f:
                skips = json.load(f)
            if skips:
                st.divider()
                st.subheader(f"⏭️ Trade yang Di-skip ({len(skips)})")
                st.caption("Evaluasi apakah sinyal yang di-skip ternyata profit atau tidak.")
                df_skip = pd.DataFrame(skips)
                st.dataframe(df_skip, use_container_width=True)

        if st.button("🗑️ Reset Semua Jurnal"):
            os.remove("logs/trade_journal.json")
            st.success("Jurnal dihapus!")
            st.rerun()

# ════════════════════════════════════════════════════════
# TAB 4 — Performa
# ════════════════════════════════════════════════════════
with tab4:
    st.subheader("📊 Statistik Performa")
    s = statistik_jurnal()

    if s["total"] == 0:
        st.info("Belum ada trade selesai.")
    else:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Total Trade",   s["total"])
        p2.metric("Win Rate",      f"{s['win_rate']}%")
        p3.metric("Total PnL",     f"{s['total_pnl']:+.2f}%",
                  delta="Profit" if s["total_pnl"] > 0 else "Loss")
        p4.metric("Profit Factor", s["profit_factor"])

        p5, p6, p7 = st.columns(3)
        p5.metric("Avg Win",  f"{s['avg_win']:+.2f}%")
        p6.metric("Avg Loss", f"{s['avg_loss']:+.2f}%")
        p7.metric("Open",     s["open"])

        jurnal_data = load_jurnal()
        closed      = [t for t in jurnal_data if t["status"] == "CLOSED"]
        if closed:
            df_pnl = pd.DataFrame(closed)[["tanggal_tutup", "pnl_pct"]].copy()
            df_pnl["pnl_kumulatif"] = df_pnl["pnl_pct"].cumsum()
            df_pnl.set_index("tanggal_tutup", inplace=True)
            st.subheader("📈 PnL Kumulatif")
            st.line_chart(df_pnl["pnl_kumulatif"])

        st.divider()
        st.subheader("🎯 Progress Target Mingguan (4-5%)")
        st.progress(min(max(s["total_pnl"] / 5.0, 0), 1.0))
        st.caption(f"PnL: {s['total_pnl']:+.2f}% | Target: 4–5%")

# ════════════════════════════════════════════════════════
# TAB 5 — Kalkulator Posisi
# ════════════════════════════════════════════════════════
with tab5:
    st.subheader("🧮 Kalkulator Ukuran Posisi")
    st.caption("Hitung berapa unit yang harus dibeli berdasarkan modal IDR dan risk management.")
    st.divider()

    st.markdown("#### Modal & Risiko")
    k1, k2, k3 = st.columns(3)
    modal_idr = k1.number_input("Modal (IDR)", value=2_000_000, step=100_000)
    kurs      = k2.number_input("Kurs IDR/USDT", value=16_200, step=100,
                                 help="Cek harga P2P Binance")
    risk_pct  = k3.number_input("Risk per trade (%)", value=1.5, step=0.1,
                                 min_value=0.1, max_value=5.0)

    st.markdown("#### Aset & Harga")
    a1, a2, a3 = st.columns(3)
    aset_kal  = a1.selectbox("Aset", [
        "BTC","ETH","BNB","SOL","XRP","ADA","AVAX","DOT","MATIC","LINK"
    ], index=3, key="aset_kal")
    entry_kal = a2.number_input("Entry (USDT)", value=150.0, step=0.01, format="%.4f")
    sl_kal    = a3.number_input("Stop Loss (USDT)", value=147.0, step=0.01, format="%.4f")

    b1, b2 = st.columns(2)
    tp1_kal = b1.number_input("Target 1 (USDT)", value=156.0, step=0.01, format="%.4f")
    tp2_kal = b2.number_input("Target 2 (USDT)", value=162.0, step=0.01, format="%.4f")

    st.markdown("#### Leverage")
    lev_kal = st.select_slider("Pilih Leverage", options=[1,2,3,5,10], value=1)

    st.divider()

    jarak_sl = abs(entry_kal - sl_kal)

    if jarak_sl > 0 and entry_kal > 0:
        modal_usdt = modal_idr / kurs
        risk_usdt  = modal_usdt * (risk_pct / 100)
        sl_pct_kal = (sl_kal - entry_kal) / entry_kal * 100
        tp1_pct    = (tp1_kal - entry_kal) / entry_kal * 100
        tp2_pct    = (tp2_kal - entry_kal) / entry_kal * 100

        size     = risk_usdt / jarak_sl
        exposure = size * entry_kal
        margin   = exposure / lev_kal
        max_loss = size * jarak_sl
        profit1  = size * abs(tp1_kal - entry_kal)
        profit2  = size * abs(tp2_kal - entry_kal)
        rr1      = profit1 / max_loss if max_loss > 0 else 0
        rr2      = profit2 / max_loss if max_loss > 0 else 0
        actual_risk_pct = (max_loss / modal_usdt) * 100

        st.markdown("#### Hasil Kalkulasi")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("📦 Ukuran Posisi",    f"{size:.4f} {aset_kal}")
        r2.metric("💵 Modal USDT",       f"${modal_usdt:,.2f}")
        r3.metric("💳 Margin Dibutuhkan",f"${margin:,.2f}",
                  delta=f"Rp {margin * kurs:,.0f}")
        r4.metric("📊 Total Exposure",   f"${exposure:,.2f}",
                  delta=f"{lev_kal}x leverage")

        st.divider()
        r5, r6, r7, r8 = st.columns(4)
        r5.metric("🛑 Max Loss",
                  f"-${max_loss:,.2f}",
                  delta=f"-Rp {max_loss * kurs:,.0f}",
                  delta_color="inverse")
        r6.metric(f"🎯 Target 1 ({tp1_pct:+.1f}%)",
                  f"+${profit1:,.2f}",
                  delta=f"+Rp {profit1 * kurs:,.0f}")
        r7.metric(f"🎯 Target 2 ({tp2_pct:+.1f}%)",
                  f"+${profit2:,.2f}",
                  delta=f"+Rp {profit2 * kurs:,.0f}")
        r8.metric("⚖️ R:R Ratio",
                  f"1:{rr1:.1f} / 1:{rr2:.1f}")

        st.markdown(f"**Risk dari modal: {actual_risk_pct:.2f}%**")
        st.progress(min(actual_risk_pct / 5, 1.0))

        warns = []
        if margin > modal_usdt:
            warns.append("Margin melebihi modal USDT — kurangi ukuran atau naikkan leverage.")
        if actual_risk_pct > 2:
            warns.append(f"Risk {actual_risk_pct:.1f}% melebihi batas aman 2% per trade.")
        if rr1 < 2:
            warns.append("R:R ratio di bawah 1:2 — naikkan target atau ketatkan stop loss.")
        if lev_kal >= 10:
            warns.append("Leverage 10x sangat berisiko.")
        for w in warns:
            st.warning(f"⚠️ {w}")
        if not warns:
            st.success("✅ Semua parameter aman. Siap trading!")

        st.divider()
        st.markdown("#### 📋 Ringkasan Order")
        st.code(
            f"Aset      : {aset_kal}/USDT\n"
            f"Entry     : ${entry_kal:,.4f}\n"
            f"Stop Loss : ${sl_kal:,.4f}  ({sl_pct_kal:+.2f}%)\n"
            f"Target 1  : ${tp1_kal:,.4f}  ({tp1_pct:+.2f}%)\n"
            f"Target 2  : ${tp2_kal:,.4f}  ({tp2_pct:+.2f}%)\n"
            f"Ukuran    : {size:.4f} {aset_kal}\n"
            f"Leverage  : {lev_kal}x\n"
            f"Margin    : ${margin:,.2f}  (Rp {margin * kurs:,.0f})\n"
            f"Max Loss  : ${max_loss:,.2f}  (Rp {max_loss * kurs:,.0f})\n"
            f"R:R       : 1:{rr1:.1f} / 1:{rr2:.1f}",
            language="text"
        )

        st.divider()
        catatan_kal = st.text_input("Catatan (opsional)",
                                     placeholder="misal: breakout resistance, volume tinggi",
                                     key="catatan_kal")
        if st.button("🚀 Catat Trade Ini ke Jurnal", type="primary"):
            trade = catat_trade(
                symbol=f"{aset_kal}/USDT", aksi="BUY",
                entry=entry_kal, sl=sl_kal,
                target_1=tp1_kal, target_2=tp2_kal,
                ukuran=round(size, 6), leverage=lev_kal, catatan=catatan_kal
            )
            st.success(f"✅ Trade #{trade['id']} dicatat ke jurnal!")
    else:
        st.warning("Isi entry dan stop loss dengan nilai berbeda.")

# ════════════════════════════════════════════════════════
# TAB 6 — Backtest
# ════════════════════════════════════════════════════════
with tab6:
    from backtest.engine import backtest_strategi

    st.subheader("🧪 Backtest Strategi")
    st.caption("Uji performa strategi di data historis sebelum trading uang nyata.")
    st.divider()

    b1, b2, b3 = st.columns(3)
    bt_symbol    = b1.selectbox("Aset", BIGCAP_WATCHLIST, key="bt_sym")
    bt_timeframe = b2.selectbox("Timeframe", ["1h", "4h", "1d"], index=1, key="bt_tf")
    bt_bulan = b3.slider("Periode (bulan)", 3, 24, 12, key="bt_bulan")

    # Konversi bulan ke candle otomatis
    candle_per_bulan = {"1h": 720, "4h": 180, "1d": 30}
    bt_limit = bt_bulan * candle_per_bulan.get(bt_timeframe, 180)
    st.caption(f"= {bt_limit} candle ({bt_bulan} bulan data)")
    

    if st.button("▶️ Jalankan Backtest", type="primary"):
        with st.spinner(f"Backtesting {bt_symbol} {bt_timeframe}... sabar ya..."):
            hasil = backtest_strategi(bt_symbol, bt_timeframe, bt_limit)

        if "error" in hasil:
            st.error(hasil["error"])
        else:
            st.subheader("📊 Hasil Backtest")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Trade",   hasil["total_trade"])
            m2.metric("Win Rate",      f"{hasil['win_rate']}%",
                      delta="Bagus" if hasil["win_rate"] >= 55 else "Perlu perbaikan")
            m3.metric("Profit Factor", hasil["profit_factor"],
                      delta="Bagus" if hasil["profit_factor"] >= 1.5 else "Di bawah target")
            m4.metric("Sharpe Ratio",  hasil["sharpe"],
                      delta="Bagus" if hasil["sharpe"] >= 1.2 else "Perlu perbaikan")

            m5, m6, m7, m8 = st.columns(4)
            m5.metric("Return Total",  f"{hasil['return_total']:+.1f}%",
                      delta="Profit" if hasil["return_total"] > 0 else "Loss")
            m6.metric("Max Drawdown",  f"{hasil['max_drawdown']:.1f}%",
                      delta="Aman" if hasil["max_drawdown"] > -15 else "Terlalu dalam",
                      delta_color="inverse")
            m7.metric("Modal Awal",    f"${hasil['modal_awal']:,.0f}")
            m8.metric("Modal Akhir",   f"${hasil['modal_akhir']:,.0f}",
                      delta=f"{hasil['return_total']:+.1f}%")

            st.divider()
            skor = 0
            if hasil["win_rate"] >= 55:       skor += 1
            if hasil["profit_factor"] >= 1.5: skor += 1
            if hasil["sharpe"] >= 1.2:        skor += 1
            if hasil["max_drawdown"] >= -15:  skor += 1
            if hasil["return_total"] > 0:     skor += 1

            if skor >= 4:
                st.success(f"✅ Strategi LAYAK untuk paper trading ({skor}/5 kriteria terpenuhi)")
            elif skor >= 3:
                st.warning(f"⚠️ Strategi CUKUP tapi perlu optimasi ({skor}/5 kriteria terpenuhi)")
            else:
                st.error(f"❌ Strategi BELUM layak untuk live trading ({skor}/5 kriteria terpenuhi)")

            kriteria = {
                "Win Rate ≥ 55%"      : hasil["win_rate"] >= 55,
                "Profit Factor ≥ 1.5" : hasil["profit_factor"] >= 1.5,
                "Sharpe Ratio ≥ 1.2"  : hasil["sharpe"] >= 1.2,
                "Max Drawdown > -15%" : hasil["max_drawdown"] >= -15,
                "Return Total > 0%"   : hasil["return_total"] > 0
            }
            for nama, lulus in kriteria.items():
                st.caption(f"{'✅' if lulus else '❌'} {nama}")

            st.divider()
            st.subheader("📈 Equity Curve")
            st.line_chart(pd.DataFrame({"Equity ($)": hasil["equity"]}))

            st.subheader("🔍 Performa Per Metode")
            st.dataframe(hasil["per_metode"].rename(columns={
                "metode": "Metode", "total": "Total", "win": "Win",
                "win_rate": "Win Rate (%)", "pnl_total": "PnL Total ($)"
            }), use_container_width=True)

            st.subheader("📋 Semua Trade")
            df_show = hasil["trades"][[
                "tanggal_masuk", "tanggal_keluar", "arah", "metode",
                "entry", "keluar", "hasil", "pnl_pct", "pnl_usdt"
            ]].copy()
            df_show.columns = ["Masuk","Keluar","Arah","Metode","Entry","Keluar $","Hasil","PnL %","PnL $"]
            st.dataframe(df_show, use_container_width=True)

            st.subheader("📊 Distribusi PnL per Trade")
            st.bar_chart(hasil["trades"].set_index("tanggal_masuk")["pnl_pct"])
            # ════════════════════════════════════════════════════════
# TAB 7 — Pembelajaran
# ════════════════════════════════════════════════════════
with tab7:
    from logs.learning_engine import analisa_pola_loss, ringkasan_pembelajaran

    st.subheader("🧠 Bot Learning Engine")
    st.caption("Bot belajar dari trade historis dan menyesuaikan scoring otomatis.")

    if st.button("🔄 Analisa Pola Historis", type="primary"):
        pembelajaran = analisa_pola_loss()

        if not pembelajaran["cukup_data"]:
            st.warning(pembelajaran["pesan"])
        else:
            st.success(f"✅ Analisa dari {pembelajaran['total_trade']} trade selesai!")

            l1, l2 = st.columns(2)
            l1.metric("Total Trade Closed", pembelajaran["total_trade"])
            l2.metric("Win Rate Global",    f"{pembelajaran['win_rate_global']}%")

            if pembelajaran["aset_dihindari"]:
                st.error(f"🚫 Aset dengan performa buruk: {', '.join(pembelajaran['aset_dihindari'])}")

            st.subheader("📋 Pola yang Ditemukan")
            for kondisi in pembelajaran["kondisi_buruk"]:
                if kondisi.startswith("-") or "loss" in kondisi.lower() or "buruk" in kondisi.lower():
                    st.error(f"❌ {kondisi}")
                else:
                    st.success(f"✅ {kondisi}")

            st.subheader("⚙️ Penyesuaian Skor Aktif")
            if pembelajaran["penyesuaian_skor"]:
                for key, val in pembelajaran["penyesuaian_skor"].items():
                    color = "🔴" if val < 0 else "🟢"
                    st.caption(f"{color} **{key}**: {val:+d} poin")
            else:
                st.info("Belum ada penyesuaian — performa semua kondisi masih normal.")

    st.divider()
    st.caption("💡 Pembelajaran aktif setelah minimal 5 trade closed. Semakin banyak trade, semakin akurat.")
    
    # ════════════════════════════════════════════════════════
# TAB 8 — Quant Analysis
# ════════════════════════════════════════════════════════
with tab8:
    from strategies.quant import (quant_analisis, hitung_momentum_ranking,
                                   sinyal_pairs, kelly_sizing)

    st.subheader("📐 Quant Analysis")

    qt1, qt2, qt3 = st.tabs(["🎯 Regime + Z-Score", "📊 Momentum Ranking", "🔗 Pairs Trading"])

    # ── Regime + Z-Score ─────────────────────────────────
    with qt1:
        st.markdown("#### Deteksi Regime Pasar + Z-Score Signal")
        q1, q2 = st.columns(2)
        q_sym = q1.selectbox("Aset", BIGCAP_WATCHLIST, key="q_sym")
        q_tf  = q2.selectbox("Timeframe", ["1h", "4h", "1d"], index=1, key="q_tf")

        if st.button("🔍 Analisa Quant", type="primary"):
            with st.spinner("Menghitung..."):
                df  = get_ohlcv(q_sym, q_tf, 300)
                res = quant_analisis(df, q_sym)

            reg = res["regime"]
            sz  = res["sinyal_zscore"]

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Regime",     reg["regime"])
            r2.metric("Hurst Exp.", reg["hurst"],
                      delta="Trending" if reg["hurst"] > 0.55 else
                            ("Mean Rev." if reg["hurst"] < 0.45 else "Random"))
            r3.metric("Vol Kini",   f"{reg['vol_kini']}%")
            r4.metric("Vol Ratio",  reg["vol_ratio"],
                      delta_color="inverse" if reg["vol_ratio"] > 2 else "normal")

            st.info(reg["rekomendasi"])

            st.divider()
            z1, z2 = st.columns(2)
            z1.metric("Z-Score",      sz["zscore"])
            z2.metric("Sinyal Quant", res["rekomendasi"])
            st.caption(res["alasan"])

            # Chart Z-Score
            from strategies.quant import hitung_zscore
            df_z = hitung_zscore(df)
            st.subheader("Z-Score History")
            st.line_chart(df_z[["zscore", "zscore_upper", "zscore_lower"]].tail(100))

            # Kelly Sizing
            st.divider()
            st.markdown("#### 💰 Kelly Criterion Sizing")
            k1, k2, k3 = st.columns(3)
            k_wr  = k1.number_input("Win Rate (%)", value=55.0, step=1.0) / 100
            k_win = k2.number_input("Avg Win (%)", value=4.0, step=0.1) / 100
            k_los = k3.number_input("Avg Loss (%)", value=2.0, step=0.1) / 100

            kelly = kelly_sizing(k_wr, k_win, k_los, MODAL_TOTAL / 16200)
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric("Full Kelly",  f"{kelly['kelly_full']}%")
            kc2.metric("Half Kelly",  f"{kelly['kelly_half']}%")
            kc3.metric("Recommended", f"{kelly['kelly_final']}%")
            st.success(f"💡 {kelly['rekomendasi']}")

    # ── Momentum Ranking ─────────────────────────────────
    with qt2:
        st.markdown("#### Cross-Sectional Momentum — Ranking 10 Big Cap")
        m_tf = st.selectbox("Timeframe", ["4h", "1d"], key="m_tf")

        if st.button("📊 Hitung Ranking", type="primary"):
            with st.spinner("Mengambil data semua aset..."):
                data_dict = {}
                prog = st.progress(0)
                for i, sym in enumerate(BIGCAP_WATCHLIST):
                    try:
                        data_dict[sym] = get_ohlcv(sym, m_tf, 100)
                    except:
                        pass
                    prog.progress((i+1) / len(BIGCAP_WATCHLIST))

            ranking = hitung_momentum_ranking(data_dict)

            st.dataframe(
                ranking.rename(columns={
                    "symbol": "Aset", "return_14d": "Return 14D (%)",
                    "return_1d": "Return 1D (%)", "volatilitas_14d": "Vol 14D (%)",
                    "momentum_score": "Momentum Score", "rank": "Rank", "sinyal": "Sinyal"
                }),
                use_container_width=True
            )

            buy_list  = ranking[ranking["sinyal"].str.contains("LONG")]["symbol"].tolist()
            short_list= ranking[ranking["sinyal"].str.contains("SHORT")]["symbol"].tolist()

            if buy_list:
                st.success(f"🟢 LONG (momentum terkuat): {', '.join(buy_list)}")
            if short_list:
                st.error(f"🔴 SHORT (momentum terlemah): {', '.join(short_list)}")

    # ── Pairs Trading ────────────────────────────────────
    with qt3:
        st.markdown("#### Statistical Arbitrage — Pairs Trading")
        p1, p2, p3 = st.columns(3)
        pair_sym1 = p1.selectbox("Aset 1", BIGCAP_WATCHLIST, index=0, key="ps1")
        pair_sym2 = p2.selectbox("Aset 2", BIGCAP_WATCHLIST, index=1, key="ps2")
        pair_tf   = p3.selectbox("Timeframe", ["4h", "1d"], key="ptf")

        if st.button("🔗 Analisa Pairs", type="primary"):
            with st.spinner("Mengecek kointegrasi..."):
                df1 = get_ohlcv(pair_sym1, pair_tf, 300)
                df2 = get_ohlcv(pair_sym2, pair_tf, 300)
                hasil_pairs = sinyal_pairs(df1, df2, pair_sym1, pair_sym2)

            if hasil_pairs["sinyal"] == "SKIP":
                st.error(f"❌ {hasil_pairs['alasan']}")
            else:
                ps1, ps2, ps3 = st.columns(3)
                ps1.metric("Sinyal",  hasil_pairs["sinyal"])
                ps2.metric("Z-Score", hasil_pairs["zscore"])
                ps3.metric("P-Value", hasil_pairs.get("pvalue", "-"))

                st.info(f"📋 Aksi: **{hasil_pairs.get('aksi', '-')}**")
                st.caption(hasil_pairs.get("detail", ""))

                if hasil_pairs.get("hedge_ratio"):
                    st.caption(f"Hedge ratio: {hasil_pairs['hedge_ratio']} — untuk setiap 1 unit {pair_sym1}, hedge dengan {hasil_pairs['hedge_ratio']} unit {pair_sym2}")

                from strategies.quant import hitung_spread_zscore
                spread_df, _ = hitung_spread_zscore(df1, df2)
                st.subheader("Spread Z-Score History")
                st.line_chart(spread_df["zscore_spread"].tail(100))
# ════════════════════════════════════════════════════════
# TAB 9 — Paper Trading
# ════════════════════════════════════════════════════════
with tab9:
    from paper_trading.tracker import (
    init_paper_trading, statistik_paper, catat_paper_trade,
    tutup_paper_trade, load_paper_trades, load_paper_config, laporan_mingguan
)

    st.subheader("📝 Paper Trading — 30 Hari Terstruktur")
    st.caption("Simulasi trading dengan aturan ketat sebelum live trading.")

    stats_p = statistik_paper()
    config_p = load_paper_config() if os.path.exists("logs/paper_config.json") else {}

    # ── Header Status ─────────────────────────────────
    ph1, ph2, ph3, ph4, ph5 = st.columns(5)
    ph1.metric("💰 Modal Sim",
               f"Rp {stats_p.get('modal_sim', 3_000_000):,.0f}",
               delta=f"Rp {stats_p.get('total_pnl_idr', 0):+,.0f}")
    ph2.metric("📅 Hari Berjalan",
               f"{stats_p.get('hari_berjalan', 0)} / 30")
    ph3.metric("🏆 Win Rate",
               f"{stats_p.get('win_rate', 0)}%",
               delta=f"{stats_p.get('win', 0)}W / {stats_p.get('loss', 0)}L")
    ph4.metric("📈 Return",
               f"{stats_p.get('total_pnl_pct', 0):+.2f}%")
    ph5.metric("✅ Status",
               "LULUS" if stats_p.get("lulus") else "BELUM",
               delta=f"{stats_p.get('total', 0)} trade closed")

    # Progress bar 30 hari
    hari = stats_p.get("hari_berjalan", 0)
    st.progress(min(hari / 30, 1.0))
    st.caption(f"Hari ke-{hari} dari 30 | Sisa {stats_p.get('hari_sisa', 30)} hari")

    # ── Inisialisasi ──────────────────────────────────
    if not os.path.exists("logs/paper_config.json"):
        st.warning("Paper trading belum dimulai.")
        if st.button("🚀 Mulai Paper Trading 30 Hari", type="primary"):
            init_paper_trading()
            st.success("✅ Paper trading dimulai! Semua sinyal skor ≥ 10 harus diambil.")
            st.rerun()
    else:
        pt1, pt2, pt3 = st.tabs(["📊 Dashboard", "📒 Trades", "📋 Laporan Mingguan"])

        # ── Dashboard Paper ───────────────────────────
        with pt1:
            kriteria = stats_p.get("kriteria", {})
            if kriteria:
                st.subheader("🎯 Kriteria Kelulusan")
                for nama, lulus in kriteria.items():
                    st.caption(f"{'✅' if lulus else '❌'} {nama}")

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Profit Factor", stats_p.get("profit_factor", 0),
                          delta="Bagus" if stats_p.get("profit_factor", 0) >= 1.3 else "Kurang")
            col_m2.metric("Max Drawdown",  f"{stats_p.get('max_drawdown', 0):.1f}%",
                          delta="Aman" if stats_p.get("max_drawdown", 0) < 15 else "Bahaya",
                          delta_color="inverse")
            col_m3.metric("Sharpe Ratio",  stats_p.get("sharpe", 0))

            # Catat paper trade manual
            st.divider()
            st.subheader("➕ Catat Paper Trade")
            st.caption("Isi dari sinyal yang sudah dianalisa di Tab Analisa.")

            pc1, pc2, pc3 = st.columns(3)
            p_sym  = pc1.selectbox("Aset", BIGCAP_WATCHLIST, key="p_sym")
            p_aksi = pc2.selectbox("Aksi", ["BUY", "SELL", "SHORT"], key="p_aksi")
            p_lev  = pc3.selectbox("Leverage", [1, 2, 3, 5], key="p_lev")

            pp1, pp2, pp3, pp4 = st.columns(4)
            p_entry = pp1.number_input("Entry", value=0.0, format="%.4f", key="p_entry")
            p_sl    = pp2.number_input("Stop Loss", value=0.0, format="%.4f", key="p_sl")
            p_tp1   = pp3.number_input("Target 1", value=0.0, format="%.4f", key="p_tp1")
            p_tp2   = pp4.number_input("Target 2", value=0.0, format="%.4f", key="p_tp2")

            ps1, ps2 = st.columns(2)
            p_skor = ps1.number_input("Skor sinyal", value=10, key="p_skor")
            p_keyak= ps2.number_input("Keyakinan AI", value=7, key="p_keyak")
            p_cat  = st.text_input("Catatan", key="p_cat")

            if st.button("📝 Catat Paper Trade", type="primary"):
                if p_entry > 0 and p_sl > 0:
                    result = catat_paper_trade(
                        p_sym, p_aksi, p_entry, p_sl, p_tp1, p_tp2,
                        0, p_lev, p_skor, p_keyak, p_cat
                    )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"✅ Paper trade #{result['id']} dicatat!")
                        st.rerun()
                else:
                    st.warning("Isi entry dan stop loss dulu.")

        # ── List Trades ───────────────────────────────
        with pt2:
            trades_p = load_paper_trades()
            open_p   = [t for t in trades_p if t["status"] == "OPEN"]
            closed_p = [t for t in trades_p if t["status"] == "CLOSED"]

            if open_p:
                st.subheader(f"📂 Open ({len(open_p)})")
                for t in open_p:
                    with st.expander(f"#{t['id']} {t['symbol']} {t['aksi']} @ {t['entry']}"):
                        ca, cb, cc = st.columns(3)
                        ca.metric("Entry", t["entry"])
                        cb.metric("SL",    t["stop_loss"])
                        cc.metric("TP1",   t["target_1"])

                        tx1, tx2, tx3 = st.columns(3)
                        h_keluar = tx1.number_input("Harga Keluar",
                                                     value=float(t["entry"]),
                                                     key=f"pk_{t['id']}")
                        h_hasil  = tx2.selectbox("Hasil", ["WIN","LOSS","BREAKEVEN"],
                                                  key=f"ph_{t['id']}")
                        with tx3:
                            st.write("")
                            st.write("")
                            if st.button(f"✅ Tutup #{t['id']}", key=f"ptutup_{t['id']}"):
                                closed = tutup_paper_trade(t["id"], h_keluar, h_hasil)
                                pnl    = closed.get("pnl_idr", 0)
                                st.success(f"{'🟢' if pnl > 0 else '🔴'} PnL: Rp {pnl:+,.0f}")
                                st.rerun()

            if closed_p:
                st.divider()
                st.subheader(f"📋 Closed ({len(closed_p)})")
                df_p = pd.DataFrame(closed_p)[[
                    "id", "tanggal", "symbol", "aksi", "entry",
                    "harga_keluar", "pnl_idr", "pnl_pct_modal",
                    "hasil", "durasi_jam", "skor_entry"
                ]]
                st.dataframe(df_p, use_container_width=True)

        # ── Laporan Mingguan ──────────────────────────
        with pt3:
            st.subheader("📋 Laporan Mingguan")
            lap = laporan_mingguan()
            if "pesan" in lap:
                st.info(lap["pesan"])
            else:
                l1, l2, l3, l4 = st.columns(4)
                l1.metric("Periode",     lap["periode"])
                l2.metric("Total Trade", lap["total_trade"])
                l3.metric("Win Rate",    f"{lap['win_rate']}%")
                l4.metric("PnL Minggu",  f"Rp {lap['pnl_idr']:+,.0f}",
                          delta=f"{lap['pnl_pct']:+.2f}%")
                st.metric("Avg Durasi Trade", f"{lap['avg_durasi']} jam")

        # Reset
        st.divider()
        if st.button("🗑️ Reset Paper Trading"):
            os.remove("logs/paper_trading.json")
            os.remove("logs/paper_config.json")
            st.success("Paper trading direset.")
            st.rerun()
