from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class FileFormat(StrEnum):
    """List of supported file formats for upload"""

    # video
    MOV = "video/quicktime"
    MP4 = "video/mp4"

    # game
    # FUTURE: add game format

    # FUTURE: music streaming???

class ContentType(StrEnum):

    MOVIE = 'movie'

    TV_SHOW = 'tv_show'

    TV_SEASON = 'tv_season'

    TV_EPISODE = 'tv_episode'

    RECORDING = 'recording'


class ContentModel(BaseModel):

    name: str

    title: str

    format: FileFormat

    description: str

    content_type: ContentType

    parent_id: int | None = Field(default=None)


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
    Create and saved compressed version of file for later download
    """


class TaskStatus(StrEnum):

    IN_PROGRESS = "in_progress"

    COMPLETE = "complete"

    FAILED = "failed"
