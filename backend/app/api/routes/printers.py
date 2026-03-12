"""
AutoSlice — Printers listing route.
GET /api/printers — returns all available printer profiles.
"""

import json
from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter()


class PrinterOut(BaseModel):
    id: str
    display_name: str
    build_volume_x_mm: int
    build_volume_y_mm: int
    build_volume_z_mm: int
    supported_filaments: list[str]
    max_colors: int = 1


@router.get("/printers", response_model=list[PrinterOut])
def list_printers() -> list[PrinterOut]:
    printers = []
    for f in sorted(settings.printers_dir.glob("*.json")):
        data = json.loads(f.read_text())
        printers.append(PrinterOut(
            id=data["id"],
            display_name=data["display_name"],
            build_volume_x_mm=data["build_volume_x_mm"],
            build_volume_y_mm=data["build_volume_y_mm"],
            build_volume_z_mm=data["build_volume_z_mm"],
            supported_filaments=data["supported_filaments"],
            max_colors=data.get("max_colors", 1),
        ))
    return printers
