import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useCallback, useRef } from "react";
import { SignalBadge } from "@/components/trading/SignalBadge";
import { Button } from "@/components/ui/button";
import { formatPct, formatUSDT } from "@/lib/format";
import { ChevronDown, Download, Loader2, RefreshCw, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type TradeTerbuka, type TradeTertutup, type JurnalData, type SkippedItem } from "@/lib/api";
import { openTrades as mockOpen, closedTrades as mockClosed } from "@/lib/mock";

export const Route = createFileRoute("/journal")({
  component: JournalPage,
});

const TABS = ["Open Trades", "Closed Trades", "Skipped"] as const;

const MOCK_JURNAL: JurnalData = {
  open: mockOpen.map((t, i) => ({
    id: i + 104,
    symbol: t.symbol,
    aksi: t.action,
    entry: t.entry,
    sl: t.sl,
    target_1: t.tp1,
    target_2: t.tp2,
    ukuran: 0.045,
    leverage: 3,
    tanggal: t.date,
    status: "OPEN",
  })),
  closed: mockClosed.map((t, i) => ({
    id: i + 101,
    symbol: t.symbol,
    aksi: t.action,
    entry: t.entry,
    sl: 0,
    target_1: 0,
    target_2: 0,
    ukuran: 0.045,
    leverage: 3,
    tanggal: t.date,
    status: "CLOSED",
    harga_keluar: t.exit,
    hasil: t.result,
    pnl_pct: t.pnl,
    tanggal_tutup: t.date,
  })),
  total: mockOpen.length + mockClosed.length,
};

function JournalPage() {
  const [tab, setTab] = useState<typeof TABS[number]>("Open Trades");
  const [jurnal, setJurnal] = useState<JurnalData>(MOCK_JURNAL);
  const [skipped, setSkipped] = useState<SkippedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [isMock, setIsMock] = useState(true);

  const fetchJurnal = useCallback(async () => {
    setLoading(true);
    try {
      const [data, sk] = await Promise.all([api.jurnal(), api.skipped().catch(() => ({ skipped: [] }))]);
      setJurnal(data);
      setSkipped(sk.skipped);
      setIsMock(false);
    } catch {
      setIsMock(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchJurnal(); }, [fetchJurnal]);

  const handleTutup = useCallback(async (id: number, harga: number, hasil: string) => {
    try {
      await api.tutupTrade(id, { harga_keluar: harga, hasil });
      await fetchJurnal();
    } catch (e) {
      alert("Gagal tutup trade: " + String(e));
    }
  }, [fetchJurnal]);

  const handleExportCSV = useCallback(() => {
    const headers = ["ID", "Tanggal", "Tanggal Tutup", "Aset", "Aksi", "Entry", "SL", "TP1", "TP2", "Harga Keluar", "PnL%", "Hasil", "Leverage", "Ukuran"];
    const rows = jurnal.closed.map((t) => [
      t.id,
      String(t.tanggal).slice(0, 10),
      String(t.tanggal_tutup || t.tanggal).slice(0, 10),
      t.symbol,
      t.aksi,
      t.entry,
      t.sl,
      t.target_1,
      t.target_2,
      t.harga_keluar ?? "",
      t.pnl_pct ?? "",
      t.hasil,
      t.leverage,
      t.ukuran,
    ]);
    const escape = (v: unknown) => `"${String(v).replace(/"/g, '""')}"`;
    const csv = [headers, ...rows].map((r) => r.map(escape).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `jurnal-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [jurnal.closed]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Jurnal Trade</h1>
          <p className="text-sm text-muted-foreground">Riwayat lengkap trade dengan kontrol manajemen posisi.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchJurnal} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </Button>
          {tab === "Closed Trades" && (
            <Button variant="outline" size="sm" onClick={handleExportCSV} disabled={jurnal.closed.length === 0}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> Export CSV
            </Button>
          )}
        </div>
      </div>

      {!isMock && (
        <div className="rounded-md border border-success/40 bg-success/10 px-3 py-1.5 text-xs text-success">
          ✅ Data live · Open: {jurnal.open.length} · Closed: {jurnal.closed.length}
        </div>
      )}

      <div className="flex gap-1 rounded-lg border bg-card p-1 w-fit">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn("rounded-md px-3 py-1.5 text-xs transition", tab === t ? "bg-success/15 text-success" : "text-muted-foreground hover:text-foreground")}>
            {t}{t === "Open Trades" && ` (${jurnal.open.length})`}
            {t === "Closed Trades" && ` (${jurnal.closed.length})`}
            {t === "Skipped" && skipped.length > 0 && ` (${skipped.length})`}
          </button>
        ))}
      </div>

      {tab === "Open Trades" && (
        <div className="space-y-3">
          {jurnal.open.length === 0 ? (
            <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
              Tidak ada open trade saat ini.
            </div>
          ) : (
            jurnal.open.map((t) => <OpenTradeCard key={t.id} trade={t} onTutup={handleTutup} onRefresh={fetchJurnal} />)
          )}
        </div>
      )}

      {tab === "Closed Trades" && (
        <div className="overflow-x-auto rounded-lg border bg-card">
          {jurnal.closed.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Belum ada closed trade.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b bg-background/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  {["ID", "Tanggal", "Aset", "Aksi", "Entry", "Keluar", "PnL%", "Hasil"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {jurnal.closed.map((t) => (
                  <tr key={t.id} className="border-b last:border-b-0 hover:bg-background/30">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">#{t.id}</td>
                    <td className="px-4 py-3 text-xs">{String(t.tanggal_tutup || t.tanggal).slice(0, 10)}</td>
                    <td className="px-4 py-3 font-mono">{t.symbol}</td>
                    <td className="px-4 py-3"><SignalBadge signal={t.aksi} size="sm" /></td>
                    <td className="px-4 py-3 font-mono">{formatUSDT(t.entry)}</td>
                    <td className="px-4 py-3 font-mono">{formatUSDT(t.harga_keluar ?? 0)}</td>
                    <td className={cn("px-4 py-3 font-mono", (t.pnl_pct ?? 0) >= 0 ? "text-success" : "text-danger")}>
                      {formatPct(t.pnl_pct ?? 0)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-md px-2 py-0.5 text-xs font-semibold",
                        t.hasil === "WIN" ? "bg-success/15 text-success" :
                        t.hasil === "LOSS" ? "bg-danger/15 text-danger" :
                        "bg-muted text-muted-foreground")}>
                        {t.hasil}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "Skipped" && (
        skipped.length === 0 ? (
          <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
            Belum ada sinyal yang di-skip.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="border-b bg-background/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  {["Tanggal", "Aset", "TF", "Sinyal", "Grade", "Harga", "Alasan"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...skipped].reverse().map((s) => (
                  <tr key={s.id} className="border-b last:border-b-0 hover:bg-background/30">
                    <td className="px-4 py-3 text-xs text-muted-foreground">{s.tanggal}</td>
                    <td className="px-4 py-3 font-mono font-semibold">{s.symbol}</td>
                    <td className="px-4 py-3 font-mono text-xs">{s.timeframe}</td>
                    <td className="px-4 py-3"><SignalBadge signal={s.sinyal} size="sm" /></td>
                    <td className="px-4 py-3 text-xs">{s.grade}</td>
                    <td className="px-4 py-3 font-mono">{formatUSDT(s.harga)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground max-w-xs truncate">{s.alasan}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}

function OpenTradeCard({ trade, onTutup, onRefresh }: {
  trade: TradeTerbuka;
  onTutup: (id: number, harga: number, hasil: string) => Promise<void>;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [exitPrice, setExitPrice] = useState("");
  const [hasil, setHasil] = useState("WIN");
  const [closing, setClosing] = useState(false);
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [partialLoading, setPartialLoading] = useState(false);
  const [beLoading, setBeLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await api.price(trade.symbol);
        setLivePrice(res.price);
      } catch { /* ignore */ }
    };
    fetch();
    intervalRef.current = setInterval(fetch, 30_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [trade.symbol]);

  const livePnl = livePrice != null
    ? (() => {
        const raw = (livePrice - trade.entry) / trade.entry * trade.leverage * 100;
        return trade.aksi === "SELL" || trade.aksi === "SHORT" ? -raw : raw;
      })()
    : null;

  const handleTutup = async () => {
    if (!exitPrice) return;
    setClosing(true);
    await onTutup(trade.id, Number(exitPrice), hasil);
    setClosing(false);
    setOpen(false);
  };

  const handlePartialTP = async () => {
    setPartialLoading(true);
    try {
      const res = await api.partialTP(trade.id);
      alert(res.pesan);
      onRefresh();
    } catch (e) { alert("Gagal: " + String(e)); }
    finally { setPartialLoading(false); }
  };

  const handleBreakeven = async () => {
    if (livePrice == null) { alert("Harga live belum tersedia."); return; }
    setBeLoading(true);
    try {
      const res = await api.breakeven(trade.id, livePrice);
      alert(res.pesan);
      if (res.status === "OK") onRefresh();
    } catch (e) { alert("Gagal: " + String(e)); }
    finally { setBeLoading(false); }
  };

  return (
    <div className="rounded-lg border bg-card p-4">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-semibold">{trade.symbol}</span>
          <SignalBadge signal={trade.aksi} size="sm" />
          <span className="text-xs text-muted-foreground">{String(trade.tanggal).slice(0, 16)}</span>
        </div>
        <div className="flex items-center gap-3">
          {livePnl != null && (
            <span className={cn("flex items-center gap-1 font-mono text-sm font-semibold",
              livePnl >= 0 ? "text-success" : "text-danger")}>
              {livePnl >= 0
                ? <TrendingUp className="h-3.5 w-3.5" />
                : <TrendingDown className="h-3.5 w-3.5" />}
              {livePnl >= 0 ? "+" : ""}{livePnl.toFixed(2)}%
            </span>
          )}
          <span className="font-mono text-sm text-muted-foreground">{formatUSDT(trade.entry)}</span>
          <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition", open && "rotate-180")} />
        </div>
      </button>
      {open && (
        <div className="mt-4 space-y-4 border-t pt-4">
          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-3 text-sm md:grid-cols-6">
            <Stat label="Entry" value={formatUSDT(trade.entry)} />
            <Stat label="SL" value={formatUSDT(trade.sl)} tone="danger" />
            <Stat label="TP1" value={formatUSDT(trade.target_1)} tone="success" />
            <Stat label="TP2" value={formatUSDT(trade.target_2)} tone="success" />
            <Stat label="Ukuran" value={String(trade.ukuran)} />
            <Stat label="Leverage" value={`${trade.leverage}x`} />
          </div>
          {livePrice != null && (
            <div className="rounded-md border bg-background/50 px-3 py-2 text-xs flex items-center justify-between">
              <span className="text-muted-foreground">Harga sekarang</span>
              <div className="flex items-center gap-3">
                <span className="font-mono font-semibold">{formatUSDT(livePrice)}</span>
                <span className={cn("font-mono font-bold text-sm",
                  livePnl != null && livePnl >= 0 ? "text-success" : "text-danger")}>
                  {livePnl != null ? `${livePnl >= 0 ? "+" : ""}${livePnl.toFixed(2)}% PnL` : ""}
                </span>
              </div>
            </div>
          )}
          {/* Quick actions */}
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={handlePartialTP} disabled={partialLoading}
              className="flex-1 border-success/40 text-success hover:bg-success/10 hover:text-success">
              {partialLoading && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Partial TP (50%)
            </Button>
            <Button size="sm" variant="outline" onClick={handleBreakeven} disabled={beLoading || livePrice == null}
              className="flex-1">
              {beLoading && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Geser Break-even
            </Button>
          </div>
          {/* Manual close */}
          <div className="space-y-2">
            <div className="flex gap-2">
              <input value={exitPrice} onChange={(e) => setExitPrice(e.target.value)}
                placeholder="Harga keluar" type="number"
                className="h-9 flex-1 rounded-md border bg-background px-3 text-sm font-mono" />
              <select value={hasil} onChange={(e) => setHasil(e.target.value)}
                className="h-9 rounded-md border bg-card px-2 text-sm">
                <option>WIN</option><option>LOSS</option><option>BREAKEVEN</option>
              </select>
            </div>
            <Button onClick={handleTutup} disabled={!exitPrice || closing}
              className="w-full bg-success text-success-foreground hover:bg-success/90">
              {closing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Tutup Trade
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "danger" | "success" }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("font-mono text-sm", tone === "danger" && "text-danger", tone === "success" && "text-success")}>{value}</div>
    </div>
  );
}
