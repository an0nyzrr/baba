# spidtok-server/tiktok.py
# author: Найзер (spidos team)
"""Turning a @username into the numeric account id the mod and the badge
table actually key on -- a username can be freed and retaken, the id can't.

TikTok won't hand this out through any authenticated API we have, so it's
read the same way a browser gets it: the public profile page embeds a json
blob with the account's SIGI state, and the id is in there.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)

NAME_RE = re.compile(r"^[A-Za-z0-9._]{2,30}$")
DATA_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.S,
)

_cache: dict[str, tuple[float, "Profile"]] = {}
CACHE_TTL = 6 * 3600


@dataclass
class Profile:
    uid: str
    username: str
    nickname: str
    avatar: str | None


def is_valid_username(name: str) -> bool:
    return bool(name) and bool(NAME_RE.match(name.lstrip("@")))


def resolve(username: str, timeout: float = 12.0) -> Profile | None:
    """@username -> Profile, or None if the page can't be read or parsed.

    Cached for a few hours: the bot and the http server both call this and
    neither needs TikTok asked twice for the same name inside a minute.
    """
    username = username.lstrip("@").strip()
    if not is_valid_username(username):
        return None

    cached = _cache.get(username.lower())
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    url = "https://www.tiktok.com/@" + urllib.parse.quote(username)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(1_500_000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError):
        return None

    match = DATA_RE.search(html)
    if not match:
        return None
    try:
        blob = json.loads(match.group(1))
        user_detail = blob["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["user"]
        uid = str(user_detail["id"])
        nickname = user_detail.get("nickname") or username
        avatar = user_detail.get("avatarLarger") or user_detail.get("avatarMedium")
    except (KeyError, TypeError, ValueError):
        return None

    if not uid.isdigit():
        return None

    profile = Profile(uid=uid, username=username, nickname=nickname, avatar=avatar)
    if len(_cache) > 10_000:
        _cache.clear()
    _cache[username.lower()] = (time.time(), profile)
    return profile
