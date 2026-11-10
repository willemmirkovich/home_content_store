import re
from uuid import UUID, uuid4
from contextlib import contextmanager
from datetime import datetime, date, timezone
from typing import Iterator, Optional

from sqlalchemy import JSON, Column, LargeBinary, event
from sqlmodel import SQLModel, Field, Session, create_engine, select

from home_content_store.models import ContentType, FileFormat, TaskType, TaskStatus, ThumbnailFormat
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


@event.listens_for(engine, "connect")
def _register_regexp(dbapi_connection, connection_record) -> None:
    # sqlite has no native regex support; `Column.regexp_match()` compiles
    # to the REGEXP operator, which sqlite dispatches to a user-defined
    # function that must be registered per-connection.
    dbapi_connection.create_function(
        "REGEXP", 2, lambda pattern, value: re.search(pattern, value) is not None
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Content(SQLModel, table=True):

    id: int = Field(default=None, primary_key=True)

    name: str = Field(unique=True)
    """
    Name of the content. Must be unique
    """

    title: str
    """
    Tiltle of content, can be duplicated. For instance, Season 1
    of tv show
    """

    format: FileFormat
    """
    Media type of the content
    """

    description: str
    """
    Long form description of content

    Examples: Movie description, video game synopsis, ...
    """

    content_type: ContentType
    """
    Type of content
    """

    release_date: date

    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """
    Genres of content
    """

    # TODO: add metadata support

    duration_s: int | None
    """
    OPTIONAL

    Duration of content in seconds
    """

    content_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))

    creation_time: datetime = Field(default_factory=utc_now)
    """
    When the content item was created, before any media is attached
    """

    upload_time: datetime | None = Field(default=None)
    """
    When the media was uploaded, `None` until then
    """

    processed_time: datetime | None = Field(default=None)


class Thumbnail(SQLModel, table=True):
    """
    Thumbnail image for a content item, kept out of `Content` so listing
    content doesn't load every image blob.
    """

    content_id: int = Field(primary_key=True, foreign_key="content.id")

    data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    """
    Raw image bytes
    """

    format: ThumbnailFormat
    """
    Image media type of `data`
    """

    update_time: datetime = Field(default_factory=utc_now)
    """
    When the thumbnail was last set, used to version the thumbnail URL
    """


class Task(SQLModel, table=True):

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    content_id: int

    task_type: str

    status: str

    progress: float

    start_time: datetime = Field(default_factory=utc_now)

    end_time: datetime | None = Field(default=None)

    error: str | None = Field(default=None)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        # media can only be uploaded once per content item
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS content_upload_once
            BEFORE UPDATE OF upload_time ON content
            WHEN OLD.upload_time IS NOT NULL
            BEGIN
                SELECT RAISE(ABORT, 'content already uploaded');
            END
            """
        )


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
    title: str,
    format: FileFormat,
    content_type: ContentType,
    description: str,
    release_date: date,
    genres: list[str] | None = None,
    content_metadata: dict | None = None,
    duration_s: int | None = None,
) -> Content:
    with get_session() as session:
        content = Content(
            name=name,
            title=title,
            content_type=content_type,
            format=format,
            description=description,
            release_date=release_date,
            genres=genres or [],
            content_metadata=content_metadata or {},
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


def get_content_by_id(content_id: int) -> Optional[Content]:
    with get_session() as session:
        return session.get(Content, content_id)


# TODO: add genres
# TODO: add page iterator
def browse_content(
    name: Optional[str] = None,
    content_type: Optional[ContentType] = None,
) -> list[tuple[Content, Optional[datetime]]]:
    """
    Filter content by name and/or type (media format), both matched as regexes.

    Returns each content item with its thumbnail's `update_time`, `None` if
    it has no thumbnail. The image bytes themselves aren't loaded.
    """
    query = (
        select(Content, Thumbnail.update_time)
        .outerjoin(Thumbnail, Thumbnail.content_id == Content.id)
        .where(Content.processed_time != None)
    )
    if name is not None:
        query = query.where(Content.name.regexp_match(name))
    if content_type is not None:
        query = query.where(Content.content_type == content_type)
    with get_session() as session:
        return [(content, thumbnail_time) for content, thumbnail_time in session.exec(query).all()]


def set_thumbnail(content_id: int, data: bytes, format: ThumbnailFormat) -> None:
    """
    Create or replace the thumbnail for `content_id`
    """
    with get_session() as session:
        thumbnail = session.get(Thumbnail, content_id)
        if thumbnail is None:
            thumbnail = Thumbnail(content_id=content_id, data=data, format=format)
        else:
            thumbnail.data = data
            thumbnail.format = format
            thumbnail.update_time = utc_now()
        session.add(thumbnail)


def get_thumbnail(content_id: int) -> Optional[Thumbnail]:
    with get_session() as session:
        return session.get(Thumbnail, content_id)


def get_thumbnail_time(content_id: int) -> Optional[datetime]:
    """
    `update_time` of the thumbnail for `content_id`, without loading the image
    """
    with get_session() as session:
        return session.exec(
            select(Thumbnail.update_time).where(Thumbnail.content_id == content_id)
        ).first()


def mark_uploaded(content_id: int, upload_time: Optional[datetime] = None) -> None:
    """
    Set `upload_time`. Raises `IntegrityError` (via the `content_upload_once`
    trigger) if media was already uploaded.
    """
    with get_session() as session:
        content = session.get(Content, content_id)
        if content is None:
            raise ValueError(f"no content with id {content_id}")
        content.upload_time = upload_time or utc_now()
        session.add(content)


def set_duration(content_id: int, duration_s: int) -> None:
    with get_session() as session:
        content = session.get(Content, content_id)
        if content is None:
            raise ValueError(f"no content with id {content_id}")
        content.duration_s = duration_s
        session.add(content)


def mark_processed(content_id: int, processed_time: Optional[datetime] = None) -> None:
    with get_session() as session:
        content = session.get(Content, content_id)
        if content is None:
            raise ValueError(f"no content with id {content_id}")
        content.processed_time = processed_time or utc_now()
        session.add(content)
        session.flush()
        session.refresh(content)
