"""
AutoSlice — Application configuration.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Upload
    upload_dir: Path = Path(os.environ.get("UPLOAD_DIR", str(BASE_DIR / "temp")))

    # Database — explicit path so it never moves on restart
    db_path: Path = Path(os.environ.get("DB_PATH", str(BASE_DIR / "autoslice.db")))
    max_upload_size_mb: int = 200

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Data
    printers_dir: Path = BASE_DIR / "data" / "printers"
    filaments_dir: Path = BASE_DIR / "data" / "filaments"

    # Auth
    jwt_secret_key: str = "autoslice-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Email (Brevo SMTP relay)
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "AutoSlice <admin@autoslice.be>"
    app_base_url: str = "http://localhost:3000"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
