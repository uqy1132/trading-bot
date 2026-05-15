import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { SYMBOLS, TIMEFRAMES, equityCurve as mockCurve } from "@/lib/mock";
import { Button } from "@/components/ui/button";
import { EquityChart } from "@/components/charts/EquityChart";
import { Play, Loader2, Check, X as XIcon } from "lucide-react";
import { StatCard } from "@/components/trading/StatCard";
import { formatPct, formatUSDT, formatIDR } from "@/lib/format";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { api, type BacktestData } from "@/lib/api";

export const Route = createFileRoute("/backtest")({
  component: BacktestPage,
});

function BacktestPage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [tf, setTf] = useState("4H");
  const [months, setMonths] = useState(6);
  const [result, setResult] = useState<BacktestData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const candles = months * 30 * (tf === "1H" ? 24 : tf === "4H" ? 6 : 1);

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest({ symbol, timeframe: tf, limit: candles });
      if (res.error) {
        setError(res.error);
      } else {
        setResult(res);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menjalankan backtest");
    } finally {
      setLoading(false);
    }
  }, [symbol, tf, candles]);

  const sel = "h-10 rounded-md border bg-card px-3 text-sm font-mono";

  const equityForChart = result?.equity && result.equity.length > 0
    ? result.equity
    : mockCurve;

  const checks = result ? [
    { label: "Win rate ≥ 50%", ok: result.winRate >= 50 },
    { label: "Profit factor ≥ 1.5", ok: result.profitFactor >= 1.5 },
    { label: `Max drawdown ≤ 15% (${Math.abs(result.maxDrawdown).toFixed(1)}%)`, ok: Math.abs(result.maxDrawdown) <= 15 },
    { label: `Total trade ≥ 30 (${result.totalTrade})`, ok: result.totalTrade >= 30 },
  ] : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Backtest</h1>
        <p className="text-sm text-muted-foreground">Uji strategi terhadap data historis.</p>
      </div>

      <div className="grid gap-3 rounded-lg border bg-card p-4 md:grid-cols-4">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Aset</span>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={sel}>
            {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</span>
          <select value={tf} onChange={(e) => setTf(e.target.value)} className={sel}>
            {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Periode: {months} bulan · ~{candles.toLocaleString()} candle
          </span>
          <input type="range" min={3} max={24} value={months} onChange={(e) => setMonths(+e.target.value)} className="accent-success mt-3" />
        </label>
        <div className="flex items-end">
          <Button onClick={handleRun} disabled={loading} className="w-full bg-success text-success-foreground hover:bg-success/90 h-10">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            {loading ? "Menjalankan..." : "Jalankan Backtest"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          ⚠️ {error}
        </div>
      )}

      {loading && <div className="h-32 animate-pulse rounded-lg bg-muted/50" />}

      {result && !loading && (
        <>
          <div className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
            ✅ Backtest selesai · {result.symbol} · {result.timeframe} · Return: {formatPct(result.returnTotal)}
          </div>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Total Trade" value={result.totalTrade} />
            <StatCard label="Win Rate" value={`${result.winRate.toFixed(1)}%`} tone={result.winRate >= 50 ? "success" : "danger"} />
            <StatCard label="Profit Factor" value={result.profitFactor.toFixed(2)} tone={result.profitFactor >= 1.5 ? "success" : "danger"} />
            <StatCard label="Max DD" value={`${result.maxDrawdown.toFixed(1)}%`} tone="danger" />
            <StatCard label="Return Total" value={formatPct(result.returnTotal)} tone={result.returnTotal >= 0 ? "success" : "danger"} />
            <StatCard label="Sharpe Ratio" value={result.sharpe?.toFixed(2) ?? "—"} tone={result.sharpe >= 1 ? "success" : "warning"} />
            <StatCard label="Modal Awal" value={formatIDR(result.modalAwal)} />
            <StatCard label="Modal Akhir" value={formatIDR(result.modalAkhir)} tone={result.modalAkhir >= result.modalAwal ? "success" : "danger"} />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border bg-card p-5 lg:col-span-2">
              <h3 className="text-sm font-semibold">Equity Curve</h3>
              <div className="mt-3"><EquityChart data={equityForChart} /></div>
            </div>
            <div className="rounded-lg border bg-card p-5">
              <h3 className="text-sm font-semibold">Kriteria Strategi</h3>
              <ul className="mt-4 space-y-2 text-sm">
                {checks.map((c) => (
                  <li key={c.label} className="flex items-center gap-2">
                    {c.ok ? <Check className="h-4 w-4 text-success shrink-0" /> : <XIcon className="h-4 w-4 text-danger shrink-0" />}
                    <span className={c.ok ? "text-foreground" : "text-muted-foreground line-through"}>{c.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {result.trades && result.trades.length > 0 && (
            <div className="overflow-x-auto rounded-lg border bg-card">
              <div className="flex items-center justify-between px-4 py-3 border-b">
                <h3 className="text-sm font-semibold">Trade List</h3>
                <span className="text-xs text-muted-foreground">{result.trades.length} trade (maks 50)</span>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-background/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>{["#", "Tanggal", "Aset", "Aksi", "Entry", "Keluar", "PnL%"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i} className="border-t">
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">#{i + 1}</td>
                      <td className="px-4 py-2 text-xs">{String(t.tanggal_entry ?? "").slice(0, 10)}</td>
                      <td className="px-4 py-2 font-mono">{t.symbol}</td>
                      <td className="px-4 py-2"><SignalBadge signal={t.aksi ?? "BUY"} size="sm" /></td>
                      <td className="px-4 py-2 font-mono">{formatUSDT(t.entry ?? 0)}</td>
                      <td className="px-4 py-2 font-mono">{formatUSDT(t.exit ?? 0)}</td>
                      <td className={`px-4 py-2 font-mono ${(t.pnl ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                        {formatPct(t.pnl ?? 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!result && !loading && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <Play className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Pilih aset, timeframe, dan periode lalu klik "Jalankan Backtest"</p>
        </div>
      )}
    </div>
  );
}
