import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { AssignmentDialog, AssignmentDialogTrigger } from "@/components/AssignmentDialog";
import { toast } from "@/components/Toaster";
import { api, type Assignment } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

type Status = "upcoming" | "all" | "past";

export function AssignmentsPage() {
  const [status, setStatus] = useState<Status>("upcoming");
  const [courseId, setCourseId] = useState<number | undefined>(undefined);
  const [editing, setEditing] = useState<Assignment | null>(null);
  const qc = useQueryClient();

  const { data: courses } = useQuery({ queryKey: ["courses"], queryFn: api.courses });
  const { data, isLoading } = useQuery({
    queryKey: ["assignments", status, courseId],
    queryFn: () => api.assignments({ status, courseId }),
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteAssignment,
    onSuccess: () => {
      toast.success("Assignment deleted");
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["assignments"] });
    },
    onError: (e: unknown) => {
      toast.error("Couldn't delete", e instanceof Error ? e.message : String(e));
    },
  });

  function onDelete(a: Assignment) {
    if (!window.confirm(`Delete "${a.title}"? This can't be undone.`)) return;
    deleteMutation.mutate(a.id);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <CardTitle>Assignments</CardTitle>
          <AssignmentDialogTrigger />
        </div>
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
                <TableHead className="w-[80px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {a.url ? (
                        <a href={a.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                          {a.title}
                        </a>
                      ) : (
                        a.title
                      )}
                      {a.manual && (
                        <Badge variant="outline" className="text-[10px]">
                          manual
                        </Badge>
                      )}
                    </div>
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
                  <TableCell className="text-right">
                    {a.manual && (
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => setEditing(a)}
                          aria-label="Edit assignment"
                          title="Edit"
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(a)}
                          aria-label="Delete assignment"
                          title="Delete"
                          className="rounded p-1 text-muted-foreground hover:bg-urgent/15 hover:text-urgent"
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {/* Edit modal — controlled. Opens when a row's pencil is clicked. */}
      <AssignmentDialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        initial={
          editing
            ? {
                id: editing.id,
                courseId: editing.courseId ?? null,
                title: editing.title,
                dueAt: editing.dueAt ?? null,
                pointsPossible: editing.pointsPossible ?? null,
                url: editing.url ?? null,
              }
            : null
        }
      />
    </Card>
  );
}
