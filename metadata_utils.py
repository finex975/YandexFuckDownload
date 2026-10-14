import io
import os
import urllib.request

from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TPE2, TALB, TRCK, TDRC, TCON, APIC,
    error as ID3Error,
)
from mutagen.flac import FLAC, Picture

COVER_SIZE = "700x700"
_UA = {"User-Agent": "Mozilla/5.0 (YandexMusicDownloader)"}


def build_cover_url(cover_uri: str | None) -> str | None:
    if not cover_uri:
        return None
    return "https://" + cover_uri.replace("%%", COVER_SIZE)


def download_cover(cover_uri: str | None, timeout: int = 12) -> bytes | None:
    url = build_cover_url(cover_uri)
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        return data if len(data) > 1000 else None
    except Exception:
        return None


def get_cover_thumbnail(cover_uri: str | None, size: tuple = (64, 64)):
    try:
        from PIL import Image
    except Exception:
        return None
    data = download_cover(cover_uri)
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        return img
    except Exception:
        return None


def extract_metadata(track) -> dict:
    title = track.title or "Unknown"
    artists = ", ".join(a.name for a in (track.artists or []) if a.name) or "Unknown Artist"

    album_title = ""
    album_year = ""
    track_number = ""
    total_tracks = ""
    genre = ""

    if getattr(track, "albums", None):
        album = track.albums[0]
        album_title = getattr(album, "title", "") or ""
        if getattr(album, "year", None):
            album_year = str(album.year)
        genre = getattr(album, "genre", "") or ""

    pos = getattr(track, "track_position", None) or getattr(track, "position", None)
    if pos is not None:
        idx = getattr(pos, "index", None)
        vol = getattr(pos, "volume", None)
        if idx:
            track_number = str(idx)
        if vol:
            total_tracks = str(vol)

    cover_uri = getattr(track, "cover_uri", None)
    if not cover_uri and getattr(track, "albums", None):
        cover_uri = getattr(track.albums[0], "cover_uri", None)

    return {
        "title": title,
        "artists": artists,
        "album": album_title,
        "year": album_year,
        "track_number": track_number,
        "total_tracks": total_tracks,
        "genre": genre,
        "cover_uri": cover_uri,
    }


def extract_cover_uri(track) -> str | None:
    cover = getattr(track, "cover_uri", None)
    if cover:
        return cover
    if getattr(track, "albums", None):
        return getattr(track.albums[0], "cover_uri", None)
    return None


def embed_metadata(filepath: str, meta: dict) -> None:
    ext = os.path.splitext(filepath)[1].lower()
    cover_data = download_cover(meta.get("cover_uri"))

    if ext == ".mp3":
        _embed_mp3(filepath, meta, cover_data)
    elif ext == ".flac":
        _embed_flac(filepath, meta, cover_data)


def _embed_mp3(filepath: str, meta: dict, cover: bytes | None) -> None:
    try:
        audio = MP3(filepath, ID3=ID3)
    except ID3Error:
        audio = MP3(filepath)
        audio.add_tags()

    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags

    if meta.get("title"):
        tags.add(TIT2(encoding=3, text=meta["title"]))
    if meta.get("artists"):
        tags.add(TPE1(encoding=3, text=meta["artists"]))
        tags.add(TPE2(encoding=3, text=meta["artists"]))
    if meta.get("album"):
        tags.add(TALB(encoding=3, text=meta["album"]))
    if meta.get("year"):
        tags.add(TDRC(encoding=3, text=meta["year"]))
    if meta.get("genre"):
        tags.add(TCON(encoding=3, text=meta["genre"]))
    if meta.get("track_number"):
        trck = meta["track_number"]
        if meta.get("total_tracks"):
            trck = f"{trck}/{meta['total_tracks']}"
        tags.add(TRCK(encoding=3, text=trck))

    if cover:
        tags.delall("APIC")
        tags.add(APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,
            desc="Cover",
            data=cover,
        ))

    audio.save(v2_version=3)


def _embed_flac(filepath: str, meta: dict, cover: bytes | None) -> None:
    audio = FLAC(filepath)

    if meta.get("title"):
        audio["title"] = meta["title"]
    if meta.get("artists"):
        audio["artist"] = meta["artists"]
        audio["albumartist"] = meta["artists"]
    if meta.get("album"):
        audio["album"] = meta["album"]
    if meta.get("year"):
        audio["date"] = meta["year"]
    if meta.get("genre"):
        audio["genre"] = meta["genre"]
    if meta.get("track_number"):
        audio["tracknumber"] = meta["track_number"]

    if cover:
        audio.clear_pictures()
        pic = Picture()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.desc = "Cover"
        pic.data = cover
        audio.add_picture(pic)

    audio.save()


# ═══════════════════════════════════════════════════════════════════════
#                          ★ ТЕКСТЫ ПЕСЕН ★
# ═══════════════════════════════════════════════════════════════════════

def fetch_lyrics(track) -> str | None:
    """
    Возвращает текст песни (обычно LRC с таймкодами),
    либо None если текста нет или нет прав.
    """
    try:
        lyrics = getattr(track, "lyrics", None)
        if not lyrics:
            return None
        if getattr(lyrics, "has_rights", True) is False:
            return None

        # Lazy-load
        if hasattr(lyrics, "fetch"):
            try:
                fetched = lyrics.fetch()
                if fetched:
                    lyrics = fetched
            except Exception:
                pass

        text = (getattr(lyrics, "text", None) or "").strip()
        if not text:
            text = (getattr(lyrics, "full_text", None) or "").strip()

        return text or None
    except Exception:
        return None


def save_lyrics(audio_path: str, lyrics_text: str) -> str | None:
    """Сохраняет .lrc рядом с аудиофайлом."""
    if not lyrics_text:
        return None
    try:
        base, _ = os.path.splitext(audio_path)
        lrc_path = base + ".lrc"
        with open(lrc_path, "w", encoding="utf-8") as f:
            f.write(lyrics_text)
        return lrc_path
    except Exception:
        return None