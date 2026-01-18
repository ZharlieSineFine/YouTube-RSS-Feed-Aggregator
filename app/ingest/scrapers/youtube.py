"""YouTube channel scraper for fetching videos and transcripts."""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import feedparser
from pydantic import BaseModel, ConfigDict, Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

# Import IpBlocked if available (for handling IP blocking)
try:
    from youtube_transcript_api._errors import IpBlocked
except ImportError:
    # Fallback: check exception type name dynamically
    IpBlocked = None


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
        videos_with_transcripts = scraper.ingest_channel("CHANNEL_ID", hours_back=24)
    """
    
    def __init__(self):
        """Initialize the YouTube scraper."""
        self._transcript_api = YouTubeTranscriptApi()
    
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
        feed = feedparser.parse(rss_url)
        
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
        Fetch transcript for a YouTube video.
        
        Args:
            video_id: YouTube video ID
            languages: Preferred language codes (default: ['en']). 
                      Falls back to available languages.
        
        Returns:
            Transcript model with text, or None if transcript unavailable
        """
        if languages is None:
            languages = ['en']
        
        try:
            transcript_list = self._transcript_api.list(video_id)
            
            # Try to get transcript in preferred language
            transcript = None
            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except NoTranscriptFound:
                    continue
            
            # If preferred language not found, try to get any available transcript
            if transcript is None:
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                except NoTranscriptFound:
                    pass
            
            # Fetch the actual transcript data
            # transcript.fetch() returns a list of FetchedTranscriptSnippet objects
            # Each object has: .text, .start, .duration attributes
            transcript_data = transcript.fetch()
            
            # Extract text from each snippet and join into a single string
            full_text = ' '.join([snippet.text for snippet in transcript_data])
            
            return Transcript(text=full_text)
        
        except AttributeError as e:
            print(f"Error fetching transcript for video {video_id}: {e}")
            return None
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            print(f"Transcript not available for video {video_id}: {e}")
            return None
        except Exception as e:
            # Check if this is an IpBlocked exception
            exception_type_name = type(e).__name__
            
            # Try isinstance check if IpBlocked was imported successfully
            if IpBlocked and isinstance(e, IpBlocked):
                print(f"IP blocked by YouTube for video {video_id}. Consider using a proxy or waiting before retrying.")
                return None
            
            # Check by type name (works even if import failed)
            if exception_type_name == 'IpBlocked':
                print(f"IP blocked by YouTube for video {video_id}. Consider using a proxy or waiting before retrying.")
                return None
            
            # Check error message for IP blocking indicators (fallback)
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['ip blocked', 'blocking requests', 'ip has been blocked', 'cloud provider']):
                print(f"IP blocked by YouTube for video {video_id}. Consider using a proxy or waiting before retrying.")
                return None
            
            # Generic error handler
            print(f"Error fetching transcript for video {video_id}: {e}")
            return None
    
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
