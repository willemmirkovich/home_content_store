"""
Overall plan

upload -> allow for uploading of video, music, ...

browse -> either search for, or get all content available

stream -> get location of mpd file to stream movie/music
    Need to flesh this out
"""


import asyncio
from datetime import date
import logging

from contextlib import asynccontextmanager
from queue import Empty
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from os import makedirs
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import Manager, Queue
from shutil import rmtree

from home_content_store.env import DATA_DIR, STREAM_DIR
from home_content_store.db import Task, browse_content, get_content_by_id, init_db, mark_processed, update_task, init_db
from home_content_store.models import FILE_FORMAT_TO_EXT, BrowseResponse, ContentModel, ContentResponse, ContentType, FileFormat, TaskStatus, UploadResponse
from home_content_store.workers import download_file
from home_content_store.handlers import HANDLERS


logger = logging.getLogger('uvicorn.error')


PROCESS_WORKERS = 2


init_db()


# TODO: staging area dir, data dir for all stream/db/... files


async def _progress_listener(queue: Queue) -> None:
    """Single listener draining every task's progress updates and logging them."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            task_id, progress = await loop.run_in_executor(None, queue.get, True, 0.5)
        except Empty:
            continue
        update_task(task_id, progress=progress)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f'starting with {PROCESS_WORKERS} process workers')
    app.state.executor = ProcessPoolExecutor(max_workers=PROCESS_WORKERS)
    app.state.manager = Manager()
    app.state.progress_queue = app.state.manager.Queue()
    listener = asyncio.create_task(_progress_listener(app.state.progress_queue))
    yield
    logger.info('shutting down')
    listener.cancel()
    app.state.executor.shutdown()
    app.state.manager.shutdown()


app = FastAPI(lifespan=lifespan)

# TODO: setup lifespan with process pool
# NOTE: max_tasks_per_child to setup lifetime for process

app.mount("/streams", StaticFiles(directory=STREAM_DIR), name="streams")


async def cleanup_when_done(tasks: list[Task], futures: list[Future], staging_dir_path: str):
    asyncio_futures = [asyncio.wrap_future(f) for f in futures]
    # actually, can have do db updates here based on futures and tasks
    results = await asyncio.gather(*(asyncio_futures), return_exceptions=True)
    processing_complete = True
    for task, result in zip(tasks, results):
        if isinstance(result, Exception):
            processing_complete = False
            error = str(result)
            logger.error(f'task {task.id} [{task.task_type}] failed: {error}')
            update_task(task.id, error=error, status=TaskStatus.FAILED)
        else:
            logger.info(f'task {task.id} [{task.task_type}] complete')
            update_task(task.id, status=TaskStatus.COMPLETE)
    content_id = tasks[0].content_id
    if processing_complete:
        logger.info(f'content {content_id} complete')
        mark_processed(content_id)
    else:
        logger.error(f'content {content_id} failed to process')

    rmtree(staging_dir_path)
    logger.info(f'{staging_dir_path} removed')


@app.post("/upload")
async def post_upload(
    request: Request,
    # TODO: modify in place arg?
    name: str,
    title: str,
    format: FileFormat,
    description: str,
    content_type: ContentType,
    release_date: date,
    genres: list[str] | None = None,
) -> UploadResponse:
    name_snake_case = name.lower().replace(" ", "_").strip()

    dir_path = DATA_DIR / "files" / name_snake_case
    # dir_path = path.join(DIR, 'files', name_snake_case)
    file_ext = FILE_FORMAT_TO_EXT[format]
    # file_path = path.join(dir_path, f'{name_snake_case}.{file_ext}')
    file_path = str(dir_path / f'{name_snake_case}.{file_ext}')
    makedirs(dir_path)

    total_bytes = await download_file(request, file_path)

    content_model = ContentModel(
        name=name_snake_case,
        title=title,
        format=format,
        description=description,
        content_type=content_type,
        release_date=release_date,
        genres=genres,
    )


    try:
        handler = HANDLERS[content_type]
    except KeyError:
        raise HTTPException(status_code=500, detail=f'{content_type} is not handled yet')
    content, tasks, futures = handler(
        request, content_model, file_path
    )

    asyncio.create_task(cleanup_when_done(tasks, futures, str(dir_path)))

    return UploadResponse(
        id=content.id,
        size_mb=total_bytes
    )


@app.get('/browse')
async def get_browse(name: str | None = None, content_type: ContentType | None = None) -> list[BrowseResponse]:
    try:
        contents = browse_content(name=name, content_type=content_type)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f'invalid regex: {e}')
    return [BrowseResponse(content_id=content.id, name=content.name) for content in contents]


@app.get('/content/{content_id}')
async def get_content(content_id: int) -> ContentResponse:
    """
    Get content information, and if streamable, get streaming location
    """
    content = get_content_by_id(content_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f'no content with id {content_id}')

    manifest_url = None
    if content.processed_time is not None:
        manifest_url = f'/streams/{content.id}/manifest.mpd'

    return ContentResponse(
        id=content.id,
        name=content.name,
        format=content.format,
        description=content.description,
        duration_s=content.duration_s,
        upload_time=content.uploade_time,
        processed_time=content.processed_time,
        manifest_url=manifest_url,
    )
