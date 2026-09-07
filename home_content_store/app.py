"""
Overall plan

upload -> allow for uploading of video, music, ...

browse -> either search for, or get all content available

stream -> get location of mpd file to stream movie/music
    Need to flesh this out
"""


import asyncio
from asyncio.tasks import create_task
import logging

from contextlib import asynccontextmanager
from queue import Empty
from fastapi import FastAPI, Request
from os import makedirs, path
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import Manager, Queue
from shutil import rmtree

from home_content_store.db import Task, create_content, init_db, mark_processed, update_task, create_task, init_db
from home_content_store.models import FILE_FORMAT_TO_EXT, FileFormat, TaskStatus, TaskType, UploadResponse
from home_content_store.workers import download_file, create_streamable_artifact, probe_video_info


logger = logging.getLogger('uvicorn.error')


PROCESS_WORKERS = 2


init_db()


async def _progress_listener(queue: Queue) -> None:
    """Single listener draining every task's progress updates and logging them."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            task_id, progress = await loop.run_in_executor(None, queue.get, True, 0.5)
        except Empty:
            continue
        logger.info(f'task {task_id} progress: {progress}')
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

DIR = path.abspath(path.join(__file__, "..", "..", "test"))
STREAM_DIR = path.abspath(path.join(__file__, "..", "..", "test", "streams"))



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


@app.get("/download/{id}")
async def download(id: int):
    pass


@app.post("/upload")
async def upload(request: Request,
                 name: str,
                 format: FileFormat,
                 description: str) -> UploadResponse:
    name_snake_case = name.lower().replace(" ", "_").strip()
    dir_path = path.join(DIR, 'files', name_snake_case)
    file_ext = FILE_FORMAT_TO_EXT[format]
    file_path = path.join(dir_path, f'{name_snake_case}.{file_ext}')
    makedirs(dir_path)

    total_bytes = await download_file(request, file_path)

    # conditional here
    duration_s, total_frames = probe_video_info(file_path)

    # TODO: async?
    content = create_content(name, format, description, int(duration_s))

    stream_path = path.join(STREAM_DIR, str(content.id))

    # TODO: create taskids here
    # TODO: handle file types

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
    asyncio.create_task(cleanup_when_done(tasks, futures, dir_path))

    return UploadResponse(
        id=content.id,
        size_mb=total_bytes
    )
