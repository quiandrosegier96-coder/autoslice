"""
AutoSlice — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import upload, analyze, convert, auth, printers, admin, feedback, diagnostics, scoring, ratings, gcode
from app.config import settings
from app.database import init_db, seed_admin_users

app = FastAPI(
    title="AutoSlice API",
    description="Converts Bambu/MakerWorld 3MF project files into optimized Anycubic 3MF files.",
    version="1.3.3",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router,      prefix="/api", tags=["upload"])
app.include_router(analyze.router,     prefix="/api", tags=["analyze"])
app.include_router(convert.router,     prefix="/api", tags=["convert"])
app.include_router(auth.router,        prefix="/api", tags=["auth"])
app.include_router(printers.router,    prefix="/api", tags=["printers"])
app.include_router(admin.router,       prefix="/api", tags=["admin"])
app.include_router(feedback.router,    prefix="/api", tags=["feedback"])
app.include_router(diagnostics.router, prefix="/api", tags=["diagnostics"])
app.include_router(scoring.router,     prefix="/api", tags=["scoring"])
app.include_router(ratings.router,     prefix="/api", tags=["ratings"])
app.include_router(gcode.router,       prefix="/api", tags=["gcode"])


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_admin_users()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "autoslice"}
