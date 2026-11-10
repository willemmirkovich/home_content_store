from os import path
from concurrent.futures import Future
from typing import Callable
from asyncio.tasks import create_task
from fastapi import Request

from home_content_store.db import Task, create_task, set_duration, Content
from home_content_store.models import ContentType, TaskType
from home_content_store.env import STREAM_DIR
from home_content_store.workers import create_streamable_artifact, probe_video_info


type HandlerReturn = tuple[Content, list[Task], list[Future]]
type HandlerFunc = Callable[[Request, Content, str], HandlerReturn]



def movie_handler(
    request: Request,
    content: Content,
    file_path: str,
) -> HandlerReturn:
    duration_s, total_frames = probe_video_info(file_path)

    set_duration(content.id, int(duration_s))

    stream_path = str(STREAM_DIR / str(content.id))
    # NOTE: should not happen in production setting with db managing ids
    if path.exists(stream_path):
        raise RuntimeError(f'{stream_path} path already exists')

    task = create_task(content.id, TaskType.MPEG_DASH)

    tasks = [task]

    futures = [
        request.app.state.executor.submit(create_streamable_artifact, 
                                          task.id,
                                          file_path,
                                          stream_path,
                                          total_frames,
                                          request.app.state.progress_queue)
    ]
    return content, tasks, futures


# TODO: add other content type handlers


HANDLERS: dict[ContentType, HandlerFunc] = {
    ContentType.MOVIE: movie_handler,
}
