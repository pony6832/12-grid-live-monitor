from __future__ import annotations

from urllib.parse import urlencode

from app.core.youtube import YouTubeUrlError, parse_youtube_url


def build_watch_playback_url(url: str) -> str:
    normalized = _normalize_url(url)
    separator = "&" if "?" in normalized else "?"
    params = {
        "autoplay": "1",
        "mute": "1",
        "vq": "hd1080",
    }
    return normalized + separator + urlencode(params)


def build_embed_playback_url(url: str) -> str:
    params = {
        "autoplay": "1",
        "mute": "1",
        "controls": "1",
        "rel": "0",
        "modestbranding": "1",
        "iv_load_policy": "3",
        "vq": "hd1080",
    }
    try:
        target = parse_youtube_url(url)
    except YouTubeUrlError:
        fallback = _normalize_url(url)
        separator = "&" if "?" in fallback else "?"
        return fallback + separator + urlencode(params)

    if target.video_id:
        if target.playlist_id:
            params["list"] = target.playlist_id
        return f"https://www.youtube.com/embed/{target.video_id}?{urlencode(params)}"

    if target.playlist_id:
        params["list"] = target.playlist_id
        return f"https://www.youtube.com/embed/videoseries?{urlencode(params)}"

    fallback = _normalize_url(url)
    separator = "&" if "?" in fallback else "?"
    return fallback + separator + urlencode(params)


def _normalize_url(url: str) -> str:
    clean = url.strip()
    if "://" not in clean:
        return "https://" + clean
    return clean
