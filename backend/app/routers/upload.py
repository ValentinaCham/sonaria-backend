from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.upload import UploadResponse
from app.services.storage_service import StorageService

router = APIRouter(prefix="/upload", tags=["upload"])
storage = StorageService()


@router.post("/audio", response_model=UploadResponse)
async def upload_audio(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
):
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only audio files are allowed",
        )

    data = await file.read()
    file_id = storage.save(data, file.filename)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "untitled",
        url=storage.get_url(file_id),
        size_bytes=len(data),
    )


@router.delete("/{file_id}", status_code=204)
def delete_audio(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    if not storage.delete(file_id):
        raise HTTPException(status_code=404, detail="File not found")
