"""
Ingestion runner - orchestrates all scrapers to fetch content from configured sources.

Usage:
    from app.ingest.runner import run_all
    
    results = run_all(hours_back=24)
    print(f"YouTube videos: {len(results['youtube'])}")
    print(f"Anthropic articles: {len(results['anthropic'])}")
    print(f"OpenAI articles: {len(results['openai'])}")
"""

from pathlib import Path
from typing import Dict, List, Any

# Import scrapers
try:
    from .scrapers.youtube import YouTubeScraper, ChannelVideo
    from .scrapers.anthropic_news import AnthropicScraper, AnthropicArticle
    from .scrapers.openai_news import OpenAINewsScraper, OpenAIArticle
except ImportError:
    # For direct execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.ingest.scrapers.youtube import YouTubeScraper, ChannelVideo
    from app.ingest.scrapers.anthropic_news import AnthropicScraper, AnthropicArticle
    from app.ingest.scrapers.openai_news import OpenAINewsScraper, OpenAIArticle

# Import config
try:
    from .config import YOUTUBE_CHANNELS, HOURS_BACK
except ImportError:
    from config import YOUTUBE_CHANNELS, HOURS_BACK


def fetch_youtube(channel_ids: List[str], hours_back: int = 24) -> List[ChannelVideo]:
    """Fetch videos from all configured YouTube channels."""
    scraper = YouTubeScraper()
    all_videos = []
    
    for channel_id in channel_ids:
        print(f"\n[YouTube] Fetching: {channel_id}...")
        try:
            videos = scraper.scrape_channel(channel_id, hours_back=hours_back)
            all_videos.extend(videos)
            print(f"  Found {len(videos)} videos")
        except Exception as e:
            print(f"  Error: {e}")
    
    return all_videos


def fetch_anthropic(hours_back: int = 24) -> List[AnthropicArticle]:
    """Fetch articles from all Anthropic RSS feeds with markdown content."""
    print("\n[Anthropic] Fetching all feeds...")
    scraper = AnthropicScraper()
    
    try:
        articles = scraper.fetch_articles_with_content(hours_back=hours_back)
        print(f"  Found {len(articles)} articles with content")
        return articles
    except Exception as e:
        print(f"  Error: {e}")
        return []


def fetch_openai(hours_back: int = 24) -> List[OpenAIArticle]:
    """Fetch articles from OpenAI news page with markdown content."""
    print("\n[OpenAI] Fetching news...")
    scraper = OpenAINewsScraper()
    
    try:
        articles = scraper.fetch_articles_with_content(hours_back=hours_back)
        print(f"  Found {len(articles)} articles with content")
        return articles
    except Exception as e:
        print(f"  Error: {e}")
        return []


def run_all(hours_back: int = None) -> Dict[str, List[Any]]:
    """
    Run all scrapers and return collected content.
    
    Args:
        hours_back: How far back to look for content (default: from config.HOURS_BACK)
    
    Returns:
        Dictionary with keys 'youtube', 'anthropic', 'openai' containing lists of articles/videos
    """
    if hours_back is None:
        hours_back = HOURS_BACK
    
    print("=" * 60)
    print(f"Running ingestion (looking back {hours_back} hours)")
    print("=" * 60)
    
    # Fetch from all sources
    results = {
        'youtube': fetch_youtube(YOUTUBE_CHANNELS, hours_back),
        'anthropic': fetch_anthropic(hours_back),
        'openai': fetch_openai(hours_back),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  YouTube videos:     {len(results['youtube'])}")
    print(f"  Anthropic articles: {len(results['anthropic'])}")
    print(f"  OpenAI articles:    {len(results['openai'])}")
    print(f"  Total items:        {sum(len(v) for v in results.values())}")
    
    return results


if __name__ == "__main__":
    # Test run with hours from config
    results = run_all()
    
    # Print YouTube videos with transcripts
    if results['youtube']:
        print("\n" + "=" * 60)
        print("YOUTUBE VIDEOS")
        print("=" * 60)
        for video in results['youtube']:
            print(f"\nTitle: {video.title}")
            print(f"Published: {video.published_at}")
            print(f"URL: {video.url}")
            if video.transcript:
                print(f"Transcript ({len(video.transcript)} chars):")
                print(f"  {video.transcript[:300]}...")
            else:
                print("Transcript: Not available")
    
    # Print Anthropic articles with content
    if results['anthropic']:
        print("\n" + "=" * 60)
        print("ANTHROPIC ARTICLES")
        print("=" * 60)
        for article in results['anthropic']:
            print(f"\nTitle: {article.title}")
            print(f"Published: {article.published_at}")
            print(f"URL: {article.url}")
            if article.content:
                print(f"Content ({len(article.content)} chars):")
                print(f"  {article.content[:300]}...")
            else:
                print("Content: Not available")
    
    # Print OpenAI articles with content
    if results['openai']:
        print("\n" + "=" * 60)
        print("OPENAI ARTICLES")
        print("=" * 60)
        for article in results['openai']:
            print(f"\nTitle: {article.title}")
            print(f"Published: {article.published_at}")
            print(f"URL: {article.url}")
            if article.content:
                print(f"Content ({len(article.content)} chars):")
                print(f"  {article.content[:300]}...")
            else:
                print("Content: Not available")
