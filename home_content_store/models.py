from enum import StrEnum
from typing import Any
from pydantic import BaseModel

class FileFormat(StrEnum):
    """List of supported file formats for upload"""

    # video
    MOV = "mov"
    MP4 = "mp4"

    # game
    # FUTURE: add game format


class UploadResponse(BaseModel):

    id: str
    name: str
    size_mb: float


class TaskType(StrEnum):

    UPLOAD = "upload"
    """
    Upload raw content data to file store compressed
    """

    MPEG_DASH = "mpeg_dash"
    """
    Create manifest and chunks of a video file for streaming 
    """


class Task(BaseModel):
    type: TaskType
    args: list[Any]
