export function formatDuration(totalSeconds: number): string {
  const sign = totalSeconds < 0 ? "-" : "";
  const seconds = Math.abs(Math.round(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${sign}${h}h ${m.toString().padStart(2, "0")}m`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-PE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMoney(value: string | number, currency = "USD"): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
}

export function formatPct(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return `${Math.round(n * 100)}%`;
}

export function intervalKey(intervalStart: string, intervalEnd: string): string {
  return `${intervalStart}|${intervalEnd}`;
}
