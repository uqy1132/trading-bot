import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { TIMEFRAMES } from "@/lib/mock";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { Button } from "@/components/ui/button";
import { Loader2, TrendingUp } from "lucide-react";
import { api, type MomentumData } from "@/lib/api";
import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/momentum")({
  component: MomentumPage,
});

function MomentumPage() {
  const [tf, setTf] = useState(TIMEFRAMES[1]);
  const [data, setData] = useState<MomentumData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.momentum(tf);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal ambil data momentum");
    } finally {
      setLoading(false);
    }
  }, [tf]);

  const maxMomentum = data
    ? Math.max(...data.ranking.map((r) => Math.abs(r.momentum)), 1)
    : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Momentum Ranking</h1>
        <p className="text-sm text-muted-foreground">
          Ranking kekuatan momentum semua aset watchlist. Momentum tinggi = tren kuat, bagus untuk trend-following.
        </p>
      </div>

      {/* Control */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</span>
          <select
            value={tf}
            onChange={(e) => setTf(e.target.value)}
            className="h-10 rounded-md border bg-card px-3 text-sm font-mono"
          >
            {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <Button onClick={handleScan} disabled={loading} className="bg-success text-success-foreground hover:bg-success/90 h-10">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TrendingUp className="mr-2 h-4 w-4" />}
          {loading ? "Menghitung..." : "Hitung Momentum"}
        </Button>
      </div>

      {/* Status */}
      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          ⚠️ {error}
        </div>
      )}
      {data && (
        <div className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
          ✅ Data live · {data.timeframe} · {data.ranking.length} aset
        </div>
      )}

      {/* Ranking */}
      {!data && !loading && (
        <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
          Klik "Hitung Momentum" untuk melihat ranking aset berdasarkan kekuatan tren.
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-lg bg-muted/50" />
          ))}
        </div>
      )}

      {data && !loading && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="grid grid-cols-[2rem_1fr_8rem_7rem_7rem] gap-0 border-b bg-muted/30 px-4 py-2 text-[10px] uppercase tracking-wider text-muted-foreground">
            <span>#</span>
            <span>Aset</span>
            <span>Momentum</span>
            <span>Sinyal</span>
            <span></span>
          </div>
          <div className="divide-y">
            {data.ranking.map((item, i) => {
              const barPct = Math.abs(item.momentum) / maxMomentum * 100;
              const isPositive = item.momentum >= 0;
              const sinyal = item.signal || item.sinyal || "HOLD";
              return (
                <div
                  key={item.symbol}
                  className="grid grid-cols-[2rem_1fr_8rem_7rem_7rem] items-center gap-0 px-4 py-3 hover:bg-accent/30 transition"
                >
                  <span className={cn(
                    "text-sm font-mono font-semibold",
                    i === 0 ? "text-yellow-400" : i === 1 ? "text-slate-300" : i === 2 ? "text-amber-600" : "text-muted-foreground"
                  )}>
                    {i + 1}
                  </span>
                  <div>
                    <div className="font-mono text-sm font-semibold">{item.symbol}</div>
                  </div>
                  <div className="pr-4">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className={cn("font-mono font-semibold", isPositive ? "text-success" : "text-danger")}>
                        {isPositive ? "+" : ""}{item.momentum.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className={cn("h-full rounded-full", isPositive ? "bg-success" : "bg-danger")}
                        style={{ width: `${barPct}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <SignalBadge signal={sinyal} />
                  </div>
                  <div className="flex justify-end">
                    <Link to="/" search={{ symbol: item.symbol }}>
                      <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
                        Analisa →
                      </Button>
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
