const API_BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000") + "/api";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const encodeSymbol = (s: string) => s.replace(/\//g, "_");

// ── Types ─────────────────────────────────────────────

export interface MarketContextData {
  btcPrice: number;
  btcChange: number;
  trend: string;
  btcRsi: number;
  fearGreed: number;
  fearGreedLabel: string;
  fundingRate: number;
  fundingSignal: string;
  bolehTrading: boolean;
  warnings: string[];
  modal: number;
}

export interface ScoringFactor {
  label: string;
  score: number;
  max?: number;
}

export interface AnalisaData {
  symbol: string;
  timeframe: string;
  harga: number;
  rsi: number;
  adx: number;
  konsensus: string;
  scoring: {
    grade: string;
    score: number;
    max: number;
    layakTrade: boolean;
    factors: ScoringFactor[];
  };
  aiDecision: {
    action: string;
    confidence: number;
    entry: number;
    sl: number;
    tp1: number;
    tp2: number;
    rr: number;
    reason: string;
    risk: string;
  };
  mtf: { tf: string; signal: string; rsi: number; peran?: string }[];
  sizing: {
    ukuran: number;
    nilaiIDR: number;
    marginUSDT: number;
    maxLossIDR: number;
    maxLossUSDT: number;
    pctModal: number;
    leverage: number;
  };
  candles: {
    time: string; open: number; high: number; low: number;
    close: number; volume: number; ema20: number; ema50: number;
    bbU: number; bbL: number;
    macd?: number; macdSignal?: number; macdHist?: number;
  }[];
  rsiData: { time: string; rsi: number }[];
  openInterest?: { value: number; changePct: number; trend: string };
}

export interface ScanItem {
  symbol: string;
  signal: string;
  rsi: number;
  adx: number;
  price: number;
  change?: number;
  skor?: number;
  skor_max?: number;
  grade?: string;
  layak?: boolean;
  arah?: string;
  mom_grade?: "HOT" | "WARM" | "NETRAL" | "BEARISH";
  roc_20?: number;
  in_momentum?: boolean;
  error?: string;
}

export interface ScanData {
  results: ScanItem[];
  timeframe: string;
}

export interface TradeTerbuka {
  id: number;
  symbol: string;
  aksi: string;
  entry: number;
  sl: number;
  target_1: number;
  target_2: number;
  ukuran: number;
  leverage: number;
  catatan?: string;
  tanggal: string;
  status: string;
}

export interface TradeTertutup extends TradeTerbuka {
  harga_keluar: number;
  hasil: string;
  pnl_pct: number;
  tanggal_tutup: string;
}

export interface JurnalData {
  open: TradeTerbuka[];
  closed: TradeTertutup[];
  total: number;
}

export interface PerformaData {
  totalTrade: number;
  winRate: number;
  totalPnL: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  openTrades: number;
  bestTrade: number;
  worstTrade?: number;
  equityCurve: { day: string; equity: number }[];
  modal: number;
  pnlDist?: { bucket: string; count: number }[];
  targetBulanan?: number;
}

export interface KalkulatorData {
  ukuran: number;
  nilai_posisi: number;
  margin_usdt: number;
  risk_usdt: number;
  risk_rupiah: number;
  pct_modal: number;
  profit1_usdt: number;
  profit1_idr: number;
  profit2_usdt: number;
  profit2_idr: number;
  rr1: number;
  rr2: number;
  error?: string;
}

export interface BacktestData {
  symbol: string;
  timeframe: string;
  totalTrade: number;
  win: number;
  loss: number;
  winRate: number;
  profitFactor: number;
  sharpe: number;
  maxDrawdown: number;
  returnTotal: number;
  modalAwal: number;
  modalAkhir: number;
  equity: { day: string; equity: number }[];
  trades: {
    tanggal_entry?: string; symbol: string; aksi?: string;
    entry?: number; exit?: number; pnl?: number;
  }[];
  error?: string;
}

export interface QuantData {
  symbol: string;
  skortTotal: number;
  keputusan: string;
  regime: { state: string; probBull: number; rekomendasi: string; amanTrading: boolean };
  garch: { volForecast: number; volState: string; amanTrading: boolean; sizingMult: number };
  kalman: { sinyal: string; zscore: number; detail: string };
  zscoreData: { time: string; zscore: number }[];
}

export interface MomentumData {
  ranking: { symbol: string; momentum: number; signal?: string; sinyal?: string }[];
  timeframe: string;
}

export interface PairsData {
  sym1: string;
  sym2: string;
  sinyal: string;
  aksi: string;
  zscore: number;
  pvalue: number;
  hedgeRatio: number;
  detail: string;
  spreadData: { time: string; zscore: number }[];
}

export interface WalletData {
  exchange: string;
  live_mode: boolean;
  usdt_total: number;
  usdt_free: number;
  usdt_used: number;
  coins: Record<string, { free: number; used: number; total: number }>;
}

export interface ExchangePosition {
  symbol: string;
  side: string;
  contracts: number;
  entryPrice: number;
  unrealizedPnl: number;
  leverage: number;
  liquidationPrice: number;
  percentage: number;
  marginMode: string;
  notional: number;
}

export interface KillSwitchData {
  status: "OK" | "PAUSE" | "STOP";
  lanjut: boolean;
  pesan: string;
  dd_hari_pct: number;
  dd_total_pct: number;
  modal_awal?: number;
  modal_sekarang?: number;
}

export interface SettingsData {
  modal: number;
  riskPct: number;
  targetBulanan: number;
  maxDdHarian: number;
  maxDdTotal: number;
  watchlist: string[];
  discordOk: boolean;
  botReady: boolean;
  liveMode: boolean;
  killSwitch: {
    status: "OK" | "PAUSE" | "STOP";
    lanjut: boolean;
    pesan: string;
    ddHari: number;
    ddTotal: number;
  };
}

export interface EksekusiResult {
  success: boolean;
  mode: "LIVE" | "VIRTUAL";
  order_id: string;
  fill_price: number;
  sl_placed?: boolean;
  tp_placed?: boolean;
}

export interface VirtualPosition {
  order_id: string;
  symbol: string;
  aksi: string;
  ukuran: number;
  fill_price: number;
  stop_loss: number;
  take_profit: number;
  leverage: number;
  status: string;
  mode: string;
  waktu: string;
  pnl_usdt: number;
}

export interface SkippedItem {
  id: number;
  tanggal: string;
  symbol: string;
  timeframe: string;
  sinyal: string;
  grade: string;
  skor: number;
  harga: number;
  alasan: string;
}

export interface PaperTrade {
  id: number;
  tanggal: string;
  symbol: string;
  aksi: string;
  entry: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  ukuran: number;
  leverage: number;
  skor_entry: number;
  keyakinan: number;
  catatan: string;
  status: "OPEN" | "CLOSED";
  harga_keluar?: number;
  pnl_usdt?: number;
  pnl_idr?: number;
  pnl_pct_modal?: number;
  hasil?: string;
  tanggal_tutup?: string;
  durasi_jam?: number;
}

export interface PaperStats {
  total: number;
  open: number;
  win: number;
  loss: number;
  win_rate: number;
  total_pnl_idr: number;
  total_pnl_pct: number;
  profit_factor: number;
  avg_win_idr: number;
  avg_loss_idr: number;
  max_drawdown: number;
  sharpe: number;
  modal_awal: number;
  modal_sim: number;
  hari_berjalan: number;
  hari_sisa: number;
  lulus: boolean;
  kriteria: Record<string, boolean>;
}

export interface PaperData {
  stats: PaperStats;
  config: { modal_awal: number; modal_sim: number; mulai: string; target_selesai: string };
  open: PaperTrade[];
  closed: PaperTrade[];
}

// ── API Functions ──────────────────────────────────────

export const api = {
  health: () => apiFetch<{ status: string; bot_ready: boolean; modal: number; watchlist: string[] }>("/health"),

  marketContext: () => apiFetch<MarketContextData>("/market-context"),

  analisa: (symbol: string, timeframe: string, leverage: number) =>
    apiFetch<AnalisaData>(`/analisa/${encodeSymbol(symbol)}/${timeframe}?leverage=${leverage}`),

  scan: (tf: string) => apiFetch<ScanData>(`/scan?tf=${tf}`),

  jurnal: () => apiFetch<JurnalData>("/jurnal"),

  catatTrade: (data: {
    symbol: string; aksi: string; entry: number; sl: number;
    target_1: number; target_2: number; ukuran: number;
    leverage?: number; catatan?: string;
  }) => apiFetch<{ success: boolean; trade: TradeTerbuka }>("/catat-trade", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  tutupTrade: (id: number, data: { harga_keluar: number; hasil: string }) =>
    apiFetch<{ success: boolean; trade: TradeTertutup }>(`/tutup-trade/${id}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  performa: () => apiFetch<PerformaData>("/performa"),

  kalkulator: (params: {
    entry: number; sl: number; tp1?: number; tp2?: number;
    leverage?: number; kurs?: number; risk_pct?: number;
  }) => {
    const q = new URLSearchParams({
      entry: String(params.entry),
      sl: String(params.sl),
      tp1: String(params.tp1 ?? 0),
      tp2: String(params.tp2 ?? 0),
      leverage: String(params.leverage ?? 2),
      kurs: String(params.kurs ?? 16200),
      risk_pct: String(params.risk_pct ?? 1.5),
    });
    return apiFetch<KalkulatorData>(`/kalkulator?${q}`);
  },

  backtest: (data: { symbol: string; timeframe: string; limit: number }) =>
    apiFetch<BacktestData>("/backtest", { method: "POST", body: JSON.stringify(data) }),

  quant: (symbol: string, timeframe: string) =>
    apiFetch<QuantData>(`/quant/${encodeSymbol(symbol)}/${timeframe}`),

  momentum: (tf: string) => apiFetch<MomentumData>(`/momentum?tf=${tf}`),

  pairs: (sym1: string, sym2: string, tf: string) =>
    apiFetch<PairsData>(`/pairs/${encodeSymbol(sym1)}/${encodeSymbol(sym2)}?tf=${tf}`),

  discordAnalisa: (data: {
    symbol: string; timeframe: string; action: string;
    confidence: number; entry: number; sl: number; tp1: number; tp2: number;
    rr: number; reason: string; grade: string; score: number; max: number;
    ukuran: number; maxLossIDR: number; nilaiIDR: number;
  }) => apiFetch<{ success: boolean; error?: string }>("/discord/analisa", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  discordScan: (results: ScanItem[], tf: string) =>
    apiFetch<{ success: boolean; error?: string }>("/discord/scan", {
      method: "POST",
      body: JSON.stringify({ results, timeframe: tf }),
    }),

  price: (symbol: string) =>
    apiFetch<{ symbol: string; price: number; change: number }>(`/price/${encodeSymbol(symbol)}`),

  skipTrade: (data: {
    symbol: string; timeframe: string; sinyal: string;
    grade: string; skor: number; harga: number; alasan?: string;
  }) => apiFetch<{ success: boolean; record: SkippedItem }>("/skip-trade", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  skipped: () => apiFetch<{ skipped: SkippedItem[] }>("/skipped"),

  partialTP: (id: number) =>
    apiFetch<{ success: boolean; status: string; pesan: string }>(`/partial-tp/${id}`, { method: "POST" }),

  breakeven: (id: number, harga: number) =>
    apiFetch<{ success: boolean; status: string; pesan: string }>(`/breakeven/${id}`, {
      method: "POST",
      body: JSON.stringify({ harga }),
    }),

  settings: () => apiFetch<SettingsData>("/settings"),

  testDiscord: () => apiFetch<{ success: boolean }>("/test-discord", { method: "POST" }),

  paperStats: () => apiFetch<PaperData>("/paper-stats"),

  paperTrade: (data: {
    symbol: string; aksi: string; entry: number; sl: number;
    target_1: number; target_2: number; ukuran?: number;
    leverage?: number; skor?: number; keyakinan?: number; catatan?: string;
  }) => apiFetch<{ success: boolean; trade: PaperTrade }>("/paper-trade", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  tutupPaper: (id: number, data: { harga_keluar: number; hasil: string }) =>
    apiFetch<{ success: boolean; trade: PaperTrade }>(`/paper-trade/tutup/${id}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  resetPaper: () => apiFetch<{ success: boolean; message: string }>("/paper-reset", { method: "POST" }),

  killSwitch: () => apiFetch<KillSwitchData>("/kill-switch"),

  eksekusiOrder: (data: {
    symbol: string; aksi: string; ukuran: number; entry: number;
    sl: number; tp1: number; tp2?: number; leverage?: number;
  }) => apiFetch<EksekusiResult>("/eksekusi-order", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  tutupPosisi: (symbol: string, data: { aksi: string; ukuran: number }) =>
    apiFetch<{ success: boolean; fill_price: number }>(`/tutup-posisi/${encodeSymbol(symbol)}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  virtualPositions: () =>
    apiFetch<{ open: VirtualPosition[]; closed: VirtualPosition[]; ringkasan: Record<string, number>; live_mode: boolean }>("/virtual-positions"),

  updateVirtual: () =>
    apiFetch<{ success: boolean; closed_count: number }>("/update-virtual", { method: "POST" }),

  resetKillSwitch: () =>
    apiFetch<{ success: boolean; message: string }>("/reset-kill-switch", { method: "POST" }),

  clearKillSwitchOverride: () =>
    apiFetch<{ success: boolean; message: string }>("/clear-kill-switch-override", { method: "POST" }),

  wallet: () => apiFetch<WalletData>("/wallet"),

  posisilExchange: () =>
    apiFetch<{ exchange: string; positions: ExchangePosition[]; count: number }>("/posisi-exchange"),
};

export default api;
