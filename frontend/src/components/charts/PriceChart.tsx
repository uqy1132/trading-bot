import { Bar, BarChart, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Candle = { time: string; open: number; high: number; low: number; close: number; volume: number; ema20: number; ema50: number; bbU: number; bbL: number };

export function PriceChart({ data }: { data: Candle[] }) {
  const enriched = data.map((c) => ({
    ...c,
    body: [Math.min(c.open, c.close), Math.max(c.open, c.close)] as [number, number],
    wick: [c.low, c.high] as [number, number],
    bullish: c.close >= c.open,
  }));
  return (
    <div className="space-y-2">
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <ComposedChart data={enriched} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
            <XAxis dataKey="time" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
            <YAxis domain={["auto", "auto"]} tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} width={60} />
            <Tooltip
              contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "var(--muted-foreground)" }}
            />
            <Bar dataKey="wick" fill="var(--muted-foreground)" barSize={1} isAnimationActive={false} />
            <Bar dataKey="body" barSize={5} isAnimationActive={false}>
              {enriched.map((c, i) => (
                <rect key={i} />
              ))}
            </Bar>
            <Line type="monotone" dataKey="bbU" stroke="var(--chart-4)" strokeOpacity={0.4} dot={false} strokeWidth={1} />
            <Line type="monotone" dataKey="bbL" stroke="var(--chart-4)" strokeOpacity={0.4} dot={false} strokeWidth={1} />
            <Line type="monotone" dataKey="ema20" stroke="var(--warning)" dot={false} strokeWidth={1.5} />
            <Line type="monotone" dataKey="ema50" stroke="var(--chart-4)" dot={false} strokeWidth={1.5} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="h-20 w-full">
        <ResponsiveContainer>
          <BarChart data={enriched} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
            <XAxis dataKey="time" hide />
            <YAxis hide />
            <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
            <Bar dataKey="volume" isAnimationActive={false}>
              {enriched.map((c, i) => (
                <rect key={i} fill={c.bullish ? "var(--success)" : "var(--danger)"} fillOpacity={0.5} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
