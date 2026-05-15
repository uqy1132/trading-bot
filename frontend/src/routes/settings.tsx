import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { formatIDR } from "@/lib/format";
import { api, type SettingsData } from "@/lib/api";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Send, XCircle, Zap, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<boolean | null>(null);
  const [ksLoading, setKsLoading] = useState(false);
  const [ksMsg, setKsMsg] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.settings();
      setData(res);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleTestDiscord = useCallback(async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await api.testDiscord();
      setTestResult(res.success);
    } catch {
      setTestResult(false);
    } finally {
      setTestLoading(false);
    }
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Konfigurasi aktif bot. Edit via <code className="font-mono text-xs bg-muted px-1 rounded">config/.env</code> lalu restart server.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetch} disabled={loading}>
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
        </Button>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-muted/50" />
          ))}
        </div>
      ) : data ? (
        <>
          {/* Status chips */}
          <div className="flex flex-wrap gap-3">
            <StatusChip ok={data.botReady} label={data.botReady ? "Bot Ready" : "Bot Error"} />
            <StatusChip ok={data.discordOk} label={data.discordOk ? "Discord Terhubung" : "Discord Tidak Dikonfigurasi"} />
            <div className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
              data.liveMode
                ? "border-orange-500/60 bg-orange-500/10 text-orange-400"
                : "border-muted-foreground/30 bg-muted/30 text-muted-foreground"
            )}>
              <Zap className="h-3.5 w-3.5" />
              {data.liveMode ? "LIVE MODE Aktif" : "Virtual Mode"}
            </div>
            <div className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
              data.killSwitch.status === "OK"
                ? "border-success/40 bg-success/10 text-success"
                : data.killSwitch.status === "PAUSE"
                ? "border-warning/60 bg-warning/10 text-warning"
                : "border-danger/60 bg-danger/10 text-danger"
            )}>
              <AlertTriangle className="h-3.5 w-3.5" />
              Kill Switch: {data.killSwitch.status}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Manajemen Modal */}
            <div className="rounded-lg border bg-card p-5 space-y-3">
              <h3 className="text-sm font-semibold">Manajemen Modal</h3>
              <Row label="Modal Total" value={formatIDR(data.modal)} />
              <Row label="Risk per Trade" value={`${data.riskPct}%`} tone={data.riskPct <= 2 ? "success" : data.riskPct <= 3 ? "warning" : "danger"} />
              <Row label="Target Bulanan" value={`${data.targetBulanan}%`} tone="success" />
              <Row label="Max DD Harian" value={`${data.maxDdHarian}%`} tone="danger" />
              <Row label="Max DD Total" value={`${data.maxDdTotal}%`} tone="danger" />
            </div>

            {/* Notifikasi */}
            <div className="rounded-lg border bg-card p-5 space-y-4">
              <h3 className="text-sm font-semibold">Notifikasi Discord</h3>
              <div className="flex items-center gap-2 text-sm">
                {data.discordOk
                  ? <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
                  : <XCircle className="h-4 w-4 text-danger shrink-0" />}
                <span className={data.discordOk ? "text-success" : "text-danger"}>
                  {data.discordOk ? "Webhook URL dikonfigurasi" : "DISCORD_WEBHOOK_URL belum diisi"}
                </span>
              </div>
              {data.discordOk && (
                <>
                  <Button
                    onClick={handleTestDiscord}
                    disabled={testLoading}
                    variant="outline"
                    className="w-full"
                  >
                    {testLoading
                      ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      : <Send className="mr-2 h-4 w-4" />}
                    Kirim Pesan Test
                  </Button>
                  {testResult === true && (
                    <p className="text-xs text-success">✅ Pesan terkirim ke Discord.</p>
                  )}
                  {testResult === false && (
                    <p className="text-xs text-danger">❌ Gagal kirim. Cek URL webhook di .env.</p>
                  )}
                </>
              )}
              {!data.discordOk && (
                <p className="text-xs text-muted-foreground">
                  Tambahkan <code className="font-mono bg-muted px-1 rounded">DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...</code> ke <code className="font-mono bg-muted px-1 rounded">config/.env</code>
                </p>
              )}
            </div>

            {/* Kill Switch Detail */}
            <div className="rounded-lg border bg-card p-5 space-y-3">
              <h3 className="text-sm font-semibold">Kill Switch</h3>
              <Row label="Status" value={data.killSwitch.status}
                tone={data.killSwitch.status === "OK" ? "success" : data.killSwitch.status === "PAUSE" ? "warning" : "danger"} />
              <Row label="DD Hari Ini" value={`${data.killSwitch.ddHari.toFixed(2)}%`}
                tone={data.killSwitch.ddHari >= data.maxDdHarian * 0.8 ? "danger" : undefined} />
              <Row label="DD Total" value={`${data.killSwitch.ddTotal.toFixed(2)}%`}
                tone={data.killSwitch.ddTotal >= data.maxDdTotal * 0.8 ? "danger" : undefined} />
              {data.killSwitch.status !== "OK" && (
                <p className="text-xs text-danger border border-danger/30 bg-danger/5 rounded px-2 py-1.5">
                  ⚠️ {data.killSwitch.pesan}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Batas: DD Harian {data.maxDdHarian}% · DD Total {data.maxDdTotal}%
              </p>
              {data.killSwitch.status !== "OK" && (
                <Button
                  variant="outline"
                  className="w-full border-warning/40 text-warning hover:bg-warning/10 text-xs"
                  disabled={ksLoading}
                  onClick={async () => {
                    if (!confirm("Override kill switch selama 24 jam? Pastikan situasi aman.")) return;
                    setKsLoading(true);
                    setKsMsg(null);
                    try {
                      const r = await api.resetKillSwitch();
                      setKsMsg(r.message);
                      fetch();
                    } catch { setKsMsg("Gagal override"); }
                    finally { setKsLoading(false); }
                  }}
                >
                  {ksLoading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
                  Override Kill Switch (24 jam)
                </Button>
              )}
              {data.killSwitch.status === "OK" && data.killSwitch.pesan.includes("Override") && (
                <Button
                  variant="outline"
                  className="w-full border-muted-foreground/30 text-muted-foreground text-xs"
                  disabled={ksLoading}
                  onClick={async () => {
                    setKsLoading(true);
                    try {
                      await api.clearKillSwitchOverride();
                      fetch();
                    } catch { /* ignore */ }
                    finally { setKsLoading(false); }
                  }}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  Batalkan Override
                </Button>
              )}
              {ksMsg && <p className="text-xs text-warning">{ksMsg}</p>}
            </div>

            {/* Live Mode */}
            <div className="rounded-lg border bg-card p-5 space-y-3">
              <h3 className="text-sm font-semibold">Mode Eksekusi</h3>
              <div className={cn(
                "rounded-md border px-3 py-2.5 text-sm font-medium",
                data.liveMode
                  ? "border-orange-500/50 bg-orange-500/10 text-orange-400"
                  : "border-muted-foreground/30 bg-muted/20 text-muted-foreground"
              )}>
                {data.liveMode ? "⚡ LIVE MODE — Order nyata ke exchange" : "🤖 Virtual Mode — Simulasi tanpa order nyata"}
              </div>
              <p className="text-xs text-muted-foreground">
                Ubah via <code className="font-mono bg-muted px-1 rounded">config/.env</code> →{" "}
                <code className="font-mono bg-muted px-1 rounded">LIVE_MODE=true</code> untuk aktifkan live trading.
              </p>
              {data.liveMode && (
                <p className="text-xs text-warning border border-warning/30 bg-warning/5 rounded px-2 py-1.5">
                  ⚠️ Live mode aktif — pastikan API key exchange sudah dikonfigurasi di .env
                </p>
              )}
            </div>

            {/* Watchlist */}
            <div className="rounded-lg border bg-card p-5 space-y-3 md:col-span-2">
              <h3 className="text-sm font-semibold">Watchlist ({data.watchlist.length} aset)</h3>
              <div className="flex flex-wrap gap-2">
                {data.watchlist.map((sym) => (
                  <span key={sym} className="rounded-md border bg-background px-3 py-1 font-mono text-sm">
                    {sym}
                  </span>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Edit di <code className="font-mono bg-muted px-1 rounded">config/settings.py</code> → <code className="font-mono bg-muted px-1 rounded">CRYPTO_WATCHLIST</code>
              </p>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
          Gagal memuat settings — pastikan backend berjalan.
        </div>
      )}
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "success" | "warning" | "danger" }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono",
        tone === "success" && "text-success",
        tone === "warning" && "text-warning",
        tone === "danger" && "text-danger",
      )}>{value}</span>
    </div>
  );
}

function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className={cn("flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
      ok ? "border-success/40 bg-success/10 text-success" : "border-danger/40 bg-danger/10 text-danger"
    )}>
      {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
      {label}
    </div>
  );
}
