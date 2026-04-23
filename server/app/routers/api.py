"""
ESP32-facing REST API endpoints.
All endpoints require a valid API key via X-API-Key header.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.auth import require_api_key

router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(require_api_key)])


@router.get("/health")
async def health():
    """Simple health check for ESP32 connectivity test."""
    return {"status": "ok"}


@router.get("/songs")
async def list_songs():
    """
    Return all active songs as a JSON array.
    Shape matches what the ESP32 firmware expects.
    """
    db = get_db()
    cursor = db.songs.find({"active": True}, {"_id": 0})
    songs = []
    async for doc in cursor:
        songs.append(
            {
                "dial_code": doc.get("dial_code", ""),
                "spotify_uri": doc.get("spotify_uri", ""),
                "song_name": doc.get("song_name", ""),
                "artist": doc.get("artist", ""),
                "is_playlist": doc.get("is_playlist", False),
            }
        )
    return songs


@router.get("/songs/{dial_code}")
async def get_song(dial_code: str):
    """Return a single active song by dial code."""
    db = get_db()
    doc = await db.songs.find_one(
        {"dial_code": dial_code, "active": True}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Song not found")
    return {
        "dial_code": doc.get("dial_code", ""),
        "spotify_uri": doc.get("spotify_uri", ""),
        "song_name": doc.get("song_name", ""),
        "artist": doc.get("artist", ""),
        "is_playlist": doc.get("is_playlist", False),
    }


# ── Player Control Proxy ────────────────────────────────────
# These allow the ESP32 to control Spotify without handling OAuth tokens itself.

from pydantic import BaseModel
from app import spotify as spotify_helper

class PlayRequest(BaseModel):
    uri: str
    is_playlist: bool = False

@router.post("/player/play")
async def player_play(req: PlayRequest):
    success = await spotify_helper.play(req.uri, req.is_playlist)
    if not success:
        raise HTTPException(status_code=400, detail="Playback failed")
    return {"status": "ok"}

@router.post("/player/volume")
async def player_volume(percent: int):
    success = await spotify_helper.set_volume(percent)
    if not success:
        raise HTTPException(status_code=400, detail="Volume change failed")
    return {"status": "ok"}

@router.post("/player/next")
async def player_next():
    success = await spotify_helper.next_track()
    if not success:
        raise HTTPException(status_code=400, detail="Action failed")
    return {"status": "ok"}

@router.post("/player/previous")
async def player_prev():
    success = await spotify_helper.prev_track()
    if not success:
        raise HTTPException(status_code=400, detail="Action failed")
    return {"status": "ok"}

@router.post("/player/restart")
async def player_restart():
    success = await spotify_helper.restart_track()
    if not success:
        raise HTTPException(status_code=400, detail="Action failed")
    return {"status": "ok"}

@router.get("/player/now-playing")
async def player_now_playing():
    data = await spotify_helper.now_playing()
    if not data:
        raise HTTPException(status_code=404, detail="No song currently playing")
    return data

