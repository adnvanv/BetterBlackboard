import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { fmtRelative } from "@/lib/format";
import { ScrapeButton } from "@/components/ScrapeButton";

const tabs = [
  { to: "/", label: "Home", end: true },
  { to: "/assignments", label: "Assignments" },
  { to: "/announcements", label: "Announcements" },
  { to: "/grades", label: "Grades" },
];

export function TopNav() {
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: api.health });
  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
      <div className="container flex h-14 items-center gap-4">
        <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <GraduationCap className="h-5 w-5 text-accent" />
          <span>BetterBlackboard</span>
        </NavLink>
        <nav className="ml-4 flex items-center gap-1 rounded-md bg-muted p-1">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                cn(
                  "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {health?.startedAt ? (
              <span title={new Date(health.startedAt).toLocaleString()}>
                Last scrape {fmtRelative(health.startedAt)} ago · {health.status}
              </span>
            ) : (
              <span>No scrape yet</span>
            )}
          </span>
          <ScrapeButton />
        </div>
      </div>
    </header>
  );
}
