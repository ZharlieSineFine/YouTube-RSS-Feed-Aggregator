# Windows Task Scheduler — daily ingest / summarize / digest

The scheduled script runs **`uv run python -m app.daily`**, which:

1. Runs **incremental ingest** (only items newer than the last watermark in `.cache/ingest_state.json`).
2. If **no new items** from any source: sends a short **“no updates”** email (English: *We have no updates for today.*; Chinese lists get *今日暂无更新。*). Agent and digest are skipped.
3. If there **are** new items: runs the **agent** (bounded by `AGGREGATOR_AGENT_LIMIT`), then **`python -m app.digest send`**.

Set **`DIGEST_SINCE_HOURS=24`** in `.env` so the digest only includes articles published in roughly the last day, matching a **once-per-24-hours** schedule. Incremental ingest already limits each run to *new* rows; the digest window is separate and filters what appears in the email.

## Prerequisites

1. **Repository path** fixed (e.g. `C:\Cursor_Projects\ai-news-aggregator-test`).
2. **`uv`** on `PATH` (same as in your interactive shell).
3. **`.env`** in the repo root with agent settings (default: Ollama + `qwen3:14b`; see `env.example`), digest SMTP settings, recipient lists, and database settings as needed.
4. If using **Docker + PostgreSQL**: Docker Desktop running, `docker compose -f docker/docker-compose.yml up -d`, and `DATABASE_URL` or `POSTGRES_*` set before the task runs.

## Create the scheduled task

1. Open **Task Scheduler** → **Create Task…** (not Basic Task, so we can tune security).
2. **General**
   - Name: `AI News Aggregator daily` (or any label).
   - Select **Run whether user is logged on or not** if you want it when logged out (stores your password).
   - Optionally: **Run with highest privileges** — not required for this script.
3. **Triggers** → **New…**
   - Daily (or your preferred cadence), set time (e.g. 07:00).
4. **Actions** → **New…**
   - Action: **Start a program**
   - Program/script: `powershell.exe`
   - Add arguments:

     ```text
     -NoProfile -ExecutionPolicy Bypass -File "C:\Cursor_Projects\ai-news-aggregator-test\scripts\run_daily_chain.ps1"
     ```

     Adjust the path to match your clone.

5. **Conditions** — optional: uncheck **Start only if on AC power** for laptops if you want runs on battery.
6. **Settings** — optional: **If the task fails, restart every…** with a short interval.

Confirm the task runs: right-click → **Run**, then check `data\scheduler_last_run.log` in the repo.

## Turn the schedule off (always reversible)

| Method | What it does |
|--------|----------------|
| **Disable task** | Task Scheduler → your task → right-click → **Disable**. Re-enable anytime. |
| **Remove trigger** | Edit the task and delete the trigger (task stays, never fires). |
| **`schedule_disabled` file** | Create an empty file named `schedule_disabled` in the **repo root** (same folder as `pyproject.toml`). The script exits immediately without running ingest/agent/digest. Delete the file to resume. This file is listed in `.gitignore` so it stays local. |

## Environment overrides

- **`DIGEST_SINCE_HOURS`** — e.g. `24` for a daily digest window (recommended with a 24h trigger).
- **`AGGREGATOR_AGENT_LIMIT`** — max articles the agent processes when there are new items (default `50`). Raise if your daily ingest is larger.

## English + Chinese summaries and split inboxes

In `.env`:

```env
AGENT_SUMMARY_LANGUAGES=en,zh-cn
DIGEST_EMAIL_TO_EN=you@example.com,peer2@example.com
DIGEST_EMAIL_TO_ZH=reader1@example.com,reader2@example.com
```

Re-summarize existing rows with `uv run python -m app.agent --all --force` once (uses API quota) after changing languages.
