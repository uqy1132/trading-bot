import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import { equityCurve as mockCurve, performance as mockPerf } from "@/lib/mock";
import { StatCard } from "@/components/trading/StatCard";
import { EquityChart } from "@/components/charts/EquityChart";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPct, formatIDR } from "@/lib/format";
import { api, type PerformaData } from "@/lib/api";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/performance")({
  component: PerformancePage,
});

const MOCK_DIST = [
  { bucket: "<-5%", count: 0 }, { bucket: "-5~-3%", count: 0 },
  { bucket: "-3~-1%", count: 0 }, { bucket: "-1~1%", count: 0 },
  { bucket: "1~3%", count: 0 }, { bucket: "3~5%", count: 0 },
  { bucket: ">5%", count: 0 },
];

const MOCK_PERFORMA: PerformaData = {
  ...mockPerf,
  worstTrade: -3.2,
  equityCurve: mockCurve,
  modal: 3_000_000,
  pnlDist: MOCK_DIST,
  targetBulanan: 4,
};

function PerformancePage() {
  const [data, setData] = useState<PerformaData>(MOCK_PERFORMA);
  const [loading, setLoading] = useState(false);
  const [isMock, setIsMock] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.performa();
      if (res.equityCurve && res.equityCurve.length > 0) {
        setData(res);
        setIsMock(false);
      }
    } catch {
      setIsMock(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const target = data.targetBulanan ?? 4;
  const dist = data.pnlDist ?? MOCK_DIST;
  const progress = Math.min(100, (data.totalPnL / target) * 100);
  const lastEquity = data.equityCurve[data.equityCurve.length - 1]?.equity ?? data.modal;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Performa</h1>
          <p className="text-sm text-muted-foreground">Statistik akun, equity curve, dan distribusi PnL.</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetch} disabled={loading}>
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
        </Button>
      </div>

      {!isMock && (
        <div className="rounded-md border border-success/40 bg-success/10 px-3 py-1.5 text-xs text-success">
          ✅ Data live dari backend
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total Trade" value={data.totalTrade} />
        <StatCard label="Win Rate" value={`${data.winRate.toFixed(1)}%`} tone="success" />
        <StatCard label="Total PnL" value={formatPct(data.totalPnL)} tone={data.totalPnL >= 0 ? "success" : "danger"} />
        <StatCard label="Profit Factor" value={data.profitFactor.toFixed(2)} tone="success" />
        <StatCard label="Avg Win" value={formatPct(data.avgWin)} tone="success" />
        <StatCard label="Avg Loss" value={formatPct(data.avgLoss)} tone="danger" />
        <StatCard label="Open Trades" value={data.openTrades} />
        <StatCard label="Best Trade" value={formatPct(data.bestTrade)} tone="success" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border bg-card p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Equity Curve</h3>
            <span className="text-xs text-muted-foreground">{formatIDR(lastEquity)}</span>
          </div>
          <div className="mt-3"><EquityChart data={data.equityCurve} /></div>
        </div>

        <div className="rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Target Bulanan</h3>
          <div className="mt-4">
            <div className="flex items-baseline justify-between">
              <span className={`font-mono text-2xl ${data.totalPnL >= 0 ? "text-success" : "text-danger"}`}>
                {formatPct(data.totalPnL)}
              </span>
              <span className="text-xs text-muted-foreground">target {target}%</span>
            </div>
            <div className="mt-3 h-3 overflow-hidden rounded-full bg-muted">
              <div className="h-full bg-success transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Progress: <span className="font-mono text-foreground">{progress.toFixed(0)}%</span>
            </p>
          </div>
          <div className="mt-4 border-t pt-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Modal Awal</span>
              <span className="font-mono">{formatIDR(data.modal)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Equity Sekarang</span>
              <span className={`font-mono ${lastEquity >= data.modal ? "text-success" : "text-danger"}`}>{formatIDR(lastEquity)}</span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-5 lg:col-span-3">
          <h3 className="text-sm font-semibold">Distribusi Win/Loss</h3>
          <div className="mt-3 h-52 w-full">
            <ResponsiveContainer>
              <BarChart data={dist} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <XAxis dataKey="bucket" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 }} />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {dist.map((d, i) => (
                    <Cell key={i} fill={d.bucket.startsWith("<") || d.bucket.startsWith("-") ? "var(--danger)" : "var(--success)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
