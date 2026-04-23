"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import connect_db, close_db
from app.auth import setup_auth_exception_handler
from app.routers import api, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="Beetel Song Manager",
    description="Song database manager & REST API for the Beetel telephone Spotify controller",
    version="1.0.0",
    lifespan=lifespan,
)

# Auth redirect handler
setup_auth_exception_handler(app)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(api.router)
app.include_router(admin.router)
