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

- Have listener that picks up work and creates jobs on the fly
- Keep original copy of content for bookeeping purposes
- Add authentication for web app
- Add content store for video game files


## Disclaimer

Home Content Store is a personal tool for organizing and playing media files
that you own or are otherwise legally entitled to use. It does not host,
provide, index, or link to any copyrighted content, and it does not include
any means of circumventing DRM or other protection measures.

The author does not condone or endorse piracy or the unauthorized
reproduction or distribution of copyrighted material. You are solely
responsible for ensuring your use of this software complies with the laws of
your jurisdiction and the rights of content owners. The software is provided
"as is", without warranty, and the author accepts no liability for misuse.
