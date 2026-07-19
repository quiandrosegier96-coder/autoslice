"""Entry point for PyInstaller — starts the uvicorn server."""
import sys
import os

# When frozen, make sure the bundle dir is on sys.path so 'app' is importable
if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

import uvicorn
from app.main import app  # noqa: E402 — import after path fix

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=port,
        reload=False,
    )
