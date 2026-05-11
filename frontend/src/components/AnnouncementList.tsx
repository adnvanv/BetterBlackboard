import { Link } from "react-router-dom";
import type { Announcement } from "@/lib/api";
import { fmtDate } from "@/lib/format";

export function AnnouncementList({
  items,
  compact = false,
}: {
  items: Announcement[];
  compact?: boolean;
}) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">No announcements.</p>;
  }
  return (
    <ul className="flex flex-col divide-y">
      {items.map((a) => (
        <li key={a.id} className="py-3 first:pt-0 last:pb-0">
          <div className="flex items-baseline justify-between gap-2">
            <div className="font-medium leading-tight">{a.title}</div>
            <time className="shrink-0 text-xs text-muted-foreground">{fmtDate(a.postedAt)}</time>
          </div>
          {a.course && (
            <div className="mt-0.5 text-xs text-muted-foreground">
              {a.courseId ? (
                <Link to={`/course/${a.courseId}`} className="hover:underline">
                  {a.course}
                </Link>
              ) : (
                a.course
              )}
            </div>
          )}
          {!compact && a.bodyHtml && (
            <details className="mt-1.5 text-sm">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Read</summary>
              <div
                className="prose prose-sm prose-invert mt-2 max-w-none rounded-md bg-muted/40 p-3"
                dangerouslySetInnerHTML={{ __html: a.bodyHtml }}
              />
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}
