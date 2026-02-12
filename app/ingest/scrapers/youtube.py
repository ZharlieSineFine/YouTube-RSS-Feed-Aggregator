"""YouTube channel scraper for fetching videos and transcripts."""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import feedparser
import requests
import yt_dlp
from pydantic import BaseModel, ConfigDict, Field

try:
    from .cache import get_cached, set_cached
except ImportError:
    from cache import get_cached, set_cached

# #region agent log
LOG_PATH = r"c:\Cursor_Projects\ai-news-aggregator-test\.cursor\debug.log"
def _dbg(hyp, loc, msg, data): open(LOG_PATH, "a").write(json.dumps({"hypothesisId": hyp, "location": loc, "message": msg, "data": data, "timestamp": datetime.now().isoformat()}) + "\n")
# #endregion


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
    
    def fetch_channel_videos(
        self, 
        channel_id: str, 
        hours_back: int = 24
    ) -> List[ChannelVideo]:
        """
        Fetch latest videos from a YouTube channel via RSS feed.
        
        Args:
            channel_id: YouTube channel ID
            hours_back: Only return videos published within this many hours (default: 24)
        
        Returns:
            List of ChannelVideo models
        """
        rss_url = self.build_rss_url(channel_id)
        
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
        
        videos = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours_back)
        
        # #region agent log
        _dbg("A", "youtube.py:fetch_channel_videos", "time_filter", {"now": now.isoformat(), "cutoff": cutoff_time.isoformat(), "hours_back": hours_back, "total_entries": len(feed.entries)})
        # #endregion
        
        for entry in feed.entries:
            # Parse published date
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
            
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            
            # #region agent log
            _dbg("A", "youtube.py:fetch_channel_videos", "entry_date", {"title": entry.title[:50], "published": published_time.isoformat(), "passes_filter": published_time >= cutoff_time})
            # #endregion
            
            # Filter by time window
            if published_time < cutoff_time:
                continue
            
            video_id = self.extract_video_id(entry.link)
            if not video_id:
                continue
            
            videos.append(ChannelVideo(
                title=entry.title,
                url=entry.link,
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
        Fetch transcript for a YouTube video using yt-dlp.
        
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
        
        try:
            # Configure yt-dlp to extract subtitles
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': languages,
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
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
            
            # Download and parse the transcript (with caching)
            cache_key = f"transcript_{video_id}"
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
