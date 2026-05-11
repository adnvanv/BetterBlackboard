import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { GradeTable } from "@/components/GradeTable";
import { AnnouncementList } from "@/components/AnnouncementList";
import { api } from "@/lib/api";
import { fmtDateTime, fmtPct } from "@/lib/format";

export function CoursePage() {
  const { id } = useParams<{ id: string }>();
  const courseId = id ? Number(id) : NaN;
  const { data, isLoading, error } = useQuery({
    queryKey: ["course", courseId],
    queryFn: () => api.course(courseId),
    enabled: Number.isFinite(courseId),
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error || !data)
    return <p className="text-sm text-destructive">Course not found.</p>;

  const g = data.gradeGroups[0];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
        </Link>
        <div className="mt-2 flex items-baseline justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{data.course.name}</h1>
            <p className="text-sm text-muted-foreground">
              {data.course.code}
              {data.course.term && <> · {data.course.term}</>}
            </p>
          </div>
          {data.course.url && (
            <a
              href={data.course.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
            >
              Open in Blackboard <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      </div>

      <Tabs defaultValue="assignments" className="w-full">
        <TabsList>
          <TabsTrigger value="assignments">Assignments ({data.assignments.length})</TabsTrigger>
          <TabsTrigger value="grades">Grades</TabsTrigger>
          <TabsTrigger value="announcements">Announcements ({data.announcements.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="assignments">
          <Card>
            <CardContent className="p-0">
              {data.assignments.length === 0 ? (
                <p className="p-6 text-sm text-muted-foreground">No assignments scraped.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Due</TableHead>
                      <TableHead className="text-right">Points</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.assignments.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell className="font-medium">
                          {a.url ? (
                            <a
                              href={a.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:underline"
                            >
                              {a.title}
                            </a>
                          ) : (
                            a.title
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
        </TabsContent>

        <TabsContent value="grades">
          <Card>
            <CardHeader className="flex flex-row items-baseline justify-between">
              <CardTitle>Grades</CardTitle>
              {g?.averagePct != null && (
                <span className="text-2xl font-semibold tabular-nums text-[hsl(var(--later))]">
                  {fmtPct(g.averagePct)}
                </span>
              )}
            </CardHeader>
            <CardContent>{g ? <GradeTable rows={g.rows} /> : <p className="text-sm text-muted-foreground">No grades.</p>}</CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="announcements">
          <Card>
            <CardContent>
              <AnnouncementList items={data.announcements} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
