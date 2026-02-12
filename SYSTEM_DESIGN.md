# AI News Aggregator - System Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SOURCES                                │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│  YouTube RSS    │  Anthropic RSS  │  OpenAI News    │  Substack RSS         │
│  (Channel Feed) │  (3 Feeds)      │  (HTML Scrape)  │  (Newsletter Feed)    │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SCRAPERS LAYER                                  │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ YouTubeScraper  │ AnthropicScraper│ OpenAINewsScraper│ SubstackScraper      │
│ ─────────────── │ ─────────────── │ ─────────────────│ ───────────────────  │
│ • RSS parsing   │ • News feed     │ • Playwright     │ • RSS parsing        │
│ • yt-dlp        │ • Engineering   │ • HTML scraping  │ • Date filtering     │
│   transcripts   │ • Research      │ • Date extraction│                      │
│                 │ • Docling→MD    │ • Docling→MD     │                      │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
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
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ ChannelVideo    │ AnthropicArticle│ OpenAIArticle   │ SubstackArticle       │
│ ─────────────── │ ─────────────── │ ─────────────── │ ───────────────────── │
│ • title         │ • title         │ • title         │ • title               │
│ • url           │ • url           │ • url           │ • url                 │
│ • video_id      │ • guid          │ • published_at  │ • guid                │
│ • published_at  │ • published_at  │ • description   │ • published_at        │
│ • description   │ • description   │ • content (MD)  │ • description         │
│ • channel_id    │ • category      │                 │ • content             │
│ • transcript    │ • feed_type     │                 │ • author              │
│                 │ • content (MD)  │                 │                       │
│ Transcript      │                 │                 │                       │
│ ─────────────── │                 │                 │                       │
│ • text          │                 │                 │                       │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         └─────────────────┴────────┬────────┴───────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATION                                   │
│                              (runner.py)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  run_all(hours_back=24) → {                                                 │
│      'youtube': List[ChannelVideo],                                         │
│      'anthropic': List[AnthropicArticle],                                   │
│      'openai': List[OpenAIArticle]                                          │
│  }                                                                           │
│                                                                              │
│  Configuration (config.py):                                                  │
│  • HOURS_BACK = 300                                                         │
│  • YOUTUBE_CHANNELS = ["UC11aHtNnc5bEPLI4jf6mnYg", ...]                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FUTURE COMPONENTS (Planned)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Database   │    │    Agent     │    │    Email     │                   │
│  │  (Postgres)  │    │   (OpenAI)   │    │   (SMTP)     │                   │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤                   │
│  │ • Source     │    │ • System     │    │ • HTML       │                   │
│  │ • Article    │    │   Prompt     │    │   Digest     │                   │
│  │ • Summary    │    │ • Summarize  │    │ • Daily      │                   │
│  │ • Digest     │    │ • Insights   │    │   Schedule   │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                              │
│  Docker: PostgreSQL container for persistent storage                         │
│  Deploy: Render with 24-hour scheduled runs                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘


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
│  YouTube RSS    │    │  GitHub RSS     │    │  openai.com     │
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
│   └── ingest/
│       ├── config.py              # HOURS_BACK, YOUTUBE_CHANNELS
│       ├── runner.py              # Main orchestrator
│       └── scrapers/
│           ├── cache.py           # HTTP response caching
│           ├── youtube.py         # YouTubeScraper class
│           ├── anthropic_news.py  # AnthropicScraper class
│           ├── openai_news.py     # OpenAINewsScraper class
│           └── substack.py        # SubstackScraper class
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
│  Future:                                                         │
│  ├── Database:   PostgreSQL + SQLAlchemy                        │
│  ├── LLM:        OpenAI API                                     │
│  ├── Email:      smtplib (SMTP)                                 │
│  └── Deploy:     Docker + Render                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
