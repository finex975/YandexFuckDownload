import os
import json
import time
import threading


class DownloadHistory:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()

    # ─────────── IO ───────────

    def _load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self) -> None:
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass

    # ─────────── API ───────────

    def start(self, mode: str, url: str, quality: str,
              folder_title: str, target_path: str, tracks: list) -> None:
        with self.lock:
            self.data = {
                "mode": mode,
                "url": url,
                "quality": quality,
                "folder_title": folder_title,
                "target_path": target_path,
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
                "queue": [
                    {**t, "status": "pending", "position": i + 1, "total": len(tracks)}
                    for i, t in enumerate(tracks)
                ],
            }
            self._save()

    def mark(self, track_id: str, status: str) -> None:
        with self.lock:
            for item in self.data.get("queue", []):
                if item.get("id") == track_id:
                    item["status"] = status
                    break
            self.data["updated_at"] = int(time.time())
            self._save()

    def pending(self) -> list:
        with self.lock:
            return [it for it in self.data.get("queue", []) if it.get("status") == "pending"]

    def has_unfinished(self) -> bool:
        with self.lock:
            q = self.data.get("queue", [])
            if not q:
                return False
            return any(it.get("status") == "pending" for it in q)

    def folder_title(self) -> str:
        with self.lock:
            return self.data.get("folder_title") or ""

    def target_path(self) -> str:
        with self.lock:
            return self.data.get("target_path") or ""

    def summary(self) -> dict:
        with self.lock:
            q = self.data.get("queue", [])
            if not q:
                return {}
            ok = sum(1 for it in q if it.get("status") == "ok")
            fail = sum(1 for it in q if it.get("status") == "fail")
            skip = sum(1 for it in q if it.get("status") == "skip")
            pending = sum(1 for it in q if it.get("status") == "pending")
            return {
                "mode": self.data.get("mode"),
                "url": self.data.get("url"),
                "quality": self.data.get("quality"),
                "folder_title": self.data.get("folder_title"),
                "target_path": self.data.get("target_path"),
                "total": len(q),
                "ok": ok,
                "fail": fail,
                "skip": skip,
                "pending": pending,
            }

    def clear(self) -> None:
        with self.lock:
            self.data = {}
            self._save()