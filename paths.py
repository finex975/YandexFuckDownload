"""
Определяет, куда сохранять пользовательские данные приложения:
settings.json, history.json, stats.db, logs/, token.dat

Всегда использует системную папку пользователя:
  Windows:  %LOCALAPPDATA%\FinexStudio\YandexMusicDownloader\
  Linux:    ~/.local/share/YandexMusicDownloader/
  macOS:    ~/Library/Application Support/YandexMusicDownloader/

Исключение: если задана переменная окружения YMD_DATA_DIR — данные пойдут туда
(удобно для портативного режима и отладки).
"""
import os
import sys
import shutil

APP_VENDOR = "FinexStudio"
APP_NAME = "YandexMusicDownloader"


def get_data_dir() -> str:
    """Системная папка для данных приложения."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not base:
            base = os.path.expanduser(r"~\AppData\Local")
        path = os.path.join(base, APP_VENDOR, APP_NAME)

    elif sys.platform == "darwin":
        path = os.path.expanduser(
            f"~/Library/Application Support/{APP_NAME}"
        )

    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        path = os.path.join(base, APP_NAME)

    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = os.path.join(os.path.expanduser("~"), f".{APP_NAME}")
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass

    return path


def resolve_app_dir(frozen: bool, project_dir: str) -> str:
    """
    Куда писать данные:
    - YMD_DATA_DIR (если задана) — используем её.
    - Во всех остальных случаях — системная папка.
    Параметры frozen/project_dir оставлены для совместимости, но не влияют.
    """
    override = os.environ.get("YMD_DATA_DIR")
    if override:
        try:
            os.makedirs(override, exist_ok=True)
        except Exception:
            pass
        return override

    return get_data_dir()


def migrate_old_data(old_dir: str, new_dir: str) -> None:
    """
    Если раньше данные лежали рядом с exe / исходниками — переносим их
    в системную папку. Копируем только те файлы, которых нет в новой.
    """
    if not old_dir or not new_dir:
        return
    try:
        if os.path.abspath(old_dir) == os.path.abspath(new_dir):
            return
    except Exception:
        return

    if not os.path.isdir(old_dir):
        return

    for fname in ("settings.json", "history.json", "stats.db", "token.dat"):
        old_f = os.path.join(old_dir, fname)
        new_f = os.path.join(new_dir, fname)
        if os.path.isfile(old_f) and not os.path.exists(new_f):
            try:
                shutil.copy2(old_f, new_f)
            except Exception:
                pass

    old_logs = os.path.join(old_dir, "logs")
    new_logs = os.path.join(new_dir, "logs")
    if os.path.isdir(old_logs) and not os.path.isdir(new_logs):
        try:
            shutil.copytree(old_logs, new_logs)
        except Exception:
            pass