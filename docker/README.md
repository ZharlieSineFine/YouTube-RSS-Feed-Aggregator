# PostgreSQL via Docker

This stack runs **only** the database. The Python app stays on your machine and connects to `localhost`.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2)

## Start

From the **repository root**:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Wait until healthy (`docker compose -f docker/docker-compose.yml ps`).

## Stop

```bash
docker compose -f docker/docker-compose.yml down
```

Data survives in the named volume `postgres_data`. Use `down -v` to wipe the database.

## Configure the app

Either set a full URL (recommended for production):

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_news_aggregator
```

Or set discrete variables (the app builds the URL when `DATABASE_URL` is unset):

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_news_aggregator
```

Then create tables:

```bash
uv run python -m app.db init
```

## Default credentials

Compose defaults match the examples above (`postgres` / `postgres`, database `ai_news_aggregator`). Override via shell env or a `docker/.env` file next to `docker-compose.yml` if you change `POSTGRES_*` for the container, **use the same values** in your app `.env`.

## Troubleshooting

### `failed to connect to the docker API at npipe://... dockerDesktopLinuxEngine`

The **Docker engine is not running** (or did not finish starting). The CLI is installed, but nothing is listening on Docker Desktop’s named pipe yet.

1. **Start Docker Desktop** from the Start menu and wait until it reports **Docker is running** (whale icon idle, not “Starting…”).
2. If it stays stuck: **Quit Docker Desktop** fully, start it again, or reboot after enabling WSL2 / virtualization in BIOS (Docker Desktop requirements).
3. Verify: `docker version` should exit **0** and show both **Client** and **Server** sections. Then retry `docker compose -f docker/docker-compose.yml up -d`.

**Without Docker:** use the app’s default **SQLite** database (unset `DATABASE_URL` and `POSTGRES_HOST`) or install PostgreSQL for Windows and point `DATABASE_URL` at it—Compose is optional.
