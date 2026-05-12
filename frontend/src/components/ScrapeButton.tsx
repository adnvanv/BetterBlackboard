import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/Toaster";
import { cn } from "@/lib/utils";
import { parseUtc } from "@/lib/format";

function isSessionExpired(err?: string | null): boolean {
  if (!err) return false;
  return /SESSION_EXPIRED|Saved Blackboard session|relogin|CAS/.test(err);
}

export function ScrapeButton() {
  const qc = useQueryClient();
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api_health,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 2000 : false),
  });

  const running = health?.status === "running";
  const progress = health?.progress;

  // Tick a counter while running so the label shows elapsed seconds.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  const startedAtDate = parseUtc(health?.startedAt);
  const elapsedSec =
    running && startedAtDate
      ? Math.max(0, Math.floor((now - startedAtDate.getTime()) / 1000))
      : 0;

  // Show toasts when a scrape ends (running -> not-running).
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running) {
      qc.invalidateQueries();
      if (health?.status === "ok") {
        toast.success(`Scrape complete — ${health?.coursesScraped ?? 0} course(s).`);
      } else if (isSessionExpired(health?.error || progress?.message)) {
        // The persistent pill handles this case — no toast needed.
      } else if (health?.status === "error") {
        toast.error("Scrape failed", health?.error || progress?.message || "Unknown error");
      }
    }
    wasRunning.current = running;
  }, [running, health, progress, qc]);

  // Toast on mutation 409 (already running) too.
  const mutation = useMutation({
    mutationFn: api_scrape,
    onSuccess: (data) => {
      if (data && (data as any).started === false) {
        toast.info("Scrape already in progress.");
      }
    },
    onError: (e: unknown) => {
      toast.error("Couldn't start scrape", e instanceof Error ? e.message : String(e));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["health"] }),
  });

  const sessionExpired =
    !running && health?.status === "error" && isSessionExpired(health?.error);

  const disabled = running || mutation.isPending;

  let label: string;
  if (running) {
    if (progress?.total && progress.total > 0) {
      label = `Scraping ${progress.current}/${progress.total} · ${elapsedSec}s`;
    } else if (progress?.stage) {
      label = `${progress.stage}… ${elapsedSec}s`;
    } else {
      label = `Scraping… ${elapsedSec}s`;
    }
  } else if (mutation.isPending) {
    label = "Starting…";
  } else {
    label = "Scrape now";
  }

  const pct = progress?.total ? Math.min(100, (progress.current / progress.total) * 100) : 0;

  return (
    <div className="flex items-center gap-2">
      {sessionExpired && <SessionExpiredPill />}

      <div className="relative w-[220px]">
        <Button
          variant="accent"
          size="sm"
          onClick={() => mutation.mutate()}
          disabled={disabled}
          className="w-full gap-2"
        >
          {running || mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {label}
        </Button>
        {running && (
          <div className="pointer-events-none absolute left-0 right-0 top-full mt-1">
            <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-accent transition-all duration-500"
                style={{ width: progress?.total ? `${pct}%` : "100%" }}
              />
            </div>
            {progress?.detail && (
              <div
                className="mt-1 truncate text-[11px] text-muted-foreground"
                title={progress.detail}
              >
                {progress.detail}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Small clickable pill that opens a popover with details + a link to the laptop helper. */
function SessionExpiredPill() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex items-center gap-1 rounded-full border border-soon/40 bg-soon/10 px-2.5 py-1 text-xs font-medium text-soon",
          "hover:bg-soon/15",
        )}
        title="Click for details"
      >
        <AlertTriangle className="h-3.5 w-3.5" />
        Session expired
      </button>
      {open && (
        <div className="absolute right-0 top-full z-40 mt-2 w-[320px] rounded-md border bg-card p-3 text-xs shadow-xl">
          <div className="flex items-center gap-2 text-sm font-semibold text-soon">
            <AlertTriangle className="h-4 w-4" /> Blackboard session expired
          </div>
          <p className="mt-2 leading-relaxed text-muted-foreground">
            The saved cookies are no longer valid. Open{" "}
            <span className="font-medium text-foreground">BetterBlackboard-Login</span> on your
            laptop, finish the Duo prompt, and click <em>Send session to server</em>. Then click
            Scrape now again.
          </p>
          <div className="mt-3 flex justify-end">
            <a
              href="https://github.com/your/repo/blob/main/login_client/README.md"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              How to login <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// Local imports kept at the bottom to keep the diff against the prior file small.
import { api } from "@/lib/api";
const api_health = api.health;
const api_scrape = api.scrape;
