from os import path
from concurrent.futures import Future
from typing import Callable
from asyncio.tasks import create_task
from fastapi import HTTPException, Request

from home_content_store.db import Task, create_content, create_task, Content
from home_content_store.models import ContentModel, ContentType, TaskType
from home_content_store.env import STREAM_DIR
from home_content_store.workers import create_streamable_artifact, probe_video_info


type HandlerReturn = tuple[Content, list[Task], list[Future]]
type HandlerFunc = Callable[[Request, ContentModel, str], HandlerReturn]



def movie_handler(
    request: Request,
    content_model: ContentModel,
    file_path: str,
) -> HandlerReturn:


    if content_model.parent_id:
        raise HTTPException(
            status_code=400, 
            detail=f"{content_model.content_type} does not support parent"
        )


    duration_s, total_frames = probe_video_info(file_path)

    # TODO: async?
    # TODO: how to handle parent validation?
    content = create_content(
        content_model.name,
        content_model.title,
        content_model.format,
        content_model.content_type,
        content_model.description,
        int(duration_s)
    )

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


async def tv_show_handler():
    # TODO: check not parent_id
    pass


async def tv_season_handler():
    # TODO: check parent is tv_show type
    pass


async def tv_episode_handler():
    # TODO: check parent is tv_episode type
    pass


async def recording_handler():
    pass


HANDLERS: dict[ContentType, HandlerFunc] = {
    # TODO: fix type
    ContentType.MOVIE: movie_handler,
}
