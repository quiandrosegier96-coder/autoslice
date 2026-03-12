"""
AutoSlice — Upload validator.
Checks that the uploaded file is a valid .3mf archive before processing.
"""

from fastapi import UploadFile, HTTPException

from app.config import settings

# Magic bytes for ZIP (all .3mf files are ZIP archives)
_ZIP_MAGIC = b"PK\x03\x04"


async def validate_3mf_upload(file: UploadFile) -> None:
    """
    Validate the uploaded file:
    - Must have .3mf extension
    - Must not exceed size limit
    - Must start with ZIP magic bytes
    Raises HTTPException on failure.
    """
    if not file.filename or not file.filename.lower().endswith(".3mf"):
        raise HTTPException(status_code=400, detail="Only .3mf files are accepted.")

    # Read first 4 bytes to check magic, then reset
    header = await file.read(4)
    await file.seek(0)

    if header != _ZIP_MAGIC:
        raise HTTPException(status_code=400, detail="File does not appear to be a valid ZIP/3MF archive.")

    # Check content-length header if provided
    if file.size and file.size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
        )
