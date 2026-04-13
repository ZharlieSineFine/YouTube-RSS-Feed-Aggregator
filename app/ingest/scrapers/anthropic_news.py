"""Anthropic RSS scraper for fetching news, engineering, and research articles."""

import logging
import os
import tempfile
import warnings
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from enum import Enum

import feedparser
import requests
from docling.document_converter import DocumentConverter
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict, Field

# Suppress docling formatting warnings
logging.getLogger("docling").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="Clashing formatting")

try:
    from .cache import get_cached, set_cached
except ImportError:
    from cache import get_cached, set_cached


class AnthropicFeedType(str, Enum):
    """Anthropic feed types."""
    NEWS = "news"
    ENGINEERING = "engineering"
    RESEARCH = "research"


class AnthropicArticle(BaseModel):
    """Pydantic model for an Anthropic article."""
    
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    guid: str = Field(..., description="Unique article identifier")
    published_at: Optional[datetime] = Field(default=None, description="Publication timestamp in UTC")
    description: str = Field(default="", description="Article description/summary")
    category: str = Field(default="", description="Article category (e.g., Announcements, Engineering)")
    feed_type: AnthropicFeedType = Field(..., description="Which feed this came from")
    content: Optional[str] = Field(default=None, description="Full article content in markdown")
    
    model_config = ConfigDict()


class AnthropicScraper:
    """
    Scraper for Anthropic RSS feeds (news, engineering, research).
    
    Example usage:
        scraper = AnthropicScraper()
        
        # Fetch from all feeds
        articles = scraper.fetch_articles(hours_back=168)  # Last week
        
        # Fetch from specific feed
        news = scraper.fetch_articles(feed_types=[AnthropicFeedType.NEWS], hours_back=24)
        
        # Fetch engineering posts only
        eng = scraper.fetch_articles(feed_types=[AnthropicFeedType.ENGINEERING])
    """
    
    # Feed URLs (hosted on GitHub by Olshansk)
    FEEDS = {
        AnthropicFeedType.NEWS: "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        AnthropicFeedType.ENGINEERING: "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        AnthropicFeedType.RESEARCH: "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
    }
    
    def fetch_articles(
        self,
        feed_types: Optional[List[AnthropicFeedType]] = None,
        hours_back: int = 24,
        include_undated: bool = False
    ) -> List[AnthropicArticle]:
        """
        Fetch articles from Anthropic RSS feeds.
        
        Args:
            feed_types: List of feed types to fetch (default: all feeds)
            hours_back: Only return articles published within this many hours (default: 24)
            include_undated: Include articles without a published date (default: False)
        
        Returns:
            List of AnthropicArticle models, sorted by published_at (newest first)
        """
        if feed_types is None:
            feed_types = list(AnthropicFeedType)
        
        all_articles = []
        
        for feed_type in feed_types:
            articles = self._fetch_feed(feed_type, hours_back, include_undated)
            all_articles.extend(articles)
        
        # Sort by published_at (newest first), putting None dates at the end
        all_articles.sort(
            key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        return all_articles
    
    def _fetch_feed(
        self,
        feed_type: AnthropicFeedType,
        hours_back: int,
        include_undated: bool
    ) -> List[AnthropicArticle]:
        """Fetch articles from a single feed."""
        rss_url = self.FEEDS[feed_type]
        
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
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            
            # Filter by time window (if article has a date)
            if published_at is not None:
                if published_at < cutoff_time:
                    continue
            elif not include_undated:
                # Skip undated articles unless explicitly requested
                continue
            
            # Extract category from tags
            category = ""
            if hasattr(entry, 'tags') and entry.tags:
                category = entry.tags[0].get('term', '')
            
            articles.append(AnthropicArticle(
                title=entry.title,
                url=entry.link,
                guid=entry.get('id', entry.link),
                published_at=published_at,
                description=getattr(entry, 'summary', ''),
                category=category,
                feed_type=feed_type,
            ))
        
        return articles
    
    def fetch_news(self, hours_back: int = 24) -> List[AnthropicArticle]:
        """Convenience method to fetch only news articles."""
        return self.fetch_articles(feed_types=[AnthropicFeedType.NEWS], hours_back=hours_back)
    
    def fetch_engineering(self, hours_back: int = 168) -> List[AnthropicArticle]:
        """Convenience method to fetch only engineering blog posts."""
        return self.fetch_articles(feed_types=[AnthropicFeedType.ENGINEERING], hours_back=hours_back)
    
    def fetch_research(self, include_undated: bool = True) -> List[AnthropicArticle]:
        """Convenience method to fetch research articles (usually undated)."""
        return self.fetch_articles(
            feed_types=[AnthropicFeedType.RESEARCH],
            hours_back=99999,  # Large window since research is often undated
            include_undated=include_undated
        )
    
    def convert_url_to_markdown(self, url: str) -> str:
        """
        Convert an article URL to markdown content using docling.
        Uses Playwright to fetch HTML first (bypasses bot protection).
        
        Args:
            url: The article URL to convert
        
        Returns:
            Markdown string of the article content
        """
        # Check cache first
        cached_html = get_cached(url, "html")
        
        if cached_html:
            html_content = cached_html
        else:
            # Use Playwright to fetch HTML (bypasses Cloudflare/bot protection)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(2000)  # Allow JS to render
                html_content = page.content()
                browser.close()
            
            # Cache the HTML
            set_cached(url, html_content, "html")
        
        # Save to temp file and convert with docling
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_path = f.name
        
        try:
            converter = DocumentConverter()
            result = converter.convert(temp_path)
            return result.document.export_to_markdown()
        finally:
            os.unlink(temp_path)
    
    def fetch_articles_with_content(
        self,
        feed_types: Optional[List[AnthropicFeedType]] = None,
        hours_back: int = 24,
        include_undated: bool = False
    ) -> List[AnthropicArticle]:
        """
        Fetch articles and convert each to markdown content.
        
        Args:
            feed_types: List of feed types to fetch (default: all feeds)
            hours_back: Only return articles published within this many hours
            include_undated: Include articles without a published date
        
        Returns:
            List of AnthropicArticle models with content populated
        """
        articles = self.fetch_articles(
            feed_types=feed_types,
            hours_back=hours_back,
            include_undated=include_undated
        )
        
        for article in articles:
            try:
                article.content = self.convert_url_to_markdown(article.url)
            except Exception as e:
                print(f"Failed to convert {article.url}: {e}")
                article.content = None
        
        return articles


if __name__ == "__main__":
    """Test suite for AnthropicScraper."""
    
    scraper = AnthropicScraper()
    
    # Test fetching from all feeds (last 30 days)
    print("=== All Feeds (last 30 days) ===")
    articles = scraper.fetch_articles(hours_back=720)
    print(f"Found {len(articles)} articles")
    
    for article in articles[:5]:  # Show first 5
        print(f"\n[{article.feed_type.value.upper()}] {article.title}")
        print(f"  Category: {article.category}")
        print(f"  Published: {article.published_at}")
        print(f"  URL: {article.url}")
    
    # Test individual feeds
    print("\n\n=== News Only (last 7 days) ===")
    news = scraper.fetch_news(hours_back=168)
    print(f"Found {len(news)} news articles")
    
    print("\n=== Engineering Only (last 30 days) ===")
    eng = scraper.fetch_engineering(hours_back=720)
    print(f"Found {len(eng)} engineering posts")
    
    print("\n=== Research (all, including undated) ===")
    research = scraper.fetch_research()
    print(f"Found {len(research)} research articles")
    
    # Test URL to markdown conversion
    if articles:
        print("\n" + "="*50)
        print("Testing URL to Markdown conversion...")
        print("="*50)
        
        test_url = articles[0].url
        print(f"Converting: {test_url}")
        
        markdown = scraper.convert_url_to_markdown(test_url)
        print(f"\nMarkdown output (first 500 chars):\n{markdown[:500]}...")
