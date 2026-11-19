# YouTube Extractor MCP Subsystem

## Overview
The YouTube Extractor MCP enables AI agents to interface seamlessly with YouTube videos. It utilizes `yt-dlp` for raw video/audio downloading and `youtube-transcript-api` to scrape closed captions and auto-generated transcripts.

## Architecture
- **Runtime Server (Port 8076)**: Centralized FastAPI backend that executes the downloading and scraping logic.
- **MCP Server 1 (Port 8077)**: Proxy node exposing the YouTube tools.
- **MCP Server 2 (Port 8078)**: Proxy node exposing the YouTube tools.

## Tools Exposed
- `download_yt_video(url: str)`: Downloads the YouTube video to the local filesystem and returns the path.
- `get_yt_transcript(url_or_id: str)`: Scrapes and returns the text transcript of the video.

## Execution
```bash
source venv/bin/activate
python runtime_server.py &
python mcp_server_1.py &
python mcp_server_2.py &
```
