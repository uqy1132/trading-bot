import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback, useEffect } from "react";
import { SYMBOLS, TIMEFRAMES, LEVERAGES, scoring as mockScoring, aiDecision as mockAI, mtf as mockMtf, genCandles, genRSI } from "@/lib/mock";
import { formatIDR, formatNum, formatUSDT } from "@/lib/format";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { PriceChart } from "@/components/charts/PriceChart";
import { RSIChart } from "@/components/charts/RSIChart";
import { Button } from "@/components/ui/button";
import { Star, TrendingUp, Target, Shield, Zap, X, Send, Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type AnalisaData, type KillSwitchData } from "@/lib/api";
import { Bar, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>) => ({
    symbol: (search.symbol as string | undefined) ?? "",
  }),
  component: AnalysisPage,
});

function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: readonly (string | number)[]; label: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 rounded-md border bg-card px-3 text-sm font-mono outline-none focus:border-success/60"
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

const MOCK_CANDLES = genCandles(80, 80000);
const MOCK_RSI = genRSI(80);

const MOCK_DATA: AnalisaData = {
  symbol: "BTC/USDT", timeframe: "4H", harga: 80246.9, rsi: 55, adx: 28, konsensus: "BUY",
  scoring: mockScoring,
  aiDecision: { action: "BUY", confidence: 8, entry: 80250, sl: 78900, tp1: 82500, tp2: 84800, rr: 2.4, reason: mockAI.reason, risk: "MEDIUM" },
  mtf: mockMtf.map(m => ({ ...m, signal: m.signal as string })),
  sizing: { ukuran: 0.045, nilaiIDR: 54_000_000, marginUSDT: 2000, maxLossIDR: 60_000, maxLossUSDT: 3.7, pctModal: 2, leverage: 3 },
  candles: MOCK_CANDLES,
  rsiData: MOCK_RSI,
};

function AnalysisPage() {
  const { symbol: qSymbol } = Route.useSearch();
  const [symbol, setSymbol] = useState(qSymbol || SYMBOLS[0]);
  const [tf, setTf] = useState(TIMEFRAMES[1]);
  const [lev, setLev] = useState("3");
  const [result, setResult] = useState<AnalisaData>(MOCK_DATA);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(true);
  const [discordLoading, setDiscordLoading] = useState(false);
  const [discordSent, setDiscordSent] = useState(false);
  const [ambilLoading, setAmbilLoading] = useState(false);
  const [ambilDone, setAmbilDone] = useState(false);
  const [skipLoading, setSkipLoading] = useState(false);
  const [skipDone, setSkipDone] = useState(false);
  const [paperLoading, setPaperLoading] = useState(false);
  const [paperDone, setPaperDone] = useState(false);
  const [eksekusiLoading, setEksekusiLoading] = useState(false);
  const [eksekusiDone, setEksekusiDone] = useState(false);
  const [killSwitch, setKillSwitch] = useState<KillSwitchData | null>(null);
  const [liveMode, setLiveMode] = useState(false);

  useEffect(() => {
    api.killSwitch().then(setKillSwitch).catch(() => {});
    api.settings().then((s) => setLiveMode(s.liveMode)).catch(() => {});
  }, []);

  const handleAnalisa = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDiscordSent(false);
    setAmbilDone(false);
    setSkipDone(false);
    setPaperDone(false);
    setEksekusiDone(false);
    try {
      const data = await api.analisa(symbol, tf, Number(lev));
      // Pastikan ada data chart — fallback ke mock kalau kosong
      if (!data.candles || data.candles.length === 0) {
        data.candles = genCandles(80, data.harga || 80000);
      }
      if (!data.rsiData || data.rsiData.length === 0) {
        data.rsiData = genRSI(80);
      }
      setResult(data);
      setIsMock(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal mengambil data analisa");
      setIsMock(true);
    } finally {
      setLoading(false);
    }
  }, [symbol, tf, lev]);

  const handleDiscord = useCallback(async () => {
    setDiscordLoading(true);
    try {
      await api.discordAnalisa({
        symbol: result.symbol,
        timeframe: result.timeframe,
        action: result.aiDecision.action,
        confidence: result.aiDecision.confidence,
        entry: result.aiDecision.entry,
        sl: result.aiDecision.sl,
        tp1: result.aiDecision.tp1,
        tp2: result.aiDecision.tp2,
        rr: result.aiDecision.rr,
        reason: result.aiDecision.reason,
        grade: result.scoring.grade,
        score: result.scoring.score,
        max: result.scoring.max,
        ukuran: result.sizing.ukuran,
        maxLossIDR: result.sizing.maxLossIDR,
        nilaiIDR: result.sizing.nilaiIDR,
      });
      setDiscordSent(true);
    } catch {
      setDiscordSent(false);
    } finally {
      setDiscordLoading(false);
    }
  }, [result]);

  const handleAmbilTrade = useCallback(async () => {
    if (isMock) { alert("Jalankan analisa live dulu sebelum mengambil trade."); return; }
    setAmbilLoading(true);
    try {
      await api.catatTrade({
        symbol: result.symbol,
        aksi: result.aiDecision.action,
        entry: result.aiDecision.entry,
        sl: result.aiDecision.sl,
        target_1: result.aiDecision.tp1,
        target_2: result.aiDecision.tp2,
        ukuran: result.sizing.ukuran,
        leverage: result.sizing.leverage,
        catatan: `Grade: ${result.scoring.grade} (${result.scoring.score}/${result.scoring.max}) | ${result.timeframe}`,
      });
      setAmbilDone(true);
    } catch (e) {
      alert("Gagal catat trade: " + String(e));
    } finally {
      setAmbilLoading(false);
    }
  }, [result, isMock]);

  const handleSkip = useCallback(async () => {
    if (isMock) { alert("Jalankan analisa live dulu sebelum skip."); return; }
    setSkipLoading(true);
    try {
      await api.skipTrade({
        symbol: result.symbol,
        timeframe: result.timeframe,
        sinyal: result.aiDecision.action,
        grade: result.scoring.grade,
        skor: result.scoring.score,
        harga: result.harga,
        alasan: result.aiDecision.reason.slice(0, 120),
      });
      setSkipDone(true);
    } catch (e) {
      alert("Gagal catat skip: " + String(e));
    } finally {
      setSkipLoading(false);
    }
  }, [result, isMock]);

  const handleEksekusiLive = useCallback(async () => {
    if (isMock) { alert("Jalankan analisa live dulu sebelum eksekusi."); return; }
    if (!confirm(`Eksekusi LIVE ${result.aiDecision.action} ${result.symbol}? Order nyata akan dikirim ke exchange.`)) return;
    setEksekusiLoading(true);
    try {
      const res = await api.eksekusiOrder({
        symbol: result.symbol,
        aksi: result.aiDecision.action,
        ukuran: result.sizing.ukuran,
        entry: result.aiDecision.entry,
        sl: result.aiDecision.sl,
        tp1: result.aiDecision.tp1,
        tp2: result.aiDecision.tp2,
        leverage: result.sizing.leverage,
      });
      setEksekusiDone(true);
      alert(`✅ Order ${res.mode} tereksekusi\nFill: $${res.fill_price}\nID: ${res.order_id}`);
      // refresh kill switch setelah eksekusi
      api.killSwitch().then(setKillSwitch).catch(() => {});
    } catch (e) {
      alert("Gagal eksekusi: " + String(e));
    } finally {
      setEksekusiLoading(false);
    }
  }, [result, isMock]);

  const handlePaperTrade = useCallback(async () => {
    if (isMock) { alert("Jalankan analisa live dulu sebelum paper trade."); return; }
    setPaperLoading(true);
    try {
      await api.paperTrade({
        symbol: result.symbol,
        aksi: result.aiDecision.action,
        entry: result.aiDecision.entry,
        sl: result.aiDecision.sl,
        target_1: result.aiDecision.tp1,
        target_2: result.aiDecision.tp2,
        ukuran: result.sizing.ukuran,
        leverage: result.sizing.leverage,
        skor: result.scoring.score,
        keyakinan: result.aiDecision.confidence,
        catatan: `Paper | ${result.timeframe} | ${result.scoring.grade}`,
      });
      setPaperDone(true);
    } catch (e) {
      alert("Gagal paper trade: " + String(e));
    } finally {
      setPaperLoading(false);
    }
  }, [result, isMock]);

  const scoring = result.scoring;
  const aiDecision = result.aiDecision;
  const candles = result.candles;
  const rsiData = result.rsiData;

  const gradeColor =
    scoring.grade.startsWith("A") ? "text-success border-success/40 bg-success/10" :
    scoring.grade === "B" ? "text-warning border-warning/40 bg-warning/10" :
    "text-danger border-danger/40 bg-danger/10";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Analisa & Sinyal</h1>
          <p className="text-sm text-muted-foreground">Pilih aset & timeframe untuk membuka analisa multi-timeframe + AI decision.</p>
        </div>
        <div className="flex items-center gap-2 shrink-0 mt-1">
          {liveMode && (
            <span className="rounded-full border border-orange-500/60 bg-orange-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-orange-400">
              ⚡ LIVE MODE
            </span>
          )}
          {killSwitch && (
            <span className={cn(
              "rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
              killSwitch.status === "OK"
                ? "border-success/40 bg-success/10 text-success"
                : killSwitch.status === "PAUSE"
                ? "border-warning/60 bg-warning/10 text-warning"
                : "border-danger/60 bg-danger/10 text-danger"
            )}>
              🛡 {killSwitch.status}
            </span>
          )}
        </div>
      </div>

      {/* Control */}
      <div className="rounded-lg border bg-card p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Select label="Aset" value={symbol} onChange={setSymbol} options={SYMBOLS} />
          <Select label="Timeframe" value={tf} onChange={setTf} options={TIMEFRAMES} />
          <Select label="Leverage" value={lev} onChange={setLev} options={LEVERAGES.map((l) => `${l}`)} />
          <div className="flex items-end">
            <Button onClick={handleAnalisa} disabled={loading} className="w-full bg-success text-success-foreground hover:bg-success/90 h-10">
              {loading ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Zap className="mr-1.5 h-4 w-4" />}
              {loading ? "Menganalisa..." : "Analisa Sekarang"}
            </Button>
          </div>
        </div>
      </div>

      {/* Kill Switch Banner */}
      {killSwitch && killSwitch.status !== "OK" && (
        <div className={cn(
          "flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold",
          killSwitch.status === "STOP"
            ? "border-danger/60 bg-danger/10 text-danger"
            : "border-warning/60 bg-warning/10 text-warning"
        )}>
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span>KILL SWITCH {killSwitch.status}: {killSwitch.pesan}</span>
          <span className="ml-auto font-mono font-normal text-[11px]">
            DD Hari: {killSwitch.dd_hari_pct.toFixed(1)}% · DD Total: {killSwitch.dd_total_pct.toFixed(1)}%
          </span>
        </div>
      )}

      {/* Status banner */}
      {error && (
        <div className="flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span>Gagal menghubungi API: {error}. Menampilkan mock data sebagai fallback.</span>
        </div>
      )}
      {!error && !isMock && (
        <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
          ✅ Data live dari backend · {result.symbol} · {result.timeframe}
        </div>
      )}
      {isMock && !error && (
        <div className="rounded-md border bg-background px-3 py-2 text-xs text-muted-foreground">
          Menampilkan mock data — klik "Analisa Sekarang" untuk memuat data real.
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Scoring */}
        <div className="rounded-lg border bg-card p-5 xl:col-span-1">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Scoring Setup</h3>
            <span className="text-xs text-muted-foreground font-mono">{result.symbol} · {result.timeframe}</span>
          </div>
          <div className={cn("mt-4 inline-flex items-center gap-3 rounded-lg border px-4 py-2", gradeColor)}>
            <span className="font-mono text-3xl font-bold">{scoring.grade}</span>
            <div>
              <div className="text-xs uppercase tracking-wider opacity-80">Skor</div>
              <div className="font-mono text-base">{scoring.score} / {scoring.max}</div>
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-success transition-all" style={{ width: `${(scoring.score / scoring.max) * 100}%` }} />
          </div>
          <div className="mt-4 space-y-2">
            {scoring.factors.map((f) => (
              <div key={f.label} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{f.label}</span>
                <span className="font-mono">{f.score}{f.max ? `/${f.max}` : ""}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Charts */}
        <div className="rounded-lg border bg-card p-5 xl:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Price · EMA20/EMA50 · BB</h3>
            <SignalBadge signal={aiDecision.action} />
          </div>
          <div className="mt-3">
            <PriceChart data={candles} />
          </div>
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between">
              <h4 className="text-xs font-medium text-muted-foreground">RSI(14)</h4>
              <span className="text-xs font-mono text-muted-foreground">70 / 30</span>
            </div>
            <RSIChart data={rsiData} />
          </div>
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between">
              <h4 className="text-xs font-medium text-muted-foreground">MACD(12,26,9)</h4>
              <span className="text-xs font-mono text-muted-foreground">
                {candles.length > 0 && candles[candles.length - 1].macd != null
                  ? ((candles[candles.length - 1].macd ?? 0) >= (candles[candles.length - 1].macdSignal ?? 0)
                    ? <span className="text-success">Bullish</span>
                    : <span className="text-danger">Bearish</span>)
                  : "—"}
              </span>
            </div>
            <MACDChart data={candles} />
          </div>
        </div>

        {/* Open Interest */}
        {result.openInterest && result.openInterest.trend !== "UNKNOWN" && (
          <div className="rounded-lg border bg-card p-5 xl:col-span-3">
            <h3 className="text-sm font-semibold">Open Interest</h3>
            <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
              <div>
                <span className="text-muted-foreground text-xs">Nilai OI</span>
                <div className="font-mono">{formatNum(result.openInterest.value, 0)}</div>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">Perubahan (1d)</span>
                <div className={cn("font-mono", result.openInterest.changePct >= 0 ? "text-success" : "text-danger")}>
                  {result.openInterest.changePct >= 0 ? "+" : ""}{result.openInterest.changePct.toFixed(2)}%
                </div>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">Tren OI</span>
                <div className={cn("font-semibold",
                  result.openInterest.trend === "RISING" ? "text-success" :
                  result.openInterest.trend === "FALLING" ? "text-danger" : "text-muted-foreground")}>
                  {result.openInterest.trend === "RISING" ? "↑ NAIK" :
                   result.openInterest.trend === "FALLING" ? "↓ TURUN" : "→ STABIL"}
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {result.openInterest.trend === "RISING"
                  ? "OI naik bersama harga = posisi baru masuk, trend valid"
                  : result.openInterest.trend === "FALLING"
                  ? "OI turun = posisi ditutup, waspadai melemahnya trend"
                  : "OI stabil"}
              </p>
            </div>
          </div>
        )}

        {/* MTF */}
        <div className="rounded-lg border bg-card p-5 xl:col-span-1">
          <h3 className="text-sm font-semibold">Multi-Timeframe</h3>
          <div className="mt-4 grid grid-cols-3 gap-3">
            {result.mtf.map((m) => (
              <div key={m.tf} className="rounded-md border bg-background p-3 text-center">
                <div className="text-xs text-muted-foreground">{m.tf}</div>
                <div className="mt-2"><SignalBadge signal={m.signal} /></div>
                <div className="mt-2 text-xs text-muted-foreground">RSI</div>
                <div className="font-mono text-sm">{typeof m.rsi === "number" ? m.rsi.toFixed(1) : m.rsi}</div>
              </div>
            ))}
          </div>
        </div>

        {/* AI Decision */}
        <div className={cn("rounded-lg border bg-card p-5 xl:col-span-2",
          aiDecision.action === "BUY" ? "glow-success" : aiDecision.action === "SELL" ? "glow-danger" : "")}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold">AI Decision</h3>
              <SignalBadge signal={aiDecision.action} size="lg" />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              Keyakinan
              <span className="flex">
                {Array.from({ length: 10 }).map((_, i) => (
                  <Star key={i} className={cn("h-3.5 w-3.5", i < aiDecision.confidence ? "fill-warning text-warning" : "text-muted")} />
                ))}
              </span>
              <span className="font-mono text-foreground">{aiDecision.confidence}/10</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "Entry", value: aiDecision.entry, icon: Target },
              { label: "Stop Loss", value: aiDecision.sl, icon: Shield, tone: "danger" as const },
              { label: "TP1", value: aiDecision.tp1, icon: TrendingUp, tone: "success" as const },
              { label: "TP2", value: aiDecision.tp2, icon: TrendingUp, tone: "success" as const },
            ].map((m) => {
              const I = m.icon;
              return (
                <div key={m.label} className="rounded-md border bg-background p-3">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <I className="h-3 w-3" /> {m.label}
                  </div>
                  <div className={cn("mt-1 font-mono text-base", m.tone === "danger" && "text-danger", m.tone === "success" && "text-success")}>
                    {formatUSDT(m.value)}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="rounded-md border border-success/40 bg-success/10 px-3 py-1 font-mono text-xs text-success">R:R 1:{Number(aiDecision.rr).toFixed(2)}</span>
            <span className="rounded-md border bg-background px-3 py-1 text-xs text-muted-foreground">Risiko: {aiDecision.risk}</span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{aiDecision.reason}</p>
        </div>

        {/* Position sizing + Actions */}
        <div className="rounded-lg border bg-card p-5 xl:col-span-1">
          <h3 className="text-sm font-semibold">Position Size</h3>
          <div className="mt-4 space-y-3 text-sm">
            <Row label="Ukuran" value={`${formatNum(result.sizing.ukuran, 4)} ${result.symbol.split("/")[0]}`} />
            <Row label="Nilai (IDR)" value={formatIDR(result.sizing.nilaiIDR)} />
            <Row label="Leverage" value={`${result.sizing.leverage}x`} />
            <Row label="Margin" value={formatUSDT(result.sizing.marginUSDT)} />
            <Row label="Max Loss (IDR)" value={formatIDR(result.sizing.maxLossIDR)} tone="danger" />
            <Row label="% Modal" value={`${result.sizing.pctModal}%`} />
          </div>
          <div className="mt-5 flex flex-col gap-2">
            <Button
              onClick={handleAmbilTrade}
              disabled={ambilLoading || ambilDone || isMock}
              className="bg-success text-success-foreground hover:bg-success/90"
            >
              {ambilLoading && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              {ambilDone ? "✅ Trade Dicatat ke Jurnal" : "🚀 Ambil Trade Ini"}
            </Button>
            {liveMode && (
              <Button
                onClick={handleEksekusiLive}
                disabled={eksekusiLoading || eksekusiDone || isMock || (killSwitch?.status === "STOP")}
                className="bg-orange-600 text-white hover:bg-orange-700"
                title={killSwitch?.status === "STOP" ? "Kill switch aktif — eksekusi diblokir" : ""}
              >
                {eksekusiLoading && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                {eksekusiDone ? "✅ Order Tereksekusi" : "⚡ Eksekusi Live"}
              </Button>
            )}
            <Button
              onClick={handleDiscord}
              disabled={discordLoading || discordSent || isMock}
              variant="outline"
              className="border-border/60"
            >
              {discordLoading
                ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                : <Send className="mr-1.5 h-4 w-4" />}
              {discordSent ? "✅ Discord Terkirim" : "Kirim ke Discord"}
            </Button>
            <Button
              onClick={handlePaperTrade}
              disabled={paperLoading || paperDone || isMock}
              variant="outline"
              className="border-warning/40 text-warning hover:bg-warning/10"
            >
              {paperLoading && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              {paperDone ? "✅ Paper Trade Dicatat" : "📋 Paper Trade"}
            </Button>
            <Button
              onClick={handleSkip}
              disabled={skipLoading || skipDone || isMock || ambilDone}
              variant="outline"
              className="border-danger/40 text-danger hover:bg-danger/10 hover:text-danger"
            >
              {skipLoading && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              <X className="mr-1 h-4 w-4" />
              {skipDone ? "Dilewati" : "Skip"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "danger" | "success" }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono", tone === "danger" && "text-danger", tone === "success" && "text-success")}>{value}</span>
    </div>
  );
}

function MACDChart({ data }: { data: AnalisaData["candles"] }) {
  const chartData = data.map((d) => ({
    time: d.time.slice(0, 16),
    macd: +(d.macd ?? 0).toFixed(4),
    signal: +(d.macdSignal ?? 0).toFixed(4),
    hist: +(d.macdHist ?? 0).toFixed(4),
  }));

  return (
    <div className="h-28">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 2, right: 4, left: 0, bottom: 0 }}>
          <XAxis dataKey="time" hide />
          <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 9 }} axisLine={false} tickLine={false} width={40} />
          <Tooltip
            contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
            formatter={(v: number, name: string) => [
              v.toFixed(4),
              name === "hist" ? "Histogram" : name === "macd" ? "MACD" : "Signal",
            ]}
          />
          <ReferenceLine y={0} stroke="var(--border)" />
          <Bar dataKey="hist" barSize={4} isAnimationActive={false}>
            {chartData.map((entry, i) => (
              <rect key={i} fill={entry.hist >= 0 ? "var(--success)" : "var(--danger)"} fillOpacity={0.75} />
            ))}
          </Bar>
          <Line type="monotone" dataKey="macd" stroke="var(--chart-4)" dot={false} strokeWidth={1.5} />
          <Line type="monotone" dataKey="signal" stroke="#f59e0b" dot={false} strokeWidth={1.5} strokeDasharray="3 3" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
