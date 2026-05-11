import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GradeTable } from "@/components/GradeTable";
import { GradeCircle } from "@/components/GradeCircle";
import { api } from "@/lib/api";

export function GradesPage() {
  const { data, isLoading } = useQuery({ queryKey: ["grades"], queryFn: api.grades });

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!data?.length) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          No grades scraped yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {data.map((g) => (
        <Card key={g.course.id} className="overflow-hidden">
          <CardHeader className="flex flex-row items-baseline justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="truncate">
                <Link to={`/course/${g.course.id}`} className="hover:underline">
                  {g.course.name}
                </Link>
              </CardTitle>
              {g.course.code && (
                <p className="mt-1 text-xs text-muted-foreground">{g.course.code}</p>
              )}
            </div>
            <GradeCircle pct={g.averagePct ?? null} size={64} />

          </CardHeader>
          <CardContent>
            <GradeTable rows={g.rows} maxRows={5} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
