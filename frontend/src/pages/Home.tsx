import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { UpcomingList } from "@/components/UpcomingList";
import { AnnouncementList } from "@/components/AnnouncementList";
import { GradeTable } from "@/components/GradeTable";
import { api } from "@/lib/api";

export function Home() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });

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
          <CardHeader>
            <CardTitle>Recent grades</CardTitle>
            <p className="text-xs text-muted-foreground">Posted in the last 7 days</p>
          </CardHeader>
          <CardContent>
            <GradeTable rows={data.recentGrades} compact />
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
