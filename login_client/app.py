"""BetterBlackboard login helper (laptop-side GUI).

Run this on your laptop. It:
  1. Opens a real Chromium window so you can log in to Blackboard by hand
     (CAS + Duo MFA, with "Remember this browser" ticked).
  2. Saves the resulting cookies to a local storage_state.json.
  3. POSTs that file to your server (over Tailscale, typically) so the headless
     scrape running there picks up the fresh session.

Requires Python 3.11+ with `playwright` and `httpx` installed:
    pip install playwright httpx
    playwright install chromium
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import httpx
from playwright.async_api import async_playwright

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_STATE_PATH = Path(__file__).resolve().parent / "storage_state.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"server_url": "", "upload_token": "", "blackboard_url": ""}
    try:
        return json.loads(CONFIG_PATH.read_text("utf-8"))
    except json.JSONDecodeError:
        return {"server_url": "", "upload_token": "", "blackboard_url": ""}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# --- Dark theme palette (matches the dashboard's vibe) ---
BG = "#0f1115"        # window background
PANEL = "#181b22"     # frames / entry / log
TEXT = "#e6e8ec"
MUTED = "#8a93a3"
ACCENT = "#4f8cff"
ACCENT_FG = "#ffffff"
BORDER = "#232732"
SELECT = "#1f2937"


def _apply_dark_theme(root: tk.Tk) -> None:
    root.configure(bg=BG)
    style = ttk.Style(root)
    # 'clam' lets us re-style nearly everything; the default themes ignore most settings.
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    font=("Segoe UI", 10))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    style.map("TEntry", fieldbackground=[("focus", PANEL)],
              bordercolor=[("focus", ACCENT)])

    style.configure("TButton", background=PANEL, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    focuscolor=ACCENT, padding=(10, 6))
    style.map("TButton",
              background=[("active", SELECT), ("disabled", BG)],
              foreground=[("disabled", MUTED)])

    style.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_FG,
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    padding=(10, 6))
    style.map("Accent.TButton",
              background=[("active", "#3a78ee"), ("disabled", BG)],
              foreground=[("disabled", MUTED)])

    # tk (non-ttk) defaults — used by the scrolledtext widget.
    root.option_add("*Text.background", PANEL)
    root.option_add("*Text.foreground", TEXT)
    root.option_add("*Text.insertBackground", TEXT)
    root.option_add("*Text.selectBackground", SELECT)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("BetterBlackboard — Login helper")
        root.geometry("640x520")
        root.minsize(560, 460)
        _apply_dark_theme(root)

        self.cfg = load_config()
        self.state_path: Path = DEFAULT_STATE_PATH
        self._login_thread: threading.Thread | None = None

        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(root)
        frm.pack(fill="x", **pad)

        ttk.Label(frm, text="Blackboard URL:").grid(row=0, column=0, sticky="w")
        self.bb_url = tk.StringVar(value=self.cfg.get("blackboard_url", "https://blackboard.sc.edu"))
        ttk.Entry(frm, textvariable=self.bb_url).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(frm, text="Server URL:").grid(row=1, column=0, sticky="w")
        self.server_url = tk.StringVar(value=self.cfg.get("server_url", "http://rohu-polaris.ts.net:8000"))
        ttk.Entry(frm, textvariable=self.server_url).grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(frm, text="Upload token:").grid(row=2, column=0, sticky="w")
        self.token = tk.StringVar(value=self.cfg.get("upload_token", ""))
        ttk.Entry(frm, textvariable=self.token, show="•").grid(row=2, column=1, sticky="ew", padx=4)

        ttk.Label(frm, text="Blackboard username:").grid(row=3, column=0, sticky="w")
        self.bb_user = tk.StringVar(value=self.cfg.get("blackboard_user", ""))
        ttk.Entry(frm, textvariable=self.bb_user).grid(row=3, column=1, sticky="ew", padx=4)

        ttk.Label(frm, text="Blackboard password:").grid(row=4, column=0, sticky="w")
        self.bb_pass = tk.StringVar(value=self.cfg.get("blackboard_pass", ""))
        ttk.Entry(frm, textvariable=self.bb_pass, show="•").grid(row=4, column=1, sticky="ew", padx=4)

        frm.columnconfigure(1, weight=1)

        # Buttons
        btns = ttk.Frame(root)
        btns.pack(fill="x", **pad)
        self.login_btn = ttk.Button(btns, text="1. Open browser & log in",
                                    command=self.on_login, style="Accent.TButton")
        self.login_btn.pack(side="left", padx=4)
        self.upload_btn = ttk.Button(btns, text="2. Send session to server",
                                     command=self.on_upload, state="disabled",
                                     style="Accent.TButton")
        self.upload_btn.pack(side="left", padx=4)
        ttk.Button(btns, text="Pick existing JSON…", command=self.on_pick_existing).pack(side="left", padx=4)
        ttk.Button(btns, text="Save config", command=self.on_save_config).pack(side="right", padx=4)

        # Status text
        ttk.Label(root, text="Log:", style="Muted.TLabel").pack(anchor="w", padx=10)
        self.log = scrolledtext.ScrolledText(
            root, height=20, wrap="word",
            bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER,
            font=("Cascadia Mono", 9) if root.tk.call("tk", "windowingsystem") == "win32" else ("Menlo", 10),
        )
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._info(f"Storage will be saved to: {self.state_path}")
        if DEFAULT_STATE_PATH.exists():
            self._info("Existing storage_state.json found — you can upload it directly without re-logging.")
            self.upload_btn.configure(state="normal")

    # ---- UI helpers ----
    def _info(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.root.update_idletasks()

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.login_btn.configure(state=state)
        # upload button gets re-enabled once we have a file
        if busy:
            self.upload_btn.configure(state="disabled")
        elif self.state_path.exists():
            self.upload_btn.configure(state="normal")

    # ---- Actions ----
    def on_save_config(self) -> None:
        save_config({
            "blackboard_url": self.bb_url.get().strip(),
            "server_url": self.server_url.get().strip(),
            "upload_token": self.token.get().strip(),
            "blackboard_user": self.bb_user.get().strip(),
            "blackboard_pass": self.bb_pass.get(),
        })
        self._info(f"Config saved to {CONFIG_PATH}")

    def on_pick_existing(self) -> None:
        p = filedialog.askopenfilename(
            title="Pick a storage_state.json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not p:
            return
        self.state_path = Path(p)
        self._info(f"Will upload: {self.state_path}")
        self.upload_btn.configure(state="normal")

    def on_login(self) -> None:
        if self._login_thread and self._login_thread.is_alive():
            return
        self._set_busy(True)
        self._info("Opening Chromium…")

        def runner():
            try:
                asyncio.run(self._do_login())
            except Exception as e:
                self.root.after(0, lambda: self._info(f"Login failed: {e}"))
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        self._login_thread = threading.Thread(target=runner, daemon=True)
        self._login_thread.start()

    async def _do_login(self) -> None:
        bb_url = self.bb_url.get().strip()
        if not bb_url:
            raise RuntimeError("Set the Blackboard URL first.")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto(bb_url)
            self.root.after(0, lambda: self._info(
                "Log in by hand, including Duo MFA (tick 'Remember this browser').\n"
                "When you see your Blackboard dashboard with your courses, "
                "close the browser window to save the session."
            ))
            # Wait until the user closes the browser window.
            try:
                await page.wait_for_event("close", timeout=0)
            except Exception:
                pass
            # Also handle the case where they close the whole context.
            try:
                await ctx.storage_state(path=str(self.state_path))
                self.root.after(0, lambda: self._info(f"Saved session → {self.state_path}"))
                self.root.after(0, lambda: self.upload_btn.configure(state="normal"))
            except Exception as e:
                self.root.after(0, lambda: self._info(f"Could not save session: {e}"))
            try:
                await browser.close()
            except Exception:
                pass

    def on_upload(self) -> None:
        server = self.server_url.get().strip().rstrip("/")
        token = self.token.get().strip()
        if not server:
            messagebox.showerror("Missing server URL", "Set the server URL first.")
            return
        if not token:
            messagebox.showerror("Missing token", "Set the upload token first.")
            return
        if not self.state_path.exists():
            messagebox.showerror("No session file", f"{self.state_path} does not exist yet.")
            return

        url = f"{server}/api/admin/session"
        size = os.path.getsize(self.state_path)
        bb_user = self.bb_user.get().strip()
        bb_pass = self.bb_pass.get()
        self._info(f"POST {url}  ({size} bytes, user={'<set>' if bb_user else '<empty>'})")
        try:
            with self.state_path.open("rb") as f:
                files = {"file": ("storage_state.json", f, "application/json")}
                data = {}
                if bb_user:
                    data["blackboard_user"] = bb_user
                if bb_pass:
                    data["blackboard_pass"] = bb_pass
                r = httpx.post(
                    url,
                    headers={"X-Upload-Token": token},
                    files=files,
                    data=data,
                    timeout=30.0,
                )
            if r.status_code == 200:
                self._info(f"OK — server says: {r.json()}")
                messagebox.showinfo("Uploaded", "Server accepted the session.")
            else:
                self._info(f"HTTP {r.status_code}: {r.text}")
                messagebox.showerror("Upload failed", f"HTTP {r.status_code}\n{r.text}")
        except Exception as e:
            self._info(f"Network error: {e}")
            messagebox.showerror("Network error", str(e))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
