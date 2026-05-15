import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { TIMEFRAMES, scanResults } from "@/lib/mock";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { Button } from "@/components/ui/button";
import { formatUSDT, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Loader2, Radio, Send, Search } from "lucide-react";
import { api, type ScanItem } from "@/lib/api";
import { Link } from "@tanstack/react-router";

export const Route = createFileRoute("/scan")({
  component: ScanPage,
});

function ScanPage() {
  const [tf, setTf] = useState(TIMEFRAMES[1]);
  const [data, setData] = useState<ScanItem[]>(scanResults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(true);
  const [discordLoading, setDiscordLoading] = useState(false);
  const [discordSent, setDiscordSent] = useState(false);

  const handleScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDiscordSent(false);
    try {
      const res = await api.scan(tf);
      setData(res.results);
      setIsMock(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal scan");
      setIsMock(true);
    } finally {
      setLoading(false);
    }
  }, [tf]);

  const handleDiscord = useCallback(async () => {
    setDiscordLoading(true);
    try {
      await api.discordScan(data, tf);
      setDiscordSent(true);
    } catch {
      /* ignore */
    } finally {
      setDiscordLoading(false);
    }
  }, [data, tf]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Scan Aset</h1>
        <p className="text-sm text-muted-foreground">Scan semua aset watchlist sekaligus berdasarkan timeframe.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</span>
          <select value={tf} onChange={(e) => setTf(e.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-mono">
            {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <Button onClick={handleScan} disabled={loading} className="bg-success text-success-foreground hover:bg-success/90 h-10">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Radio className="mr-2 h-4 w-4" />}
          {loading ? "Scanning..." : "Scan Semua"}
        </Button>
        <Button
          onClick={handleDiscord}
          disabled={discordLoading || discordSent || isMock}
          variant="outline"
          className="h-10"
        >
          {discordLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
          {discordSent ? "✅ Terkirim" : "Kirim Discord"}
        </Button>
      </div>

      {/* Status */}
      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          ⚠️ Gagal scan dari API: {error}. Menampilkan data lama.
        </div>
      )}
      {!isMock && (
        <div className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
          ✅ Data live · {tf} · {data.length} aset
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-44 animate-pulse rounded-lg bg-muted/50" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((r) => (
            <div key={r.symbol} className={cn(
              "rounded-lg border bg-card p-4 transition",
              r.layak ? "hover:border-success/40 border-success/20" : "hover:border-muted-foreground/20",
            )}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="font-mono text-sm font-semibold">{r.symbol}</div>
                  {r.mom_grade && (
                    <span className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide",
                      r.mom_grade === "HOT"     ? "bg-orange-500/15 text-orange-400" :
                      r.mom_grade === "WARM"    ? "bg-success/15 text-success" :
                      r.mom_grade === "BEARISH" ? "bg-danger/15 text-danger" :
                      "bg-muted text-muted-foreground"
                    )}>
                      {r.mom_grade === "HOT" ? "🔥" : r.mom_grade === "WARM" ? "📈" : r.mom_grade === "BEARISH" ? "📉" : "➡️"} {r.mom_grade}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <SignalBadge signal={r.signal} size="lg" />
                  <Link to="/" search={{ symbol: r.symbol }}>
                    <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
                      <Search className="mr-1 h-3 w-3" />Analisa
                    </Button>
                  </Link>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                <div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>RSI</span>
                    <span className={`font-mono ${r.rsi > 70 ? "text-danger" : r.rsi < 30 ? "text-success" : "text-foreground"}`}>{r.rsi.toFixed(0)}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className={`h-full ${r.rsi > 70 ? "bg-danger" : r.rsi < 30 ? "bg-success" : "bg-warning"}`} style={{ width: `${r.rsi}%` }} />
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">ADX</span>
                  <span className="font-mono">{r.adx.toFixed(0)} {r.adx > 25 ? "· strong" : "· weak"}</span>
                </div>
                <div className="flex items-center justify-between border-t pt-2">
                  <span className="text-xs text-muted-foreground">Harga</span>
                  <div className="text-right">
                    <div className="font-mono text-sm">{formatUSDT(r.price)}</div>
                    {r.change !== undefined && (
                      <div className={`text-xs font-mono ${r.change >= 0 ? "text-success" : "text-danger"}`}>
                        {formatPct(r.change)}
                      </div>
                    )}
                  </div>
                </div>
                {r.roc_20 !== undefined && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">ROC 20 bar</span>
                    <span className={cn("font-mono", r.roc_20 >= 0 ? "text-success" : "text-danger")}>
                      {r.roc_20 >= 0 ? "+" : ""}{r.roc_20.toFixed(1)}%
                    </span>
                  </div>
                )}
                {(r.grade || r.skor !== undefined) && (
                  <div className="flex items-center justify-between border-t pt-2">
                    <span className="text-xs text-muted-foreground">Skor Setup</span>
                    <div className="flex items-center gap-1.5">
                      {r.grade && (
                        <span className={cn(
                          "rounded border px-1.5 py-0.5 font-mono text-[11px] font-semibold",
                          r.grade.startsWith("A") ? "border-success/40 bg-success/10 text-success" :
                          r.grade === "B" ? "border-warning/40 bg-warning/10 text-warning" :
                          "border-danger/40 bg-danger/10 text-danger"
                        )}>
                          {r.grade}
                        </span>
                      )}
                      {r.skor !== undefined && r.skor_max !== undefined && (
                        <span className="font-mono text-xs text-muted-foreground">{r.skor}/{r.skor_max}</span>
                      )}
                      {r.layak === false && (
                        <span className="text-[10px] text-danger">✗ Tidak layak</span>
                      )}
                      {r.layak === true && (
                        <span className="text-[10px] text-success">✓ Layak</span>
                      )}
                    </div>
                  </div>
                )}
                {r.error && (
                  <div className="text-[10px] text-danger">⚠️ {r.error}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
