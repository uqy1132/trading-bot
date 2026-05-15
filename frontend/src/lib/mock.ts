// Mock data for the trading dashboard
export const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "HYPE/USDT", "TRX/USDT"];
export const TIMEFRAMES = ["15M", "30M", "1H", "4H", "1D"];
export const LEVERAGES = [1, 2, 3, 5];

export const marketContext = {
  btcPrice: 80246.9,
  btcChange: 2.34,
  trend: "UPTREND" as "UPTREND" | "DOWNTREND",
  fearGreed: 68,
  fundingRate: 0.012,
  bolehTrading: true,
  modal: 3_000_000,
};

export function genCandles(n = 80, base = 80000) {
  const arr: { time: string; open: number; high: number; low: number; close: number; volume: number; ema20: number; ema50: number; bbU: number; bbL: number }[] = [];
  let price = base;
  let ema20 = base, ema50 = base;
  for (let i = 0; i < n; i++) {
    const open = price;
    const change = (Math.random() - 0.48) * base * 0.015;
    const close = open + change;
    const high = Math.max(open, close) + Math.random() * base * 0.005;
    const low = Math.min(open, close) - Math.random() * base * 0.005;
    const volume = Math.round(500 + Math.random() * 2500);
    ema20 = ema20 * 0.9 + close * 0.1;
    ema50 = ema50 * 0.96 + close * 0.04;
    const bbU = ema20 + base * 0.012;
    const bbL = ema20 - base * 0.012;
    const t = new Date(Date.now() - (n - i) * 3600_000);
    arr.push({ time: `${t.getHours()}:00`, open, high, low, close, volume, ema20, ema50, bbU, bbL });
    price = close;
  }
  return arr;
}

export function genRSI(n = 80) {
  const arr: { time: string; rsi: number }[] = [];
  let v = 50;
  for (let i = 0; i < n; i++) {
    v += (Math.random() - 0.5) * 8;
    v = Math.max(15, Math.min(88, v));
    arr.push({ time: `${i}`, rsi: v });
  }
  return arr;
}

export const scoring = {
  grade: "A" as "A+" | "A" | "B" | "C" | "D",
  score: 18,
  max: 22,
  layakTrade: true,
  factors: [
    { label: "Trend Alignment", score: 4, max: 4 },
    { label: "Momentum (RSI/MACD)", score: 3, max: 4 },
    { label: "Volume Confirmation", score: 3, max: 3 },
    { label: "Multi-Timeframe", score: 4, max: 5 },
    { label: "Risk/Reward", score: 3, max: 3 },
    { label: "Market Regime", score: 1, max: 3 },
  ],
};

export const aiDecision = {
  action: "BUY" as "BUY" | "SELL" | "HOLD",
  confidence: 8,
  entry: 80250,
  sl: 78900,
  tp1: 82500,
  tp2: 84800,
  rr: 2.4,
  reason:
    "Tren utama bullish di Daily, pullback selesai di EMA20 4H, RSI reset ke 52, volume buyer dominan. Funding netral, F&G greed tapi belum extreme.",
};

export const mtf = [
  { tf: "Daily", signal: "BUY", rsi: 62 },
  { tf: "4H", signal: "BUY", rsi: 55 },
  { tf: "1H", signal: "HOLD", rsi: 48 },
];

export const scanResults = SYMBOLS.map((s, i) => ({
  symbol: s,
  signal: (["BUY", "SELL", "HOLD", "BUY", "HOLD", "SELL"] as const)[i],
  rsi: 30 + ((i * 11) % 60),
  adx: 18 + ((i * 7) % 30),
  price: [80246.9, 3120.4, 168.22, 2.41, 28.7, 0.265][i],
}));

export const openTrades = [
  { id: "T-104", symbol: "BTC/USDT", action: "BUY", entry: 79850, sl: 78400, tp1: 82200, tp2: 84500, date: "10 Mei 2026 09:12" },
  { id: "T-105", symbol: "SOL/USDT", action: "BUY", entry: 162.4, sl: 158.0, tp1: 172.0, tp2: 180.0, date: "11 Mei 2026 14:48" },
];

export const closedTrades = [
  { id: "T-101", date: "05 Mei 2026", symbol: "ETH/USDT", action: "BUY", entry: 3050, exit: 3210, pnl: 5.24, result: "WIN" },
  { id: "T-102", date: "06 Mei 2026", symbol: "BTC/USDT", action: "SELL", entry: 81200, exit: 80100, pnl: 1.35, result: "WIN" },
  { id: "T-103", date: "08 Mei 2026", symbol: "XRP/USDT", action: "BUY", entry: 2.55, exit: 2.41, pnl: -2.74, result: "LOSS" },
];

export const equityCurve = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  equity: 3_000_000 + i * 18000 + Math.sin(i / 3) * 35000,
}));

export const performance = {
  totalTrade: 42,
  winRate: 62,
  totalPnL: 14.8,
  profitFactor: 2.1,
  avgWin: 3.4,
  avgLoss: -1.6,
  openTrades: 2,
  bestTrade: 8.6,
};
