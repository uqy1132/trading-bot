import { useEffect, useState } from "react";

const API = "http://localhost:8000/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function useMarketContext() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    get("/market-context").then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);
  return { data, loading, error };
}

export function useAnalysis(symbol: string, timeframe: string, leverage = 2) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = () => {
    setLoading(true); setError(null);
    const sym = symbol.replace("/", "_");
    get(`/analisa/${sym}/${timeframe}?leverage=${leverage}`)
      .then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  };
  return { data, loading, error, run };
}

export function useScan() {
  const [data, setData] = useState<Record<string, unknown>[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = (tf = "4H") => {
    setLoading(true); setError(null);
    get<{ results: Record<string, unknown>[] }>(`/scan?tf=${tf}`)
      .then((r) => setData(r.results)).catch((e) => setError(e.message)).finally(() => setLoading(false));
  };
  return { data, loading, error, run };
}

export function useJurnal() {
  const [data, setData] = useState<{ open: unknown[]; closed: unknown[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const fetch_data = () => {
    get<{ open: unknown[]; closed: unknown[] }>("/jurnal")
      .then(setData).catch(console.error).finally(() => setLoading(false));
  };
  useEffect(() => { fetch_data(); }, []);
  const catatTrade = async (body: unknown) => { await post("/catat-trade", body); fetch_data(); };
  const tutupTrade = async (id: number, harga_keluar: number, hasil: string) => {
    await post(`/tutup-trade/${id}`, { harga_keluar, hasil }); fetch_data();
  };
  return { data, loading, catatTrade, tutupTrade, refetch: fetch_data };
}

export function usePerforma() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get("/performa").then(setData).catch(console.error).finally(() => setLoading(false));
  }, []);
  return { data, loading };
}

export function useKalkulator() {
  const [result, setResult] = useState<Record<string, number> | null>(null);
  const hitung = async (params: Record<string, number>) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]))).toString();
    const res = await get<Record<string, number>>(`/kalkulator?${q}`);
    setResult(res); return res;
  };
  return { result, hitung };
}

export function useBacktest() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const run = async (symbol: string, timeframe: string, limit: number) => {
    setLoading(true);
    const res = await post<Record<string, unknown>>("/backtest", { symbol, timeframe, limit });
    setData(res); setLoading(false); return res;
  };
  return { data, loading, run };
}

export function useQuant() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const run = async (symbol: string, tf = "4H") => {
    setLoading(true);
    const sym = symbol.replace("/", "_");
    const res = await get<Record<string, unknown>>(`/quant/${sym}/${tf}`);
    setData(res); setLoading(false); return res;
  };
  return { data, loading, run };
}

export function useMomentum() {
  const [data, setData] = useState<unknown[] | null>(null);
  const [loading, setLoading] = useState(false);
  const run = async (tf = "4H") => {
    setLoading(true);
    const res = await get<{ ranking: unknown[] }>(`/momentum?tf=${tf}`);
    setData(res.ranking); setLoading(false);
  };
  return { data, loading, run };
}

export function usePairs() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const run = async (sym1: string, sym2: string, tf = "4H") => {
    setLoading(true);
    const s1 = sym1.replace("/", "_"); const s2 = sym2.replace("/", "_");
    const res = await get<Record<string, unknown>>(`/pairs/${s1}/${s2}?tf=${tf}`);
    setData(res); setLoading(false);
  };
  return { data, loading, run };
}
