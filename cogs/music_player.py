import asyncio
import discord
import yt_dlp
import re
from dataclasses import dataclass, field
from typing import Optional
import os

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.5"'
}

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

YDL_PLAYLIST_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'ignoreerrors': True,
}


@dataclass
class Track:
    title: str
    url: str
    duration: int
    thumbnail: str
    webpage_url: str
    requester: discord.Member
    stream_url: Optional[str] = None

    def format_duration(self) -> str:
        if not self.duration:
            return "Live"
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def progress_bar(self, current: int, length: int = 20) -> str:
        if not self.duration or self.duration == 0:
            return "▬" * length
        filled = int((current / self.duration) * length)
        return "▓" * filled + "░" * (length - filled)


async def search_youtube(query: str) -> Optional[dict]:
    """Search YouTube and return track info."""
    opts = dict(YDL_OPTIONS)
    if not query.startswith(('http://', 'https://')):
        query = f"ytsearch:{query}"
        opts['noplaylist'] = True
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        if not data:
            return None
        if 'entries' in data:
            data = data['entries'][0]
        return data
    except Exception as e:
        print(f"[YTSearch Error] {e}")
        return None


async def fetch_stream_url(webpage_url: str) -> Optional[str]:
    """Get direct audio stream URL from a YouTube URL."""
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(webpage_url, download=False))
        if data:
            return data.get('url')
    except Exception as e:
        print(f"[StreamURL Error] {e}")
    return None


async def fetch_playlist_tracks(url: str) -> list:
    """Fetch all tracks from a YouTube playlist."""
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YDL_PLAYLIST_OPTIONS) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        if not data or 'entries' not in data:
            return []
        tracks = []
        for entry in data['entries']:
            if entry:
                tracks.append({
                    'title': entry.get('title', 'Unknown'),
                    'url': entry.get('url') or entry.get('webpage_url') or f"https://youtube.com/watch?v={entry.get('id','')}",
                    'duration': entry.get('duration', 0),
                    'thumbnail': entry.get('thumbnail', ''),
                    'webpage_url': entry.get('webpage_url') or f"https://youtube.com/watch?v={entry.get('id','')}",
                })
        return tracks
    except Exception as e:
        print(f"[Playlist Error] {e}")
        return []


async def fetch_spotify_tracks(url: str) -> list:
    """Fetch tracks from Spotify URL using yt-dlp (no Premium needed).
    yt-dlp resolves Spotify tracks by searching YouTube automatically."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'ignoreerrors': True,
        'default_search': 'ytsearch',
    }
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        if not data:
            return []
        tracks = []
        # Single track
        if data.get('_type') == 'url' or 'entries' not in data:
            tracks.append({
                'title': data.get('title', 'Unknown'),
                'url': data.get('url') or data.get('webpage_url', ''),
                'duration': data.get('duration', 0),
                'thumbnail': data.get('thumbnail', ''),
                'webpage_url': data.get('webpage_url') or data.get('url', ''),
            })
        else:
            for entry in data.get('entries', []):
                if entry:
                    tracks.append({
                        'title': entry.get('title', 'Unknown'),
                        'url': entry.get('url') or entry.get('webpage_url', ''),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'webpage_url': entry.get('webpage_url') or entry.get('url', ''),
                    })
        return tracks
    except Exception as e:
        print(f"[Spotify/yt-dlp Error] {e}")
        return []


class GuildMusicState:
    def __init__(self):
        self.queue: list[Track] = []
        self.current: Optional[Track] = None
        self.loop_mode: str = "off"   # off / single / queue
        self.volume: float = 0.5
        self.is_247: bool = False
        self.start_time: Optional[float] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self._idle_task: Optional[asyncio.Task] = None

    def clear(self):
        self.queue.clear()
        self.current = None
        self.start_time = None

    def get_elapsed(self) -> int:
        import time
        if self.start_time:
            return int(time.time() - self.start_time)
        return 0
