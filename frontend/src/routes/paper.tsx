import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatIDR, formatPct, formatUSDT } from "@/lib/format";
import { api, type PaperData, type PaperTrade } from "@/lib/api";
import {
  CheckCircle2, XCircle, Loader2, RefreshCw, RotateCcw,
  TrendingUp, TrendingDown, Minus,
} from "lucide-react";

export const Route = createFileRoute("/paper")({
  component: PaperPage,
});

function PaperPage() {
  const [data, setData]       = useState<PaperData | null>(null);
  const [loading, setLoading] = useState(true);
  const [resetLoading, setResetLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.paperStats();
      setData(res);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleReset = useCallback(async () => {
    if (!confirm("Reset paper trading? Semua histori akan dihapus.")) return;
    setResetLoading(true);
    try { await api.resetPaper(); await fetch(); }
    catch { /* ignore */ }
    finally { setResetLoading(false); }
  }, [fetch]);

  const handleTutup = useCallback(async (id: number, harga: number, hasil: string) => {
    await api.tutupPaper(id, { harga_keluar: harga, hasil });
    fetch();
  }, [fetch]);

  if (loading) return (
    <div className="flex h-64 items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );

  const stats  = data?.stats;
  const config = data?.config;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Paper Trading</h1>
          <p className="text-sm text-muted-foreground">
            Simulasi tanpa uang sungguhan — uji strategi sebelum live.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetch} disabled={loading}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleReset} disabled={resetLoading}>
            {resetLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            <span className="ml-1.5">Reset</span>
          </Button>
        </div>
      </div>

      {stats && (
        <>
          {/* Ringkasan Modal */}
          <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
            <StatCard label="Modal Simulasi" value={formatIDR(config?.modal_sim)} />
            <StatCard label="Total PnL" value={formatIDR(stats.total_pnl_idr)}
              tone={stats.total_pnl_idr >= 0 ? "success" : "danger"} />
            <StatCard label="Return" value={formatPct(stats.total_pnl_pct)}
              tone={stats.total_pnl_pct >= 0 ? "success" : "danger"} />
            <StatCard label="Hari Berjalan"
              value={`${stats.hari_berjalan} hari`}
              sub={`${stats.hari_sisa} hari tersisa`} />
          </div>

          {/* Metrik */}
          <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
            <StatCard label="Win Rate" value={`${stats.win_rate}%`}
              tone={stats.win_rate >= 55 ? "success" : "warning"} />
            <StatCard label="Profit Factor" value={stats.profit_factor.toFixed(2)}
              tone={stats.profit_factor >= 1.3 ? "success" : "danger"} />
            <StatCard label="Max Drawdown" value={`${stats.max_drawdown.toFixed(1)}%`}
              tone={stats.max_drawdown < 15 ? "success" : "danger"} />
            <StatCard label="Sharpe Ratio" value={stats.sharpe.toFixed(2)}
              tone={stats.sharpe >= 1 ? "success" : "warning"} />
          </div>

          {/* Kriteria Lulus */}
          <div className="rounded-lg border bg-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">Kriteria Evaluasi</h3>
              <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full",
                stats.lulus ? "bg-success/15 text-success" : "bg-warning/15 text-warning")}>
                {stats.lulus ? "✅ LULUS" : "⏳ Belum Lulus"}
              </span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(stats.kriteria ?? {}).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-sm">
                  {v ? <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
                     : <XCircle className="h-4 w-4 text-danger shrink-0" />}
                  <span className={v ? "text-foreground" : "text-muted-foreground"}>{k}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Open Trades */}
          {(data?.open?.length ?? 0) > 0 && (
            <div className="rounded-lg border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b">
                <h3 className="text-sm font-semibold">Open Trades ({data!.open.length})</h3>
              </div>
              <div className="divide-y">
                {data!.open.map(t => (
                  <PaperTradeRow key={t.id} trade={t} onClose={handleTutup} />
                ))}
              </div>
            </div>
          )}

          {/* Closed Trades */}
          {(data?.closed?.length ?? 0) > 0 && (
            <div className="rounded-lg border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b flex items-center justify-between">
                <h3 className="text-sm font-semibold">Closed Trades</h3>
                <span className="text-xs text-muted-foreground">{stats.win}W / {stats.loss}L dari {stats.total} trade</span>
              </div>
              <div className="divide-y">
                {[...data!.closed].reverse().map(t => (
                  <PaperTradeRow key={t.id} trade={t} />
                ))}
              </div>
            </div>
          )}

          {stats.total === 0 && (data?.open?.length ?? 0) === 0 && (
            <div className="rounded-lg border bg-card p-10 text-center text-sm text-muted-foreground">
              Belum ada trade. Paper trade bisa ditambah dari halaman Analisa & Sinyal.
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PaperTradeRow({
  trade,
  onClose,
}: {
  trade: PaperTrade;
  onClose?: (id: number, harga: number, hasil: string) => void;
}) {
  const [hargaKeluar, setHargaKeluar] = useState("");
  const [closing, setClosing] = useState(false);

  const isOpen  = trade.status === "OPEN";
  const isWin   = trade.hasil === "WIN";
  const isLoss  = trade.hasil === "LOSS";
  const isBuy   = trade.aksi === "BUY" || trade.aksi === "LONG";

  const pnlPct  = trade.pnl_pct_modal;
  const PnlIcon = pnlPct == null ? Minus : pnlPct >= 0 ? TrendingUp : TrendingDown;

  const doClose = useCallback(async (hasil: string) => {
    const h = parseFloat(hargaKeluar);
    if (!h || !onClose) return;
    setClosing(true);
    try { await onClose(trade.id, h, hasil); }
    finally { setClosing(false); }
  }, [hargaKeluar, onClose, trade.id]);

  return (
    <div className="px-5 py-3 flex flex-wrap gap-4 items-center text-sm">
      <div className="flex items-center gap-2 min-w-28">
        <span className={cn("text-xs font-semibold px-1.5 py-0.5 rounded",
          isBuy ? "bg-success/15 text-success" : "bg-danger/15 text-danger")}>
          {trade.aksi}
        </span>
        <span className="font-mono font-medium">{trade.symbol}</span>
      </div>

      <div className="flex gap-4 text-muted-foreground text-xs flex-1 flex-wrap">
        <span>Entry <span className="text-foreground font-mono">{trade.entry}</span></span>
        <span>SL <span className="font-mono text-danger">{trade.stop_loss}</span></span>
        <span>TP1 <span className="font-mono text-success">{trade.target_1}</span></span>
        {!isOpen && trade.harga_keluar && (
          <span>Exit <span className="font-mono">{trade.harga_keluar}</span></span>
        )}
      </div>

      {isOpen ? (
        <div className="flex items-center gap-2 ml-auto">
          <input
            type="number"
            placeholder="Harga keluar"
            value={hargaKeluar}
            onChange={e => setHargaKeluar(e.target.value)}
            className="w-32 rounded border bg-background px-2 py-1 text-xs font-mono"
          />
          <Button size="sm" variant="outline" className="text-success border-success/30"
            onClick={() => doClose("WIN")} disabled={closing || !hargaKeluar}>
            WIN
          </Button>
          <Button size="sm" variant="outline" className="text-danger border-danger/30"
            onClick={() => doClose("LOSS")} disabled={closing || !hargaKeluar}>
            LOSS
          </Button>
        </div>
      ) : (
        <div className={cn("ml-auto flex items-center gap-1.5 text-xs font-medium",
          isWin ? "text-success" : isLoss ? "text-danger" : "text-muted-foreground")}>
          <PnlIcon className="h-3.5 w-3.5" />
          {pnlPct != null ? formatPct(pnlPct) : "-"}
          <span className="text-muted-foreground ml-1">({formatIDR(trade.pnl_idr)})</span>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, tone }: {
  label: string; value: string; sub?: string;
  tone?: "success" | "warning" | "danger";
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("text-lg font-semibold mt-1",
        tone === "success" && "text-success",
        tone === "warning" && "text-warning",
        tone === "danger"  && "text-danger",
      )}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}
