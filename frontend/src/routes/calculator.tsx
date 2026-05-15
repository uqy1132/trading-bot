import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { SYMBOLS } from "@/lib/mock";
import { formatIDR, formatNum, formatPct, formatUSDT } from "@/lib/format";
import { AlertTriangle, BookPlus, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type KalkulatorData } from "@/lib/api";

export const Route = createFileRoute("/calculator")({
  component: CalculatorPage,
});

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function CalculatorPage() {
  const [modalIDR, setModalIDR] = useState(3_000_000);
  const [kurs, setKurs] = useState(16_300);
  const [riskPct, setRiskPct] = useState(2);
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [entry, setEntry] = useState(80250);
  const [sl, setSl] = useState(78900);
  const [tp1, setTp1] = useState(82500);
  const [tp2, setTp2] = useState(84800);
  const [lev, setLev] = useState(3);
  const [apiResult, setApiResult] = useState<KalkulatorData | null>(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [catatLoading, setCatatLoading] = useState(false);
  const [catatDone, setCatatDone] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Kalkulasi lokal (realtime, tidak butuh API)
  const local = useMemo(() => {
    const modalUSDT = modalIDR / kurs;
    const riskUSDT = (modalUSDT * riskPct) / 100;
    const slDist = Math.abs(entry - sl);
    const size = slDist > 0 ? riskUSDT / slDist : 0;
    const notional = size * entry;
    const margin = notional / lev;
    const tp1Profit = size * Math.abs(tp1 - entry);
    const tp2Profit = size * Math.abs(tp2 - entry);
    const rr = slDist > 0 ? Math.abs(tp1 - entry) / slDist : 0;
    const riskOfModal = (riskUSDT / modalUSDT) * 100;
    return { modalUSDT, riskUSDT, size, notional, margin, tp1Profit, tp2Profit, rr, riskOfModal };
  }, [modalIDR, kurs, riskPct, entry, sl, tp1, tp2, lev]);

  // Debounce fetch ke API (dipanggil setelah 800ms idle)
  const fetchApi = useCallback(async () => {
    if (!entry || !sl) return;
    setApiLoading(true);
    try {
      const res = await api.kalkulator({ entry, sl, tp1, tp2, leverage: lev, kurs, risk_pct: riskPct });
      if (!res.error) setApiResult(res);
    } catch {
      /* pakai local */
    } finally {
      setApiLoading(false);
    }
  }, [entry, sl, tp1, tp2, lev, kurs, riskPct]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchApi, 800);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [fetchApi]);

  // Gunakan hasil API kalau ada, fallback ke kalkulasi lokal
  const ukuran = apiResult?.ukuran ?? local.size;
  const margin = apiResult?.margin_usdt ?? local.margin;
  const riskUSDT = apiResult?.risk_usdt ?? local.riskUSDT;
  const riskIDR = apiResult ? apiResult.risk_rupiah : local.riskUSDT * kurs;
  const tp1Profit = apiResult?.profit1_usdt ?? local.tp1Profit;
  const tp2Profit = apiResult?.profit2_usdt ?? local.tp2Profit;
  const rrRatio = apiResult?.rr1 ?? local.rr;

  const handleCatat = useCallback(async () => {
    if (!entry || !sl) return;
    setCatatLoading(true);
    try {
      await api.catatTrade({
        symbol, aksi: "BUY", entry, sl,
        target_1: tp1, target_2: tp2,
        ukuran, leverage: lev,
        catatan: `Dari Kalkulator | R:R 1:${rrRatio.toFixed(2)}`,
      });
      setCatatDone(true);
    } catch (e) {
      alert("Gagal catat trade: " + String(e));
    } finally {
      setCatatLoading(false);
    }
  }, [symbol, entry, sl, tp1, tp2, ukuran, lev, rrRatio]);

  const safe = rrRatio >= 1.5 && riskPct <= 3;
  const num = "h-10 rounded-md border bg-card px-3 text-sm font-mono outline-none focus:border-success/60";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Kalkulator Posisi</h1>
        <p className="text-sm text-muted-foreground">Real-time risk, R:R, dan margin sizing.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Form */}
        <div className="space-y-4 rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Parameter</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Modal (IDR)"><input type="number" value={modalIDR} onChange={(e) => setModalIDR(+e.target.value)} className={num} /></Field>
            <Field label="Kurs IDR/USDT"><input type="number" value={kurs} onChange={(e) => setKurs(+e.target.value)} className={num} /></Field>
            <Field label="Risk %"><input type="number" step="0.1" value={riskPct} onChange={(e) => setRiskPct(+e.target.value)} className={num} /></Field>
            <Field label="Aset">
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={num}>
                {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Entry"><input type="number" value={entry} onChange={(e) => setEntry(+e.target.value)} className={num} /></Field>
            <Field label="Stop Loss"><input type="number" value={sl} onChange={(e) => setSl(+e.target.value)} className={num} /></Field>
            <Field label="TP1"><input type="number" value={tp1} onChange={(e) => setTp1(+e.target.value)} className={num} /></Field>
            <Field label="TP2"><input type="number" value={tp2} onChange={(e) => setTp2(+e.target.value)} className={num} /></Field>
          </div>
          <Field label={`Leverage: ${lev}x`}>
            <input type="range" min={1} max={20} value={lev} onChange={(e) => setLev(+e.target.value)} className="accent-success" />
          </Field>
        </div>

        {/* Hasil */}
        <div className="space-y-4 rounded-lg border bg-card p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Hasil Kalkulasi</h3>
            {apiLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            {apiResult && !apiLoading && <span className="text-[10px] text-success">✅ API</span>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Out label="Ukuran Posisi" value={formatNum(ukuran, 4)} hint={symbol.split("/")[0]} />
            <Out label="Notional" value={formatUSDT(ukuran * entry)} />
            <Out label="Margin" value={formatUSDT(margin)} hint={formatIDR(margin * kurs)} />
            <Out label="Max Loss" value={formatUSDT(riskUSDT)} hint={formatIDR(riskIDR)} tone="danger" />
            <Out label="Profit TP1" value={formatUSDT(tp1Profit)} hint={formatIDR(tp1Profit * kurs)} tone="success" />
            <Out label="Profit TP2" value={formatUSDT(tp2Profit)} hint={formatIDR(tp2Profit * kurs)} tone="success" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Out label="R:R Ratio" value={`1 : ${rrRatio.toFixed(2)}`} tone={rrRatio >= 1.5 ? "success" : "danger"} />
            <Out label="Risk Modal" value={formatPct(local.riskOfModal)} tone={local.riskOfModal <= 3 ? "success" : "danger"} />
          </div>

          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Risk Level</span>
              <span className={cn("font-mono", riskPct <= 1 ? "text-success" : riskPct <= 3 ? "text-warning" : "text-danger")}>
                {riskPct <= 1 ? "Conservative" : riskPct <= 3 ? "Balanced" : "Aggressive"}
              </span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full transition-all", riskPct <= 1 ? "bg-success" : riskPct <= 3 ? "bg-warning" : "bg-danger")}
                style={{ width: `${Math.min(100, riskPct * 20)}%` }} />
            </div>
          </div>

          {!safe && (
            <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>Parameter tidak optimal: pastikan R:R ≥ 1.5 dan risk ≤ 3%.</span>
            </div>
          )}

          <pre className="overflow-x-auto rounded-md border bg-background p-3 text-[11px] leading-relaxed font-mono text-muted-foreground">
{`ORDER ${symbol}
ENTRY    : ${formatUSDT(entry)}
SL       : ${formatUSDT(sl)}
TP1/TP2  : ${formatUSDT(tp1)} / ${formatUSDT(tp2)}
SIZE     : ${formatNum(ukuran, 4)}
LEVERAGE : ${lev}x
MAX LOSS : ${formatUSDT(riskUSDT)} (${formatIDR(riskIDR)})`}
          </pre>

          <Button
            onClick={handleCatat}
            disabled={catatLoading || catatDone || !entry || !sl}
            className="w-full bg-success text-success-foreground hover:bg-success/90"
          >
            {catatLoading
              ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              : <BookPlus className="mr-1.5 h-4 w-4" />}
            {catatDone ? "✅ Tercatat di Jurnal" : "Catat ke Jurnal"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Out({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "success" | "danger" }) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("mt-1 font-mono text-base", tone === "success" && "text-success", tone === "danger" && "text-danger")}>{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground font-mono">{hint}</div>}
    </div>
  );
}
