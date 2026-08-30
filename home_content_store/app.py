import asyncio
import logging

from contextlib import asynccontextmanager
from queue import Empty
from fastapi import FastAPI, Request
from os import makedirs, path, remove
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import Manager, Queue

from home_content_store.models import UploadResponse
from home_content_store.workers import download_file, compress, process_video, mock_process_video


logger = logging.getLogger('uvicorn.error')


PROCESS_WORKERS = 2


async def _log_progress(queue: Queue) -> None:
    """Single listener draining every task's progress updates and logging them."""
    loop = asyncio.get_running_loop()
    while True:
      try:
          task_id, progress = await loop.run_in_executor(None, queue.get, True, 0.5)
      except Empty:
          continue
      logger.info(f'task {task_id} progress: {progress}')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f'starting with {PROCESS_WORKERS} process workers')
    app.state.executor = ProcessPoolExecutor(max_workers=PROCESS_WORKERS)
    app.state.manager = Manager()
    app.state.progress_queue = app.state.manager.Queue()
    listener = asyncio.create_task(_log_progress(app.state.progress_queue))
    yield
    logger.info('shutting down')
    listener.cancel()
    app.state.executor.shutdown()
    app.state.manager.shutdown()


app = FastAPI(lifespan=lifespan)

# TODO: setup lifespan with process pool
# NOTE: max_tasks_per_child to setup lifetime for process

DIR = path.abspath(path.join(__file__, "..", "..", "test"))



async def cleanup_when_done(futures: list[Future], file_path: str):
    asyncio_futures = [asyncio.wrap_future(f) for f in futures]
    results = await asyncio.gather(*(asyncio_futures), return_exceptions=True)
    exceptions = list(filter(lambda el: isinstance(el, Exception), results))
    for e in exceptions:
        logger.error(e)
    remove(file_path)


@app.post("/upload")
async def upload(request: Request, name: str, format: str) -> UploadResponse:

    # STEP 1: download original file
    # STEP 3: create entry in db
    # STEP 2: kick off worker to compress original file and save to file store
    # STEP 3: kick off worker for creating streamable content


    dir_path = path.join(DIR, 'files', name)
    file_path = path.join(dir_path, f'{name}.{format}')
    makedirs(dir_path)

    total_bytes = await download_file(request, file_path)

    # TODO: handle file types
    futures = [
        request.app.state.executor.submit(mock_process_video, file_path,
                                          request.app.state.progress_queue)
    ]
    asyncio.create_task(cleanup_when_done(futures, file_path))

    return UploadResponse(
        id='test',
        name=name,
        size_mb=total_bytes
    )
