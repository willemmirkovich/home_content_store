from multiprocessing import Queue
import time

from fastapi import Request
from typing import Callable


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



def process_video(video_file: str,
                  update_progress_fn: ProgressUpdater):
    """
    process video file to `mpeg-dash` format for streaming

    video_file: file location
    update_progress_fn: callable to update progress
    """
    pass
