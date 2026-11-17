from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse


@dataclass(frozen=True, slots=True)
class YouTubeTarget:
    video_id: str | None = None
    playlist_id: str | None = None
    # A channel's current live stream: survives the stream being restarted under a new video id.
    channel_id: str | None = None

    @property
    def is_playlist(self) -> bool:
        return self.playlist_id is not None


class YouTubeUrlError(ValueError):
    pass


def parse_youtube_url(value: str) -> YouTubeTarget:
    url = value.strip()
    if not url:
        raise YouTubeUrlError("YouTube URL is empty.")

    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)

    playlist_id = _first_query_value(query, "list")
    video_id: str | None = None

    channel_id: str | None = None

    if host == "youtu.be":
        if path_parts:
            video_id = path_parts[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if len(path_parts) >= 2 and path_parts[0].lower() == "channel":
            channel_id = path_parts[1]
        elif path_parts and path_parts[0].startswith("@"):
            raise YouTubeUrlError("不支援 @帳號 網址，請改用 youtube.com/channel/UC…/live 或影片網址")
        else:
            video_id = _parse_youtube_com_path(path_parts, query)
    else:
        raise YouTubeUrlError(f"不是 YouTube 網址：{parsed.netloc}")

    if not video_id and not playlist_id and not channel_id:
        raise YouTubeUrlError("網址裡找不到影片、播放清單或頻道 ID")

    return YouTubeTarget(video_id=_clean_id(video_id), playlist_id=_clean_id(playlist_id),
                         channel_id=_clean_id(channel_id))


def _parse_youtube_com_path(path_parts: list[str], query: dict[str, list[str]]) -> str | None:
    if not path_parts:
        return _first_query_value(query, "v")

    first = path_parts[0].lower()
    if first == "watch":
        return _first_query_value(query, "v")
    if first in {"shorts", "live", "embed", "v"} and len(path_parts) >= 2:
        return path_parts[1]
    if first == "playlist":
        return None
    return _first_query_value(query, "v")


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0] or None


def _clean_id(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
