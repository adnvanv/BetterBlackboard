import { cn } from "@/lib/utils";

type Props = {
  /** 0–100 numeric percentage. Pass null for "no score yet". */
  pct: number | null | undefined;
  /** Optional override for the number shown inside the ring. */
  label?: string;
  /** Pixel size (square). Default 36. */
  size?: number;
  className?: string;
};

function color(pct: number | null | undefined): string {
  if (pct == null) return "hsl(0 0% 50%)";   // gray
  if (pct >= 90) return "hsl(142 71% 45%)";  // green
  if (pct >= 80) return "hsl(170 70% 45%)";  // teal
  if (pct >= 70) return "hsl(45 92% 50%)";   // yellow
  if (pct >= 60) return "hsl(28 92% 55%)";   // orange
  return "hsl(0 84% 60%)";                   // red
}

export function GradeCircle({ pct, label, size = 36, className }: Props) {
  const c = color(pct);
  const stroke = Math.max(2, Math.round(size / 12));
  const r = size / 2 - stroke;
  const circ = 2 * Math.PI * r;
  const filled = pct != null ? Math.max(0, Math.min(100, pct)) : 0;
  const dash = (filled / 100) * circ;
  const text = label ?? (pct != null ? `${Math.round(pct)}` : "—");

  // Font size scales with circle size. Cap so 3-digit numbers fit comfortably.
  const fontPx = Math.max(9, Math.min(Math.floor(size * 0.32), 18));

  return (
    <div
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
      title={pct != null ? `${pct.toFixed(1)}%` : "No score yet"}
      aria-label={pct != null ? `Score ${pct.toFixed(1)} percent` : "No score"}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="hsl(var(--border))" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={c}
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 400ms ease" }}
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center font-semibold tabular-nums leading-none"
        style={{ color: c, fontSize: `${fontPx}px` }}
      >
        {text}
      </span>
    </div>
  );
}
