# Personal Content Intelligence Agent
A high-performance, containerized Python framework designed to aggregate, synthesize, and deliver personalized insights from a curated list of digital sources. This system automates the bridge between high-volume content (YouTube, Blogs, RSS) and actionable intelligence.

## 🚀 Key Capabilities
Agnostic Ingestion: Seamlessly track any YouTube channel via RSS and extract full-text content from any web-based blog or article.

Custom Persona Synthesis: Leverages an agentic LLM layer that interprets raw data through the lens of a specific user-defined system prompt to generate high-signal summaries.

Structured Data Persistence: Organizes information into a relational PostgreSQL schema (Sources vs. Articles) using SQLAlchemy for easy querying and historical tracking.

Scheduled Intelligence: Designed for 24-hour execution cycles, culminating in a professionally formatted HTML digest sent via email.

Modern Infrastructure: Built with uv for ultra-fast dependency management; optional Docker Compose for PostgreSQL.

## 🛠️ Technical Stack
Language: Python 
Package Management: uv (Fastest-in-class) 
Database: SQLite by default, or PostgreSQL (via Docker or any hosted instance) 
ORM: SQLAlchemy 
Containers: Docker Compose ships only the Postgres service (see `docker/README.md`) 
Integrations: **Ollama** (default summarization, e.g. Qwen3 14B), optional OpenAI API; SMTP (email)

## Database: SQLite vs PostgreSQL

- **Default:** no env needed — data lives in `data/aggregator.db` (gitignored).
- **PostgreSQL (Docker):** from the repo root, `docker compose -f docker/docker-compose.yml up -d`, then set `DATABASE_URL` or `POSTGRES_*` as in `env.example`, and run `uv run python -m app.db init`.
- **Migrating data** from SQLite to Postgres is not automated; export/import or re-ingest if you switch.

## Scheduling (Windows) and split English / Chinese digests

- **Task Scheduler:** see [`docs/WINDOWS_SCHEDULER.md`](docs/WINDOWS_SCHEDULER.md) for a daily **ingest → summarize → email** chain and how to turn it off.
- **Two languages:** set `AGENT_SUMMARY_LANGUAGES=en,zh-cn` so the agent fills **`Article.summary`** (English) and **`Article.summary_zh`** (Chinese). Use **`DIGEST_EMAIL_TO_EN`** and **`DIGEST_EMAIL_TO_ZH`** so each group receives the matching digest. Re-summarize with `uv run python -m app.agent --all --force` after changing languages.
