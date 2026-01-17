"""YouTube channel RSS feed ingestion and transcript extraction."""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import feedparser
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats.
    
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def build_rss_url(channel_id: str) -> str:
    """
    Build YouTube RSS feed URL from channel ID.
    
    Args:
        channel_id: YouTube channel ID (e.g., 'UC_x5XG1OV2P6uZZ5FSM9Ttw')
    
    Returns:
        RSS feed URL
    """
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def fetch_channel_videos(channel_id: str, hours_back: int = 24) -> List[Dict]:
    """
    Fetch latest videos from a YouTube channel via RSS feed.
    
    Args:
        channel_id: YouTube channel ID
        hours_back: Only return videos published within this many hours (default: 24)
    
    Returns:
        List of video dictionaries with keys: title, url, video_id, published_at, description
    """
    rss_url = build_rss_url(channel_id)
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
        
        video_id = extract_video_id(entry.link)
        if not video_id:
            continue
        
        videos.append({
            'title': entry.title,
            'url': entry.link,
            'video_id': video_id,
            'published_at': published_time,
            'description': getattr(entry, 'description', ''),
            'channel_id': channel_id,
        })
    
    return videos


def get_video_transcript(video_id: str, languages: List[str] = None) -> Optional[str]:
    """
    Fetch transcript for a YouTube video.
    
    Args:
        video_id: YouTube video ID
        languages: Preferred language codes (default: ['en']). Falls back to available languages.
    
    Returns:
        Full transcript text as a single string, or None if transcript unavailable
    """
    if languages is None:
        languages = ['en']
    
    try:
        # Create instance of YouTubeTranscriptApi (required in v1.2.0+)
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
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
            transcript = transcript_list.find_generated_transcript(['en'])
        
        # Fetch the actual transcript data
        # transcript.fetch() returns a list of FetchedTranscriptSnippet objects
        # Each object has: .text, .start, .duration attributes
        transcript_data = transcript.fetch()
        
        # Extract text from each snippet and join into a single string
        full_text = ' '.join([snippet.text for snippet in transcript_data])
        
        return full_text
    
    except AttributeError as e:
        print(f"Error fetching transcript for video {video_id}: {e}")
        return None
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"Transcript not available for video {video_id}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching transcript for video {video_id}: {e}")
        return None


def ingest_channel(channel_id: str, channel_name: str = None, hours_back: int = 24) -> List[Dict]:
    """
    Ingest videos from a YouTube channel, including transcripts.
    
    Args:
        channel_id: YouTube channel ID
        channel_name: Optional channel name for logging
        hours_back: Only process videos from last N hours (default: 24)
    
    Returns:
        List of video dictionaries with transcript data included
    """
    if channel_name:
        print(f"Fetching videos from channel: {channel_name} ({channel_id})")
    else:
        print(f"Fetching videos from channel ID: {channel_id}")
    
    videos = fetch_channel_videos(channel_id, hours_back=hours_back)
    print(f"Found {len(videos)} video(s) in the last {hours_back} hours")
    
    # Fetch transcripts for each video
    for video in videos:
        print(f"  - Fetching transcript for: {video['title']}")
        transcript = get_video_transcript(video['video_id'])
        video['transcript'] = transcript
        if transcript:
            print(f"    ✓ Transcript retrieved ({len(transcript)} characters)")
        else:
            print(f"    ✗ Transcript unavailable")
    
    return videos


if __name__ == "__main__":
    # Test with a sample channel
    # Example: Google Developers channel
    test_channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    
    print("Testing YouTube ingestion...")
    print("=" * 60)
    
    videos = ingest_channel(test_channel_id, channel_name="Google Developers", hours_back=24)
    
    print("\n" + "=" * 60)
    print(f"Total videos processed: {len(videos)}")
    
    for video in videos:
        print(f"\nTitle: {video['title']}")
        print(f"URL: {video['url']}")
        print(f"Published: {video['published_at']}")
        print(f"Has transcript: {video['transcript'] is not None}")
        if video['transcript']:
            print(f"Transcript preview: {video['transcript'][:200]}...")
