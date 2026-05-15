import { useCallback, useEffect, useRef, useState } from "react";

export type ApiStatus = "idle" | "loading" | "success" | "error";

export interface UseApiDataOptions<T> {
  /** Mock data used as fallback when the API is loading or fails. */
  fallback: T;
  /** Async fetcher (kept optional so pages can wire real APIs later). */
  fetcher?: () => Promise<T>;
  /** Auto-run on mount. Defaults to true. */
  auto?: boolean;
  /** Simulated latency (ms) when no fetcher is provided. */
  simulateMs?: number;
  /** Probability (0–1) of a simulated error when no fetcher is provided. */
  simulateErrorRate?: number;
  /** Re-run when any of these change. */
  deps?: ReadonlyArray<unknown>;
}

export interface UseApiDataResult<T> {
  data: T;
  status: ApiStatus;
  isLoading: boolean;
  isError: boolean;
  isFallback: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Wraps an API call with loading + error states while always returning mock
 * data as a safe fallback. The component can render normally; the surrounding
 * banner indicates whether the data is live or fallback.
 */
export function useApiData<T>(options: UseApiDataOptions<T>): UseApiDataResult<T> {
  const {
    fallback,
    fetcher,
    auto = true,
    simulateMs = 600,
    simulateErrorRate = 0,
    deps = [],
  } = options;

  const [data, setData] = useState<T>(fallback);
  const [status, setStatus] = useState<ApiStatus>(auto ? "loading" : "idle");
  const [error, setError] = useState<string | null>(null);
  const [isFallback, setIsFallback] = useState<boolean>(true);
  const reqId = useRef(0);

  const run = useCallback(() => {
    const id = ++reqId.current;
    setStatus("loading");
    setError(null);

    const promise: Promise<T> = fetcher
      ? fetcher()
      : new Promise<T>((resolve, reject) =>
          setTimeout(() => {
            if (Math.random() < simulateErrorRate) reject(new Error("Gagal memuat data dari server"));
            else resolve(fallback);
          }, simulateMs),
        );

    promise
      .then((result) => {
        if (reqId.current !== id) return;
        setData(result);
        setIsFallback(false);
        setStatus("success");
      })
      .catch((e: unknown) => {
        if (reqId.current !== id) return;
        setData(fallback);
        setIsFallback(true);
        setError(e instanceof Error ? e.message : "Terjadi kesalahan");
        setStatus("error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher, simulateMs, simulateErrorRate]);

  useEffect(() => {
    if (auto) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return {
    data,
    status,
    isLoading: status === "loading",
    isError: status === "error",
    isFallback,
    error,
    refetch: run,
  };
}
