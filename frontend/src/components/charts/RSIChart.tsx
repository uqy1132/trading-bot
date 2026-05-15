import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function RSIChart({ data }: { data: { time: string; rsi: number }[] }) {
  return (
    <div className="h-40 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="time" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} width={30} />
          <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
          <ReferenceLine y={70} stroke="var(--danger)" strokeDasharray="3 3" />
          <ReferenceLine y={30} stroke="var(--success)" strokeDasharray="3 3" />
          <Line type="monotone" dataKey="rsi" stroke="var(--chart-4)" dot={false} strokeWidth={1.6} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
