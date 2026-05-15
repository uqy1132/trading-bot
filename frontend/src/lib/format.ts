export const formatIDR = (n: number | null | undefined) =>
  "Rp " + Math.round(n ?? 0).toLocaleString("id-ID");

export const formatUSDT = (n: number | null | undefined) =>
  "$" + (n ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatPct = (n: number | null | undefined) => {
  const v = n ?? 0;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
};

export const formatNum = (n: number | null | undefined, d = 2) =>
  (n ?? 0).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
