"""Where uploaded bytes live: the FileStorage interface (D-059).

Like WordPress's uploads folder, but behind one small interface so the app
does not care where the bytes go: a local folder (backend/.local-storage,
git-ignored) on your machine and in tests, and the private Vercel Blob store
(D-055) on staging and production. Keys are random paths under
schools/{school_id}/ that the database checks (files.storage_key).

The Blob store is connected with the first staging deploy of uploads; until
then, outside local, uploads and downloads answer 503 rather than write to a
container's disk that disappears.
"""

from pathlib import Path, PurePosixPath
from typing import Protocol

from fastapi import Request

from app.core.errors import ProblemError

LOCAL_ROOT = Path(__file__).resolve().parents[2] / ".local-storage"  # backend/.local-storage


class FileStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


class LocalFileStorage:
    """A folder on disk; keys become relative paths inside it."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("A storage key must stay inside the storage folder.")
        path = (self._root / relative).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("A storage key must stay inside the storage folder.")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


def get_file_storage(request: Request) -> FileStorage:
    if request.app.state.app_env == "local":
        return LocalFileStorage(LOCAL_ROOT)
    raise ProblemError(503, "Service unavailable", "File storage is not set up yet.")
