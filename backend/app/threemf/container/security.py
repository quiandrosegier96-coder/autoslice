"""ZIP entry validation used before any uploaded 3MF data is read."""

import stat
from pathlib import PurePosixPath
from zipfile import ZipInfo


class UnsafeThreeMFError(ValueError):
    """Raised when an archive violates package safety constraints."""


def normalized_member_name(raw_name: str) -> str:
    if not raw_name or "\\" in raw_name or "\x00" in raw_name:
        raise UnsafeThreeMFError(f"Unsafe ZIP member name: {raw_name!r}")
    path = PurePosixPath(raw_name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafeThreeMFError(f"Unsafe ZIP member path: {raw_name!r}")
    if path.parts and ":" in path.parts[0]:
        raise UnsafeThreeMFError(f"Absolute ZIP member path: {raw_name!r}")
    return path.as_posix().rstrip("/")


def validate_member_type(info: ZipInfo) -> None:
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if unix_mode and stat.S_ISLNK(unix_mode):
        raise UnsafeThreeMFError(f"Symbolic links are not allowed: {info.filename}")
    if info.flag_bits & 0x1:
        raise UnsafeThreeMFError(f"Encrypted ZIP entries are not supported: {info.filename}")
