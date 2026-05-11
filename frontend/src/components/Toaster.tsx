import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type Kind = "success" | "error" | "info";

type Toast = {
  id: number;
  kind: Kind;
  title: string;
  details?: string;
  durationMs: number;
};

type Ctx = {
  push: (t: Omit<Toast, "id">) => number;
  dismiss: (id: number) => void;
};

const ToastCtx = createContext<Ctx | null>(null);

let _toastApi: Ctx | null = null;
let _nextId = 1;

/** Use directly in any component: `toast.success("Saved")`. Works from outside React too. */
export const toast = {
  success: (title: string, details?: string, durationMs = 4500) =>
    _toastApi?.push({ kind: "success", title, details, durationMs }),
  error: (title: string, details?: string, durationMs = 7000) =>
    _toastApi?.push({ kind: "error", title, details, durationMs }),
  info: (title: string, details?: string, durationMs = 4500) =>
    _toastApi?.push({ kind: "info", title, details, durationMs }),
};

export function ToasterProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    setItems((arr) => arr.filter((t) => t.id !== id));
    const handle = timers.current.get(id);
    if (handle) {
      window.clearTimeout(handle);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback<Ctx["push"]>(
    (t) => {
      const id = _nextId++;
      setItems((arr) => [...arr, { ...t, id }]);
      if (t.durationMs > 0) {
        const handle = window.setTimeout(() => dismiss(id), t.durationMs);
        timers.current.set(id, handle);
      }
      return id;
    },
    [dismiss],
  );

  const value = useMemo<Ctx>(() => ({ push, dismiss }), [push, dismiss]);
  _toastApi = value;
  useEffect(() => () => {
    _toastApi = null;
  }, []);

  return (
    <ToastCtx.Provider value={value}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
          {items.map((t) => (
            <ToastItem key={t.id} toast={t} onClose={() => dismiss(t.id)} />
          ))}
        </div>,
        document.body,
      )}
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be inside <ToasterProvider>");
  return ctx;
}

function ToastItem({ toast: t, onClose }: { toast: Toast; onClose: () => void }) {
  const [open, setOpen] = useState(false);
  const Icon = t.kind === "success" ? CheckCircle2 : t.kind === "error" ? XCircle : Info;
  const colorRing =
    t.kind === "success"
      ? "border-later/40 bg-later/10 text-later"
      : t.kind === "error"
        ? "border-urgent/40 bg-urgent/10 text-urgent"
        : "border-accent/40 bg-accent/10 text-accent";

  const truncated = t.details && t.details.length > 120 ? t.details.slice(0, 120) + "…" : t.details;

  return (
    <div
      role="status"
      className={cn(
        "pointer-events-auto flex flex-col gap-1.5 rounded-md border px-3 py-2 text-sm shadow-lg backdrop-blur",
        "bg-card/95 text-card-foreground",
        colorRing,
      )}
    >
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex-1 leading-snug">{t.title}</div>
        <button
          onClick={onClose}
          className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      {t.details && (
        <div className="ml-6 text-xs text-muted-foreground">
          <div className={cn("whitespace-pre-wrap break-words", !open && "max-h-[3em] overflow-hidden")}>
            {open ? t.details : truncated}
          </div>
          {t.details.length > 120 && (
            <button
              onClick={() => setOpen((v) => !v)}
              className="mt-1 text-[11px] font-medium text-foreground/80 underline-offset-2 hover:underline"
            >
              {open ? "Show less" : "Show details"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
