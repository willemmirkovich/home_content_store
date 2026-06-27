# Home Content Store

Project to serve content (video, games, ...) via home DB for access via player on the web

## Initial Scope

### Languages

- Python BE
- ??? FE

### Tools

- `mpeg-dash`
    - ISO standard for storing video files for streaming
    - https://dashif.org/about/
- `ffmpeg`:
    - how to turn a video file to manifest and segments
    - https://ffmpeg.org/ffmpeg-formats.html#dash-2
- `ffmpeg-python`
    - python bindings for ffmpeg calls
- `hls.js`
    - library that supports loading streaming videos via hls

### Initial Requirements

- User can upload a video to content store, that can be accessed later
- User can browse library of videos
- User can play video via web app

### Non-functional requirements

- Store large video files (4k video)
- User with bad non-optimal internet can still play video
- Backend services should schedule work without interruption to serving new requests


### Plan

1. Setup process to take in video file that is segmented and stored
2. Setup backend REST API that takes a video file and stores it
3. Add backend API for browsing videos
4. Create FE app for browsing video files
5. Add FE viewer that can playback stored videos

## Planned Scope

- Add authentication for web app
- Add content store for video game files

