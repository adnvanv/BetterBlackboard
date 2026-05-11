# Legacy systemd units

These were the pre-Docker deployment path: install Python + Playwright on a VPS
directly, run uvicorn under systemd, and use a systemd timer to fire the daily
scrape. Kept for reference if you want to run BetterBlackboard outside Docker.

**Not maintained.** The supported deployment is `docker compose up -d --build`
from the project root — see the top-level `README.md`. The Docker image
already includes:

- uvicorn as the long-running web service
- APScheduler as the in-process cron replacement (default `0 5 * * *`)

…so you don't need either of these unit files in a normal install.

If you want to use these anyway, refer to git history before the Docker switch
for the original install instructions, or open an issue.
