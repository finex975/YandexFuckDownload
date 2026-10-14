import os
import re
import json
import time
import random
import threading
import traceback
import webbrowser
import queue as queue_module
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from yandex_music import Client
from yandex_music.exceptions import UnauthorizedError, DeviceAuthError

from translations import LANG_NAMES, NAME_TO_CODE, TRANSLATIONS
from metadata_utils import (
    extract_metadata, embed_metadata,
    fetch_lyrics, save_lyrics,
)
from secure_store import save_token, load_token, delete_token
from history import DownloadHistory
from stats import StatsDB
from log_setup import setup_logger
from updater import check_update
from notify import notify

APP_VERSION = "2.0.0"
DEFAULT_DELAY = 2.0
DEFAULT_RETRIES = 6
DEFAULT_RETRY_BASE = 8
MAX_WAIT = 60
MAX_METADATA_WORKERS = 5
DOWNLOAD_WORKERS = 3
CHUNK_SIZE = 64 * 1024
PROGRESS_THROTTLE = 0.3


# ─────────────── Утилиты ───────────────

def _sanitize(name):
    name = "".join(c for c in str(name) if c.isalnum() or c in " .-_")
    return name.strip() or "unnamed"


def _unique_path(folder: str, fname: str) -> str:
    base, ext = os.path.splitext(fname)
    candidate = os.path.join(folder, fname)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{base} ({counter}){ext}")
        counter += 1
    return candidate


def _find_existing_audio(folder: str, artist: str, title: str):
    """Ищет уже скачанный файл artist - title.(mp3|flac) в папке."""
    if not os.path.isdir(folder):
        return None
    base = f"{_sanitize(artist)} - {_sanitize(title)}"
    for ext in (".mp3", ".flac"):
        p = os.path.join(folder, base + ext)
        if _valid_file(p):
            return p
    try:
        for fname in os.listdir(folder):
            if fname.startswith(base) and fname.lower().endswith((".mp3", ".flac")):
                p = os.path.join(folder, fname)
                if _valid_file(p):
                    return p
    except Exception:
        pass
    return None


def _is_429(err):
    resp = getattr(err, "response", None)
    if resp is not None and getattr(resp, "status_code", None) == 429:
        return True
    t = str(err)
    return "429" in t or "Concurrency" in t or "Too Many Requests" in t


def _retry_after(err):
    resp = getattr(err, "response", None)
    if resp is None:
        return None
    try:
        ra = resp.headers.get("Retry-After")
        if ra is None:
            return None
        return max(1, min(int(ra), MAX_WAIT))
    except Exception:
        return None


def _backoff(attempt, base):
    return int(min(base * (2 ** (attempt - 1)) * random.uniform(0.7, 1.3), MAX_WAIT))


def _valid_file(p, min_size=500_000):
    try:
        return os.path.exists(p) and os.path.getsize(p) > min_size
    except OSError:
        return False


def _parse_playlist_url(url):
    m = re.search(r"/users/([^/]+)/playlists/(\d+)", url)
    if not m:
        raise ValueError("Invalid playlist URL")
    return m.group(1), int(m.group(2))


def _parse_album_url(url):
    m = re.search(r"/album/(\d+)", url)
    if not m:
        raise ValueError("Invalid album URL")
    return int(m.group(1))


def _parse_track_url(url):
    m = re.search(r"/track/(\d+)", url)
    if not m:
        raise ValueError("Invalid track URL")
    return int(m.group(1))


def _format_eta(seconds):
    if seconds is None or seconds <= 0:
        return "—"
    if seconds > 86400 * 3:
        return ">3d"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _folder_dialog_type():
    try:
        import webview
        if hasattr(webview, "FileDialog"):
            return webview.FileDialog.FOLDER
        if hasattr(webview, "FOLDER_DIALOG"):
            return webview.FOLDER_DIALOG
    except Exception:
        pass
    return 2


def _track_meta_dict(track, index, total):
    artist = track.artists[0].name if track.artists else "Unknown Artist"
    album = ""
    if getattr(track, "albums", None) and track.albums:
        album = getattr(track.albums[0], "title", "") or ""

    cover_uri = getattr(track, "cover_uri", None)
    if not cover_uri and getattr(track, "albums", None) and track.albums:
        cover_uri = getattr(track.albums[0], "cover_uri", None)
    cover_url = ("https://" + cover_uri.replace("%%", "120x120")) if cover_uri else ""

    duration_ms = getattr(track, "duration_ms", 0) or 0

    return {
        "id": str(getattr(track, "id", "") or ""),
        "index": index,
        "total": total,
        "title": str(getattr(track, "title", "") or ""),
        "artist": artist,
        "album": album,
        "cover_url": cover_url,
        "duration": int(duration_ms // 1000) if duration_ms else 0,
    }


class _EtaEstimator:
    def __init__(self, window: int = 12):
        self.window = window
        self.samples = []

    def add(self, duration: float):
        self.samples.append(duration)
        if len(self.samples) > self.window:
            self.samples.pop(0)

    def eta(self, remaining: int) -> str:
        if not self.samples or remaining <= 0:
            return "—"
        avg = sum(self.samples) / len(self.samples)
        avg_parallel = avg / max(1, DOWNLOAD_WORKERS)
        return _format_eta(avg_parallel * remaining)


class JsApi:
    def __init__(self, settings_path: str, app_dir: str):
        self.settings_path = settings_path
        self.app_dir = app_dir
        self._settings = self._load_settings()

        self.token_fallback_path = os.path.join(app_dir, "token.dat")
        self._token_cache = ""

        self._history = DownloadHistory(os.path.join(app_dir, "history.json"))
        self._stats = StatsDB(os.path.join(app_dir, "stats.db"))
        self._logger = setup_logger(app_dir)

        self._events = queue_module.Queue()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker_thread = None
        self._preview_thread = None
        self._auth_thread = None
        self._auth_cancel = threading.Event()
        self._rate_limit_shown = False
        self._path_lock = threading.Lock()

        self._tray = None
        self._quit_requested = False

        self._minimize_on_close = bool(self._settings.get("minimize_to_tray", False))

        self._preview_cache = {
            "mode": None, "url": None, "title": "",
            "tracks": [], "created_at": 0,
        }

    # ───────────── settings ─────────────
    def _load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.pop("token", None)
            return data
        except Exception:
            return {}

    def _save_settings(self):
        try:
            safe = {k: v for k, v in self._settings.items() if k != "token"}
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(safe, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _emit(self, kind, **payload):
        self._events.put({"type": kind, **payload})

    def _log(self, text: str):
        self._emit("log", text=text)
        self._logger.info(text)

    # ───────────── exposed ─────────────
    def get_bootstrap(self):
        return {
            "version": APP_VERSION,
            "settings": {**self._settings, "token": self.get_token()},
            "lang_names": LANG_NAMES,
            "translations": TRANSLATIONS,
            "history": self._history.summary(),
            "stats": self._stats.summary(),
        }

    def run_startup_check(self):
        """Автопроверка при старте. Эмитит события в UI, возвращает сводку."""
        try:
            from startup_check import StartupChecker
            checker = StartupChecker(self)
            results = checker.run()
        except Exception as e:
            self._log(f"[!] startup_check: {type(e).__name__}: {e}")
            return {"ok": 0, "warn": 0, "fail": 1, "results": []}

        for r in results:
            self._emit("startup_step", **r)

        ok = sum(1 for r in results if r["status"] == "ok")
        warn = sum(1 for r in results if r["status"] == "warn")
        fail = sum(1 for r in results if r["status"] == "fail")

        hist = self._history.summary()
        resume_ready = bool(hist.get("pending", 0) > 0)
        can_resume = resume_ready and fail == 0 and bool(self.get_token())

        auto = bool(self._settings.get("auto_resume_on_start", False))
        if auto and can_resume:
            self._log("[i] Автозапуск докачки (auto_resume_on_start=true)")
            try:
                self.start_download({
                    **self._settings,
                    "token": self.get_token(),
                    "resume": True,
                })
            except Exception as e:
                self._log(f"[!] auto_resume: {type(e).__name__}: {e}")

        self._emit("startup_done",
                   ok=ok, warn=warn, fail=fail,
                   resume_ready=can_resume,
                   history=hist)

        return {"ok": ok, "warn": warn, "fail": fail, "results": results}

    def save_settings(self, data):
        if isinstance(data, dict):
            if "token" in data:
                self.set_token(data.pop("token"))
            self._settings.update(data)
            if "minimize_to_tray" in self._settings:
                self._minimize_on_close = bool(self._settings["minimize_to_tray"])
            self._save_settings()
        return True

    def get_token(self):
        if self._token_cache:
            return self._token_cache
        self._token_cache = load_token(self.token_fallback_path)
        return self._token_cache

    def set_token(self, token: str):
        self._token_cache = token or ""
        save_token(self._token_cache, self.token_fallback_path)

    def poll_events(self):
        out = []
        try:
            while True:
                out.append(self._events.get_nowait())
        except queue_module.Empty:
            pass
        return out

    def pick_folder(self, initial=None):
        try:
            import webview as wv
            w = wv.windows[0] if getattr(wv, "windows", None) else None
            if not w:
                return None
            dialog_type = _folder_dialog_type()
            result = w.create_file_dialog(dialog_type, directory=initial or "")
            if result:
                return result[0]
        except Exception as e:
            self._log(f"[!] pick_folder: {type(e).__name__}: {e}")
        return None

    def open_external(self, url):
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

    def open_folder(self, path):
        try:
            path = str(path or "").strip()
            if not path or not os.path.isdir(path):
                return False
            if os.name == "nt":
                os.startfile(path)
            else:
                import subprocess
                cmd = ["open", path] if os.uname().sysname == "Darwin" else ["xdg-open", path]
                subprocess.Popen(cmd)
            return True
        except Exception:
            return False

    def get_history(self):
        return self._history.summary()

    def clear_history(self):
        self._history.clear()
        return True

    def check_update(self):
        try:
            result = check_update(APP_VERSION)
            return result or {"available": False}
        except Exception:
            return {"available": False}

    def get_stats(self):
        return self._stats.summary()

    def clear_stats(self):
        return self._stats.clear()

    # ★ Отладка трека
    def debug_track(self, track_id):
        """Отладочная инфа по треку — почему не качается."""
        try:
            token = self.get_token()
            if not token:
                return {"error": "no_token"}
            client = Client(token).init()
            res = client.tracks([str(track_id)])
            if not res:
                return {"error": "not_found"}
            t = res[0]
            infos = t.get_download_info() or []
            return {
                "id": t.id,
                "title": t.title,
                "artists": [a.name for a in (t.artists or [])],
                "available": getattr(t, "available", None),
                "download_infos": [
                    {"codec": getattr(i, "codec", None),
                     "bitrate": getattr(i, "bitrate_in_kbps", None)}
                    for i in infos
                ],
                "count": len(infos),
            }
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    # ★ RESET
    def reset_data(self, kinds):
        result = {}
        kinds = set(kinds or [])
        try:
            if "token" in kinds:
                self.set_token("")
                result["token"] = True
            if "stats" in kinds:
                self._stats.clear()
                result["stats"] = True
            if "history" in kinds:
                self._history.clear()
                result["history"] = True
            if "logs" in kinds:
                self._clear_logs()
                result["logs"] = True
            if "settings" in kinds:
                self._settings = {}
                self._save_settings()
                result["settings"] = True
        except Exception as e:
            self._log(f"[!] reset_data: {type(e).__name__}: {e}")
        return result

    def _clear_logs(self):
        try:
            logs_dir = os.path.join(self.app_dir, "logs")
            if not os.path.isdir(logs_dir):
                return
            for fname in os.listdir(logs_dir):
                if fname.startswith("app.log"):
                    try:
                        os.remove(os.path.join(logs_dir, fname))
                    except Exception:
                        pass
        except Exception:
            pass

    def get_help_info(self):
        return {
            "app_dir": self.app_dir,
            "settings_path": self.settings_path,
            "token_path": self.token_fallback_path,
            "history_path": os.path.join(self.app_dir, "history.json"),
            "stats_path": os.path.join(self.app_dir, "stats.db"),
            "logs_dir": os.path.join(self.app_dir, "logs"),
        }

    # ───────────── TRAY / QUIT ─────────────
    def set_tray(self, tray):
        self._tray = tray

    def minimize_to_tray(self, enable: bool = True):
        self._minimize_on_close = bool(enable)
        self._settings["minimize_to_tray"] = self._minimize_on_close
        self._save_settings()
        return True

    def hide_window(self):
        try:
            import webview as wv
            if getattr(wv, "windows", None):
                wv.windows[0].hide()
                return True
        except Exception as e:
            self._log(f"[!] hide_window: {type(e).__name__}: {e}")
        return False

    def request_quit(self):
        self._quit_requested = True
        self._stop_event.set()
        self._pause_event.clear()
        try:
            if self._tray:
                self._tray.stop()
        except Exception:
            pass

    def should_quit(self) -> bool:
        return bool(self._quit_requested)

    # ───────────── EXPORT / IMPORT ─────────────
    def export_settings(self):
        try:
            import webview as wv
            w = wv.windows[0] if getattr(wv, "windows", None) else None
            if not w:
                return {"ok": False, "error": "no_window"}

            try:
                from webview import SAVE_DIALOG
            except Exception:
                SAVE_DIALOG = getattr(getattr(wv, "FileDialog", None), "SAVE", 1)

            path = w.create_file_dialog(
                SAVE_DIALOG,
                save_filename="ymd_settings.json",
                file_types=("JSON files (*.json)",),
            )
            if not path:
                return {"ok": False, "error": "cancelled"}
            if isinstance(path, (list, tuple)):
                path = path[0]

            data = {k: v for k, v in self._settings.items() if k != "token"}
            data["__version__"] = APP_VERSION
            data["__exported_at"] = int(time.time())

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return {"ok": True, "path": path}
        except Exception as e:
            self._log(f"[!] export_settings: {type(e).__name__}: {e}")
            return {"ok": False, "error": str(e)}

    def import_settings(self):
        try:
            import webview as wv
            w = wv.windows[0] if getattr(wv, "windows", None) else None
            if not w:
                return {"ok": False, "error": "no_window"}

            dialog_type = _folder_dialog_type()
            try:
                from webview import OPEN_DIALOG
                dialog_type = OPEN_DIALOG
            except Exception:
                fd = getattr(wv, "FileDialog", None)
                if fd is not None and hasattr(fd, "OPEN"):
                    dialog_type = fd.OPEN

            result = w.create_file_dialog(
                dialog_type,
                allow_multiple=False,
                file_types=("JSON files (*.json)",),
            )
            if not result:
                return {"ok": False, "error": "cancelled"}
            path = result[0] if isinstance(result, (list, tuple)) else result

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"ok": False, "error": "invalid_format"}

            data.pop("__version__", None)
            data.pop("__exported_at", None)
            data.pop("token", None)

            self._settings.update(data)
            if "minimize_to_tray" in self._settings:
                self._minimize_on_close = bool(self._settings["minimize_to_tray"])
            self._save_settings()
            return {"ok": True, "settings": self._settings}
        except Exception as e:
            self._log(f"[!] import_settings: {type(e).__name__}: {e}")
            return {"ok": False, "error": str(e)}

    # ───────────── AUTH ─────────────
    def start_auth(self):
        if self._auth_thread and self._auth_thread.is_alive():
            self._log("[!] Авторизация уже идёт")
            return False
        self._auth_cancel.clear()
        self._auth_thread = threading.Thread(target=self._auth_worker, daemon=True)
        self._auth_thread.start()
        return True

    def cancel_auth(self):
        self._auth_cancel.set()
        return True

    def _auth_worker(self):
        try:
            client = Client()

            def on_code(dev):
                self._emit("auth_code",
                           user_code=dev.user_code,
                           url=dev.verification_url)

            def should_cancel():
                return self._auth_cancel.is_set()

            self._log("[i] Запрашиваю код устройства у Яндекса...")
            token = client.device_auth(on_code=on_code, poll_interval=2,
                                       timeout=300, should_cancel=should_cancel)
            if token is None:
                self._emit("auth_error", message="Отменено пользователем")
                return
            self._emit("auth_token", token=token.access_token)
        except DeviceAuthError as e:
            self._emit("auth_error", message=f"OAuth: {e}")
        except Exception as e:
            self._emit("auth_error", message=f"{type(e).__name__}: {e}")

    # ───────────── PREVIEW ─────────────
    def preview_tracks(self, cfg):
        if self._preview_thread and self._preview_thread.is_alive():
            self._log("[!] Загрузка списка уже идёт")
            return False
        if self._worker_thread and self._worker_thread.is_alive():
            self._log("[!] Скачивание уже идёт")
            return False

        self._stop_event.clear()
        self._preview_thread = threading.Thread(
            target=self._preview_worker, args=(cfg or {},), daemon=True)
        self._preview_thread.start()
        return True

    def _preview_worker(self, cfg):
        try:
            token = str(cfg.get("token") or self.get_token() or "").strip()
            mode = cfg.get("mode", "likes")
            url = str(cfg.get("url", "")).strip()

            if not token:
                self._log("[ERR] Токен пустой. Введите токен или войдите в Яндекс.")
                self._emit("preview_done", ok=False, error="no_token")
                return
            if mode != "likes" and not url:
                self._log("[ERR] Не указана ссылка")
                self._emit("preview_done", ok=False, error="no_url")
                return

            self._log("[i] Авторизация...")
            client = Client(token).init()
            self._log("[OK] Авторизация успешна")

            self._emit("preview_start")
            tracks, title = self._collect_tracks(client, mode, url, False)
            if not tracks:
                self._log("[!] Треков не найдено")
                self._emit("preview_done", ok=False, error="no_tracks")
                return

            total = len(tracks)
            self._log(f"[i] Загружено метаданных: {total}")

            self._preview_cache = {
                "mode": mode,
                "url": url,
                "title": title,
                "tracks": tracks,
                "created_at": time.time(),
            }

            batch = []
            for i, tr in enumerate(tracks, 1):
                if self._stop_event.is_set():
                    break
                batch.append(_track_meta_dict(tr, i, total))
                if len(batch) >= 20:
                    self._emit("preview_batch", items=batch)
                    batch = []
                    time.sleep(0.01)
            if batch:
                self._emit("preview_batch", items=batch)

            self._emit("preview_done", ok=True, total=total, title=title)

        except UnauthorizedError:
            self._log("[ERR] Неверный токен")
            self._emit("preview_done", ok=False, error="unauthorized")
        except ValueError as e:
            self._log(f"[ERR] Неверная ссылка: {e}")
            self._emit("preview_done", ok=False, error="bad_url")
        except Exception as e:
            self._log(f"[ERR] {type(e).__name__}: {e!r}")
            self._emit("preview_done", ok=False, error="critical")

    def clear_preview(self):
        self._preview_cache = {"mode": None, "url": None, "title": "",
                               "tracks": [], "created_at": 0}
        return True

    # ───────────── DOWNLOAD ─────────────
    def start_download(self, cfg):
        if self._worker_thread and self._worker_thread.is_alive():
            self._log("[!] Скачивание уже идёт")
            return False
        if self._preview_thread and self._preview_thread.is_alive():
            self._log("[!] Сначала дождись загрузки списка")
            return False
        self._stop_event.clear()
        self._pause_event.clear()
        self._rate_limit_shown = False
        self._worker_thread = threading.Thread(
            target=self._download_worker, args=(cfg or {},), daemon=True)
        self._worker_thread.start()
        return True

    def cancel_download(self):
        self._stop_event.set()
        self._pause_event.clear()
        return True

    def pause_download(self):
        self._pause_event.set()
        return True

    def resume_download(self):
        self._pause_event.clear()
        return True

    def is_busy(self):
        busy = (self._worker_thread and self._worker_thread.is_alive()) or \
               (self._preview_thread and self._preview_thread.is_alive()) or \
               (self._auth_thread and self._auth_thread.is_alive())
        return bool(busy)

    # ───────────── DOWNLOAD WORKER ─────────────
    def _download_worker(self, cfg):
        try:
            token = str(cfg.get("token") or self.get_token() or "").strip()
            mode = cfg.get("mode", "likes")
            url = str(cfg.get("url", "")).strip()
            path = str(cfg.get("path", "")).strip()
            quality = cfg.get("quality", "auto")
            resume = bool(cfg.get("resume", False))
            save_lyr = bool(cfg.get("save_lyrics", True))
            folder_structure = bool(cfg.get("folder_structure", False))
            selected_ids = cfg.get("selected_ids")

            try:
                delay = float(cfg.get("delay", DEFAULT_DELAY))
            except Exception:
                delay = DEFAULT_DELAY
            try:
                retries = int(cfg.get("retries", DEFAULT_RETRIES))
            except Exception:
                retries = DEFAULT_RETRIES
            try:
                retry_base = int(cfg.get("retry_base", DEFAULT_RETRY_BASE))
            except Exception:
                retry_base = DEFAULT_RETRY_BASE

            if not token:
                self._log("[ERR] Токен пустой.")
                self._emit("done", ok=0, failed=0, unavailable=0)
                return

            if resume and not path:
                path = self._history.target_path() or ""

            if not path:
                self._log("[ERR] Не указана папка для скачивания. Нажмите «Обзор».")
                self._emit("done", ok=0, failed=0, unavailable=0)
                return

            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                self._log(f"[ERR] Не удалось создать папку: {path} — {e}")
                self._emit("done", ok=0, failed=0, unavailable=0)
                return

            use_cache = (
                self._preview_cache["tracks"]
                and self._preview_cache["mode"] == mode
                and (mode == "likes" or self._preview_cache["url"] == url)
                and (time.time() - self._preview_cache["created_at"] < 3600)
            )

            if use_cache:
                tracks = list(self._preview_cache["tracks"])
                title = self._preview_cache["title"] or "Liked"
                self._log(f"[i] Использую загруженный список ({len(tracks)} треков)")
            else:
                self._log("[i] Авторизация...")
                client = Client(token).init()
                self._log("[OK] Авторизация успешна")
                tracks, title = self._collect_tracks(client, mode, url, resume)

            if not tracks:
                self._log("[!] Треков не найдено")
                self._emit("done", ok=0, failed=0, unavailable=0)
                return

            if selected_ids:
                ids_set = set(str(x) for x in selected_ids)
                before = len(tracks)
                tracks = [t for t in tracks if str(getattr(t, "id", "")) in ids_set]
                self._log(f"[i] Отфильтровано: {len(tracks)} из {before}")

            if not tracks:
                self._log("[!] Ничего не выбрано")
                self._emit("done", ok=0, failed=0, unavailable=0)
                return

            if resume:
                folder_title = self._history.folder_title() or _sanitize(title) or "resume"
                self._log(f"[i] Докачка в существующую папку: {folder_title}")
            else:
                folder_title = _sanitize(title)

            folder = os.path.join(path, folder_title)
            os.makedirs(folder, exist_ok=True)

            if not resume:
                self._history.start(
                    mode, url, quality, folder_title, path,
                    [
                        {
                            "id": str(getattr(t, "id", "") or ""),
                            "title": str(getattr(t, "title", "") or ""),
                            "artist": ", ".join(a.name for a in (t.artists or []) if a.name),
                        } for t in tracks
                    ]
                )

            self._log(f"[i] Папка: {folder}")
            self._log(f"[i] К скачиванию: {len(tracks)} (в {DOWNLOAD_WORKERS} потока)")
            if folder_structure:
                self._log("[i] Структура: Artist/Album/NN - Title")

            stats = self._download_loop(
                tracks, folder, quality,
                retries, retry_base, delay, save_lyr,
                folder_structure=folder_structure,
                base_path=folder,
            )

            self._log(f"[i] Итог: скачано {stats.get('ok',0)}, "
                      f"пропущено {stats.get('skip',0)}, "
                      f"недоступно {stats.get('unavailable',0)}, "
                      f"ошибок {stats.get('fail',0)}")

            if not self._history.has_unfinished():
                self._history.clear()
                self._log("[i] Очередь докачки очищена (всё завершено)")

            try:
                total_ok = stats.get("ok", 0) + stats.get("skip", 0)
                total_fail = stats.get("fail", 0)
                total_unavail = stats.get("unavailable", 0)
                if total_ok or total_fail or total_unavail:
                    msg = f"Скачано: {total_ok}"
                    if total_unavail:
                        msg += f", недоступно: {total_unavail}"
                    if total_fail:
                        msg += f", ошибок: {total_fail}"
                    notify("Yandex Music Downloader", msg)
            except Exception:
                pass

            self._emit("done",
                       ok=stats.get("ok", 0) + stats.get("skip", 0),
                       failed=stats.get("fail", 0),
                       unavailable=stats.get("unavailable", 0),
                       path=folder)

        except UnauthorizedError:
            self._log("[ERR] Неверный токен. Проверьте токен или войдите заново.")
            self._emit("done", ok=0, failed=0, unavailable=0)
        except ValueError as e:
            self._log(f"[ERR] Неверная ссылка: {e}")
            self._emit("done", ok=0, failed=0, unavailable=0)
        except Exception as e:
            self._log(f"[ERR] Критическая ошибка: {type(e).__name__}: {e!r}")
            for line in traceback.format_exc().splitlines():
                self._log("   " + line)
            self._emit("done", ok=0, failed=0, unavailable=0)

    # ───────────── COLLECT ─────────────
    def _collect_tracks(self, client, mode, url, resume: bool):
        tracks, title = [], ""

        if resume and self._history.has_unfinished():
            pending_ids = [it["id"] for it in self._history.pending()]
            if not pending_ids:
                return [], ""
            self._log(f"[i] Докачка: {len(pending_ids)} треков из истории")
            try:
                fetched = client.tracks(pending_ids)
                tracks = [t for t in fetched if t]
                title = self._history.folder_title() or "resume"
            except Exception as e:
                self._log(f"[ERR] Не удалось получить pending: {e}")
                return [], ""
            return tracks, title

        if mode == "likes":
            self._log("[i] Загружаю 'Мне нравится'...")
            liked = client.users_likes_tracks()
            if not liked:
                self._log("[!] Треков нет")
                return [], ""
            total = len(liked)
            self._emit("total", total=total)
            self._log(f"[i] Найдено треков: {total}")

            def extract(lt):
                try:
                    return lt.fetch_track()
                except Exception as e:
                    self._log(f"    [!] fetch_track: {type(e).__name__}: {e}")
                    return None

            tracks = self._fetch_parallel(list(liked), total, extract)
            title = "Liked"

        elif mode == "playlist":
            self._log(f"[i] Загружаю плейлист: {url}")
            clean = url.split("?")[0].split("#")[0]
            user_id, kind = _parse_playlist_url(clean)
            pl = None
            try:
                res = client.users_playlists(kind, user_id)
                if isinstance(res, list) and res:
                    pl = res[0]
                elif hasattr(res, "fetch_tracks"):
                    pl = res
                elif isinstance(res, dict) and res:
                    first = next(iter(res.values()))
                    if hasattr(first, "fetch_tracks"):
                        pl = first
            except Exception as e:
                self._log(f"[!] {type(e).__name__}: {e!r}")
            if pl is None:
                self._log("[ERR] Не удалось получить плейлист")
                return [], ""
            title = getattr(pl, "title", None) or f"playlist_{kind}"
            try:
                fetched = pl.fetch_tracks()
                raw = fetched if isinstance(fetched, list) else (getattr(fetched, "tracks", []) or [])
            except Exception as e:
                self._log(f"[ERR] {type(e).__name__}: {e!r}")
                return [], ""
            self._emit("total", total=len(raw))
            self._log(f"[i] Плейлист: {title}, треков: {len(raw)}")

            def extract(it):
                try:
                    return it.fetch_track() if hasattr(it, "fetch_track") else it
                except Exception:
                    return None

            tracks = self._fetch_parallel(raw, len(raw), extract)

        elif mode == "album":
            self._log(f"[i] Загружаю альбом: {url}")
            clean = url.split("?")[0].split("#")[0]
            album_id = _parse_album_url(clean)
            album = client.albums_with_tracks(album_id)
            title = album.title or f"album_{album_id}"
            tracks = [t for vol in album.volumes for t in vol]
            self._emit("total", total=len(tracks))

        elif mode == "track":
            self._log(f"[i] Загружаю трек: {url}")
            clean = url.split("?")[0].split("#")[0]
            tid = _parse_track_url(clean)
            res = client.tracks([tid])
            if not res:
                self._log("[ERR] Трек не найден")
                return [], ""
            track = res[0]
            a = track.artists[0].name if track.artists else "Unknown"
            title = f"{a} - {track.title}"
            tracks = [track]
            self._emit("total", total=1)

        else:
            self._log(f"[ERR] Неизвестный режим: {mode}")

        return tracks, title

    def _fetch_parallel(self, items, total, extractor):
        tracks = [None] * len(items)
        done = 0
        with ThreadPoolExecutor(max_workers=MAX_METADATA_WORKERS) as ex:
            futs = {ex.submit(extractor, it): i for i, it in enumerate(items)}
            for fut in as_completed(futs):
                if self._stop_event.is_set():
                    break
                idx = futs[fut]
                try:
                    tracks[idx] = fut.result()
                except Exception as e:
                    self._log(f"    [!] meta {idx}: {type(e).__name__}: {e}")
                done += 1
                if done % 5 == 0 or done == total:
                    self._emit("status", text=f"Загрузка метаданных: {done}/{total}")
        return [t for t in tracks if t]

    # ───────────── DOWNLOAD LOOP ─────────────
    def _download_loop(self, tracks, folder, quality,
                       retries, retry_base, delay, save_lyr,
                       folder_structure=False, base_path=""):
        total = len(tracks)
        eta_calc = _EtaEstimator(window=12)

        for i, track in enumerate(tracks, 1):
            artist = track.artists[0].name if track.artists else "Unknown Artist"
            ext = "flac" if quality == "flac" else "mp3"
            fname = f"{_sanitize(artist)} - {_sanitize(track.title)}.{ext}"
            cover_uri = getattr(track, "cover_uri", None)
            if not cover_uri and getattr(track, "albums", None):
                cover_uri = getattr(track.albums[0], "cover_uri", None)
            cover_url = ("https://" + cover_uri.replace("%%", "200x200")) if cover_uri else ""
            self._emit("track_start", index=i, total=total,
                       name=fname, cover_url=cover_url)

        done_lock = threading.Lock()
        stats_lock = threading.Lock()
        done_count = [0]
        stats = {"ok": 0, "fail": 0, "skip": 0, "unavailable": 0, "cancelled": 0}

        def _run_one(idx, track):
            if delay > 0:
                time.sleep(random.uniform(0, min(delay, 1.0)))
            t0 = time.time()
            try:
                status = self._download_one(
                    idx, track, folder, quality,
                    retries, retry_base, total, save_lyr,
                    folder_structure=folder_structure,
                    base_path=base_path,
                )
            except Exception as e:
                self._log(f"    [ERR] {type(e).__name__}: {e}")
                status = "fail"

            with stats_lock:
                stats[status] = stats.get(status, 0) + 1
                with done_lock:
                    done_count[0] += 1
                    cur = done_count[0]

            eta_calc.add(time.time() - t0)
            eta_str = eta_calc.eta(total - cur)
            self._emit("progress", cur=cur, total=total, eta=eta_str)
            return status

        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as ex:
            futs = [ex.submit(_run_one, i, t) for i, t in enumerate(tracks, 1)]
            for fut in as_completed(futs):
                if self._stop_event.is_set():
                    for f in futs:
                        f.cancel()
                    break

        return stats

    # ───────────── SINGLE DOWNLOAD ─────────────
    def _download_one(self, idx, track, folder, quality,
                      retries, retry_base, total, save_lyr,
                      folder_structure=False, base_path=""):
        artist = track.artists[0].name if track.artists else "Unknown Artist"
        title = getattr(track, "title", "") or "Unknown"

        if folder_structure:
            album = ""
            if getattr(track, "albums", None) and track.albums:
                album = getattr(track.albums[0], "title", "") or ""
            target_dir = os.path.join(
                base_path or folder,
                _sanitize(artist),
                _sanitize(album) if album else "Singles",
            )
        else:
            target_dir = folder

        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            target_dir = folder

        existing = _find_existing_audio(target_dir, artist, title)
        if existing:
            self._log(f"[{idx}/{total}] ⏭ Пропуск: {os.path.basename(existing)}")
            self._emit("track_status", index=idx, status="skip", text="⏭ Пропуск")
            self._history.mark(str(track.id), "skip")
            return "skip"

        prefix = ""
        if folder_structure:
            pos = getattr(track, "track_position", None) or getattr(track, "position", None)
            num = getattr(pos, "index", None) if pos else None
            if num:
                prefix = f"{int(num):02d} - "

        ext = "flac" if quality == "flac" else "mp3"
        base_name = f"{prefix}{_sanitize(artist)} - {_sanitize(title)}.{ext}"
        base_file = os.path.join(target_dir, base_name)

        with self._path_lock:
            if os.path.exists(base_file):
                fpath = _unique_path(target_dir, base_name)
            else:
                fpath = base_file

        fname = os.path.basename(fpath)

        self._log(f"[{idx}/{total}] ⬇ {fname}")

        for attempt in range(1, retries + 1):
            if self._stop_event.is_set():
                return "cancelled"
            try:
                ok, err = self._stream_download(track, fpath, quality, idx)
                if ok:
                    meta = {}
                    try:
                        meta = extract_metadata(track)
                        embed_metadata(fpath, meta)
                    except Exception as e:
                        self._log(f"    [!] metadata: {e}")

                    if save_lyr:
                        try:
                            lyr = fetch_lyrics(track)
                            if lyr:
                                lrc_path = save_lyrics(fpath, lyr)
                                if lrc_path:
                                    self._log(f"    ♪ Текст: {os.path.basename(lrc_path)}")
                        except Exception as e:
                            self._log(f"    [!] lyrics: {e}")

                    try:
                        size = os.path.getsize(fpath)
                        self._stats.add(
                            track.id, title, artist,
                            meta.get("album", ""), quality, size,
                        )
                    except Exception:
                        pass

                    self._emit("track_status", index=idx, status="ok", text="✓ Готово")
                    self._emit("track_progress", index=idx, got=0, total=0, pct=100)
                    self._history.mark(str(track.id), "ok")
                    return "ok"

                # ★ Недоступен для скачивания
                if err == "__UNAVAILABLE__":
                    self._log(f"    ⛔ Трек недоступен для скачивания "
                              f"(регион / подписка / удалён)")
                    self._emit("track_status", index=idx, status="fail",
                               text="⛔ Недоступен")
                    self._history.mark(str(track.id), "fail")
                    return "unavailable"

                raise RuntimeError(err or "unknown download error")

            except Exception as e:
                if _is_429(e):
                    if not self._rate_limit_shown:
                        self._log("[i] Это лимит Яндекс.Музыки, продолжаю автоматически...")
                        self._rate_limit_shown = True
                    ra = _retry_after(e)
                    wait = ra if ra is not None else _backoff(attempt, retry_base)
                    self._log(f"    429, ждём {wait}с ({attempt}/{retries})")
                    for _ in range(wait):
                        if self._stop_event.is_set():
                            return "cancelled"
                        time.sleep(1)
                else:
                    # ★ Красивое сообщение вместо "RuntimeError: None"
                    msg = str(e)
                    if not msg or msg == "None":
                        msg = "трек недоступен (нет download_info)"
                    self._log(f"    [ERR] {msg}")
                    break

        self._emit("track_status", index=idx, status="fail", text="✗ Ошибка")
        self._history.mark(str(track.id), "fail")
        return "fail"

    # ───────────── STREAM ─────────────
    def _stream_download(self, track, fpath, quality, idx):
        url = None
        infos = []
        try:
            infos = track.get_download_info() or []
            chosen = self._pick_info(infos, quality)
            if chosen:
                for attr in ("download_url", "direct_link", "url"):
                    u = getattr(chosen, attr, None)
                    if u:
                        url = u
                        break
                if not url and hasattr(chosen, "get_direct_link"):
                    try:
                        url = chosen.get_direct_link()
                    except Exception:
                        pass
        except Exception as e:
            self._log(f"    [!] download_info: {type(e).__name__}: {e}")
            url = None

        # ★ Если ссылок нет — трек недоступен для скачивания
        if not url:
            if not infos:
                return False, "__UNAVAILABLE__"
            try:
                self._download_track_lib(track, fpath, quality)
                return True, None
            except Exception as e:
                msg = str(e) or type(e).__name__
                if msg == "None":
                    msg = "трек недоступен для скачивания"
                return False, msg

        tmp = fpath + ".part"
        try:
            with requests.get(url, stream=True, timeout=(10, 60)) as r:
                r.raise_for_status()
                try:
                    total_bytes = int(r.headers.get("Content-Length") or 0)
                except Exception:
                    total_bytes = 0
                got = 0
                last_emit = 0.0
                last_pct = -1

                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if self._stop_event.is_set():
                            raise RuntimeError("cancelled")
                        while self._pause_event.is_set() and not self._stop_event.is_set():
                            time.sleep(0.2)
                        if not chunk:
                            continue
                        f.write(chunk)
                        got += len(chunk)

                        now = time.time()
                        pct = int(got / total_bytes * 100) if total_bytes else 0
                        if (now - last_emit >= PROGRESS_THROTTLE
                                or pct - last_pct >= 5
                                or pct == 100):
                            last_emit = now
                            last_pct = pct
                            self._emit("track_progress", index=idx,
                                       got=got, total=total_bytes, pct=pct)

            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
            os.replace(tmp, fpath)

            ok, err = self._verify_file(fpath)
            if not ok:
                try: os.remove(fpath)
                except Exception: pass
                return False, f"integrity: {err}"

            self._emit("track_progress", index=idx, got=got, total=got, pct=100)
            return True, None

        except Exception as e:
            try:
                if os.path.exists(tmp): os.remove(tmp)
            except Exception:
                pass
            return False, str(e)

    def _pick_info(self, infos, quality):
        if not infos:
            return None

        def cbr(info):
            c = (getattr(info, "codec", "") or "").lower()
            b = getattr(info, "bitrate_in_kbps", 0) or 0
            return c, b

        if quality == "flac":
            prefs = [("flac", None)]
        elif quality == "mp3_320":
            prefs = [("mp3", 320)]
        elif quality == "mp3_192":
            prefs = [("mp3", 192)]
        else:
            prefs = [("flac", None), ("mp3", 320), ("mp3", 192), ("mp3", 128)]

        for want_c, want_b in prefs:
            for info in infos:
                c, b = cbr(info)
                if c == want_c and (want_b is None or b == want_b):
                    return info
        return infos[0]

    def _download_track_lib(self, track, fpath, quality):
        if quality == "flac":
            try:
                track.download(fpath, codec="flac"); return
            except Exception:
                pass
        if quality == "mp3_320":
            try:
                track.download(fpath, codec="mp3", bitrate_in_kbps=320); return
            except Exception:
                pass
        if quality == "mp3_192":
            try:
                track.download(fpath, codec="mp3", bitrate_in_kbps=192); return
            except Exception:
                pass
        track.download(fpath)

    def _verify_file(self, fpath):
        try:
            size = os.path.getsize(fpath)
        except OSError:
            return False, "not found"
        if size < 100_000:
            return False, f"too small ({size} B)"

        ext = os.path.splitext(fpath)[1].lower()
        try:
            if ext == ".mp3":
                from mutagen.mp3 import MP3
                audio = MP3(fpath)
                if not audio.info or audio.info.length < 0.5:
                    return False, "duration too short"
            elif ext == ".flac":
                from mutagen.flac import FLAC
                audio = FLAC(fpath)
                if not audio.info or audio.info.length < 0.5:
                    return False, "duration too short"
        except Exception as e:
            return False, f"parse error: {type(e).__name__}"
        return True, "ok"