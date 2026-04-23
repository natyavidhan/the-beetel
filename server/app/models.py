"""
Pydantic models for song CRUD validation.
"""

import re
from pydantic import BaseModel, field_validator
from typing import Optional


def spotify_url_to_uri(value: str) -> str:
    """
    Convert a Spotify URL to a Spotify URI if needed.
    Handles formats like:
      - https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6
      - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
      - spotify:track:6rqhFgbbKwnb9MLmUQDhG6   (already a URI)
    """
    value = value.strip()

    # Already a Spotify URI
    if value.startswith("spotify:"):
        return value

    # Convert URL → URI
    match = re.match(
        r"https?://open\.spotify\.com/(track|playlist|album|artist|episode|show)/([a-zA-Z0-9]+)",
        value,
    )
    if match:
        resource_type = match.group(1)
        resource_id = match.group(2)
        return f"spotify:{resource_type}:{resource_id}"

    return value  # Return as-is if format unrecognized


class SongCreate(BaseModel):
    """Input model for creating a new song entry."""

    dial_code: str
    spotify_uri: str
    song_name: str = ""
    artist: str = ""
    is_playlist: bool = False
    active: bool = True

    @field_validator("dial_code")
    @classmethod
    def validate_dial_code(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("Dial code must contain only digits")
        if len(v) > 6:
            raise ValueError("Dial code must be at most 6 digits")
        if len(v) == 0:
            raise ValueError("Dial code cannot be empty")
        return v

    @field_validator("spotify_uri")
    @classmethod
    def normalize_spotify_uri(cls, v: str) -> str:
        uri = spotify_url_to_uri(v)
        if not uri.startswith("spotify:"):
            raise ValueError(
                "Invalid Spotify URI or URL. "
                "Expected format: spotify:track:ID or https://open.spotify.com/track/ID"
            )
        return uri


class SongUpdate(BaseModel):
    """Input model for updating an existing song entry (all fields optional)."""

    dial_code: Optional[str] = None
    spotify_uri: Optional[str] = None
    song_name: Optional[str] = None
    artist: Optional[str] = None
    is_playlist: Optional[bool] = None
    active: Optional[bool] = None

    @field_validator("dial_code")
    @classmethod
    def validate_dial_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v.isdigit():
            raise ValueError("Dial code must contain only digits")
        if len(v) > 6:
            raise ValueError("Dial code must be at most 6 digits")
        return v

    @field_validator("spotify_uri")
    @classmethod
    def normalize_spotify_uri(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        uri = spotify_url_to_uri(v)
        if not uri.startswith("spotify:"):
            raise ValueError("Invalid Spotify URI or URL")
        return uri


class SongResponse(BaseModel):
    """Output model for song entries."""

    id: str
    dial_code: str
    spotify_uri: str
    song_name: str
    artist: str
    is_playlist: bool
    active: bool
