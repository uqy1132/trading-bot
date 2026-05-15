import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback, useEffect } from "react";
import { SYMBOLS } from "@/lib/mock";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "@/lib/utils";
import { api, type QuantData, type MomentumData, type PairsData } from "@/lib/api";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/quant")({
  component: QuantPage,
});

const TABS = ["Regime & Z-Score", "Momentum Ranking", "Pairs Trading"] as const;
const MOCK_Z = Array.from({ length: 60 }, (_, i) => ({ time: String(i), zscore: Math.sin(i / 5) * 1.8 + (Math.random() - 0.5) * 0.5 }));

function QuantPage() {
  const [tab, setTab] = useState<typeof TABS[number]>("Regime & Z-Score");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Quant Analysis</h1>
        <p className="text-sm text-muted-foreground">Regime detection, momentum ranking, dan statistical arbitrage.</p>
      </div>

      <div className="flex gap-1 rounded-lg border bg-card p-1 w-fit flex-wrap">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn("rounded-md px-3 py-1.5 text-xs transition", tab === t ? "bg-success/15 text-success" : "text-muted-foreground hover:text-foreground")}>
            {t}
          </button>
        ))}
      </div>

      {tab === "Regime & Z-Score" && <RegimeTab />}
      {tab === "Momentum Ranking" && <MomentumTab />}
      {tab === "Pairs Trading" && <PairsTab />}
    </div>
  );
}

function RegimeTab() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [tf, setTf] = useState("4H");
  const [data, setData] = useState<QuantData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.quant(symbol, tf);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memuat data quant");
    } finally {
      setLoading(false);
    }
  }, [symbol, tf]);

  useEffect(() => { fetch(); }, [fetch]);

  const zData = data?.zscoreData && data.zscoreData.length > 0 ? data.zscoreData : MOCK_Z;
  const regime = data?.regime?.state ?? "BULL";
  const volState = data?.garch?.volState ?? "MEDIUM";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Aset</span>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
            {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</span>
          <select value={tf} onChange={(e) => setTf(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
            {["1H", "4H", "1D"].map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <Button onClick={fetch} disabled={loading} variant="outline" className="h-10">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
        {data && !loading && <span className="text-xs text-success">✅ Live · {symbol} {tf}</span>}
        {error && <span className="text-xs text-danger">⚠️ {error}</span>}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border bg-card p-5">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Market Regime</div>
          <div className="mt-3">
            <span className={`rounded-md border px-3 py-1.5 text-sm font-semibold ${regime === "BULL" ? "border-success/40 bg-success/10 text-success" : "border-danger/40 bg-danger/10 text-danger"}`}>
              {regime}
            </span>
          </div>
          {data && <p className="mt-3 text-xs text-muted-foreground">{data.regime.rekomendasi}</p>}
          {data && <div className="mt-2 text-xs font-mono text-muted-foreground">Prob Bull: {(data.regime.probBull * 100).toFixed(0)}%</div>}
        </div>

        <div className="rounded-lg border bg-card p-5">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Volatility (GARCH)</div>
          <div className="mt-3">
            <span className={`rounded-md border px-3 py-1.5 text-sm font-semibold ${volState === "HIGH" ? "border-danger/40 bg-danger/10 text-danger" : volState === "LOW" ? "border-success/40 bg-success/10 text-success" : "border-warning/40 bg-warning/10 text-warning"}`}>
              {volState}
            </span>
          </div>
          {data && <p className="mt-3 text-xs text-muted-foreground">Vol forecast: {(data.garch.volForecast * 100).toFixed(2)}%</p>}
          {data && <p className="mt-1 text-xs text-muted-foreground">Sizing mult: {data.garch.sizingMult}x</p>}
        </div>

        <div className="rounded-lg border bg-card p-5">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Kalman Filter</div>
          {data ? (
            <>
              <div className="mt-3"><SignalBadge signal={data.kalman.sinyal} size="md" /></div>
              <div className="mt-2 font-mono text-sm">Z-Score: {data.kalman.zscore.toFixed(3)}</div>
              <p className="mt-2 text-xs text-muted-foreground">{data.kalman.detail}</p>
            </>
          ) : (
            <div className="mt-3 animate-pulse h-8 bg-muted/50 rounded" />
          )}
        </div>

        <div className="rounded-lg border bg-card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold">Z-Score Chart (mean-reversion bands)</h3>
          <div className="mt-3 h-64">
            <ResponsiveContainer>
              <LineChart data={zData}>
                <XAxis dataKey="time" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <YAxis domain={[-3, 3]} tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 }} />
                <ReferenceLine y={2} stroke="var(--danger)" strokeDasharray="3 3" label={{ value: "+2σ", fill: "var(--danger)", fontSize: 10 }} />
                <ReferenceLine y={-2} stroke="var(--success)" strokeDasharray="3 3" label={{ value: "-2σ", fill: "var(--success)", fontSize: 10 }} />
                <ReferenceLine y={0} stroke="var(--border)" />
                <Line type="monotone" dataKey="zscore" stroke="var(--chart-4)" dot={false} strokeWidth={1.6} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {data && (
          <div className="rounded-lg border bg-card p-5">
            <h3 className="text-sm font-semibold">Multi-Factor Score</h3>
            <div className="mt-4 space-y-3 text-sm">
              <Row label="Total Skor" value={String(data.skortTotal)} />
              <Row label="Keputusan" value={data.keputusan} />
              <Row label="Kelly %" value="—" />
              <Row label="Aman Trading" value={data.regime.amanTrading ? "✅ Ya" : "⛔ Tidak"} tone={data.regime.amanTrading ? "success" : "danger"} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MomentumTab() {
  const [tf, setTf] = useState("4H");
  const [data, setData] = useState<MomentumData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.momentum(tf);
      setData(res);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [tf]);

  useEffect(() => { fetch(); }, [fetch]);

  const medals = ["🥇", "🥈", "🥉"];
  const ranking = data?.ranking ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <select value={tf} onChange={(e) => setTf(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
          {["1H", "4H", "1D"].map((t) => <option key={t}>{t}</option>)}
        </select>
        <Button onClick={fetch} disabled={loading} variant="outline" className="h-10">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </Button>
        {data && <span className="text-xs text-success">✅ Live</span>}
      </div>

      <div className="overflow-x-auto rounded-lg border bg-card">
        {loading ? (
          <div className="p-8 text-center text-sm text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-background/50 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>{["Rank", "Aset", "Momentum Score", "Signal"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {ranking.map((r, i) => {
                const sig = r.signal ?? r.sinyal ?? "HOLD";
                return (
                  <tr key={r.symbol} className="border-b last:border-b-0">
                    <td className="px-4 py-3 text-lg">{medals[i] ?? <span className="font-mono text-sm text-muted-foreground">#{i + 1}</span>}</td>
                    <td className="px-4 py-3 font-mono">{r.symbol}</td>
                    <td className={cn("px-4 py-3 font-mono", r.momentum >= 0 ? "text-success" : "text-danger")}>
                      {r.momentum.toFixed(2)}
                    </td>
                    <td className="px-4 py-3">
                      <SignalBadge signal={sig === "LONG" ? "BUY" : sig === "SHORT" ? "SELL" : "HOLD"} size="sm" />
                    </td>
                  </tr>
                );
              })}
              {ranking.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">Klik Refresh untuk memuat data</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function PairsTab() {
  const [a, setA] = useState("BTC/USDT");
  const [b, setB] = useState("ETH/USDT");
  const [tf, setTf] = useState("4H");
  const [data, setData] = useState<PairsData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    if (a === b) return;
    setLoading(true);
    try {
      const res = await api.pairs(a, b, tf);
      setData(res);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [a, b, tf]);

  const spreadData = data?.spreadData && data.spreadData.length > 0 ? data.spreadData : MOCK_Z;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Aset A</span>
          <select value={a} onChange={(e) => setA(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
            {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Aset B</span>
          <select value={b} onChange={(e) => setB(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
            {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</span>
          <select value={tf} onChange={(e) => setTf(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
            {["1H", "4H", "1D"].map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <Button onClick={fetch} disabled={loading || a === b} className="h-10 bg-success text-success-foreground hover:bg-success/90">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Analisa Pairs
        </Button>
        {data && (
          <>
            <span className="rounded-md border border-success/40 bg-success/10 px-3 py-1.5 text-xs text-success">
              Correlation — pvalue: {data.pvalue.toFixed(3)}
            </span>
            <SignalBadge signal={data.sinyal === "BUY_A" ? "BUY" : data.sinyal === "SELL_A" ? "SELL" : "HOLD"} />
            <span className="rounded-md border bg-background px-3 py-1.5 text-xs">
              Hedge ratio: <span className="font-mono">1 : {data.hedgeRatio.toFixed(2)}</span>
            </span>
          </>
        )}
      </div>

      {data && (
        <div className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
          ✅ {data.sym1} vs {data.sym2} · Z-Score: {data.zscore.toFixed(3)} · {data.detail}
        </div>
      )}

      <div className="rounded-lg border bg-card p-5">
        <h3 className="text-sm font-semibold">Spread Z-Score</h3>
        <div className="mt-3 h-64">
          <ResponsiveContainer>
            <LineChart data={spreadData}>
              <XAxis dataKey="time" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <YAxis domain={[-3, 3]} tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 }} />
              <ReferenceLine y={2} stroke="var(--danger)" strokeDasharray="3 3" />
              <ReferenceLine y={-2} stroke="var(--success)" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="zscore" stroke="var(--success)" dot={false} strokeWidth={1.6} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "success" | "danger" }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono", tone === "success" && "text-success", tone === "danger" && "text-danger")}>{value}</span>
    </div>
  );
}
