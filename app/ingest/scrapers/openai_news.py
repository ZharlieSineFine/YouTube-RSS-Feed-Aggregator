"""OpenAI News scraper - scrapes the news page directly."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json
import os
import re
import tempfile

from docling.document_converter import DocumentConverter
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict, Field

try:
    from .cache import get_cached, set_cached
except ImportError:
    from cache import get_cached, set_cached

# #region agent log
LOG_PATH = r"c:\Cursor_Projects\ai-news-aggregator-test\.cursor\debug.log"
def _dbg(hyp, loc, msg, data): open(LOG_PATH, "a").write(json.dumps({"hypothesisId": hyp, "location": loc, "message": msg, "data": data, "timestamp": datetime.now().isoformat()}) + "\n")
# #endregion


class OpenAIArticle(BaseModel):
    """Pydantic model for an OpenAI news article."""
    
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    published_at: datetime = Field(..., description="Publication timestamp in UTC")
    description: str = Field(default="", description="Article description/summary")
    content: Optional[str] = Field(default=None, description="Full article content in markdown")
    
    model_config = ConfigDict()


class OpenAINewsScraper:
    """
    Scraper for OpenAI News page using Playwright headless browser.
    
    Example usage:
        scraper = OpenAINewsScraper()
        articles = scraper.fetch_articles(hours_back=24)
    
    Requires: playwright install chromium
    """
    
    NEWS_URL = "https://openai.com/news"
    
    def _fetch_page_html(self, url: str) -> str:
        """Fetch HTML from a URL using Playwright, with caching."""
        # Check cache first
        cached_html = get_cached(url, "html")
        if cached_html:
            return cached_html
        
        # Fetch with Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            response = page.goto(url, wait_until="load", timeout=60000)
            
            if response is None or response.status != 200:
                browser.close()
                raise ValueError(f"Failed to load page: status={response.status if response else 'None'}")
            
            page.wait_for_timeout(3000)  # Give JS time to render
            
            try:
                page.wait_for_selector("a[href*='/index/']", timeout=15000)
            except:
                page.wait_for_selector("a", timeout=5000)
            
            html_content = page.content()
            browser.close()
        
        # Cache the result
        set_cached(url, html_content, "html")
        return html_content
    
    def fetch_articles(self, hours_back: int = 24) -> List[OpenAIArticle]:
        """
        Fetch articles from OpenAI News page by scraping HTML.
        
        Args:
            hours_back: Only return articles published within this many hours (default: 24)
        
        Returns:
            List of OpenAIArticle models
        """
        # Get HTML (from cache or fresh)
        html_content = self._fetch_page_html(self.NEWS_URL)
        
        # Parse HTML with Playwright (need browser for JS evaluation)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content)
            
            # Find all article links
            articles_data = page.evaluate("""
                () => {
                    const articles = [];
                    // Look for article links - they typically link to /index/article-slug
                    const links = document.querySelectorAll('a[href*="/index/"]');
                    const seen = new Set();
                    
                    // Patterns to exclude (product names, section headers)
                    const excludePatterns = [
                        /^gpt-?[0-9.]+$/i,
                        /^o[0-9](-mini)?$/i,
                        /^sora\\s*[0-9]*$/i,
                        /^dall-?e\\s*[0-9]*$/i,
                        /^whisper$/i,
                        /^codex$/i,
                        /^research$/i,
                        /^api$/i,
                        /^chatgpt$/i,
                        /^safety$/i,
                        /^products?$/i,
                    ];
                    
                    // Date pattern to extract from text (e.g., "Jan 18, 2026")
                    const datePattern = /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{1,2},\\s+\\d{4}/i;
                    
                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        if (!href || seen.has(href)) return;
                        
                        // Skip section index pages (e.g., /research/index/)
                        if (href.endsWith('/index/') || href.endsWith('/index')) return;
                        
                        seen.add(href);
                        
                        // Get full text content (includes title + category + date)
                        const fullText = link.textContent?.trim() || '';
                        
                        // Extract date from the text
                        const dateMatch = fullText.match(datePattern);
                        const dateStr = dateMatch ? dateMatch[0] : '';
                        
                        // Extract clean title (remove date and category suffix)
                        let title = fullText;
                        if (dateMatch) {
                            // Remove date and everything after it
                            title = fullText.substring(0, fullText.indexOf(dateMatch[0]));
                            // Remove category labels (Research, Company, Safety, etc.)
                            title = title.replace(/(Research|Company|Safety|Product|API|ChatGPT|Announcements?)\\s*$/i, '').trim();
                        }
                        
                        // Skip short titles (likely navigation items)
                        if (!title || title.length < 15) return;
                        
                        // Skip titles matching exclude patterns
                        if (excludePatterns.some(p => p.test(title))) return;
                        
                        // Look for description in nearby elements
                        const container = link.closest('article, [class*="card"], [class*="item"], div');
                        const descEl = container?.querySelector('p, [class*="description"], [class*="excerpt"]');
                        const description = descEl?.textContent?.trim() || '';
                        
                        articles.push({
                            title: title.substring(0, 200),
                            url: href.startsWith('http') ? href : 'https://openai.com' + href,
                            dateStr: dateStr,
                            description: description.substring(0, 500)
                        });
                    });
                    
                    return articles;
                }
            """)
            
            # #region agent log
            _dbg("SCRAPE", "openai_news.py:fetch", "articles_found", {"count": len(articles_data), "sample": articles_data[:3] if articles_data else []})
            # #endregion
            
            browser.close()
        
        # Parse articles and filter by time
        articles = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours_back)
        
        for item in articles_data:
            # Parse date from the extracted date string (e.g., "Jan 18, 2026")
            date_str = item.get('dateStr', '')
            published_at = self._parse_date(date_str)
            
            # #region agent log
            _dbg("SCRAPE", "openai_news.py:fetch", "parsed_date", {"title": item.get('title', '')[:50], "dateStr": date_str, "parsed": published_at.isoformat() if published_at else None})
            # #endregion
            
            # Skip articles without a valid date (we can't filter by time)
            if published_at is None:
                continue
            
            # Filter by time window
            if published_at < cutoff_time:
                continue
            
            articles.append(OpenAIArticle(
                title=item['title'],
                url=item['url'],
                published_at=published_at,
                description=item.get('description', ''),
            ))
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse various date formats."""
        if not date_str:
            return None
        
        # Common date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        # Try relative dates like "2 days ago"
        relative_match = re.match(r'(\d+)\s*(day|hour|minute|week)s?\s*ago', date_str.lower())
        if relative_match:
            num = int(relative_match.group(1))
            unit = relative_match.group(2)
            now = datetime.now(timezone.utc)
            if unit == 'day':
                return now - timedelta(days=num)
            elif unit == 'hour':
                return now - timedelta(hours=num)
            elif unit == 'minute':
                return now - timedelta(minutes=num)
            elif unit == 'week':
                return now - timedelta(weeks=num)
        
        return None
    
    def convert_url_to_markdown(self, url: str) -> str:
        """
        Convert a URL to markdown content using docling.
        Uses Playwright to fetch HTML first (bypasses Cloudflare), then docling to convert.
        """
        # Check cache first for HTML
        cached_html = get_cached(url, "html")
        
        if cached_html:
            html_content = cached_html
        else:
            # Use Playwright to fetch the HTML (bypasses Cloudflare protection)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(2000)
                html_content = page.content()
                browser.close()
            
            # Cache the HTML
            set_cached(url, html_content, "html")
        
        # Save HTML to temp file and convert with docling
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_path = f.name
        
        try:
            converter = DocumentConverter()
            result = converter.convert(temp_path)
            return result.document.export_to_markdown()
        finally:
            os.unlink(temp_path)
    
    def fetch_articles_with_content(self, hours_back: int = 24) -> List[OpenAIArticle]:
        """
        Fetch articles and convert each to markdown content.
        
        Args:
            hours_back: Only return articles published within this many hours
        
        Returns:
            List of OpenAIArticle models with content populated
        """
        articles = self.fetch_articles(hours_back=hours_back)
        
        for article in articles:
            try:
                article.content = self.convert_url_to_markdown(article.url)
            except Exception as e:
                print(f"Failed to convert {article.url}: {e}")
                article.content = None
        
        return articles


if __name__ == "__main__":
    """Test suite for OpenAINewsScraper."""
    
    scraper = OpenAINewsScraper()
    articles: List[OpenAIArticle] = scraper.fetch_articles(hours_back=72)  # Last 3 days
    
    print(f"Found {len(articles)} articles")
    for article in articles:
        print(f"\n{article.title}")
        print(f"Published: {article.published_at}")
        print(f"URL: {article.url}")
    
    # Test URL to markdown conversion
    if articles:
        print("\n" + "="*50)
        print("Testing URL to Markdown conversion...")
        print("="*50)
        
        test_url = articles[0].url
        print(f"Converting: {test_url}")
        
        markdown = scraper.convert_url_to_markdown(test_url)
        print(f"\nMarkdown output (first 500 chars):\n{markdown[:500]}...")