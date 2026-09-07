from uuid import UUID, uuid4
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from sqlmodel import SQLModel, Field, Session, create_engine

from home_content_store.models import FileFormat, TaskType, TaskStatus
from home_content_store.env import DATA_DIR


# `data/` sits next to the package so the db file (and any other file-based
# stores) can be moved to a new machine by copying one directory.
DB_PATH = DATA_DIR / "content_store.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    # lets the ProcessPoolExecutor workers each open their own connection
    # against the same file without sqlite complaining.
    connect_args={"check_same_thread": False},
)


class Content(SQLModel, table=True):

    id: int = Field(default=None, primary_key=True)

    name: str
    """
    Name of the content
    """

    format: str
    """
    Media type of the content
    """

    description: str
    """
    Long form description of content

    Examples: Movie description, video game synopsis, ...
    """

    # TODO: add metadata support

    duration_s: int | None
    """
    OPTIONAL

    Duration of content in seconds
    """

    # TODO: thumbnail
    # thumbnail_b64_encoded: str
    # """
    # base64 encoded image thumbnail for content
    # """

    uploade_time: datetime = Field(default_factory=datetime.now)

    processed_time: datetime | None = Field(default=None)


class Task(SQLModel, table=True):

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    content_id: int

    task_type: str

    status: str

    progress: float

    start_time: datetime = Field(default_factory=datetime.now)

    end_time: datetime | None = Field(default=None)

    error: str | None = Field(default=None)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    # expire_on_commit=False: callers return ORM objects out of this
    # context manager after the session is closed, so attributes must
    # stay populated instead of expiring on commit.
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_content(
    name: str,
    format: FileFormat,
    description: str,
    duration_s: Optional[int] = None,
) -> Content:
    with get_session() as session:
        content = Content(
            name=name,
            format=format.value,
            description=description,
            duration_s=duration_s,
        )
        session.add(content)
        session.flush()
        session.refresh(content)
        return content


def create_task(
    content_id: int,
    task_type: TaskType,
) -> Task:
    with get_session() as session:
        task = Task(
            content_id=content_id,
            task_type=task_type.value,
            status=TaskStatus.IN_PROGRESS.value,
            progress=0.0
        )
        session.add(task)
        session.flush()
        session.refresh(task)
        return task 


def update_task(
    task_id: UUID,
    status: Optional[TaskStatus] = None,
    progress: Optional[float] = None,
    error: Optional[str] = None,
    end_time: Optional[datetime] = None,
) -> None:
    with get_session() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"no task with id {task_id}")
        if status is not None:
            task.status = status.value
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error = error
        if end_time is not None:
            task.end_time = end_time
        session.add(task)
        session.flush()
        session.refresh(task)


def mark_processed(content_id: int, processed_time: Optional[datetime] = None) -> None:
    with get_session() as session:
        content = session.get(Content, content_id)
        if content is None:
            raise ValueError(f"no content with id {content_id}")
        content.processed_time = processed_time or datetime.now()
        session.add(content)
        session.flush()
        session.refresh(content)
