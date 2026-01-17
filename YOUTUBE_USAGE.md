# YouTube Ingestion Usage Guide

## Overview

The YouTube ingestion module (`app/ingest/youtube.py`) allows you to:
1. Fetch latest videos from YouTube channels via RSS feeds
2. Filter videos by time window (e.g., last 24 hours)
3. Extract full transcripts for each video

## Setup

1. **Install dependencies** (if not already done):
   ```bash
   uv sync
   # or
   uv add youtube-transcript-api feedparser
   ```

2. **Get YouTube Channel IDs**:
   - Go to the YouTube channel page
   - Look at the URL or channel "About" page
   - Channel ID format: `UC_x5XG1OV2P6uZZ5FSM9Ttw` (starts with `UC`)
   - You can also find it in the channel's RSS feed URL

## Basic Usage

### Fetch videos from a channel

```python
from app.ingest.youtube import fetch_channel_videos

channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"  # Google Developers
videos = fetch_channel_videos(channel_id, hours_back=24)

for video in videos:
    print(f"{video['title']} - {video['url']}")
```

### Get transcript for a video

```python
from app.ingest.youtube import get_video_transcript

video_id = "dQw4w9WgXcQ"  # Extract from YouTube URL
transcript = get_video_transcript(video_id)

if transcript:
    print(transcript)
```

### Full ingestion (videos + transcripts)

```python
from app.ingest.youtube import ingest_channel

channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
videos = ingest_channel(channel_id, channel_name="Google Developers", hours_back=24)

for video in videos:
    print(f"Title: {video['title']}")
    print(f"Transcript available: {video['transcript'] is not None}")
    if video['transcript']:
        print(f"Transcript length: {len(video['transcript'])} characters")
```

## Testing

Run the test script to verify everything works:

```bash
# Run all tests
python test_youtube.py

# Run specific tests
python test_youtube.py fetch      # Test RSS feed fetching
python test_youtube.py transcript  # Test transcript extraction
python test_youtube.py full       # Test full ingestion pipeline
```

## Configuration

Channel IDs can be configured in `config/sources.yml` (copy from `config/sources.example.yml`):

```yaml
youtube_channels:
  - name: "Google Developers"
    channel_id: "UC_x5XG1OV2P6uZZ5FSM9Ttw"
  - name: "Your Channel"
    channel_id: "YOUR_CHANNEL_ID_HERE"
```

## Notes

- **Transcript availability**: Not all videos have transcripts. The module handles missing transcripts gracefully.
- **Time filtering**: Videos are filtered by `published_at` timestamp in UTC.
- **Rate limiting**: YouTube RSS feeds are public and don't require API keys, but be respectful with request frequency.
- **Video ID extraction**: Automatically extracts video IDs from various YouTube URL formats.

## Troubleshooting

- **No videos found**: Check that the channel ID is correct and the channel has published videos in the time window
- **Transcript unavailable**: Some videos don't have transcripts enabled, or may only have auto-generated transcripts in certain languages
- **RSS feed errors**: Verify the channel ID format (should start with `UC` and be 24 characters)
