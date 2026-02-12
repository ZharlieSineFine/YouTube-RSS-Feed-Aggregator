# Project Structure

## Directory Tree

```
ai-news-aggregator-test/
├── app/
│   └── ingest/
│       ├── config.py              # Configuration (HOURS_BACK, YOUTUBE_CHANNELS)
│       ├── runner.py              # Main orchestrator - runs all scrapers
│       └── scrapers/
│           ├── cache.py           # Caching utility for HTTP responses
│           ├── youtube.py         # YouTubeScraper (RSS + yt-dlp transcripts)
│           ├── anthropic_news.py  # AnthropicScraper (3 RSS feeds + markdown)
│           ├── openai_news.py     # OpenAINewsScraper (HTML scraping + markdown)
│           └── substack.py        # SubstackScraper (RSS feeds)
├── .cache/                        # Cached HTTP responses (auto-generated)
├── main.py                        # Application entry point
├── pyproject.toml                 # Dependencies (uv)
├── README.md                      # Project overview
└── YOUTUBE_USAGE.md               # YouTube scraper documentation
```

## Architecture Diagram

```mermaid
flowchart TB
    subgraph sources [External Sources]
        YT[YouTube RSS Feeds]
        AN[Anthropic RSS Feeds]
        OA[OpenAI News Page]
        SS[Substack RSS]
    end

    subgraph scrapers [Scrapers Layer]
        YTS[YouTubeScraper]
        ANS[AnthropicScraper]
        OAS[OpenAINewsScraper]
        SSS[SubstackScraper]
    end

    subgraph cache [Caching Layer]
        C[cache.py]
        CF[".cache/ files"]
    end

    subgraph models [Pydantic Models]
        CV[ChannelVideo]
        TR[Transcript]
        AA[AnthropicArticle]
        OAA[OpenAIArticle]
        SA[SubstackArticle]
    end

    subgraph runner [Orchestration]
        R[runner.py]
        CFG[config.py]
    end

    YT --> YTS
    AN --> ANS
    OA --> OAS
    SS --> SSS

    YTS <--> C
    ANS <--> C
    OAS <--> C
    SSS <--> C
    C <--> CF

    YTS --> CV
    YTS --> TR
    ANS --> AA
    OAS --> OAA
    SSS --> SA

    CFG --> R
    R --> YTS
    R --> ANS
    R --> OAS

    CV --> R
    AA --> R
    OAA --> R
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Runner as runner.py
    participant Config as config.py
    participant YT as YouTubeScraper
    participant AN as AnthropicScraper
    participant OA as OpenAINewsScraper
    participant Cache as cache.py
    participant Web as External APIs

    User->>Runner: run_all(hours_back)
    Runner->>Config: Load YOUTUBE_CHANNELS, HOURS_BACK
    
    par Fetch YouTube
        Runner->>YT: scrape_channel(channel_id)
        YT->>Cache: get_cached(rss_url)
        alt Cache Hit
            Cache-->>YT: cached content
        else Cache Miss
            YT->>Web: fetch RSS feed
            Web-->>YT: XML data
            YT->>Cache: set_cached(content)
        end
        YT->>YT: Filter by date
        YT->>YT: Get transcripts via yt-dlp
        YT-->>Runner: List of ChannelVideo
    and Fetch Anthropic
        Runner->>AN: fetch_articles_with_content()
        AN->>Cache: Check cache for feeds
        AN->>Web: Fetch RSS + HTML
        AN->>AN: Convert to markdown
        AN-->>Runner: List of AnthropicArticle
    and Fetch OpenAI
        Runner->>OA: fetch_articles_with_content()
        OA->>Cache: Check cache for HTML
        OA->>Web: Scrape news page
        OA->>OA: Convert to markdown
        OA-->>Runner: List of OpenAIArticle
    end
    
    Runner-->>User: Combined results dict
```

## Component Details

### Scrapers

| Scraper | Source Type | Output Model | Content |
|---------|-------------|--------------|---------|
| `YouTubeScraper` | RSS + yt-dlp | `ChannelVideo`, `Transcript` | Video metadata + full transcript |
| `AnthropicScraper` | 3 RSS feeds | `AnthropicArticle` | News, Engineering, Research articles + markdown |
| `OpenAINewsScraper` | HTML scraping | `OpenAIArticle` | Blog articles + markdown content |
| `SubstackScraper` | RSS feed | `SubstackArticle` | Newsletter articles |

### Configuration (`config.py`)

```python
HOURS_BACK = 300        # How far back to look for content
YOUTUBE_CHANNELS = [    # List of channel IDs to monitor
    "UC11aHtNnc5bEPLI4jf6mnYg",
]
```

### Caching System

- Location: `.cache/` directory
- Format: MD5 hash of URL as filename
- Suffixes: `.xml` (RSS), `.html` (web pages), `.vtt` (transcripts)
- Control: `USE_CACHE` environment variable (default: enabled)

## Usage

```bash
# Run the full ingestion pipeline
python -m app.ingest.runner

# Or run directly
python app/ingest/runner.py
```

## Future Components (Planned)

```
app/
├── agent/                 # LLM summarization layer
│   └── system_prompt.py   # User persona/insights prompt
├── db/                    # Database layer
│   ├── models.py          # SQLAlchemy models (Source, Article)
│   └── session.py         # Database connection
├── digest/                # Daily digest generation
│   └── email.py           # HTML email formatting + SMTP
docker/
└── docker-compose.yml     # PostgreSQL container setup
```
