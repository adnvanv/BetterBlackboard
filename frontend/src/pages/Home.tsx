import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { UpcomingList } from "@/components/UpcomingList";
import { AnnouncementList } from "@/components/AnnouncementList";
import { GradeTable } from "@/components/GradeTable";
import { api } from "@/lib/api";

export function Home() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const [showUngraded, setShowUngraded] = useState(false);

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) return <p className="text-sm text-destructive">Failed to load dashboard.</p>;
  if (!data) return null;

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="md:col-span-2 flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Upcoming</CardTitle>
            <p className="text-xs text-muted-foreground">Next 14 days</p>
          </CardHeader>
          <CardContent>
            <UpcomingList items={data.upcoming} />
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>Recent grades</CardTitle>
              <p className="text-xs text-muted-foreground">Posted in the last 7 days</p>
            </div>
            <ToggleSwitch
              checked={showUngraded}
              onChange={setShowUngraded}
              label="Show ungraded"
            />
          </CardHeader>
          <CardContent>
            <GradeTable rows={data.recentGrades} compact enteredOnly={!showUngraded} />
          </CardContent>
        </Card>
      </div>

      <aside className="md:col-span-1">
        <Card className="md:sticky md:top-20">
          <CardHeader>
            <CardTitle>Announcements</CardTitle>
            <p className="text-xs text-muted-foreground">Most recent first</p>
          </CardHeader>
          <CardContent>
            <AnnouncementList items={data.recentAnnouncements} compact />
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex shrink-0 cursor-pointer items-center gap-2 select-none">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={
          "relative inline-flex h-5 w-9 items-center rounded-full transition-colors " +
          (checked ? "bg-accent" : "bg-muted")
        }
      >
        <span
          className={
            "inline-block h-4 w-4 transform rounded-full bg-background shadow transition-transform " +
            (checked ? "translate-x-4" : "translate-x-0.5")
          }
        />
      </button>
    </label>
  );
}
