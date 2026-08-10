"""Bounded immutable in-memory representation of a 3MF ZIP package."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import zipfile

from app.threemf.container.security import UnsafeThreeMFError, normalized_member_name, validate_member_type


@dataclass(frozen=True)
class ContainerLimits:
    max_files: int = 2_000
    max_entry_bytes: int = 256 * 1024 * 1024
    max_uncompressed_bytes: int = 512 * 1024 * 1024
    max_compression_ratio: float = 200.0


class ThreeMFContainer:
    """Read-only package contents validated before exposure to parsers."""

    __slots__ = ("_entries", "filename")

    def __init__(self, entries: dict[str, bytes], filename: str = "upload.3mf") -> None:
        self._entries = dict(entries)
        self.filename = filename

    @classmethod
    def from_path(cls, path: Path, limits: ContainerLimits | None = None) -> "ThreeMFContainer":
        return cls.from_bytes(path.read_bytes(), filename=path.name, limits=limits)

    @classmethod
    def from_bytes(cls, payload: bytes, filename: str = "upload.3mf", limits: ContainerLimits | None = None) -> "ThreeMFContainer":
        configured = limits or ContainerLimits()
        try:
            archive = zipfile.ZipFile(BytesIO(payload), "r")
        except zipfile.BadZipFile as exc:
            raise UnsafeThreeMFError("File is not a valid ZIP/3MF package.") from exc
        entries: dict[str, bytes] = {}
        total_size = 0
        with archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(infos) > configured.max_files:
                raise UnsafeThreeMFError(f"Archive contains too many files ({len(infos)}).")
            for info in infos:
                name = normalized_member_name(info.filename)
                validate_member_type(info)
                if name in entries:
                    raise UnsafeThreeMFError(f"Duplicate ZIP member: {name}")
                if info.file_size > configured.max_entry_bytes:
                    raise UnsafeThreeMFError(f"ZIP member is too large: {name}")
                total_size += info.file_size
                if total_size > configured.max_uncompressed_bytes:
                    raise UnsafeThreeMFError("Archive exceeds the uncompressed size limit.")
                if info.file_size / max(info.compress_size, 1) > configured.max_compression_ratio:
                    raise UnsafeThreeMFError(f"Suspicious compression ratio: {name}")
                entries[name] = archive.read(info)
        return cls(entries, filename)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def exists(self, path: str) -> bool:
        return path.lstrip("/") in self._entries

    def read(self, path: str) -> bytes:
        normalized = path.lstrip("/")
        try:
            return self._entries[normalized]
        except KeyError as exc:
            raise FileNotFoundError(normalized) from exc

    def files_with_suffix(self, suffix: str) -> tuple[str, ...]:
        return tuple(path for path in self.paths if path.lower().endswith(suffix.lower()))
