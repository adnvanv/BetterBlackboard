# BetterBlackboard

A personal Blackboard dashboard. Scrapes your enrolled (favorited) courses once a day, stores the data in SQLite, and renders a fast React UI showing upcoming assignments, recent grades (with colored circles by percentage), announcements, and calendar events — everything that's normally buried under tabs and clicks.

> **Personal use only.** Scraping Blackboard with your own credentials may violate your institution's terms of service. Do not run this against an account that isn't yours, and don't expose the dashboard to the public internet.

## What's in the box

```
┌───────────────────┐                          ┌──────────────────────┐
│ Laptop (Windows)  │                          │ Server (Pi / VPS)    │
│ login_client GUI  │── storage_state.json ──▶ │ Docker container     │
│ (Playwright +     │   over Tailscale          │  ├─ uvicorn (API)    │
│  Duo MFA, once    │                          │  ├─ APScheduler       │
│  per ~week)       │                          │  ├─ Playwright scrape │
└───────────────────┘                          │  └─ React UI (built)  │
                                               └──────────────────────┘
                                                        │
                                                        ▼
                                                  Blackboard
```

- **Server side** runs in one Docker container: FastAPI backend + built React frontend + headless Playwright. Scrapes daily at 5am local time. Exposes a dashboard at `http://<server>:8000/`.
- **Laptop side** is a tiny tkinter app (`login_client/`). You log in to Blackboard by hand once — through Duo MFA — and the GUI POSTs the resulting session cookies to the server. The server then scrapes unattended for as long as your school's "Remember this browser" / CAS session lasts (usually a week or two).
- **Connectivity** is whatever you want, but the project is designed for [Tailscale](https://tailscale.com/) so the dashboard is only reachable from your devices.

## Quick start (server)

You need Docker + `docker compose`. On a fresh Pi or Ubuntu box:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker     # or log out / back in
```

Clone, configure, run:

```bash
git clone https://github.com/<you>/betterblackboard.git
cd betterblackboard
cp .env.example .env
nano .env         # fill in — see "Configuration" below
mkdir data
docker compose up -d --build
```

First build pulls a ~1.5 GB Playwright base image, so it's slow the first time (~5–15 min on a Pi). After that, rebuilds are fast.

Verify:

```bash
curl http://localhost:8000/api/health
# {"status":"no-runs","coursesScraped":0,...}
```

Then go set up the laptop side (next section) and trigger your first scrape.

## Quick start (laptop)

The laptop bootstraps the session cookies the server reuses. See [`login_client/README.md`](login_client/README.md) for the full walkthrough — the short version on Windows:

1. Copy or clone the `login_client/` folder anywhere on your laptop.
2. Double-click **`BetterBlackboard-Login.bat`**. First run sets up its own venv, installs Playwright Chromium, and opens `config.json` in Notepad — fill in:
   ```json
   {
     "blackboard_url": "https://blackboard.<your-school>.edu",
     "server_url": "http://<server-tailscale-name>:8000",
     "upload_token": "<the BB_UPLOAD_TOKEN value from the server's .env>"
   }
   ```
3. After setup the GUI opens. Click **1. Open browser & log in** → log in to Blackboard (CAS + Duo, tick "Remember this browser") → close Chromium → click **2. Send session to server**.

Once that's done, hit **Scrape now** on `http://<server>:8000/` (or wait for 5am) and the dashboard fills in.

## Configuration

All server-side config lives in `.env`:

| Variable | What | Default |
|---|---|---|
| `BLACKBOARD_URL` | Your school's Blackboard URL | _(required)_ |
| `BLACKBOARD_USER` | Username, used as a fallback if the saved session can be auto-renewed via CAS | _(required)_ |
| `BLACKBOARD_PASS` | Password, same caveat | _(required)_ |
| `BB_UPLOAD_TOKEN` | Long random string that the `login_client` GUI sends in the `X-Upload-Token` header. Set this, paste the same value into `login_client/config.json`. Generate: `python3 -c "import secrets;print(secrets.token_urlsafe(32))"` | empty (upload endpoint disabled) |
| `BB_SCHEDULE` | Cron-style schedule for the daily auto-scrape (5 fields: `min hour dom mon dow`). Empty disables auto-scrape | `0 5 * * *` |
| `BB_TIMEZONE` | Timezone for the cron schedule | `America/New_York` |
| `BB_DB_PATH` | SQLite file path inside the container | `/data/betterblackboard.db` |
| `BB_STORAGE_STATE` | Session-cookie file inside the container | `/data/storage_state.json` |
| `BB_HEADLESS` | Run Chromium headless (always true on a server) | `true` |
| `BB_SCRAPE_CONCURRENCY` | Max courses scraped in parallel | `3` |

The `./data/` host folder is mounted into `/data` in the container, so both the DB and the session cookies persist across rebuilds.

## Daily life

- The dashboard auto-refreshes data every 60 seconds.
- The **Scrape now** button (top right) runs an on-demand scrape and shows live progress.
- A **5am** local-time cron runs a scrape every day (configurable via `BB_SCHEDULE`).
- When the saved session eventually expires, the dashboard shows a yellow "Session expired" pill. Open the login GUI on your laptop, re-do the Duo flow, click **Send session to server**, done.

## Useful Docker commands

```bash
docker compose logs -f web              # tail logs
docker compose exec web python -m scraper run   # manual scrape (CLI)
docker compose down                     # stop + remove containers (data/ preserved)
docker compose up -d --build            # rebuild after pulling new code
```

## Tweaking the scraper

Blackboard themes vary by institution. If something looks empty in the dashboard, the parser for that section probably doesn't match your school's exact HTML. Each area has its own small file in `scraper/`:

- `scraper/courses.py` — favorited course list (uses the `data-course-id` attribute on `<article>` tiles)
- `scraper/assignments.py`
- `scraper/announcements.py`
- `scraper/grades.py`
- `scraper/calendar.py`

To iterate locally, set `BB_HEADLESS=false` and run `python -m scraper run` from a venv on your laptop (not in Docker) so you can watch the browser drive itself. See the venv-based dev setup in the project root if you want to go that route.

## Project layout

```
betterblackboard/
├── app/                # FastAPI backend + APScheduler + progress tracking
│   ├── main.py         # routes (/api/dashboard, /api/scrape, /api/admin/session, SPA catch-all)
│   ├── views.py        # query helpers
│   ├── models.py       # SQLModel tables
│   └── progress.py     # in-memory scrape progress
├── scraper/            # Playwright + selectolax — one file per Blackboard area
├── frontend/           # React + Vite + Tailwind + shadcn/ui dashboard
├── login_client/       # Laptop-side tkinter GUI (run separately from the server)
├── deploy/             # Optional legacy systemd units (Docker is the recommended path)
├── Dockerfile          # Multi-stage: builds frontend then bundles with backend
├── docker-compose.yml
└── pyproject.toml
```

## License

MIT — see [`LICENSE`](LICENSE).
