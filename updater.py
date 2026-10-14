"""Проверка обновлений через GitHub Releases API."""
import re
import json
import urllib.request


# ⚠️ Замени на свой реальный репозиторий
GITHUB_REPO = "https://github.com/finex975/YandexFuckDownload"


def _parse_ver(v: str) -> tuple:
    v = (v or "").strip().lstrip("vV")
    parts = []
    for p in v.split(".")[:3]:
        m = re.match(r"(\d+)", p)
        parts.append(int(m.group(1)) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_update(current_version: str, repo: str = GITHUB_REPO, timeout: int = 8):
    """
    Возвращает dict или None при любой ошибке.
    {available, version, url, notes}
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "YandexMusicDownloader",
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

    tag = data.get("tag_name") or data.get("name") or ""
    html_url = data.get("html_url") or ""
    notes = (data.get("body") or "")[:600]

    cur = _parse_ver(current_version)
    new = _parse_ver(tag)

    return {
        "available": new > cur,
        "version": tag.lstrip("vV"),
        "url": html_url,
        "notes": notes,
    }