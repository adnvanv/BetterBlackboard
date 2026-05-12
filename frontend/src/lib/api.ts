// Typed fetch wrappers for the FastAPI backend.

export type Course = {
  id: number;
  name: string;
  code?: string | null;
  term?: string | null;
  url?: string | null;
};

export type Urgency = "urgent" | "soon" | "later";

export type UpcomingItem = {
  kind: "assignment" | "event";
  id?: number | null;
  title: string;
  when: string; // ISO
  course?: string | null;
  courseId?: number | null;
  url?: string | null;
  urgency: Urgency;
  manual?: boolean;
};

export type Announcement = {
  id: number;
  title: string;
  bodyHtml?: string | null;
  postedAt?: string | null;
  author?: string | null;
  course?: string | null;
  courseId?: number | null;
};

export type GradeRow = {
  title: string;
  dueAt?: string | null;
  postedAt?: string | null;
  score?: number | null;
  possible?: number | null;
  letter?: string | null;
  raw: string;
  isNew: boolean;
  scrapedAt?: string | null;
};

export type CourseGrades = {
  course: Course;
  averagePct?: number | null;
  rows: GradeRow[];
};

export type Assignment = {
  id: number;
  title: string;
  dueAt?: string | null;
  pointsPossible?: number | null;
  url?: string | null;
  course?: string | null;
  courseId?: number | null;
  /** True when the row was added manually via /api/assignments, not scraped. */
  manual?: boolean;
};

export type ScrapeProgress = {
  runId: number | null;
  stage: string;
  current: number;
  total: number;
  detail: string;
  finished: boolean;
  success: boolean | null;
  message: string;
};

export type Health = {
  status: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  coursesScraped: number;
  error?: string | null;
  progress?: ScrapeProgress;
};

export type DashboardData = {
  upcoming: UpcomingItem[];
  recentGrades: GradeRow[];
  recentAnnouncements: Announcement[];
  health: Health;
};

export type CourseDetail = {
  course: Course;
  assignments: Assignment[];
  announcements: Announcement[];
  gradeGroups: CourseGrades[];
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export type ScrapeStartResponse =
  | { started: true; runId: number; status: 202 }
  | { started: false; reason: "already-running"; runId: number; status: 409 };

async function postScrape(): Promise<ScrapeStartResponse> {
  const res = await fetch("/api/scrape", {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  const body = await res.json().catch(() => ({}));
  return { ...body, status: res.status as 202 | 409 };
}

export const api = {
  dashboard: () => get<DashboardData>("/api/dashboard"),
  assignments: (params?: { courseId?: number; status?: "all" | "upcoming" | "past" }) => {
    const qs = new URLSearchParams();
    if (params?.courseId != null) qs.set("courseId", String(params.courseId));
    if (params?.status) qs.set("status", params.status);
    const q = qs.toString();
    return get<Assignment[]>(`/api/assignments${q ? `?${q}` : ""}`);
  },
  announcements: (params?: { courseId?: number }) => {
    const qs = new URLSearchParams();
    if (params?.courseId != null) qs.set("courseId", String(params.courseId));
    const q = qs.toString();
    return get<Announcement[]>(`/api/announcements${q ? `?${q}` : ""}`);
  },
  grades: () => get<CourseGrades[]>("/api/grades"),
  courses: () => get<Course[]>("/api/courses"),
  course: (id: number) => get<CourseDetail>(`/api/courses/${id}`),
  health: () => get<Health>("/api/health"),
  scrape: postScrape,
  createAssignment: async (input: {
    courseId: number;
    title: string;
    dueAt: string; // ISO datetime
    pointsPossible?: number | null;
    url?: string | null;
  }): Promise<Assignment> => {
    const res = await fetch("/api/assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`);
    }
    return res.json();
  },
  updateAssignment: async (
    id: number,
    input: Partial<{
      courseId: number;
      title: string;
      dueAt: string;
      pointsPossible: number | null;
      url: string | null;
    }>,
  ): Promise<Assignment> => {
    const res = await fetch(`/api/assignments/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`);
    }
    return res.json();
  },
  deleteAssignment: async (id: number): Promise<void> => {
    const res = await fetch(`/api/assignments/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`);
    }
  },
};
