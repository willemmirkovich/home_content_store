import asyncio
import logging

from contextlib import asynccontextmanager
from queue import Empty
import re

from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from os import makedirs
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import Manager, Queue
from shutil import rmtree

from home_content_store.env import DATA_DIR, STREAM_DIR
from home_content_store.db import Task, browse_content, create_content, get_content_by_id, get_thumbnail, get_thumbnail_time, init_db, mark_processed, mark_uploaded, set_thumbnail, update_task
from home_content_store.models import FILE_FORMAT_TO_EXT, MAX_THUMBNAIL_BYTES, BrowseResponse, ContentModel, ContentResponse, ContentType, CreateContentResponse, TaskStatus, ThumbnailFormat, UploadResponse
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

# NOTE: max_tasks_per_child to setup lifetime for process

app.mount("/streams", StaticFiles(directory=STREAM_DIR), name="streams")


def thumbnail_url(content_id: int, thumbnail_time: datetime | None) -> str | None:
    """
    Versioned so a replaced thumbnail gets a new URL, letting clients
    cache each version indefinitely.
    """
    if thumbnail_time is None:
        return None
    return f'/content/{content_id}/thumbnail?v={int(thumbnail_time.timestamp())}'


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

    # TODO: retry tasks requires orginal file
    rmtree(staging_dir_path)
    logger.info(f'{staging_dir_path} removed')


@app.post("/content", status_code=201)
async def post_content(content_model: ContentModel) -> CreateContentResponse:
    """
    Create a content item. The media itself is posted later to `/upload/{content_id}`
    """
    try:
        content = create_content(
            name=content_model.name.lower().replace(" ", "_").strip(),
            title=content_model.title,
            format=content_model.format,
            content_type=content_model.content_type,
            description=content_model.description,
            release_date=content_model.release_date,
            genres=content_model.genres,
            content_metadata=content_model.content_metadata,
        )
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f'content named {content_model.name} already exists')
    return CreateContentResponse(id=content.id)


@app.post("/upload/{content_id}")
async def post_upload(request: Request, content_id: int) -> UploadResponse:
    content = get_content_by_id(content_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f'no content with id {content_id}')

    try:
        handler = HANDLERS[content.content_type]
    except KeyError:
        raise HTTPException(status_code=500, detail=f'{content.content_type} is not handled yet')

    try:
        mark_uploaded(content_id)
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f'content {content_id} already has media uploaded')

    dir_path = DATA_DIR / "files" / content.name
    file_ext = FILE_FORMAT_TO_EXT[content.format]
    file_path = str(dir_path / f'{content.name}.{file_ext}')
    makedirs(dir_path, exist_ok=True)

    total_bytes = await download_file(request, file_path)

    content, tasks, futures = handler(request, content, file_path)

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
    return [
        BrowseResponse(
            content_id=content.id,
            name=content.name,
            thumbnail_url=thumbnail_url(content.id, thumbnail_time),
        )
        for content, thumbnail_time in contents
    ]


@app.put('/content/{content_id}/thumbnail', status_code=204)
async def put_thumbnail(
    request: Request,
    content_id: int,
    content_type: str = Header(),
) -> None:
    """
    Set or replace a content item's thumbnail. The body is the raw image, with
    `Content-Type` set to its image format.
    """
    try:
        format = ThumbnailFormat(content_type)
    except ValueError:
        allowed = ', '.join(f.value for f in ThumbnailFormat)
        raise HTTPException(status_code=415, detail=f'thumbnail must be one of: {allowed}')

    if get_content_by_id(content_id) is None:
        raise HTTPException(status_code=404, detail=f'no content with id {content_id}')

    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_THUMBNAIL_BYTES:
            raise HTTPException(status_code=413, detail=f'thumbnail exceeds {MAX_THUMBNAIL_BYTES} bytes')
    if not data:
        raise HTTPException(status_code=400, detail='thumbnail is empty')

    set_thumbnail(content_id, bytes(data), format)


@app.get('/content/{content_id}/thumbnail')
async def get_content_thumbnail(content_id: int) -> Response:
    thumbnail = get_thumbnail(content_id)
    if thumbnail is None:
        raise HTTPException(status_code=404, detail=f'no thumbnail for content {content_id}')
    return Response(
        content=thumbnail.data,
        media_type=thumbnail.format,
        # safe to cache long-term: `thumbnail_url` changes when it's replaced
        headers={'Cache-Control': 'public, max-age=31536000, immutable'},
    )


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
        creation_time=content.creation_time,
        upload_time=content.upload_time,
        processed_time=content.processed_time,
        manifest_url=manifest_url,
        thumbnail_url=thumbnail_url(content.id, get_thumbnail_time(content.id)),
    )
