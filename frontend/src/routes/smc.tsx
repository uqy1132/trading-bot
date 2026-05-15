import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { api, type SmcScanItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Loader2, Search, TrendingUp, TrendingDown, Target } from "lucide-react";

export const Route = createFileRoute("/smc")({
  component: SmcPage,
});

const TF_OPTIONS = ["15M", "30M", "1H"];
const CHANGE_OPTIONS = [3, 5, 8, 10];

function QualityBadge({ quality }: { quality: SmcScanItem["entry_quality"] }) {
  return (
    <span className={cn(
      "rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wide",
      quality === "OPTIMAL" ? "bg-green-500/20 text-green-400 ring-1 ring-green-500/40" :
      quality === "VALID"   ? "bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/40" :
                              "bg-muted text-muted-foreground"
    )}>
      {quality === "OPTIMAL" ? "OTE" : quality}
    </span>
  );
}

function SmcCard({ item }: { item: SmcScanItem }) {
  const ob = item.nearest_bull_ob;

  // Kalkulasi SL dan TP 1:3 (Kevin Sailly)
  const entry  = ob ? ob.midpoint : item.price;
  const sl     = ob ? ob.ob_low   : item.price;
  const risk   = entry - sl;
  const tp     = entry + risk * 3;

  const isGainer = item.kategori === "GAINER";

  return (
    <div className={cn(
      "rounded-xl border bg-card p-4 flex flex-col gap-3 transition-all hover:border-primary/40",
      item.entry_quality === "OPTIMAL" && "border-green-500/30",
      item.entry_quality === "VALID"   && "border-blue-500/20",
    )}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm">{item.symbol.replace("/USDT", "")}</span>
          <QualityBadge quality={item.entry_quality} />
          <span className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-semibold",
            isGainer ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"
          )}>
            {isGainer ? <TrendingUp className="inline w-3 h-3 mr-0.5" /> : <TrendingDown className="inline w-3 h-3 mr-0.5" />}
            {item.change_24h > 0 ? "+" : ""}{item.change_24h}%
          </span>
        </div>
        <span className="text-xs text-muted-foreground font-mono">
          ${item.price < 1 ? item.price.toFixed(5) : item.price.toFixed(2)}
        </span>
      </div>

      {/* OB Zone */}
      {ob && (
        <div className="rounded-lg bg-muted/40 p-2.5 text-xs space-y-1">
          <div className="flex justify-between text-muted-foreground mb-1">
            <span className="font-semibold text-foreground">Bullish OB Zone</span>
            <span className="text-green-400">{item.dist_bull_ob.toFixed(1)}% jauh</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">OB High</span>
            <span className="font-mono">{ob.ob_high < 1 ? ob.ob_high.toFixed(5) : ob.ob_high.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-green-400">
            <span>OTE Zone</span>
            <span className="font-mono">
              {ob.ote_low < 1 ? ob.ote_low.toFixed(5) : ob.ote_low.toFixed(2)} –{" "}
              {ob.ote_high < 1 ? ob.ote_high.toFixed(5) : ob.ote_high.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">OB Low (SL)</span>
            <span className="font-mono text-red-400">{ob.ob_low < 1 ? ob.ob_low.toFixed(5) : ob.ob_low.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* TP/SL 1:3 */}
      {ob && (
        <div className="rounded-lg bg-primary/5 border border-primary/10 p-2.5 text-xs space-y-1">
          <div className="flex items-center gap-1 text-primary font-semibold mb-1">
            <Target className="w-3 h-3" /> Plan 1:3 (Kevin Sailly)
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Entry (midpoint OB)</span>
            <span className="font-mono">{entry < 1 ? entry.toFixed(5) : entry.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-red-400">Stop Loss</span>
            <span className="font-mono text-red-400">{sl < 1 ? sl.toFixed(5) : sl.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-green-400">Take Profit (3R)</span>
            <span className="font-mono text-green-400">{tp < 1 ? tp.toFixed(5) : tp.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* Konfirmasi */}
      <div className="flex gap-1.5 flex-wrap">
        <span className={cn("rounded px-1.5 py-0.5 text-[10px]",
          item.rsi < 35 ? "bg-green-500/15 text-green-400" :
          item.rsi > 70 ? "bg-red-500/15 text-red-400" :
          "bg-muted text-muted-foreground"
        )}>
          RSI {item.rsi}
        </span>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px]",
          item.ema_bull ? "bg-green-500/15 text-green-400" : "bg-muted text-muted-foreground"
        )}>
          EMA {item.ema_bull ? "Bullish" : "Bearish"}
        </span>
        {item.fvg_count > 0 && (
          <span className="rounded px-1.5 py-0.5 text-[10px] bg-purple-500/15 text-purple-400">
            {item.fvg_count} FVG
          </span>
        )}
        {item.liquidity_above && (
          <span className="rounded px-1.5 py-0.5 text-[10px] bg-yellow-500/15 text-yellow-400">
            Liq {item.liquidity_above.level < 1
              ? item.liquidity_above.level.toFixed(5)
              : item.liquidity_above.level.toFixed(2)}
          </span>
        )}
        {item.vol_spike && (
          <span className="rounded px-1.5 py-0.5 text-[10px] bg-orange-500/15 text-orange-400">
            Vol Spike
          </span>
        )}
      </div>

      {/* Score bar */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground">Konfirmasi</span>
        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all",
              item.conf_score >= 4 ? "bg-green-500" :
              item.conf_score >= 3 ? "bg-blue-500" :
              item.conf_score >= 2 ? "bg-yellow-500" : "bg-muted-foreground"
            )}
            style={{ width: `${(item.conf_score / 5) * 100}%` }}
          />
        </div>
        <span className="text-[10px] font-mono text-muted-foreground">{item.conf_score}/5</span>
      </div>
    </div>
  );
}

function SmcPage() {
  const [tf, setTf] = useState("15M");
  const [minChange, setMinChange] = useState(3);
  const [data, setData] = useState<SmcScanItem[]>([]);
  const [meta, setMeta] = useState<{ total_scan: number; setup_found: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.smcScan(tf, minChange);
      setData(res.results);
      setMeta({ total_scan: res.total_scan, setup_found: res.setup_found });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal scan");
    } finally {
      setLoading(false);
    }
  }, [tf, minChange]);

  const optimal = data.filter(d => d.entry_quality === "OPTIMAL");
  const valid   = data.filter(d => d.entry_quality === "VALID");
  const wait    = data.filter(d => d.entry_quality === "WAIT");

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold">SMC Scan</h1>
        <p className="text-sm text-muted-foreground">
          Scan gainers &amp; losers — filter setup Order Block / OTE (Kevin Sailly style)
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex gap-1">
          {TF_OPTIONS.map(t => (
            <Button key={t} size="sm" variant={tf === t ? "default" : "outline"}
              onClick={() => setTf(t)} className="text-xs px-3">
              {t}
            </Button>
          ))}
        </div>
        <div className="flex gap-1">
          {CHANGE_OPTIONS.map(c => (
            <Button key={c} size="sm" variant={minChange === c ? "default" : "outline"}
              onClick={() => setMinChange(c)} className="text-xs px-3">
              ±{c}%
            </Button>
          ))}
        </div>
        <Button onClick={handleScan} disabled={loading} className="gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          {loading ? "Scanning..." : "Scan Sekarang"}
        </Button>
      </div>

      {/* Meta info */}
      {meta && (
        <div className="text-xs text-muted-foreground flex gap-3">
          <span>Scan: <b className="text-foreground">{meta.total_scan}</b> pair</span>
          <span>Setup ditemukan: <b className="text-foreground">{meta.setup_found}</b></span>
          <span>OTE: <b className="text-green-400">{optimal.length}</b></span>
          <span>Valid: <b className="text-blue-400">{valid.length}</b></span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {data.length === 0 && !loading && !error && (
        <div className="text-center py-16 text-muted-foreground text-sm">
          Tekan "Scan Sekarang" untuk mencari setup SMC dari gainers & losers OKX
        </div>
      )}

      {/* OTE setups */}
      {optimal.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-green-400">OTE — Optimal Trade Entry ({optimal.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {optimal.map(item => <SmcCard key={item.symbol} item={item} />)}
          </div>
        </div>
      )}

      {/* Valid setups */}
      {valid.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-blue-400">Valid — Di dalam OB ({valid.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {valid.map(item => <SmcCard key={item.symbol} item={item} />)}
          </div>
        </div>
      )}

      {/* Wait */}
      {wait.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-muted-foreground">Wait — Dekat OB ({wait.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {wait.map(item => <SmcCard key={item.symbol} item={item} />)}
          </div>
        </div>
      )}
    </div>
  );
}
