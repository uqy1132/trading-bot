import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw, TrendingUp, TrendingDown } from "lucide-react";
import { api, type VirtualPosition } from "@/lib/api";
import { formatUSDT } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/virtual")({
  component: VirtualPage,
});

function VirtualPage() {
  const [open, setOpen]         = useState<VirtualPosition[]>([]);
  const [closed, setClosed]     = useState<VirtualPosition[]>([]);
  const [ringkasan, setRingkasan] = useState<Record<string, number>>({});
  const [liveMode, setLiveMode] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [updLoading, setUpdLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.virtualPositions();
      setOpen(res.open);
      setClosed(res.closed);
      setRingkasan(res.ringkasan);
      setLiveMode(res.live_mode);
      setLastUpdate(new Date().toLocaleTimeString("id-ID"));
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  const handleUpdate = useCallback(async () => {
    setUpdLoading(true);
    try {
      const res = await api.updateVirtual();
      if (res.closed_count > 0) await fetchData();
      else setLastUpdate(new Date().toLocaleTimeString("id-ID"));
    } catch { /* ignore */ }
    finally { setUpdLoading(false); }
  }, [fetchData]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const totalPnl = closed.reduce((s, p) => s + (p.pnl_usdt ?? 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Virtual & Live Positions</h1>
          <p className="text-sm text-muted-foreground">
            Posisi dari eksekusi virtual/live. Auto-close saat TP/SL hit via scheduler.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0 mt-1">
          <span className={cn(
            "rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
            liveMode ? "border-orange-500/60 bg-orange-500/10 text-orange-400"
                     : "border-muted-foreground/30 bg-muted/30 text-muted-foreground"
          )}>
            {liveMode ? "⚡ LIVE" : "Virtual"}
          </span>
          <Button variant="outline" size="sm" onClick={handleUpdate} disabled={updLoading}>
            {updLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            <span className="ml-1.5 text-xs">Cek TP/SL</span>
          </Button>
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {/* Ringkasan */}
      {Object.keys(ringkasan).length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total Trade" value={String(ringkasan.total ?? 0)} />
          <StatCard label="Open" value={String(ringkasan.open ?? 0)} tone="warning" />
          <StatCard label="Win Rate"
            value={ringkasan.total ? `${((ringkasan.win ?? 0) / ringkasan.total * 100).toFixed(0)}%` : "—"}
            tone="success" />
          <StatCard label="Total PnL"
            value={`${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)} USDT`}
            tone={totalPnl >= 0 ? "success" : "danger"} />
        </div>
      )}

      {/* Posisi OPEN */}
      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b bg-muted/20">
          <h3 className="text-sm font-semibold">Posisi Open ({open.length})</h3>
        </div>
        {open.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted-foreground text-center">
            Tidak ada posisi open.
          </p>
        ) : (
          <div className="divide-y">
            {open.map((p) => (
              <PosisiRow key={p.order_id} pos={p} />
            ))}
          </div>
        )}
      </div>

      {/* Posisi CLOSED */}
      {closed.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b bg-muted/20">
            <h3 className="text-sm font-semibold">Riwayat Closed (20 terakhir)</h3>
            <span className={cn(
              "font-mono text-sm font-semibold",
              totalPnl >= 0 ? "text-success" : "text-danger"
            )}>
              Total: {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} USDT
            </span>
          </div>
          <div className="divide-y">
            {[...closed].reverse().map((p) => (
              <PosisiRow key={p.order_id} pos={p} showResult />
            ))}
          </div>
        </div>
      )}

      {lastUpdate && (
        <p className="text-[11px] text-muted-foreground text-right">
          Terakhir diperbarui: {lastUpdate}
        </p>
      )}
    </div>
  );
}

function PosisiRow({ pos, showResult }: { pos: VirtualPosition; showResult?: boolean }) {
  const isLong = pos.aksi in { BUY: 1, LONG: 1 };
  const pnl    = pos.pnl_usdt ?? 0;
  const modeColor = pos.mode === "LIVE"
    ? "border-orange-500/40 bg-orange-500/10 text-orange-400"
    : "border-muted-foreground/30 bg-muted/20 text-muted-foreground";

  return (
    <div className="grid grid-cols-[1fr_1fr_1fr_1fr] items-center gap-2 px-5 py-3 text-sm hover:bg-accent/20 transition">
      <div>
        <div className="font-mono font-semibold">{pos.symbol.split("/")[0]}/USDT</div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={cn(
            "inline-flex items-center gap-0.5 text-[11px] font-semibold",
            isLong ? "text-success" : "text-danger"
          )}>
            {isLong ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {pos.aksi} · {pos.leverage}x
          </span>
          <span className={cn("rounded border px-1 py-0.5 text-[10px]", modeColor)}>
            {pos.mode}
          </span>
        </div>
        <div className="text-[10px] text-muted-foreground mt-0.5">{pos.waktu}</div>
      </div>
      <div>
        <div className="text-[10px] text-muted-foreground">Fill / Entry</div>
        <div className="font-mono">{formatUSDT(pos.fill_price)}</div>
      </div>
      <div>
        <div className="text-[10px] text-muted-foreground">SL · TP</div>
        <div className="font-mono text-danger text-xs">{formatUSDT(pos.stop_loss)}</div>
        <div className="font-mono text-success text-xs">{formatUSDT(pos.take_profit)}</div>
      </div>
      <div className="text-right">
        {showResult ? (
          <>
            <div className={cn(
              "font-mono font-semibold",
              pnl >= 0 ? "text-success" : "text-danger"
            )}>
              {pnl >= 0 ? "+" : ""}{pnl.toFixed(4)} USDT
            </div>
            <div className={cn(
              "text-xs font-semibold mt-0.5",
              (pos as any).hasil === "WIN" ? "text-success" : "text-danger"
            )}>
              {(pos as any).hasil ?? "—"}
            </div>
          </>
        ) : (
          <div className="text-xs text-muted-foreground">Open</div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, tone }: {
  label: string; value: string; tone?: "success" | "warning" | "danger";
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn(
        "mt-1.5 font-mono text-xl font-bold",
        tone === "success" && "text-success",
        tone === "warning" && "text-warning",
        tone === "danger" && "text-danger",
        !tone && "text-foreground",
      )}>{value}</div>
    </div>
  );
}
