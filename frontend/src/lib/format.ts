/**
 * Parse an ISO datetime as UTC. The Python backend emits naive UTC strings
 * (no trailing Z), which JS otherwise parses as local time — making "now -
 * startedAt" come out negative and the elapsed counter stick at 0.
 */
export function parseUtc(iso?: string | null): Date | null {
  if (!iso) return null;
  // Already has tz info? Trust it.
  if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso)) return new Date(iso);
  return new Date(iso + "Z");
}

export function fmtDateTime(iso?: string | null): string {
  const d = parseUtc(iso);
  if (!d) return "—";
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function fmtDate(iso?: string | null): string {
  const d = parseUtc(iso);
  if (!d) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function fmtRelative(iso?: string | null): string {
  const d = parseUtc(iso);
  if (!d) return "—";
  const ms = d.getTime() - Date.now();
  const abs = Math.abs(ms);
  const day = 86_400_000;
  const hour = 3_600_000;
  const min = 60_000;
  const sign = ms < 0 ? "-" : "";
  if (abs > day) return `${sign}${Math.round(abs / day)}d`;
  if (abs > hour) return `${sign}${Math.round(abs / hour)}h`;
  return `${sign}${Math.round(abs / min)}m`;
}

export function fmtPct(n?: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

export function fmtScore(score?: number | null, possible?: number | null, letter?: string | null, raw?: string): string {
  if (score != null && possible != null) return `${score} / ${possible}`;
  if (letter) return letter;
  return raw || "—";
}
