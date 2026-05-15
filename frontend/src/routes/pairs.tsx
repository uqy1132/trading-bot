import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { SYMBOLS, TIMEFRAMES } from "@/lib/mock";
import { Button } from "@/components/ui/button";
import { Loader2, GitCompare } from "lucide-react";
import { api, type PairsData } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Line, ComposedChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

export const Route = createFileRoute("/pairs")({
  component: PairsPage,
});

function PairsPage() {
  const [sym1, setSym1] = useState(SYMBOLS[0]);
  const [sym2, setSym2] = useState(SYMBOLS[1]);
  const [tf, setTf] = useState(TIMEFRAMES[1]);
  const [data, setData] = useState<PairsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalisa = useCallback(async () => {
    if (sym1 === sym2) { alert("Pilih dua aset yang berbeda."); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.pairs(sym1, sym2, tf);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal analisa pairs");
    } finally {
      setLoading(false);
    }
  }, [sym1, sym2, tf]);

  const zscoreColor =
    data && Math.abs(data.zscore) >= 2
      ? data.zscore > 0 ? "text-danger" : "text-success"
      : "text-foreground";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Pairs Trading</h1>
        <p className="text-sm text-muted-foreground">
          Analisa korelasi dua aset berdasarkan spread Z-score. Sinyal muncul saat Z-score ekstrem (±2σ).
        </p>
      </div>

      {/* Control */}
      <div className="rounded-lg border bg-card p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Aset 1</span>
            <select value={sym1} onChange={(e) => setSym1(e.target.value)}
              className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
              {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Aset 2</span>
            <select value={sym2} onChange={(e) => setSym2(e.target.value)}
              className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
              {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</span>
            <select value={tf} onChange={(e) => setTf(e.target.value)}
              className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
              {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <Button onClick={handleAnalisa} disabled={loading}
              className="w-full bg-success text-success-foreground hover:bg-success/90 h-10">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitCompare className="mr-2 h-4 w-4" />}
              {loading ? "Menganalisa..." : "Analisa Pairs"}
            </Button>
          </div>
        </div>
      </div>

      {/* Status */}
      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          ⚠️ {error}
        </div>
      )}

      {!data && !loading && (
        <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
          Pilih dua aset dan klik "Analisa Pairs" untuk melihat spread dan sinyal korelasi.
        </div>
      )}

      {loading && (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-muted/50" />
          ))}
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          {/* Sinyal utama */}
          <div className={cn(
            "rounded-lg border p-4",
            data.sinyal === "LONG" ? "border-success/50 bg-success/5" :
            data.sinyal === "SHORT" ? "border-danger/50 bg-danger/5" :
            "border-border bg-card"
          )}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Sinyal Pairs</div>
                <div className={cn(
                  "text-2xl font-bold font-mono",
                  data.sinyal === "LONG" ? "text-success" : data.sinyal === "SHORT" ? "text-danger" : "text-muted-foreground"
                )}>
                  {data.sinyal === "LONG" ? "🟢 LONG SPREAD" : data.sinyal === "SHORT" ? "🔴 SHORT SPREAD" : "⚪ WAIT"}
                </div>
                <div className="text-sm text-muted-foreground mt-1">{data.aksi}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-muted-foreground">Pasangan</div>
                <div className="font-mono text-lg font-semibold">{data.sym1} / {data.sym2}</div>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
            <StatCard label="Z-Score" value={data.zscore.toFixed(3)} valueClass={zscoreColor}
              sub={Math.abs(data.zscore) >= 2 ? "⚠️ Ekstrem" : "Normal"} />
            <StatCard label="P-Value" value={data.pvalue.toFixed(4)}
              sub={data.pvalue < 0.05 ? "✅ Cointegrated" : "❌ Tidak cointegrated"} />
            <StatCard label="Hedge Ratio" value={data.hedgeRatio.toFixed(4)} sub="β koefisien" />
            <StatCard label="Timeframe" value={tf} sub={`${data.spreadData.length} candle`} />
          </div>

          {/* Detail */}
          <div className="rounded-lg border bg-card p-4">
            <h3 className="text-sm font-semibold mb-2">Interpretasi</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">{data.detail}</p>
          </div>

          {/* Z-Score Chart */}
          {data.spreadData.length > 0 && (
            <div className="rounded-lg border bg-card p-5">
              <h3 className="text-sm font-semibold mb-3">Z-Score Spread History</h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={data.spreadData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <XAxis dataKey="time" hide />
                    <YAxis
                      tick={{ fill: "var(--muted-foreground)", fontSize: 9 }}
                      axisLine={false} tickLine={false} width={38}
                    />
                    <Tooltip
                      contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
                      formatter={(v: number) => [v.toFixed(3), "Z-Score"]}
                      labelFormatter={(l: string) => l.slice(0, 16)}
                    />
                    <ReferenceLine y={0} stroke="var(--border)" />
                    <ReferenceLine y={2} stroke="var(--danger)" strokeDasharray="4 2" strokeOpacity={0.6} />
                    <ReferenceLine y={-2} stroke="var(--success)" strokeDasharray="4 2" strokeOpacity={0.6} />
                    <ReferenceLine y={1} stroke="var(--danger)" strokeDasharray="2 4" strokeOpacity={0.3} />
                    <ReferenceLine y={-1} stroke="var(--success)" strokeDasharray="2 4" strokeOpacity={0.3} />
                    <Line
                      type="monotone" dataKey="zscore"
                      stroke="var(--chart-4)" dot={false} strokeWidth={1.5}
                      isAnimationActive={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <div className="flex gap-4 mt-2 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-[2px] w-4 bg-danger/60 inline-block rounded" />±2σ (sinyal)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-[2px] w-4 bg-danger/30 inline-block rounded" />±1σ (peringatan)
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, valueClass }: {
  label: string; value: string; sub: string; valueClass?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("font-mono text-xl font-semibold mt-1", valueClass)}>{value}</div>
      <div className="text-[10px] text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}
