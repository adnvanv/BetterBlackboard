import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

type Status = "upcoming" | "all" | "past";

export function AssignmentsPage() {
  const [status, setStatus] = useState<Status>("upcoming");
  const [courseId, setCourseId] = useState<number | undefined>(undefined);

  const { data: courses } = useQuery({ queryKey: ["courses"], queryFn: api.courses });
  const { data, isLoading } = useQuery({
    queryKey: ["assignments", status, courseId],
    queryFn: () => api.assignments({ status, courseId }),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle>Assignments</CardTitle>
        <div className="flex items-center gap-2">
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
          <div className="flex rounded-md bg-muted p-0.5">
            {(["upcoming", "all", "past"] as Status[]).map((s) => (
              <Button
                key={s}
                variant={status === s ? "default" : "ghost"}
                size="sm"
                onClick={() => setStatus(s)}
                className="h-7 px-3 text-xs"
              >
                {s[0].toUpperCase() + s.slice(1)}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !data?.length ? (
          <p className="text-sm text-muted-foreground">No assignments match.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Course</TableHead>
                <TableHead>Due</TableHead>
                <TableHead className="text-right">Points</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="font-medium">
                    {a.url ? (
                      <a href={a.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                        {a.title}
                      </a>
                    ) : (
                      a.title
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {a.courseId ? (
                      <Link to={`/course/${a.courseId}`} className="hover:underline">
                        {a.course}
                      </Link>
                    ) : (
                      a.course
                    )}
                  </TableCell>
                  <TableCell>{fmtDateTime(a.dueAt)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {a.pointsPossible ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
