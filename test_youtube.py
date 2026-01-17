"""Test script for YouTube ingestion functionality."""

from app.ingest.youtube import ingest_channel, fetch_channel_videos, get_video_transcript


def test_basic_fetch():
    """Test fetching videos from a channel."""
    print("=" * 60)
    print("TEST 1: Fetching videos from Predictive History's channel")
    print("=" * 60)
    
    channel_id = "UC11aHtNnc5bEPLI4jf6mnYg"
    hours_back = 72
    videos = fetch_channel_videos(channel_id, hours_back=72)
    
    print(f"\nFound {len(videos)} video(s) in the last {hours_back} hours:\n")
    for video in videos:
        print(f"  • {video['title']}")
        print(f"    URL: {video['url']}")
        print(f"    Published: {video['published_at']}")
        print()


def test_transcript():
    """Test fetching transcript for a specific video."""
    print("=" * 60)
    print("TEST 2: Fetching transcript for a video")
    print("=" * 60)
    
    # Example video ID - replace with a real video ID that has transcripts
    # You can get this from any YouTube video URL: youtube.com/watch?v=VIDEO_ID
    test_video_id = "MX93U4KzA28"  # Replace with a real video ID
    
    print(f"\nFetching transcript for video ID: {test_video_id}")
    transcript = get_video_transcript(test_video_id)
    
    if transcript:
        print(f"\n✓ Transcript retrieved!")
        print(f"  Length: {len(transcript)} characters")
        print(f"\n  Preview (first 300 chars):")
        print(f"  {transcript[:300]}...")
    else:
        print("\n✗ Transcript not available for this video")


def test_full_ingestion():
    """Test full ingestion pipeline with transcripts."""
    print("=" * 60)
    print("TEST 3: Full ingestion pipeline")
    print("=" * 60)
    
    channel_id = "UC11aHtNnc5bEPLI4jf6mnYg"
    videos = ingest_channel(channel_id, channel_name="Predictive History", hours_back=200)
    
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: Processed {len(videos)} video(s)")
    print(f"{'=' * 60}\n")
    
    for i, video in enumerate(videos, 1):
        print(f"{i}. {video['title']}")
        print(f"   URL: {video['url']}")
        print(f"   Published: {video['published_at']}")
        if video.get('transcript'):
            print(f"   Transcript: {len(video['transcript'])} characters")
        else:
            print(f"   Transcript: Not available")
        print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "fetch":
            test_basic_fetch()
        elif test_name == "transcript":
            test_transcript()
        elif test_name == "full":
            test_full_ingestion()
        else:
            print(f"Unknown test: {test_name}")
            print("Available tests: fetch, transcript, full")
    else:
        # Run all tests
        print("Running all YouTube ingestion tests...\n")
        test_basic_fetch()
        print("\n")
        test_transcript()
        print("\n")
        test_full_ingestion()
