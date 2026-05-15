import { cn } from "@/lib/utils";

type Signal = "BUY" | "SELL" | "HOLD" | "UPTREND" | "DOWNTREND" | string;

export function SignalBadge({
  signal,
  size = "md",
  className,
}: {
  signal: Signal;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const isBuy = signal === "BUY" || signal === "UPTREND";
  const isSell = signal === "SELL" || signal === "DOWNTREND";
  const sizes = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-xs",
    lg: "px-4 py-2 text-base",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md font-semibold tracking-wide font-mono",
        sizes[size],
        isBuy && "bg-success/15 text-success border border-success/40",
        isSell && "bg-danger/15 text-danger border border-danger/40",
        !isBuy && !isSell && "bg-muted text-muted-foreground border border-border",
        className,
      )}
    >
      {signal}
    </span>
  );
}
