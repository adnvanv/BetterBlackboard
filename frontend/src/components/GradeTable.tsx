import { Badge } from "@/components/ui/badge";
import { GradeCircle } from "@/components/GradeCircle";
import type { GradeRow } from "@/lib/api";
import { fmtDate, fmtScore } from "@/lib/format";
import { cn } from "@/lib/utils";

function pctOf(r: GradeRow): number | null {
  if (r.score != null && r.possible && r.possible > 0) return (r.score / r.possible) * 100;
  return null;
}

export function GradeTable({ rows, compact = false }: { rows: GradeRow[]; compact?: boolean }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No grades yet.</p>;
  }
  const circleSize = compact ? 30 : 36;

  return (
    <ul className="divide-y divide-border">
      {rows.map((r, i) => {
        const pct = pctOf(r);
        return (
          <li
            key={i}
            className={cn(
              "grid grid-cols-[1fr_auto] items-center gap-3 py-2.5",
              r.isNew && "bg-accent/5 -mx-1 px-1 rounded",
            )}
          >
            {/* LEFT — title (truncated), optional due-date subtitle, optional 'new' chip */}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium" title={r.title}>
                  {r.title}
                </span>
                {r.isNew && (
                  <Badge variant="accent" className="shrink-0 text-[10px]">
                    new
                  </Badge>
                )}
              </div>
              {r.dueAt && (
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  Due {fmtDate(r.dueAt)}
                </div>
              )}
            </div>

            {/* RIGHT — fixed-width score block: raw "X / Y" + colored circle */}
            <div className="flex shrink-0 items-center gap-2 text-right">
              <span className="text-xs tabular-nums text-muted-foreground">
                {fmtScore(r.score, r.possible, r.letter, r.raw)}
              </span>
              <GradeCircle pct={pct} size={circleSize} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
