"""
Admin web UI routes — login, dashboard, settings, and CRUD operations.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database import get_db
from app.auth import (
    require_login,
    create_session_cookie,
    verify_session_cookie,
    SESSION_COOKIE,
)
from app.config import settings
from app.models import SongCreate, SongUpdate
from app import spotify as spotify_helper

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


# ── Auth routes ──────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    # If already logged in, redirect to dashboard
    token = request.cookies.get(SESSION_COOKIE)
    if token and verify_session_cookie(token):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Process login form."""
    if username == settings.ADMIN_USER and password == settings.ADMIN_PASS:
        response = RedirectResponse("/", status_code=303)
        cookie = create_session_cookie(username)
        response.set_cookie(
            SESSION_COOKIE, cookie, httponly=True, samesite="lax", max_age=86400
        )
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password"},
    )


@router.get("/logout")
async def logout():
    """Clear session and redirect to login."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── Dashboard ────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_login)):
    """Render the main song management dashboard."""
    db = get_db()
    songs = []
    db_connected = True

    try:
        async for doc in db.songs.find().sort("dial_code", 1):
            songs.append(
                {
                    "id": str(doc["_id"]),
                    "dial_code": doc.get("dial_code", ""),
                    "spotify_uri": doc.get("spotify_uri", ""),
                    "song_name": doc.get("song_name", ""),
                    "artist": doc.get("artist", ""),
                    "is_playlist": doc.get("is_playlist", False),
                    "active": doc.get("active", True),
                }
            )
    except Exception:
        db_connected = False

    active_count = sum(1 for s in songs if s["active"])
    playlist_count = sum(1 for s in songs if s["is_playlist"])

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "songs": songs,
            "total": len(songs),
            "active_count": active_count,
            "playlist_count": playlist_count,
            "db_connected": db_connected,
        },
    )


# ── Song CRUD (AJAX) ────────────────────────────────────────


@router.post("/songs")
async def create_song(request: Request, user=Depends(require_login)):
    """Create a new song entry."""
    body = await request.json()
    try:
        song = SongCreate(**body)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    db = get_db()
    doc = song.model_dump()
    try:
        result = await db.songs.insert_one(doc)
    except DuplicateKeyError:
        return JSONResponse(
            {"error": f"Dial code '{song.dial_code}' already exists"}, status_code=409
        )

    return JSONResponse(
        {"id": str(result.inserted_id), "message": "Song created"}, status_code=201
    )


@router.put("/songs/{song_id}")
async def update_song(song_id: str, request: Request, user=Depends(require_login)):
    """Update an existing song entry."""
    body = await request.json()
    try:
        update = SongUpdate(**body)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    # Build update dict, excluding None fields
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    db = get_db()
    try:
        result = await db.songs.update_one(
            {"_id": ObjectId(song_id)}, {"$set": update_data}
        )
    except DuplicateKeyError:
        return JSONResponse(
            {"error": f"Dial code '{update_data.get('dial_code')}' already exists"},
            status_code=409,
        )

    if result.matched_count == 0:
        return JSONResponse({"error": "Song not found"}, status_code=404)

    return JSONResponse({"message": "Song updated"})


@router.delete("/songs/{song_id}")
async def delete_song(song_id: str, user=Depends(require_login)):
    """Delete a song entry."""
    db = get_db()
    result = await db.songs.delete_one({"_id": ObjectId(song_id)})
    if result.deleted_count == 0:
        return JSONResponse({"error": "Song not found"}, status_code=404)
    return JSONResponse({"message": "Song deleted"})


# ── Spotify lookup (AJAX) ───────────────────────────────────


@router.post("/spotify/lookup")
async def spotify_lookup(request: Request, user=Depends(require_login)):
    """Look up song/playlist metadata from Spotify."""
    body = await request.json()
    uri = body.get("uri", "")
    if not uri:
        return JSONResponse({"error": "No URI provided"}, status_code=400)

    result = await spotify_helper.lookup(uri)
    if not result:
        return JSONResponse(
            {"error": "Could not look up metadata. Check the URI and Spotify credentials."},
            status_code=404,
        )
    return JSONResponse(result)


@router.post("/spotify/test")
async def spotify_test(user=Depends(require_login)):
    """Test Spotify API credentials."""
    result = await spotify_helper.test_credentials()
    status_code = 200 if result["ok"] else 400
    return JSONResponse(result, status_code=status_code)


# ── Settings page ────────────────────────────────────────────


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user=Depends(require_login)):
    """Render the settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "spotify_client_id": settings.SPOTIFY_CLIENT_ID,
            "spotify_client_secret": settings.SPOTIFY_CLIENT_SECRET,
            "spotify_refresh_token": settings.SPOTIFY_REFRESH_TOKEN,
            "esp32_api_key": settings.ESP32_API_KEY,
        },
    )
