from enum import StrEnum
from typing import Any
from pydantic import BaseModel


class FileFormat(StrEnum):
    """List of supported file formats for upload"""

    # video
    MOV = "video/quicktime"
    MP4 = "video/mp4"

    # game
    # FUTURE: add game format

    # FUTURE: music streaming???


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
