from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field
from datetime import date


class FileFormat(StrEnum):
    """List of supported file formats for upload"""

    # video
    MOV = "video/quicktime"
    MP4 = "video/mp4"

    # FUTURE: add game format

    # FUTURE: music streaming???

class ContentType(StrEnum):
    """Content types to store"""

    MOVIE = 'movie'


class ContentModel(BaseModel):

    name: str

    title: str

    format: FileFormat

    description: str

    release_date: date

    content_type: ContentType

    genres: list[str] | None = Field(default=[])

    content_metadata: dict | None = Field(default={})


FILE_FORMAT_TO_EXT: dict[FileFormat, str] = {
    FileFormat.MOV: "mov",
    FileFormat.MP4: "mp4",
}


class UploadResponse(BaseModel):
    id: int
    size_mb: float


class BrowseResponse(BaseModel):
    content_id: int
    name: str


class ContentResponse(BaseModel):
    id: int
    name: str
    format: str
    description: str
    duration_s: int | None
    upload_time: datetime
    processed_time: datetime | None
    manifest_url: str | None
    """
    URL to the streaming manifest, only set once processing has completed
    """


class TaskType(StrEnum):

    MPEG_DASH = "mpeg_dash"
    """
    Create manifest and chunks of a file for streaming 
    """

    STORE = "save"
    """
    Store original content for download 
    """


class TaskStatus(StrEnum):

    IN_PROGRESS = "in_progress"

    COMPLETE = "complete"

    FAILED = "failed"
