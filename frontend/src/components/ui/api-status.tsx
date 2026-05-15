import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ApiStatus } from "@/hooks/use-api-data";
import { cn } from "@/lib/utils";

interface ApiStatusBannerProps {
  status: ApiStatus;
  isFallback?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Label of the resource being loaded (e.g. "data scan"). */
  label?: string;
  className?: string;
}

export function ApiStatusBanner({ status, isFallback, error, onRetry, label = "data", className }: ApiStatusBannerProps) {
  if (status === "loading") {
    return (
      <div className={cn("flex items-center gap-2 rounded-md border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning", className)}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>Memuat {label} dari server… menampilkan data sementara.</span>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className={cn("flex flex-wrap items-center justify-between gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger", className)}>
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5" />
          <span>
            Gagal memuat {label}{error ? `: ${error}` : ""}. Menampilkan mock data sebagai fallback.
          </span>
        </div>
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry} className="h-7 border-danger/40 text-danger hover:bg-danger/10 hover:text-danger">
            <RefreshCw className="mr-1 h-3 w-3" /> Coba lagi
          </Button>
        )}
      </div>
    );
  }
  if (status === "success" && isFallback) {
    return (
      <div className={cn("rounded-md border bg-background px-3 py-2 text-xs text-muted-foreground", className)}>
        Menampilkan mock data.
      </div>
    );
  }
  return null;
}

export function ApiSkeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted/50", className)} />;
}
