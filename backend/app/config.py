"""
AutoSlice — Application configuration.
"""

import os
import sys
from typing import Annotated, Any
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# When frozen with PyInstaller sys.executable is the .exe itself;
# its parent is the backend/ folder inside the install dir.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Upload
    upload_dir: Path = Path(os.environ.get("UPLOAD_DIR", str(BASE_DIR / "temp")))

    # Database — explicit path so it never moves on restart
    db_path: Path = Path(os.environ.get("DB_PATH", str(BASE_DIR / "autoslice.db")))
    max_upload_size_mb: int = 200

    # CORS
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    coolify_fqdn: str | None = None

    # Data — override with AUTOSLICE_DATA_DIR when running from installer
    @property
    def data_dir(self) -> Path:
        override = os.environ.get("AUTOSLICE_DATA_DIR")
        if override:
            return Path(override)
        return BASE_DIR / "data"

    @property
    def printers_dir(self) -> Path:  # type: ignore[override]
        return self.data_dir / "printers"

    @property
    def filaments_dir(self) -> Path:  # type: ignore[override]
        return self.data_dir / "filaments"

    # Auth
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    jwt_expire_hours_remembered: int = 720  # 30 days

    # Email (Brevo SMTP relay)
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "admin@autoslice.be"
    from_name: str = "Autoslice"
    app_base_url: str = "http://localhost:3000"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            return []
        if value.startswith("["):
            import json

            return json.loads(value)
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def cors_origins(self) -> list[str]:
        origins = list(self.allowed_origins)
        if self.coolify_fqdn:
            origins.extend(self._origins_from_fqdn(self.coolify_fqdn))
        return list(dict.fromkeys(self._normalize_origin(origin) for origin in origins if origin))

    @staticmethod
    def _origins_from_fqdn(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    @staticmethod
    def _normalize_origin(origin: str) -> str:
        origin = origin.strip().strip('"').strip("'").rstrip("/")
        if not origin:
            return origin
        if origin.startswith("http://") or origin.startswith("https://"):
            return origin
        if origin.startswith("localhost") or origin.startswith("127.0.0.1"):
            return f"http://{origin}"
        return f"https://{origin}"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
if not settings.jwt_secret_key:
    raise RuntimeError("Missing required environment variable: JWT_SECRET_KEY")
settings.upload_dir.mkdir(parents=True, exist_ok=True)


def get_jwt_secret() -> str:
    """Return the JWT signing secret. Raises RuntimeError if not configured."""
    secret = settings.jwt_secret_key
    if not secret:
        raise RuntimeError("Missing required environment variable: JWT_SECRET_KEY")
    return secret
