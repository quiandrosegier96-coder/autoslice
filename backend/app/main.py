"""
AutoSlice — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import upload, analyze, convert, auth, printers, admin, feedback, diagnostics, scoring, ratings, gcode, community
from app.api.routes import support_engine, download
from app.api.routes import universal_convert
from app.ai import router as ai_router
from app.reviews import router as reviews_router
from app.config import settings
from app.database import init_db, seed_admin_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_admin_users()
    yield


app = FastAPI(
    title="AutoSlice API",
    description="Converts Bambu/MakerWorld 3MF project files into optimized Anycubic 3MF files.",
    version="1.5.63",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
app.include_router(gcode.router,           prefix="/api", tags=["gcode"])
app.include_router(community.router,       prefix="/api", tags=["community"])
app.include_router(support_engine.router,  tags=["support-engine"])
app.include_router(download.router,        prefix="/api", tags=["download"])
app.include_router(universal_convert.router, prefix="/api", tags=["universal-3mf"])
app.include_router(ai_router.router,       prefix="/api", tags=["ai"])
app.include_router(reviews_router.router,  prefix="/api", tags=["reviews"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "autoslice"}
