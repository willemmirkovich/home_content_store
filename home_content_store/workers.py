import json
import subprocess
import time

from fastapi import Request
from os import makedirs, path
from typing import Callable
from multiprocessing import Queue

from ffmpeg import FFmpeg, Progress


type ProgressUpdater = Callable[[float], None]
"""
Must be safely shareable across processes (e.g. `functools.partial` over
a `multiprocessing.Manager` queue's `put`) since these functions are meant
to run inside a `ProcessPoolExecutor` worker.
"""


async def download_file(request: Request, file: str) -> int:
    """
    download file to local location from upload request
    
    request: `fastapi` `Request`
    file: file location to download to

    returns `total_bytes` of file
    """
    total_bytes = 0
    with open(file, 'wb') as f:
        async for chunk in request.stream():
            total_bytes += len(chunk)
            f.write(chunk)
    return total_bytes


def compress(file: str,
             update_progress_fn: ProgressUpdater):
    """
    compress file with `zstd` to save raw file in content store

    file: file location
    update_progress_fn: callable to update progress
    """
    pass


def mock_process_video(video_file: str,
                       progress_queue: Queue):
    progress_queue.put((video_file, 1))
    return


def _probe_total_frames(video_file: str) -> int:
    """
    total frame count of `video_file`'s first video stream, via `ffprobe`.

    Prefers the container's own `nb_frames`; falls back to
    `duration * frame_rate` when that's unavailable (e.g. some streamed
    containers don't record a frame count).
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration:stream=r_frame_rate,nb_frames",
            "-of", "json",
            video_file,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]

    duration = float(data["format"]["duration"])
    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    return round(duration * fps)


# TODO: name here
def create_streamable_artifact(video_file: str,
                               stream_dir: str,
                               progress_queue: Queue):
    """
    process video file to `mpeg-dash` format for streaming

    video_file: file location
    stream_dir: directory to write the dash manifest and segments to
    progress_queue: queue to publish `(video_file, progress_fraction)` updates to
    """
    makedirs(stream_dir, exist_ok=True)
    name = path.splitext(path.basename(video_file))[0]
    manifest_path = path.join(stream_dir, f'{name}.mpd')

    total_frames = _probe_total_frames(video_file)

    ffmpeg = (
        FFmpeg()
        .input(video_file)
        .output(
            manifest_path,
            {"codec:v": "libx264", "codec:a": "aac", "profile:v": "high"},
            f="dash",
            seg_duration=3,
            pix_fmt="yuv420p",
        )
    )

    @ffmpeg.on("progress")
    def on_progress(progress: Progress):
        progress_queue.put((video_file, min(progress.frame / total_frames, 1.0)))

    ffmpeg.execute()
