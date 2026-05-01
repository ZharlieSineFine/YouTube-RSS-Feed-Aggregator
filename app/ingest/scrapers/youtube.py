"""YouTube channel scraper for fetching videos and transcripts."""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import feedparser
import requests
import yt_dlp
from pydantic import BaseModel, ConfigDict, Field

try:
    from .cache import get_cached, read_cached_ignore_ttl, set_cached
except ImportError:
    from cache import get_cached, read_cached_ignore_ttl, set_cached


# Public Invidious / Piped / RSSHub instances that mirror YouTube's channel RSS
# feed when YouTube itself 404s / blocks the host IP. These are community-run;
# any given instance may be slow, down, or rate-limiting, and the full list of
# healthy instances changes monthly. The fetcher tries them in order and falls
# back to the next on any non-XML or error response.
#
# Override with ``YOUTUBE_RSS_MIRRORS`` env var — comma-separated list of URL
# templates containing ``{id}`` as the placeholder for the channel id. A
# current list of instances can be found at:
#   Invidious: https://docs.invidious.io/instances/
#   Piped:     https://github.com/TeamPiped/Piped/wiki/Instances
#   RSSHub:    https://docs.rsshub.app/guide/instances
#
# Example:
#   YOUTUBE_RSS_MIRRORS="https://yewtu.be/feed/channel/{id},https://invidious.nerdvpn.de/feed/channel/{id}"
_DEFAULT_RSS_MIRRORS: tuple[str, ...] = (
    "https://yewtu.be/feed/channel/{id}",
    "https://invidious.nerdvpn.de/feed/channel/{id}",
    "https://inv.nadeko.net/feed/channel/{id}",
    "https://invidious.materialio.us/feed/channel/{id}",
    "https://rsshub.app/youtube/channel/{id}",
)


def _rss_mirror_templates() -> tuple[str, ...]:
    raw = os.environ.get("YOUTUBE_RSS_MIRRORS", "").strip()
    if not raw:
        return _DEFAULT_RSS_MIRRORS
    parts = tuple(p.strip() for p in raw.split(",") if p.strip() and "{id}" in p)
    return parts or _DEFAULT_RSS_MIRRORS


class ChannelVideo(BaseModel):
    """Pydantic model for a YouTube channel video."""
    
    title: str = Field(..., description="Video title")
    url: str = Field(..., description="Full YouTube video URL")
    video_id: str = Field(..., description="YouTube video ID (11 characters)")
    published_at: datetime = Field(..., description="Publication timestamp in UTC")
    description: str = Field(default="", description="Video description")
    channel_id: str = Field(..., description="YouTube channel ID")
    transcript: Optional[str] = Field(default=None, description="Full transcript text if available")
    
    model_config = ConfigDict()
    # Note: Pydantic v2 automatically serializes datetime to ISO format, so json_encoders is not needed


class Transcript(BaseModel):
    """Pydantic model for a video transcript."""
    
    text: str = Field(..., description="Full transcript text")


class YouTubeScraper:
    """
    Scraper for YouTube channels that fetches videos and transcripts.
    
    Example usage:
        scraper = YouTubeScraper()
        videos = scraper.fetch_channel_videos("UC_x5XG1OV2P6uZZ5FSM9Ttw", hours_back=24)
        transcript = scraper.get_transcript("VIDEO_ID")
        videos_with_transcripts = scraper.scrape_channel("CHANNEL_ID", hours_back=24)
    """
    
    def __init__(self):
        """Initialize the YouTube scraper."""
        pass
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        Extract YouTube video ID from various URL formats.
        
        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        
        Args:
            url: YouTube video URL
            
        Returns:
            Video ID if found, None otherwise
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def build_rss_url(channel_id: str) -> str:
        """
        Build YouTube RSS feed URL from channel ID.
        
        Args:
            channel_id: YouTube channel ID (e.g., 'UC_x5XG1OV2P6uZZ5FSM9Ttw')
        
        Returns:
            RSS feed URL
        """
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    # Browser-like UA; YouTube sometimes 404s default python-requests.
    _RSS_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    }

    @staticmethod
    def _looks_like_youtube_feed(text: str) -> bool:
        """
        Minimal sanity check — a YouTube/Invidious/Piped channel feed always contains
        ``<yt:channelId>`` (YouTube namespace is preserved by all mirrors).
        """
        if not text:
            return False
        snippet = text[:2048].lower()
        if "<!doctype html" in snippet or "<html" in snippet:
            return False
        return ("yt:channelid" in snippet) or ("<feed" in snippet and "<entry" in text[:4096].lower())

    def _try_fetch_feed(self, url: str, label: str) -> Optional[str]:
        """Try to fetch ``url`` and return the text if it looks like a valid channel feed."""
        try:
            response = requests.get(url, timeout=30, headers=self._RSS_HEADERS)
        except requests.RequestException as e:
            print(f"  [YouTube RSS via {label}] error: {e}")
            return None

        status = response.status_code
        text = response.text or ""
        if status == 200 and self._looks_like_youtube_feed(text):
            return text

        body_snippet = text[:120].replace("\n", " ")
        print(
            f"  [YouTube RSS via {label}] unusable response "
            f"(status={status}, {len(text)} bytes): {body_snippet}"
        )
        return None

    def fetch_channel_videos(
        self, 
        channel_id: str, 
        hours_back: int = 24
    ) -> List[ChannelVideo]:
        """
        Fetch latest videos from a YouTube channel via RSS feed.

        Strategy (each step falls through on failure):
          1. Fresh cache (TTL respected).
          2. YouTube's own RSS feed.
          3. Community mirrors (Invidious / Piped). Configure via YOUTUBE_RSS_MIRRORS.
          4. Stale cache (past TTL, better than nothing).
        
        Args:
            channel_id: YouTube channel ID
            hours_back: Only return videos published within this many hours (default: 24)
        
        Returns:
            List of ChannelVideo models
        """
        rss_url = self.build_rss_url(channel_id)

        # 1. Fresh cache (respects TTL).
        feed_text: Optional[str] = get_cached(rss_url, "xml")

        # 2. YouTube directly.
        if feed_text is None:
            feed_text = self._try_fetch_feed(rss_url, "YouTube")
            if feed_text is not None:
                set_cached(rss_url, feed_text, "xml")

        # 3. Mirrors (Invidious / Piped).
        if feed_text is None:
            for template in _rss_mirror_templates():
                mirror_url = template.format(id=channel_id)
                label = mirror_url.split("/")[2] if "://" in mirror_url else mirror_url
                mirror_text = self._try_fetch_feed(mirror_url, label)
                if mirror_text is not None:
                    print(f"  [YouTube RSS] using mirror {label} for {channel_id}")
                    # Cache under the canonical URL so subsequent cache hits are transparent.
                    set_cached(rss_url, mirror_text, "xml")
                    feed_text = mirror_text
                    break

        # 4. Stale cache last resort.
        if feed_text is None:
            stale = read_cached_ignore_ttl(rss_url, "xml")
            if stale:
                print(
                    f"  [YouTube RSS] all live sources failed; "
                    f"using stale cached feed for {channel_id}"
                )
                feed_text = stale

        if feed_text is None:
            raise RuntimeError(
                f"Could not fetch YouTube channel feed for {channel_id} "
                f"(YouTube + all mirrors failed, and no cache available)."
            )

        feed = feedparser.parse(feed_text)

        if feed.bozo:
            raise ValueError(f"Failed to parse RSS feed: {feed.bozo_exception}")
        
        videos = []
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
            
            # Prefer the <yt:videoId> field — mirrors (Invidious/Piped) rewrite
            # entry.link to their own domain, which breaks extract_video_id.
            video_id = entry.get("yt_videoid") or self.extract_video_id(entry.link)
            if not video_id:
                continue

            canonical_url = f"https://www.youtube.com/watch?v={video_id}"

            videos.append(ChannelVideo(
                title=entry.title,
                url=canonical_url,
                video_id=video_id,
                published_at=published_time,
                description=getattr(entry, 'description', ''),
                channel_id=channel_id,
            ))
        
        return videos
    
    def get_transcript(
        self, 
        video_id: str, 
        languages: List[str] = None
    ) -> Optional[Transcript]:
        """
        Fetch transcript for a YouTube video using yt-dlp (or cache only).

        If a full transcript is already stored under ``.cache`` (``transcript_<id>.vtt``),
        it is parsed and returned without calling yt-dlp or YouTube, even when the
        entry would be considered stale for RSS/HTML TTL purposes.
        
        Args:
            video_id: YouTube video ID
            languages: Preferred language codes (default: ['en']). 
                      Falls back to available languages or auto-generated captions.
        
        Returns:
            Transcript model with text, or None if transcript unavailable
        """
        if languages is None:
            languages = ['en']
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        cache_key = f"transcript_{video_id}"

        cold_vtt = read_cached_ignore_ttl(cache_key, "vtt")
        if cold_vtt:
            transcript_text = self._parse_transcript(cold_vtt)
            if transcript_text:
                print(f"[YouTube] Transcript from disk cache (skipped yt-dlp): {video_id}")
                return Transcript(text=transcript_text)
        
        try:
            # Configure yt-dlp to extract subtitles
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': languages,
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                # Fail fast on 403/blocked — default retries=10 stalls for minutes per video.
                'retries': 1,
                'fragment_retries': 1,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
            
            # Try to get subtitles from available sources
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            # Combine both sources
            all_subtitles = {**automatic_captions, **subtitles}
            
            if not all_subtitles:
                print(f"Transcript not available for video {video_id}")
                return None
            
            # Try preferred languages first
            transcript_url = None
            for lang in languages:
                if lang in all_subtitles:
                    # Get the first available format (usually vtt or srv3)
                    transcript_url = all_subtitles[lang][0].get('url')
                    if transcript_url:
                        break
            
            # If preferred language not found, try any available language
            if not transcript_url:
                for lang, formats in all_subtitles.items():
                    if formats:
                        transcript_url = formats[0].get('url')
                        if transcript_url:
                            break
            
            if not transcript_url:
                print(f"Transcript not available for video {video_id}")
                return None
            
            # Download and parse the transcript (with caching / TTL for refetch)
            cached_vtt = get_cached(cache_key, "vtt")
            
            if cached_vtt:
                vtt_content = cached_vtt
            else:
                response = requests.get(transcript_url, timeout=30)
                response.raise_for_status()
                vtt_content = response.text
                set_cached(cache_key, vtt_content, "vtt")
            
            # Parse transcript (auto-detects VTT vs JSON3 format)
            transcript_text = self._parse_transcript(vtt_content)
            
            if not transcript_text:
                print(f"Failed to parse transcript for video {video_id}")
                return None
            
            return Transcript(text=transcript_text)
        
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['private', 'unavailable', 'removed', 'not found']):
                print(f"Video {video_id} is unavailable or private")
            else:
                print(f"Error fetching transcript for video {video_id}: {e}")
            return None
        except Exception as e:
            error_msg = str(e).lower()
            # Check for IP blocking or rate limiting
            if any(keyword in error_msg for keyword in ['ip blocked', 'blocking requests', 'ip has been blocked', 'cloud provider', '429', 'rate limit']):
                print(f"IP blocked or rate limited by YouTube for video {video_id}. Consider using a proxy or waiting before retrying.")
            else:
                print(f"Error fetching transcript for video {video_id}: {e}")
            return None
    
    @staticmethod
    def _parse_transcript(content: str) -> str:
        """
        Parse transcript content, auto-detecting VTT or JSON3 format.
        
        Args:
            content: Raw transcript content (VTT or JSON3)
        
        Returns:
            Cleaned transcript text
        """
        content = content.strip()
        
        # Detect format: JSON3 starts with { and contains "events"
        if content.startswith('{'):
            try:
                return YouTubeScraper._parse_json3(content)
            except (json.JSONDecodeError, KeyError):
                pass  # Fall back to VTT parsing
        
        # Default to VTT parsing
        return YouTubeScraper._parse_vtt(content)
    
    @staticmethod
    def _parse_json3(json_content: str) -> str:
        """
        Parse JSON3 (YouTube's native subtitle format) and extract text.
        
        Args:
            json_content: Raw JSON3 content
        
        Returns:
            Cleaned transcript text
        """
        data = json.loads(json_content)
        text_parts = []
        
        events = data.get('events', [])
        for event in events:
            segs = event.get('segs', [])
            for seg in segs:
                text = seg.get('utf8', '')
                if text and text != '\n':
                    text_parts.append(text)
        
        # Join and clean up
        full_text = ''.join(text_parts)
        # Normalize whitespace
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        return full_text
    
    @staticmethod
    def _parse_vtt(vtt_content: str) -> str:
        """
        Parse VTT (WebVTT) subtitle format and extract text.
        
        Args:
            vtt_content: Raw VTT content
        
        Returns:
            Cleaned transcript text
        """
        lines = vtt_content.split('\n')
        text_lines = []
        
        for line in lines:
            # Skip empty lines, timestamps, and metadata
            if not line.strip():
                continue
            if '-->' in line:  # Timestamp line
                continue
            if line.strip().startswith('WEBVTT'):
                continue
            if line.strip().startswith('NOTE'):
                continue
            if line.strip().startswith('Kind:'):
                continue
            if line.strip().startswith('Language:'):
                continue
            
            # Remove HTML tags if present
            line = re.sub(r'<[^>]+>', '', line)
            
            # Remove speaker labels (e.g., "SPEAKER 00:00:00")
            line = re.sub(r'^[A-Z\s]+\d+:\d+:\d+', '', line)
            
            if line.strip():
                text_lines.append(line.strip())
        
        return ' '.join(text_lines)
    
    def scrape_channel(
        self, 
        channel_id: str, 
        hours_back: int = 24
    ) -> List[ChannelVideo]:
        """
        Scrape videos from a YouTube channel, including transcripts.
        
        This method fetches videos from the channel and then retrieves transcripts
        for each video.
        
        Args:
            channel_id: YouTube channel ID
            hours_back: Only process videos from last N hours (default: 24)
        
        Returns:
            List of ChannelVideo models with transcript data included
        """
        videos = self.fetch_channel_videos(channel_id, hours_back=hours_back)
        
        # Fetch transcripts for each video
        updated_videos = []
        for video in videos:
            transcript = self.get_transcript(video.video_id)
            transcript_text = transcript.text if transcript else None
            updated_videos.append(video.model_copy(update={'transcript': transcript_text}))
        
        return updated_videos


if __name__ == "__main__":
    """Test suite for YouTubeScraper."""
    
    scraper = YouTubeScraper()
    transcript_data: Optional[Transcript] = scraper.get_transcript("MX93U4KzA28")
    if transcript_data:
        print(transcript_data.text)
    else:
        print("Transcript not available for this video")
    channel_videos: List[ChannelVideo] = scraper.scrape_channel("UC11aHtNnc5bEPLI4jf6mnYg", hours_back=200)
