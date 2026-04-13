# AI News Aggregator - System Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SOURCES                                │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│  YouTube RSS         │  Anthropic RSS       │  OpenAI News                  │
│  (Channel Feed)      │  (3 Feeds)           │  (HTML Scrape)                │
└──────────┬───────────┴──────────┬───────────┴──────────┬────────────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SCRAPERS LAYER                                  │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ YouTubeScraper       │ AnthropicScraper     │ OpenAINewsScraper             │
│ ──────────────────── │ ──────────────────── │ ───────────────────────────── │
│ • RSS parsing        │ • News feed          │ • Playwright                  │
│ • yt-dlp transcripts │ • Engineering        │ • HTML scraping               │
│                      │ • Research           │ • Date extraction             │
│                      │ • Docling→MD         │ • Docling→MD                  │
└──────────┬───────────┴──────────┬───────────┴──────────┬────────────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CACHING LAYER                                   │
│                              (cache.py)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  .cache/                                                                     │
│  ├── {md5_hash}.xml   ← RSS feeds                                           │
│  ├── {md5_hash}.html  ← Web pages                                           │
│  └── {md5_hash}.vtt   ← YouTube transcripts                                 │
│                                                                              │
│  Environment: USE_CACHE=1 (enabled by default)                              │
└─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA MODELS (Pydantic)                          │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ChannelVideo         │ AnthropicArticle     │ OpenAIArticle                 │
│ ──────────────────── │ ──────────────────── │ ───────────────────────────── │
│ • title              │ • title              │ • title                       │
│ • url                │ • url                │ • url                         │
│ • video_id           │ • guid               │ • published_at                │
│ • published_at       │ • published_at       │ • description                 │
│ • description        │ • description        │ • content (MD)                │
│ • channel_id         │ • category           │                               │
│ • transcript         │ • feed_type          │                               │
│                      │ • content (MD)       │                               │
│ Transcript           │                      │                               │
│ ──────────────────── │                      │                               │
│ • text               │                      │                               │
└──────────┬───────────┴──────────┬───────────┴──────────┬────────────────────┘
           │                      │                      │
           └──────────────────────┴──────────┬───────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATION                                   │
│                              (runner.py)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  run_all() → {                                                               │
│      'youtube': List[ChannelVideo],                                         │
│      'anthropic': List[AnthropicArticle],                                   │
│      'openai': List[OpenAIArticle]                                          │
│  }                                                                           │
│                                                                              │
│  Configuration (config.py): incremental windows, YOUTUBE_CHANNELS,          │
│  PERSIST_TO_DB, DATABASE_URL (optional Postgres)                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PERSISTENCE (app/db)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  SQLAlchemy: Source, Article  |  store.persist_ingest_results()            │
│  Default: sqlite:///data/aggregator.db  |  URL-keyed upsert                  │
└─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FUTURE COMPONENTS (Planned)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐                                       │
│  │    Agent     │    │    Email     │                                       │
│  │   (OpenAI)   │    │   (SMTP)     │                                       │
│  ├──────────────┤    ├──────────────┤                                       │
│  │ • System     │    │ • HTML       │                                       │
│  │   Prompt     │    │   Digest     │                                       │
│  │ • Summarize  │    │ • Daily      │                                       │
│  │ • Insights   │    │   Schedule   │                                       │
│  └──────────────┘    └──────────────┘                                       │
│                                                                              │
│  Docker: PostgreSQL container for production storage                         │
│  Deploy: Render with 24-hour scheduled runs                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```


## Data Flow Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │ python runner.py
     ▼
┌─────────────────┐     ┌─────────────────┐
│   config.py     │────▶│    runner.py    │
│ • HOURS_BACK    │     │ • fetch_youtube │
│ • CHANNELS      │     │ • fetch_anthropic│
└─────────────────┘     │ • fetch_openai  │
                        └────────┬────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ YouTubeScraper  │    │AnthropicScraper │    │OpenAINewsScraper│
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   cache.py      │    │   cache.py      │    │   cache.py      │
│ get/set_cached  │    │ get/set_cached  │    │ get/set_cached  │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  YouTube RSS    │    │  Anthropic RSS  │    │  openai.com     │
│  + yt-dlp API   │    │  (3 feeds)      │    │  (Playwright)   │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │                      ▼                      │
         │             ┌─────────────────┐             │
         │             │     Docling     │◀────────────┘
         │             │   URL → MD      │
         │             └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Combined Results                          │
│  {                                                               │
│    'youtube': [ChannelVideo(title, transcript, ...)],           │
│    'anthropic': [AnthropicArticle(title, content, ...)],        │
│    'openai': [OpenAIArticle(title, content, ...)]               │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```


## File Structure

```
ai-news-aggregator-test/
│
├── app/
│   ├── db/
│   │   ├── models.py              # SQLAlchemy Source, Article
│   │   ├── session.py             # Engine, init_db
│   │   └── store.py               # persist_ingest_results
│   └── ingest/
│       ├── config.py              # Ingest + PERSIST_TO_DB, YOUTUBE_CHANNELS
│       ├── runner.py              # Main orchestrator
│       └── scrapers/
│           ├── cache.py           # HTTP response caching
│           ├── youtube.py         # YouTubeScraper class
│           ├── anthropic_news.py  # AnthropicScraper class
│           └── openai_news.py     # OpenAINewsScraper class
│
├── .cache/                        # Cached responses (auto-generated)
│   ├── *.xml                      # RSS feeds
│   ├── *.html                     # Web pages
│   └── *.vtt                      # Transcripts
│
├── main.py                        # Entry point
├── pyproject.toml                 # Dependencies
├── README.md                      # Overview
├── PROJECT_STRUCTURE.md           # Detailed structure
└── SYSTEM_DESIGN.md               # This file
```


## Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        DEPENDENCIES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Core:           Python 3.11+                                   │
│  Package Mgmt:   uv (ultra-fast)                                │
│                                                                  │
│  Data Models:    Pydantic v2                                    │
│  RSS Parsing:    feedparser                                     │
│  HTTP Client:    requests                                       │
│  Browser:        Playwright (headless Chromium)                 │
│  Transcripts:    yt-dlp                                         │
│  MD Conversion:  docling                                        │
│                                                                  │
│  Persistence:    SQLAlchemy 2 (SQLite default; Postgres via URL) │
│  Future:                                                         │
│  ├── LLM:        OpenAI API                                     │
│  ├── Email:      smtplib (SMTP)                                 │
│  └── Deploy:     Docker + Render                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
