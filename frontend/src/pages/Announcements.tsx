import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnnouncementList } from "@/components/AnnouncementList";
import { api } from "@/lib/api";

export function AnnouncementsPage() {
  const [courseId, setCourseId] = useState<number | undefined>(undefined);
  const { data: courses } = useQuery({ queryKey: ["courses"], queryFn: api.courses });
  const { data, isLoading } = useQuery({
    queryKey: ["announcements", courseId],
    queryFn: () => api.announcements({ courseId }),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle>Announcements</CardTitle>
        <select
          value={courseId ?? ""}
          onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : undefined)}
          className="h-9 rounded-md border bg-background px-2 text-sm"
        >
          <option value="">All courses</option>
          {courses?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code ?? c.name}
            </option>
          ))}
        </select>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <AnnouncementList items={data ?? []} />
        )}
      </CardContent>
    </Card>
  );
}
