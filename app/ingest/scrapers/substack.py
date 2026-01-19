"""Substack RSS scraper for fetching articles."""

from datetime import datetime, timedelta, timezone
from typing import List

import feedparser
import requests
from pydantic import BaseModel, ConfigDict, Field

try:
    from .cache import get_cached, set_cached
except ImportError:
    from cache import get_cached, set_cached


class SubstackArticle(BaseModel):
    """Pydantic model for a Substack article."""
    
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    guid: str = Field(..., description="Unique article identifier")
    published_at: datetime = Field(..., description="Publication timestamp in UTC")
    description: str = Field(default="", description="Article description/summary")
    content: str = Field(default="", description="Full HTML content of the article")
    author: str = Field(default="", description="Article author")
    
    model_config = ConfigDict()


class SubstackScraper:
    """
    Scraper for Substack RSS feeds that fetches articles.
    
    Example usage:
        scraper = SubstackScraper()
        articles = scraper.fetch_articles("https://interarma.substack.com/feed", hours_back=24)
    """
    
    def fetch_articles(
        self,
        rss_url: str,
        hours_back: int = 24
    ) -> List[SubstackArticle]:
        """
        Fetch articles from a Substack RSS feed.
        
        Args:
            rss_url: Full URL to the Substack RSS feed
            hours_back: Only return articles published within this many hours (default: 24)
        
        Returns:
            List of SubstackArticle models
        """
        # Check cache first
        cached_content = get_cached(rss_url, "xml")
        if cached_content:
            feed = feedparser.parse(cached_content)
        else:
            # Fetch and cache
            response = requests.get(rss_url, timeout=30)
            response.raise_for_status()
            set_cached(rss_url, response.text, "xml")
            feed = feedparser.parse(response.text)
        
        if feed.bozo:
            raise ValueError(f"Failed to parse RSS feed: {feed.bozo_exception}")
        
        articles = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours_back)
        
        for entry in feed.entries:
            # Parse published date
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
            
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            
            # Filter by time window
            if published_time < cutoff_time:
                continue
            
            # Extract content from content:encoded if available
            content = ""
            if hasattr(entry, 'content'):
                # content is a list, get the first item's value
                content = entry.content[0].value if entry.content else ""
            elif hasattr(entry, 'summary'):
                # Fallback to summary if content not available
                content = entry.summary
            
            articles.append(SubstackArticle(
                title=entry.title,
                url=entry.link,
                guid=entry.get('id', entry.link),  # Use id or link as fallback
                published_at=published_time,
                description=getattr(entry, 'description', ''),
                content=content,
                author=getattr(entry, 'author', ''),
            ))
        
        return articles


if __name__ == "__main__":
    """Test suite for SubstackScraper."""
    
    scraper = SubstackScraper()
    articles: List[SubstackArticle] = scraper.fetch_articles(
        "https://predictivehistory.substack.com/feed",
        hours_back=720  # Last 30 days
    )
    
    print(f"Found {len(articles)} articles")
    for article in articles:
        print(f"\n{article.title}")
        print(f"Published: {article.published_at}")
        print(f"URL: {article.url}")
