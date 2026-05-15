import { Link, useLocation } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { Search, Radio, BookOpen, BarChart3, Calculator, FlaskConical, Sigma, Bot, Settings, ClipboardList, TrendingUp, GitCompare, Wallet, Layers } from "lucide-react";

const NAV = [
  { to: "/", label: "Analisa & Sinyal", icon: Search },
  { to: "/scan", label: "Scan Aset", icon: Radio },
  { to: "/momentum", label: "Momentum", icon: TrendingUp },
  { to: "/pairs", label: "Pairs Trading", icon: GitCompare },
  { to: "/wallet", label: "Wallet & Posisi", icon: Wallet },
  { to: "/virtual", label: "Virtual Positions", icon: Layers },
  { to: "/journal", label: "Jurnal Trade", icon: BookOpen },
  { to: "/performance", label: "Performa", icon: BarChart3 },
  { to: "/calculator", label: "Kalkulator", icon: Calculator },
  { to: "/backtest", label: "Backtest", icon: FlaskConical },
  { to: "/quant", label: "Quant Analysis", icon: Sigma },
  { to: "/paper", label: "Paper Trading", icon: ClipboardList },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r bg-card/40">
      <div className="flex items-center gap-2 px-5 py-4 border-b">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-success/15 text-success">
          <Bot className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-semibold leading-none">Trading Bot</div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-muted-foreground">Quant Suite</div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
                active
                  ? "bg-success/10 text-success border border-success/30"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className={cn("h-4 w-4", active ? "text-success" : "text-muted-foreground group-hover:text-foreground")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-4 text-xs text-muted-foreground">
        <div className="font-mono">Trading Bot v1.0</div>
        <div className="mt-0.5 opacity-60">OKX · Gate.io · MEXC</div>
      </div>
    </aside>
  );
}
