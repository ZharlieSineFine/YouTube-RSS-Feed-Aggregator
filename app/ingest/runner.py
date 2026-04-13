"""
Ingestion runner - orchestrates all scrapers to fetch content from configured sources.

Incremental mode (default): returns only items published *after* the last successful run
(watermarks in .cache/ingest_state.json). First run: only items from FIRST_RUN_LOOKBACK_HOURS.

Usage:
    from app.ingest.runner import run_all

    results = run_all()
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Import scrapers
try:
    from .scrapers.youtube import YouTubeScraper, ChannelVideo
    from .scrapers.anthropic_news import AnthropicScraper, AnthropicArticle
    from .scrapers.openai_news import OpenAINewsScraper, OpenAIArticle
    from .ingest_state import (
        filter_incremental_published,
        load_state,
        merge_scalar_watermark,
        merge_youtube_watermarks,
        parse_iso,
        save_state,
    )
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.ingest.scrapers.youtube import YouTubeScraper, ChannelVideo
    from app.ingest.scrapers.anthropic_news import AnthropicScraper, AnthropicArticle
    from app.ingest.scrapers.openai_news import OpenAINewsScraper, OpenAIArticle
    from app.ingest.ingest_state import (
        filter_incremental_published,
        load_state,
        merge_scalar_watermark,
        merge_youtube_watermarks,
        parse_iso,
        save_state,
    )

# Import config
try:
    from .config import (
        FETCH_LOOKBACK_HOURS,
        FIRST_RUN_LOOKBACK_HOURS,
        HOURS_BACK_LEGACY,
        INCREMENTAL_INGEST,
        PERSIST_TO_DB,
        YOUTUBE_CHANNELS,
    )
except ImportError:
    from config import (
        FETCH_LOOKBACK_HOURS,
        FIRST_RUN_LOOKBACK_HOURS,
        HOURS_BACK_LEGACY,
        INCREMENTAL_INGEST,
        PERSIST_TO_DB,
        YOUTUBE_CHANNELS,
    )


def fetch_youtube(
    channel_ids: List[str],
    hours_back: int,
    state: Dict[str, Any] | None,
    incremental: bool,
) -> Tuple[List[ChannelVideo], Dict[str, Any] | None]:
    """Fetch videos from all configured YouTube channels."""
    scraper = YouTubeScraper()
    all_videos: List[ChannelVideo] = []
    now = datetime.now(timezone.utc)
    new_by_channel: Dict[str, List[ChannelVideo]] = {ch: [] for ch in channel_ids}

    for channel_id in channel_ids:
        print(f"\n[YouTube] Fetching: {channel_id}...")
        try:
            raw = scraper.scrape_channel(channel_id, hours_back=hours_back)
            if incremental and state is not None:
                wm = parse_iso((state.get("youtube") or {}).get(channel_id))
                new = filter_incremental_published(
                    raw,
                    lambda v: v.published_at,
                    wm,
                    now,
                    FIRST_RUN_LOOKBACK_HOURS,
                )
                new_by_channel[channel_id] = new
                all_videos.extend(new)
                print(f"  {len(new)} new since last run (of {len(raw)} in feed window)")
            else:
                all_videos.extend(raw)
                print(f"  Found {len(raw)} videos")
        except Exception as e:
            print(f"  Error: {e}")

    if incremental and state is not None:
        state = merge_youtube_watermarks(state, channel_ids, new_by_channel)

    return all_videos, state


def fetch_anthropic(
    hours_back: int,
    state: Dict[str, Any] | None,
    incremental: bool,
) -> Tuple[List[AnthropicArticle], Dict[str, Any] | None]:
    """Fetch articles from all Anthropic RSS feeds with markdown content."""
    print("\n[Anthropic] Fetching all feeds...")
    scraper = AnthropicScraper()
    now = datetime.now(timezone.utc)

    try:
        raw = scraper.fetch_articles_with_content(hours_back=hours_back)
        if incremental and state is not None:
            wm = parse_iso(state.get("anthropic"))
            new = filter_incremental_published(
                raw,
                lambda a: a.published_at,
                wm,
                now,
                FIRST_RUN_LOOKBACK_HOURS,
            )
            print(f"  {len(new)} new since last run (of {len(raw)} in feed window)")
            state = merge_scalar_watermark(state, "anthropic", new, lambda a: a.published_at)
            return new, state
        print(f"  Found {len(raw)} articles with content")
        return raw, state
    except Exception as e:
        print(f"  Error: {e}")
        return [], state


def fetch_openai(
    hours_back: int,
    state: Dict[str, Any] | None,
    incremental: bool,
) -> Tuple[List[OpenAIArticle], Dict[str, Any] | None]:
    """Fetch articles from OpenAI news page with markdown content."""
    print("\n[OpenAI] Fetching news...")
    scraper = OpenAINewsScraper()
    now = datetime.now(timezone.utc)

    try:
        raw = scraper.fetch_articles_with_content(hours_back=hours_back)
        if incremental and state is not None:
            wm = parse_iso(state.get("openai"))
            new = filter_incremental_published(
                raw,
                lambda a: a.published_at,
                wm,
                now,
                FIRST_RUN_LOOKBACK_HOURS,
            )
            print(f"  {len(new)} new since last run (of {len(raw)} in feed window)")
            state = merge_scalar_watermark(state, "openai", new, lambda a: a.published_at)
            return new, state
        print(f"  Found {len(raw)} articles with content")
        return raw, state
    except Exception as e:
        print(f"  Error: {e}")
        return [], state


def run_all(
    hours_back: int | None = None,
    incremental: bool | None = None,
) -> Dict[str, List[Any]]:
    """
    Run all scrapers and return collected content.

    Args:
        hours_back: Legacy only — when INCREMENTAL_INGEST is False, rolling window in hours.
        incremental: Override INCREMENTAL_INGEST from config when not None.

    Returns:
        Dictionary with keys 'youtube', 'anthropic', 'openai'.
    """
    use_incremental = INCREMENTAL_INGEST if incremental is None else incremental
    hb = FETCH_LOOKBACK_HOURS if use_incremental else (hours_back if hours_back is not None else HOURS_BACK_LEGACY)

    print("=" * 60)
    if use_incremental:
        print("Running ingestion (incremental — new since last run)")
        print(f"  Feed query window: {FETCH_LOOKBACK_HOURS}h | First-run bootstrap: {FIRST_RUN_LOOKBACK_HOURS}h")
        print(f"  State: .cache/ingest_state.json")
    else:
        print(f"Running ingestion (rolling window: last {hb} hours)")
    print("=" * 60)

    state: Dict[str, Any] | None = load_state() if use_incremental else None

    results: Dict[str, List[Any]] = {}
    yt, state = fetch_youtube(YOUTUBE_CHANNELS, hb, state, use_incremental)
    results["youtube"] = yt
    ant, state = fetch_anthropic(hb, state, use_incremental)
    results["anthropic"] = ant
    oa, state = fetch_openai(hb, state, use_incremental)
    results["openai"] = oa

    if use_incremental and state is not None:
        save_state(state)

    if PERSIST_TO_DB:
        try:
            try:
                from app.db.store import persist_ingest_results
            except ImportError:
                import sys

                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from app.db.store import persist_ingest_results

            n_new = persist_ingest_results(results)
            print(f"\nDatabase: persisted ingest results ({n_new} new row(s)).")
        except Exception as e:
            print(f"\nDatabase: persist failed: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  YouTube videos:     {len(results['youtube'])}")
    print(f"  Anthropic articles: {len(results['anthropic'])}")
    print(f"  OpenAI articles:    {len(results['openai'])}")
    print(f"  Total items:        {sum(len(v) for v in results.values())}")

    return results


if __name__ == "__main__":
    results = run_all()

    if results["youtube"]:
        print("\n" + "=" * 60)
        print("YOUTUBE VIDEOS")
        print("=" * 60)
        for video in results["youtube"]:
            print(f"\nTitle: {video.title}")
            print(f"Published: {video.published_at}")
            print(f"URL: {video.url}")
            if video.transcript:
                print(f"Transcript ({len(video.transcript)} chars):")
                print(f"  {video.transcript[:300]}...")
            else:
                print("Transcript: Not available")

    if results["anthropic"]:
        print("\n" + "=" * 60)
        print("ANTHROPIC ARTICLES")
        print("=" * 60)
        for article in results["anthropic"]:
            print(f"\nTitle: {article.title}")
            print(f"Published: {article.published_at}")
            print(f"URL: {article.url}")
            if article.content:
                print(f"Content ({len(article.content)} chars):")
                print(f"  {article.content[:300]}...")
            else:
                print("Content: Not available")

    if results["openai"]:
        print("\n" + "=" * 60)
        print("OPENAI ARTICLES")
        print("=" * 60)
        for article in results["openai"]:
            print(f"\nTitle: {article.title}")
            print(f"Published: {article.published_at}")
            print(f"URL: {article.url}")
            if article.content:
                print(f"Content ({len(article.content)} chars):")
                print(f"  {article.content[:300]}...")
            else:
                print("Content: Not available")
