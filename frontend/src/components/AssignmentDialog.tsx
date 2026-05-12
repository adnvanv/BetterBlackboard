import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/Toaster";
import { api, type Assignment } from "@/lib/api";
import { parseUtc } from "@/lib/format";

/**
 * Initial values for the modal. Pass `null` (or omit) for "create" mode,
 * pass an existing Assignment to put the dialog into "edit" mode.
 */
type Initial = Pick<
  Assignment,
  "id" | "courseId" | "title" | "dueAt" | "pointsPossible" | "url"
> | null;

/** Internal modal body. Use via <AssignmentDialogTrigger /> or controlled props. */
export function AssignmentDialog({
  open,
  onClose,
  initial = null,
}: {
  open: boolean;
  onClose: () => void;
  initial?: Initial;
}) {
  const qc = useQueryClient();
  const { data: courses } = useQuery({
    queryKey: ["courses"],
    queryFn: api.courses,
    enabled: open,
  });

  const isEdit = !!initial?.id;

  // Form state, seeded from `initial` whenever it changes (or modal opens).
  const [courseId, setCourseId] = useState<number | "">("");
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState(""); // "YYYY-MM-DDTHH:MM" local
  const [pts, setPts] = useState("");
  const [url, setUrl] = useState("");

  useEffect(() => {
    if (!open) return;
    setCourseId(initial?.courseId ?? "");
    setTitle(initial?.title ?? "");
    setDueAt(initial?.dueAt ? toLocalInputValue(initial.dueAt) : "");
    setPts(initial?.pointsPossible != null ? String(initial.pointsPossible) : "");
    setUrl(initial?.url ?? "");
  }, [open, initial]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Focus the first field when opening.
  const firstFieldRef = useRef<HTMLSelectElement | null>(null);
  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  const createMutation = useMutation({
    mutationFn: api.createAssignment,
    onSuccess: () => {
      toast.success("Assignment added");
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["assignments"] });
      onClose();
    },
    onError: (e: unknown) => {
      toast.error("Couldn't add assignment", e instanceof Error ? e.message : String(e));
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Parameters<typeof api.updateAssignment>[1] }) =>
      api.updateAssignment(id, body),
    onSuccess: () => {
      toast.success("Assignment updated");
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["assignments"] });
      onClose();
    },
    onError: (e: unknown) => {
      toast.error("Couldn't update assignment", e instanceof Error ? e.message : String(e));
    },
  });

  const isPending = createMutation.isPending || updateMutation.isPending;

  if (!open) return null;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!courseId || !title.trim() || !dueAt) {
      toast.error("Missing required fields", "Course, title, and due date are required.");
      return;
    }
    const isoUtc = new Date(dueAt).toISOString();
    const body = {
      courseId: Number(courseId),
      title: title.trim(),
      dueAt: isoUtc,
      pointsPossible: pts.trim() ? Number(pts) : null,
      url: url.trim() || null,
    };
    if (isEdit && initial?.id != null) {
      updateMutation.mutate({ id: initial.id, body });
    } else {
      createMutation.mutate(body);
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="assignment-dialog-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Panel */}
      <form
        onSubmit={onSubmit}
        className="relative w-[min(480px,calc(100vw-2rem))] rounded-lg border bg-card p-5 shadow-xl"
      >
        <div className="mb-4 flex items-start justify-between gap-2">
          <h2 id="assignment-dialog-title" className="text-base font-semibold leading-tight">
            {isEdit ? "Edit assignment" : "New assignment"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Course
            <select
              ref={firstFieldRef}
              value={courseId}
              onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : "")}
              required
              className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
            >
              <option value="" disabled>
                Select a course…
              </option>
              {(courses ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code ?? c.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Due date & time
            <input
              type="datetime-local"
              value={dueAt}
              onChange={(e) => setDueAt(e.target.value)}
              required
              className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
            />
          </label>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground sm:col-span-2">
            Title
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Lab 5 — File I/O"
              required
              maxLength={200}
              className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
            />
          </label>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Points (optional)
            <input
              type="number"
              value={pts}
              onChange={(e) => setPts(e.target.value)}
              placeholder="100"
              min="0"
              step="any"
              className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
            />
          </label>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Link (optional)
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
            />
          </label>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="accent" size="sm" disabled={isPending}>
            {isPending
              ? isEdit
                ? "Saving…"
                : "Adding…"
              : isEdit
                ? "Save changes"
                : "Add assignment"}
          </Button>
        </div>
      </form>
    </div>,
    document.body,
  );
}

/** Drop-in: small "+ Add" button that opens the dialog in create mode. */
export function AssignmentDialogTrigger({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className={compact ? "h-7 gap-1 px-2" : "gap-1"}
        title="Add a manual assignment"
      >
        <Plus className="h-4 w-4" />
        Add
      </Button>
      <AssignmentDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}

/** Browser `<input type="datetime-local">` wants local "YYYY-MM-DDTHH:MM". The
 * API hands us naive-UTC ISO strings, so go through parseUtc which appends a Z. */
function toLocalInputValue(iso: string): string {
  const d = parseUtc(iso);
  if (!d || isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    d.getFullYear() +
    "-" +
    pad(d.getMonth() + 1) +
    "-" +
    pad(d.getDate()) +
    "T" +
    pad(d.getHours()) +
    ":" +
    pad(d.getMinutes())
  );
}
