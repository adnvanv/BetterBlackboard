import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GradeCircle } from "@/components/GradeCircle";
import type { GradeRow } from "@/lib/api";
import { fmtDate, fmtScore, parseUtc } from "@/lib/format";
import { cn } from "@/lib/utils";

function pctOf(r: GradeRow): number | null {
  if (r.score != null && r.possible && r.possible > 0) return (r.score / r.possible) * 100;
  return null;
}

function hasNumericGrade(r: GradeRow): boolean {
  return pctOf(r) != null;
}

type Props = {
  rows: GradeRow[];
  compact?: boolean;
  /** If set, show only the first N rows by default. A toggle reveals the rest. */
  maxRows?: number;
  /** When true, rows without a numeric grade are filtered out. Default false. */
  enteredOnly?: boolean;
};

export function GradeTable({ rows, compact = false, maxRows, enteredOnly = false }: Props) {
  const [expanded, setExpanded] = useState(false);

  // Sort: most-recent due date first; rows without a due date go to the bottom.
  // Within the no-due-date group, fall back to scrapedAt desc.
  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const da = parseUtc(a.dueAt)?.getTime();
      const db = parseUtc(b.dueAt)?.getTime();
      if (da && db) return db - da;
      if (da) return -1;
      if (db) return 1;
      const sa = parseUtc(a.scrapedAt)?.getTime() ?? 0;
      const sb = parseUtc(b.scrapedAt)?.getTime() ?? 0;
      return sb - sa;
    });
  }, [rows]);

  const filtered = enteredOnly ? sorted.filter(hasNumericGrade) : sorted;

  if (!filtered.length) {
    return <p className="text-sm text-muted-foreground">No grades yet.</p>;
  }

  const visible =
    maxRows != null && !expanded ? filtered.slice(0, maxRows) : filtered;
  const hiddenCount = filtered.length - visible.length;
  const circleSize = compact ? 30 : 36;

  return (
    <div>
      <ul className="divide-y divide-border">
        {visible.map((r, i) => {
          const pct = pctOf(r);
          return (
            <li
              key={i}
              className={cn(
                "grid grid-cols-[1fr_auto] items-center gap-3 py-2.5",
                r.isNew && "bg-accent/5 -mx-1 px-1 rounded",
              )}
            >
              {/* LEFT — title (truncated), due-date subtitle, optional 'new' chip */}
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

              {/* RIGHT — fixed-width score block */}
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

      {maxRows != null && (hiddenCount > 0 || expanded) && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 flex w-full items-center justify-center gap-1 rounded-md py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              Show fewer
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              Show all {filtered.length} ({hiddenCount} more)
            </>
          )}
        </button>
      )}
    </div>
  );
}
