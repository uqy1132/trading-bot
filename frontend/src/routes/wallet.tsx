import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw, Wallet, TrendingUp, TrendingDown } from "lucide-react";
import { api, type WalletData, type ExchangePosition } from "@/lib/api";
import { formatUSDT } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/wallet")({
  component: WalletPage,
});

function WalletPage() {
  const [wallet, setWallet]       = useState<WalletData | null>(null);
  const [positions, setPositions] = useState<ExchangePosition[]>([]);
  const [exchange, setExchange]   = useState("");
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [w, p] = await Promise.all([api.wallet(), api.posisilExchange()]);
      setWallet(w);
      setPositions(p.positions);
      setExchange(p.exchange || w.exchange);
      setLastUpdate(new Date().toLocaleTimeString("id-ID"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal konek ke exchange");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const totalUnrealizedPnl = positions.reduce((s, p) => s + p.unrealizedPnl, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Wallet & Posisi Exchange</h1>
          <p className="text-sm text-muted-foreground">
            Saldo dan posisi terbuka langsung dari exchange via API key.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0 mt-1">
          {exchange && (
            <span className="rounded-full border border-muted-foreground/30 bg-muted/30 px-2.5 py-0.5 text-[11px] font-mono text-muted-foreground uppercase">
              {exchange}
            </span>
          )}
          {wallet && (
            <span className={cn(
              "rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
              wallet.live_mode
                ? "border-orange-500/60 bg-orange-500/10 text-orange-400"
                : "border-muted-foreground/30 bg-muted/30 text-muted-foreground"
            )}>
              {wallet.live_mode ? "⚡ LIVE" : "Virtual"}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          <p className="font-semibold">Gagal terhubung ke exchange</p>
          <p className="mt-1 text-xs opacity-80">{error}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Pastikan <code className="font-mono bg-muted px-1 rounded">OKX_API_KEY</code>,{" "}
            <code className="font-mono bg-muted px-1 rounded">OKX_SECRET</code>, dan{" "}
            <code className="font-mono bg-muted px-1 rounded">OKX_PASSPHRASE</code> (atau GATE / MEXC) sudah diisi di{" "}
            <code className="font-mono bg-muted px-1 rounded">config/.env</code>.
          </p>
        </div>
      )}

      {/* Saldo USDT */}
      {wallet && (
        <>
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-3">
            <BalanceCard
              label="Total Saldo USDT"
              value={formatUSDT(wallet.usdt_total)}
              sub="Termasuk margin terpakai"
              icon={Wallet}
              highlight
            />
            <BalanceCard
              label="USDT Tersedia"
              value={formatUSDT(wallet.usdt_free)}
              sub="Siap untuk order baru"
              tone="success"
            />
            <BalanceCard
              label="USDT Terpakai (Margin)"
              value={formatUSDT(wallet.usdt_used)}
              sub="Terkunci sebagai margin"
              tone="warning"
            />
          </div>

          {/* Coin lain */}
          {Object.keys(wallet.coins).filter(c => c !== "USDT").length > 0 && (
            <div className="rounded-lg border bg-card p-5">
              <h3 className="text-sm font-semibold mb-3">Aset Lain</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {Object.entries(wallet.coins)
                  .filter(([c]) => c !== "USDT")
                  .map(([coin, data]) => (
                    <div key={coin} className="rounded-md border bg-background p-3">
                      <div className="text-xs text-muted-foreground font-mono">{coin}</div>
                      <div className="font-mono text-sm font-semibold mt-1">{data.total.toFixed(6)}</div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        Bebas: {data.free.toFixed(6)}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Posisi Terbuka */}
      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 className="text-sm font-semibold">Posisi Terbuka di Exchange</h3>
          <div className="flex items-center gap-3">
            {positions.length > 0 && (
              <span className={cn(
                "font-mono text-sm font-semibold",
                totalUnrealizedPnl >= 0 ? "text-success" : "text-danger"
              )}>
                Unrealized PnL: {totalUnrealizedPnl >= 0 ? "+" : ""}{totalUnrealizedPnl.toFixed(2)} USDT
              </span>
            )}
            <span className="text-xs text-muted-foreground">
              {positions.length} posisi
            </span>
          </div>
        </div>

        {positions.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">
            {loading ? "Memuat posisi..." : error ? "Tidak dapat memuat posisi." : "Tidak ada posisi terbuka saat ini."}
          </div>
        ) : (
          <div className="divide-y">
            {positions.map((pos, i) => {
              const isLong = pos.side === "long";
              const pnlPositive = pos.unrealizedPnl >= 0;
              return (
                <div key={i} className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr] items-center gap-2 px-5 py-4">
                  <div>
                    <div className="font-mono text-sm font-semibold">
                      {pos.symbol.split(":")[0]}
                    </div>
                    <div className={cn(
                      "mt-0.5 inline-flex items-center gap-1 text-[11px] font-semibold",
                      isLong ? "text-success" : "text-danger"
                    )}>
                      {isLong
                        ? <TrendingUp className="h-3 w-3" />
                        : <TrendingDown className="h-3 w-3" />}
                      {isLong ? "LONG" : "SHORT"} · {pos.leverage}x
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Entry</div>
                    <div className="font-mono text-sm">{formatUSDT(pos.entryPrice)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Ukuran</div>
                    <div className="font-mono text-sm">{pos.contracts}</div>
                    <div className="text-[10px] text-muted-foreground">{formatUSDT(pos.notional)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Unrealized PnL</div>
                    <div className={cn("font-mono text-sm font-semibold", pnlPositive ? "text-success" : "text-danger")}>
                      {pnlPositive ? "+" : ""}{pos.unrealizedPnl.toFixed(2)} USDT
                    </div>
                    <div className={cn("text-[10px]", pnlPositive ? "text-success" : "text-danger")}>
                      {pnlPositive ? "+" : ""}{pos.percentage.toFixed(2)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Likuidasi</div>
                    <div className="font-mono text-sm text-danger">
                      {pos.liquidationPrice > 0 ? formatUSDT(pos.liquidationPrice) : "—"}
                    </div>
                    <div className="text-[10px] text-muted-foreground capitalize">{pos.marginMode}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {lastUpdate && (
        <p className="text-[11px] text-muted-foreground text-right">
          Terakhir diperbarui: {lastUpdate}
        </p>
      )}
    </div>
  );
}

function BalanceCard({
  label, value, sub, icon: Icon, tone, highlight,
}: {
  label: string; value: string; sub: string;
  icon?: React.ComponentType<{ className?: string }>;
  tone?: "success" | "warning" | "danger";
  highlight?: boolean;
}) {
  return (
    <div className={cn(
      "rounded-lg border p-5",
      highlight ? "bg-card" : "bg-card",
    )}>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {label}
      </div>
      <div className={cn(
        "mt-2 font-mono text-2xl font-bold",
        tone === "success" && "text-success",
        tone === "warning" && "text-warning",
        tone === "danger" && "text-danger",
        !tone && "text-foreground",
      )}>
        {value}
      </div>
      <div className="mt-1 text-[11px] text-muted-foreground">{sub}</div>
    </div>
  );
}
