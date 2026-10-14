"""SQLite-статистика скачанных треков."""
import os
import time
import sqlite3
import threading


class StatsDB:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        with self.lock:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    quality TEXT,
                    size_bytes INTEGER,
                    ts INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON downloads(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artist ON downloads(artist)")
            conn.commit()

    def add(self, track_id, title, artist, album, quality, size_bytes):
        try:
            with self.lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT INTO downloads "
                    "(track_id, title, artist, album, quality, size_bytes, ts) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(track_id or ""), title or "", artist or "",
                     album or "", quality or "", int(size_bytes or 0),
                     int(time.time()))
                )
                conn.commit()
        except Exception:
            pass

    def totals(self):
        try:
            with self.lock:
                conn = self._get_conn()
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt, COALESCE(SUM(size_bytes), 0) AS sz "
                    "FROM downloads"
                ).fetchone()
                return {"count": row["cnt"], "total_size": row["sz"]}
        except Exception:
            return {"count": 0, "total_size": 0}

    def top_artists(self, limit=5):
        try:
            with self.lock:
                conn = self._get_conn()
                rows = conn.execute(
                    "SELECT artist, COUNT(*) AS cnt FROM downloads "
                    "WHERE artist != '' GROUP BY artist "
                    "ORDER BY cnt DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [{"artist": r["artist"], "count": r["cnt"]} for r in rows]
        except Exception:
            return []

    def recent(self, limit=5):
        try:
            with self.lock:
                conn = self._get_conn()
                rows = conn.execute(
                    "SELECT title, artist, ts FROM downloads "
                    "ORDER BY ts DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [{"title": r["title"], "artist": r["artist"], "ts": r["ts"]}
                        for r in rows]
        except Exception:
            return []

    def summary(self):
        t = self.totals()
        sz = t["total_size"]
        if sz >= 1024 ** 3:
            sz_str = f"{sz / (1024 ** 3):.2f} ГБ"
        elif sz >= 1024 ** 2:
            sz_str = f"{sz / (1024 ** 2):.1f} МБ"
        elif sz >= 1024:
            sz_str = f"{sz / 1024:.0f} КБ"
        else:
            sz_str = f"{sz} Б"

        return {
            "count": t["count"],
            "total_size": sz,
            "total_size_str": sz_str,
            "top_artists": self.top_artists(5),
            "recent": self.recent(5),
        }

    def clear(self):
        try:
            with self.lock:
                conn = self._get_conn()
                conn.execute("DELETE FROM downloads")
                conn.commit()
            return True
        except Exception:
            return False