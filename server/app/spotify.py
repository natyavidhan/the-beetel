"""
Spotify Web API helper — metadata lookup via Client Credentials flow.
"""

import re
import httpx
from app.config import settings


async def _get_client_token() -> str | None:
    """Get a Spotify access token using Client Credentials flow (for lookup)."""
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    return None


import time

_user_token = None
_user_token_expiry = 0

async def _get_user_token() -> str | None:
    """
    Get a Spotify access token capable of controlling playback.
    Uses the refresh_token flow.
    """
    global _user_token, _user_token_expiry

    if not settings.SPOTIFY_REFRESH_TOKEN:
        return None

    # Return cached token if valid (with 60s buffer)
    if _user_token and time.time() < _user_token_expiry - 60:
        return _user_token

    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": settings.SPOTIFY_REFRESH_TOKEN,
            },
            auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
        )
        if resp.status_code == 200:
            data = resp.json()
            _user_token = data.get("access_token")
            _user_token_expiry = time.time() + data.get("expires_in", 3600)
            return _user_token

    return None


def _parse_spotify_id(uri_or_url: str) -> tuple[str, str] | None:
    """
    Extract (type, id) from a Spotify URI or URL.
    Returns None if unrecognizable.
    """
    # URI format: spotify:track:ID
    m = re.match(r"spotify:(track|playlist|album|artist|episode|show):(\w+)", uri_or_url)
    if m:
        return m.group(1), m.group(2)

    # URL format: https://open.spotify.com/track/ID?si=...
    m = re.match(
        r"https?://open\.spotify\.com/(track|playlist|album|artist|episode|show)/(\w+)",
        uri_or_url,
    )
    if m:
        return m.group(1), m.group(2)

    return None


async def lookup(uri_or_url: str) -> dict | None:
    """
    Look up metadata for a Spotify track or playlist.

    Returns:
        {
            "song_name": str,
            "artist": str,
            "is_playlist": bool,
            "album_art": str | None,
        }
    or None on failure.
    """
    parsed = _parse_spotify_id(uri_or_url)
    if not parsed:
        return None

    resource_type, resource_id = parsed
    token = await _get_client_token()
    if not token:
        return None

    async with httpx.AsyncClient() as client:
        if resource_type == "track":
            resp = await client.get(
                f"https://api.spotify.com/v1/tracks/{resource_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                artists = ", ".join(a["name"] for a in data.get("artists", []))
                album_art = None
                images = data.get("album", {}).get("images", [])
                if images:
                    album_art = images[0]["url"]
                return {
                    "song_name": data.get("name", ""),
                    "artist": artists,
                    "is_playlist": False,
                    "album_art": album_art,
                }

        elif resource_type == "playlist":
            resp = await client.get(
                f"https://api.spotify.com/v1/playlists/{resource_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "name,owner.display_name,images"},
            )
            if resp.status_code == 200:
                data = resp.json()
                album_art = None
                images = data.get("images", [])
                if images:
                    album_art = images[0]["url"]
                return {
                    "song_name": data.get("name", ""),
                    "artist": data.get("owner", {}).get("display_name", ""),
                    "is_playlist": True,
                    "album_art": album_art,
                }

        elif resource_type == "album":
            resp = await client.get(
                f"https://api.spotify.com/v1/albums/{resource_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                artists = ", ".join(a["name"] for a in data.get("artists", []))
                album_art = None
                images = data.get("images", [])
                if images:
                    album_art = images[0]["url"]
                return {
                    "song_name": data.get("name", ""),
                    "artist": artists,
                    "is_playlist": False,
                    "album_art": album_art,
                }

    return None


async def test_credentials() -> dict:
    """
    Test if the configured Spotify credentials are valid.
    Returns {"ok": bool, "message": str}.
    """
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return {"ok": False, "message": "Spotify Client ID or Secret not configured"}

    token = await _get_client_token()
    if token:
        # Also check refresh token if present
        if settings.SPOTIFY_REFRESH_TOKEN:
            user_token = await _get_user_token()
            if not user_token:
                return {"ok": False, "message": "Client credentials valid, but Refresh Token is invalid"}
            return {"ok": True, "message": "Spotify credentials and Refresh Token are valid ✓"}
            
        return {"ok": True, "message": "Spotify client credentials valid (Lookups will work, but Playback requires Refresh Token)"}
    return {"ok": False, "message": "Failed to authenticate — check Client ID and Secret"}


# ── Playback Controls ────────────────────────────────────────

async def play(uri: str, is_playlist: bool = False) -> bool:
    """Start playback for a URI."""
    token = await _get_user_token()
    if not token:
        return False

    body = {"context_uri": uri} if is_playlist else {"uris": [uri]}
    async with httpx.AsyncClient() as client:
        res = await client.put(
            "https://api.spotify.com/v1/me/player/play",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        return res.status_code in (200, 202, 204)

async def set_volume(percent: int) -> bool:
    """Set Spotify volume."""
    token = await _get_user_token()
    if not token:
        return False
        
    async with httpx.AsyncClient() as client:
        res = await client.put(
            f"https://api.spotify.com/v1/me/player/volume?volume_percent={percent}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return res.status_code in (200, 202, 204)

async def next_track() -> bool:
    token = await _get_user_token()
    if not token: return False
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.spotify.com/v1/me/player/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        return res.status_code in (200, 202, 204)

async def prev_track() -> bool:
    token = await _get_user_token()
    if not token: return False
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.spotify.com/v1/me/player/previous",
            headers={"Authorization": f"Bearer {token}"},
        )
        return res.status_code in (200, 202, 204)

async def restart_track() -> bool:
    token = await _get_user_token()
    if not token: return False
    async with httpx.AsyncClient() as client:
        res = await client.put(
            "https://api.spotify.com/v1/me/player/seek?position_ms=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        return res.status_code in (200, 202, 204)

async def now_playing() -> dict | None:
    token = await _get_user_token()
    if not token: return None
    
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token}"},
        )
        if res.status_code == 200:
            data = res.json()
            if not data or "item" not in data or not data["item"]:
                return None
            return {
                "song_name": data["item"].get("name", ""),
                "artist": data["item"].get("artists", [{}])[0].get("name", "") if data["item"].get("artists") else "",
            }
        return None
