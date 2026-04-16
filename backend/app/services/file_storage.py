import os
import uuid
from pathlib import Path
from fastapi import UploadFile
from app.config import settings

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".3gp"}
DOC_EXTENSIONS = {".pdf"}


def get_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in PHOTO_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in DOC_EXTENSIONS:
        return "document"
    return "unknown"


async def save_upload(file: UploadFile, subdir: str) -> tuple[str, int]:
    """Save an uploaded file; returns (relative_path, size_bytes)."""
    ext = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dir_path = os.path.join(settings.upload_dir, subdir)
    Path(dir_path).mkdir(parents=True, exist_ok=True)

    full_path = os.path.join(dir_path, safe_name)
    content = await file.read()

    with open(full_path, "wb") as f:
        f.write(content)

    return os.path.join(subdir, safe_name), len(content)


def delete_file(relative_path: str) -> None:
    full_path = os.path.join(settings.upload_dir, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)


def full_path(relative_path: str) -> str:
    return os.path.join(settings.upload_dir, relative_path)
