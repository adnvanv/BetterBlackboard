# BetterBlackboard — Login Helper (laptop GUI)

A small tkinter app that lives on your laptop. It opens a real browser so you
can complete Blackboard's CAS + Duo MFA flow once, then ships the resulting
session cookies to your server (running the dockerized scraper) over your
private Tailscale network.

This exists because Duo MFA fundamentally requires a human + phone, which a
headless server can't provide. You log in here; the server reuses the cookies
until they expire (typically 1–4 weeks, depending on your school's Duo policy).

## Server-side prerequisites

On the machine running `docker compose up`:

1. Generate a long random token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Add it to the server's `.env` as `BB_UPLOAD_TOKEN=<that token>`
3. `docker compose up -d --build` (the upload endpoint is disabled until the token is set)
4. Confirm the server is reachable from your laptop: `curl http://<server>:8000/api/health`
   (use the Tailscale hostname for `<server>`)

## Laptop-side setup (one time)

```powershell
cd login_client
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium

Copy-Item config.example.json config.json
notepad config.json   # set blackboard_url, server_url, upload token,
                      # AND your Blackboard username + password
```

Username/password are shipped to the server alongside the session cookies
and stored in `data/credentials.json` there. They're used only when the
saved session expires *and* CAS still trusts your browser (silent re-login).
You no longer need to put `BLACKBOARD_USER`/`BLACKBOARD_PASS` in the server's
`.env` — the credentials.json overrides anything in `.env`.

## Usage

```powershell
.venv\Scripts\Activate.ps1
python app.py
```

In the window:

1. Click **1. Open browser & log in** — Chromium opens.
2. Log in normally: CAS username/password → approve Duo → **tick "Remember this browser"**.
3. Once you see your Blackboard dashboard with your courses, **close the Chromium window**. The app saves `storage_state.json` next to itself.
4. Click **2. Send session to server** — the file is POSTed to `/api/admin/session` with your token in the `X-Upload-Token` header. The server atomically replaces its own copy, and the next scheduled scrape picks up the new cookies.

That's it. Do this whenever the daily scrape starts failing with a "session expired" error in the server logs (Caddy/whatever shows `/api/health` red, or you spot it manually).

## Security notes

- Treat `config.json` and `storage_state.json` like passwords. Both grant Blackboard access.
- The upload endpoint requires the token via header — Tailscale already restricts access to your tailnet, but the token guards against accidents (e.g., another device on your tailnet you don't fully control).
- If you suspect the token is compromised, rotate it in the server's `.env`, `docker compose up -d`, and update `config.json`.
