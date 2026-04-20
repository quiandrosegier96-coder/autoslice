import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

router = APIRouter()

_INSTALLER_DIR = Path(__file__).resolve().parents[4] / "dist" / "installer"


def _installer_path() -> Path:
    override = os.environ.get("AUTOSLICE_INSTALLER_PATH")
    if override:
        return Path(override)
    exes = sorted(_INSTALLER_DIR.glob("*.exe"))
    if not exes:
        raise FileNotFoundError("No .exe installer found in dist/installer/")
    return exes[-1]


@router.get("/download")
def download_windows_installer():
    path = _installer_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Installer not found")
    return FileResponse(
        path=str(path),
        media_type="application/octet-stream",
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )
