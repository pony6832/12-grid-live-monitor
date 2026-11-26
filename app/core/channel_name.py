"""Find a channel's display name from a YouTube link, so slots name themselves."""
from __future__ import annotations

import html
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.youtube import YouTubeUrlError, parse_youtube_url

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5"}
CHANNEL_NAME = re.compile(r'<meta itemprop="name" content="([^"]+)"')


def _get(url: str, timeout: float) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def lookup_channel_name(url: str, timeout: float = 8) -> str | None:
    """The channel name for a video, live, playlist or /channel/ link; None when unknown."""
    try:
        target = parse_youtube_url(url)
    except YouTubeUrlError:
        return None
    try:
        if target.channel_id:
            match = CHANNEL_NAME.search(_get(f"https://www.youtube.com/channel/{target.channel_id}", timeout))
            return html.unescape(match[1]).strip() if match else None
        if target.video_id:
            page = f"https://www.youtube.com/watch?v={target.video_id}"
        else:
            page = f"https://www.youtube.com/playlist?list={target.playlist_id}"
        data = json.loads(_get("https://www.youtube.com/oembed?" + urlencode({"format": "json", "url": page}),
                               timeout))
        return str(data.get("author_name") or "").strip() or None
    except (OSError, ValueError):
        # Offline, private or removed video: the player reports the name once it plays.
        return None
