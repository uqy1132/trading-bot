import { useEffect, useState, useCallback } from "react";
import { formatIDR, formatUSDT, formatPct } from "@/lib/format";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { Activity, Wallet, Gauge, ShieldCheck, Menu, RefreshCw, Loader2 } from "lucide-react";
import { api, type MarketContextData } from "@/lib/api";
import { marketContext as mockCtx } from "@/lib/mock";

const REFRESH_MS = 30_000;

export function Header({ onMenu }: { onMenu?: () => void }) {
  const [ctx, setCtx] = useState<MarketContextData>({
    ...mockCtx,
    fearGreedLabel: "Greed",
    fundingSignal: "NETRAL",
    warnings: [],
    btcRsi: 55,
  });
  const [loading, setLoading] = useState(false);
  const [live, setLive] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchCtx = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.marketContext();
      setCtx(data);
      setLive(true);
      setLastUpdate(new Date());
    } catch {
      // tetap pakai data sebelumnya
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCtx();
    const timer = setInterval(fetchCtx, REFRESH_MS);
    return () => clearInterval(timer);
  }, [fetchCtx]);

  const fgTone =
    ctx.fearGreed >= 75 ? "text-danger" :
    ctx.fearGreed >= 55 ? "text-success" :
    ctx.fearGreed >= 40 ? "text-warning" : "text-danger";

  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
      <div className="flex items-center gap-3 px-4 py-3 lg:px-6">
        <button onClick={onMenu} className="rounded-md border p-2 lg:hidden" aria-label="Menu">
          <Menu className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <span className="text-sm font-semibold hidden sm:block">Trading Bot</span>
        </div>

        <div className="ml-2 hidden items-center gap-2 md:flex flex-wrap">
          {/* BTC */}
          <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5">
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">BTC</span>
            <span className="font-mono text-sm">{formatUSDT(ctx.btcPrice)}</span>
            <span className={`font-mono text-xs ${ctx.btcChange >= 0 ? "text-success" : "text-danger"}`}>
              {formatPct(ctx.btcChange)}
            </span>
            <SignalBadge signal={ctx.trend} size="sm" />
          </div>
          {/* Fear & Greed */}
          <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5">
            <Gauge className={`h-3.5 w-3.5 ${fgTone}`} />
            <span className="text-xs text-muted-foreground">F&G</span>
            <span className={`font-mono text-sm ${fgTone}`}>{ctx.fearGreed}</span>
            <span className={`text-xs ${fgTone}`}>{ctx.fearGreedLabel}</span>
          </div>
          {/* Funding */}
          <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5">
            <span className="text-xs text-muted-foreground">Funding</span>
            <span className="font-mono text-sm">{formatPct(ctx.fundingRate)}</span>
            <span className="text-xs text-muted-foreground">{ctx.fundingSignal}</span>
          </div>
          {/* Status */}
          <div className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 ${ctx.bolehTrading ? "border-success/40 bg-success/10 text-success" : "border-danger/40 bg-danger/10 text-danger"}`}>
            <ShieldCheck className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">{ctx.bolehTrading ? "Boleh Trading" : "Stop Trading"}</span>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Live indicator */}
          <button
            onClick={fetchCtx}
            disabled={loading}
            title={live ? `Live · diperbarui ${lastUpdate?.toLocaleTimeString("id-ID")}` : "Klik refresh"}
            className="flex items-center gap-1.5 rounded-md border bg-card px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground transition"
          >
            {loading
              ? <Loader2 className="h-3 w-3 animate-spin" />
              : <RefreshCw className={`h-3 w-3 ${live ? "text-success" : ""}`} />}
            <span className={`hidden sm:block ${live ? "text-success" : ""}`}>{live ? "Live" : "Offline"}</span>
          </button>
          {/* Modal */}
          <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5">
            <Wallet className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground hidden sm:block">Modal</span>
            <span className="font-mono text-sm font-semibold">{formatIDR(ctx.modal)}</span>
          </div>
        </div>
      </div>

      {/* Warning bar */}
      {ctx.warnings && ctx.warnings.length > 0 && (
        <div className="border-t border-warning/30 bg-warning/5 px-4 py-1.5 text-xs text-warning">
          ⚠️ {ctx.warnings.join("  ·  ")}
        </div>
      )}
    </header>
  );
}
