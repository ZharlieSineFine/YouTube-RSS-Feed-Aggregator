# AI News Aggregator

A Python pipeline that **ingests** AI-related content from configured sources, **stores** it in a relational database, **summarizes** articles with an LLM (local Ollama or OpenAI), and **emails** a bilingual HTML digest on a schedule you control.

It is a small end-to-end example of: web/RSS ingestion, caching, SQLAlchemy persistence, LLM batch summarization, and SMTP delivery—suitable to discuss in interviews as a personal “news briefing” or content-intelligence side project.

---

## What it does

1. **Ingest** — Fetches new items since the last run using **incremental watermarks** (state in `.cache/ingest_state.json`), plus HTTP caching for development. Sources are **configured in code** today:
   - **YouTube** — channel RSS and transcripts (via yt-dlp; disk cache can skip repeat YouTube calls).
   - **Anthropic** — RSS and article pages.
   - **OpenAI** — news listing and article pages.

2. **Persist** — Upserts sources and articles into **SQLite** (default, `data/aggregator.db`) or **PostgreSQL** (`DATABASE_URL` / `POSTGRES_*`; optional [`docker/docker-compose.yml`](docker/docker-compose.yml) for local Postgres).

3. **Summarize** — The **agent** fills `Article.summary` and optionally `Article.summary_zh` from `AGENT_SUMMARY_LANGUAGES` (default setup uses **Ollama** with a local model; **OpenAI** is optional).

4. **Deliver** — Builds a multipart HTML/plain digest and sends it over SMTP. Recipients can be split into **English** and **Chinese** lists. If a scheduled run finds **no new items** from any source, it sends a short **no-updates** message instead of running the full agent and digest.

The daily entrypoint is:

```bash
uv run python -m app.daily
```

That runs ingest, then either the no-updates path or `app.agent` (capped by `AGGREGATOR_AGENT_LIMIT`) plus `app.digest send`. For manual steps, see **CLI reference** below.

---

## Architecture (high level)

| Layer | Role |
|--------|------|
| `app/ingest` | Scrapers + `runner.run_all()` orchestration; incremental mode and optional DB persist. |
| `app/db` | SQLAlchemy models (`Source`, `Article`), sessions, ingest upserts. |
| `app/agent` | LLM summaries into article fields; OpenAI-compatible client (Ollama or cloud). |
| `app/digest` | Load summarized rows, render email, SMTP; no-updates template when ingest is empty. |
| `app/daily` | Single command that wires ingest → branch → agent/digest. |

More detail: [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md).

---

## Tech stack

| Area | Choices |
|------|---------|
| Language | Python 3.13+ |
| Dependencies | `uv` + `pyproject.toml` |
| ORM / DB | SQLAlchemy 2; SQLite default; PostgreSQL via psycopg optional |
| Ingestion | `requests`, `feedparser`, BeautifulSoup; YouTube via `yt-dlp` |
| LLM | OpenAI SDK-compatible API → **Ollama** (default) or **OpenAI** |
| Email | `smtplib` (STARTTLS or SSL) |

Optional: `docker compose` in `docker/` for a local Postgres instance ([`docker/README.md`](docker/README.md)).

---

## Quick start

**Prerequisites:** [uv](https://github.com/astral-sh/uv), Git. For default summarization, [Ollama](https://ollama.com/) locally (see `env.example`). For PostgreSQL instead of SQLite, use Docker or a hosted DB per [`docker/README.md`](docker/README.md).

```bash
git clone <your-fork-or-repo-url>
cd ai-news-aggregator-test
uv sync
cp env.example .env
# Edit .env: optional DATABASE_URL; Ollama/OpenAI; SMTP; DIGEST_*; optional DIGEST_SINCE_HOURS=24
```

Initialize the database schema (SQLite by default, or Postgres if configured):

```bash
uv run python -m app.db init
```

Run the full daily pipeline once:

```bash
uv run python -m app.daily
```

---

## CLI reference

| Command | Purpose |
|---------|---------|
| `uv run python -m app.daily` | Ingest → no-updates email **or** agent + digest send. |
| `uv run python -m app.ingest.runner` | Ingest only (prints summary; persists if `PERSIST_TO_DB=1`). |
| `uv run python -m app.agent -n 50` | Summarize up to N pending articles (`AGGREGATOR_AGENT_LIMIT` mirrors this). |
| `uv run python -m app.digest preview` | Print digest text without sending. |
| `uv run python -m app.digest send` | Send digest email (requires SMTP env vars). |

---

## Configuration notes

- **`.env`** — Copy from `env.example`. Default database is **SQLite** under `data/`; set `DATABASE_URL` or `POSTGRES_*` for PostgreSQL. Never commit secrets.
- **Incremental ingest** — Controlled in `app/ingest/config.py` (`INCREMENTAL_INGEST`, lookback hours). Deleting `.cache/ingest_state.json` resets “first run” behavior for watermarks.
- **Digest window** — `DIGEST_SINCE_HOURS` (e.g. `24`) filters by `published_at` (UTC). By default the effective cutoff is the **earlier** of a rolling window and **midnight UTC at the start of yesterday**, so date-only timestamps are not skipped; set `DIGEST_SINCE_STRICT_ROLLING=1` for a strict rolling window only.
- **Windows Task Scheduler** — [`docs/WINDOWS_SCHEDULER.md`](docs/WINDOWS_SCHEDULER.md) describes `scripts/run_daily_chain.ps1` and environment variables.

---

## License and scope

This repository is a personal / portfolio project. Source lists and prompts are examples; adjust `app/ingest/config.py` and agent settings for your own sources and tone.
