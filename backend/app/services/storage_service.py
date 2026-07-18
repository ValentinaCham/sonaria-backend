import uuid
from pathlib import Path

from app.config import settings


class StorageService:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, filename: str | None = None) -> str:
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix if filename else ".wav"
        filepath = self.base_dir / f"{file_id}{ext}"
        filepath.write_bytes(data)
        return file_id

    def get_path(self, file_id: str) -> Path | None:
        for f in self.base_dir.iterdir():
            if f.stem == file_id:
                return f
        return None

    def get_url(self, file_id: str) -> str:
        return f"/uploads/{file_id}"

    def delete(self, file_id: str) -> bool:
        path = self.get_path(file_id)
        if not path:
            return False
        path.unlink()
        return True
