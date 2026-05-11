import { Link } from "react-router-dom";
import { Calendar, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { UpcomingItem, Urgency } from "@/lib/api";
import { fmtDateTime, fmtRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const borderForUrgency: Record<Urgency, string> = {
  urgent: "border-l-[hsl(var(--urgent))]",
  soon: "border-l-[hsl(var(--soon))]",
  later: "border-l-[hsl(var(--later))]",
};

export function UpcomingList({ items }: { items: UpcomingItem[] }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">Nothing upcoming in the next two weeks.</p>;
  }
  return (
    <ul className="flex flex-col">
      {items.map((it, i) => {
        const Icon = it.kind === "event" ? Calendar : FileText;
        return (
          <li
            key={`${it.kind}-${i}-${it.title}`}
            className={cn(
              "flex items-start gap-3 border-l-2 px-3 py-3 first:pt-0 last:pb-0",
              borderForUrgency[it.urgency],
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{fmtDateTime(it.when)}</span>
                <span>·</span>
                <span>in {fmtRelative(it.when).replace("-", "")}</span>
              </div>
              <div className="font-medium leading-tight">
                {it.url ? (
                  <a href={it.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    {it.title}
                  </a>
                ) : (
                  it.title
                )}
              </div>
              {it.course && (
                <div className="text-xs text-muted-foreground">
                  {it.courseId ? (
                    <Link to={`/course/${it.courseId}`} className="hover:underline">
                      {it.course}
                    </Link>
                  ) : (
                    it.course
                  )}
                </div>
              )}
            </div>
            {it.urgency === "urgent" && (
              <Badge variant="urgent" className="self-center">
                Due soon
              </Badge>
            )}
          </li>
        );
      })}
    </ul>
  );
}
