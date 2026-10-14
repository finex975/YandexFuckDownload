import os
import sys
import webview
import threading

from api import JsApi, APP_VERSION
from tray import TrayIcon
from paths import resolve_app_dir, get_data_dir, migrate_old_data

FROZEN = getattr(sys, "frozen", False)

# ── Ресурсы (web/, icon) — внутри exe или рядом с исходниками ──
if FROZEN:
    RESOURCE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = RESOURCE_DIR

# ── Пользовательские данные — в системной папке ──
APP_DIR = resolve_app_dir(FROZEN, RESOURCE_DIR)

# ── Миграция из старой папки (рядом с exe) ──
if FROZEN:
    try:
        migrate_old_data(EXE_DIR, APP_DIR)
    except Exception:
        pass

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")


def resource_path(rel):
    if FROZEN:
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(RESOURCE_DIR, rel)


def set_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "FinexStudio.YandexMusicDownloader.2"
        )
    except Exception:
        pass


def main():
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Приложение должно запускаться из главного потока!")

    set_windows_app_id()

    # Лог для отладки — куда пошли данные
    print(f"[i] RESOURCE_DIR = {RESOURCE_DIR}")
    print(f"[i] EXE_DIR      = {EXE_DIR}")
    print(f"[i] APP_DIR      = {APP_DIR}")

    api = JsApi(SETTINGS_FILE, APP_DIR)

    index = resource_path(os.path.join("web", "index.html"))
    if not os.path.isfile(index):
        print(f"[!] Не найден {index}")
        sys.exit(1)

    icon_path = resource_path("icon.ico")
    if not os.path.isfile(icon_path):
        icon_path = resource_path("icon.png")

    window = webview.create_window(
        f"Yandex Music Downloader v{APP_VERSION} — FinexStudio",
        url=index,
        js_api=api,
        width=1240,
        height=820,
        min_size=(1020, 720),
        background_color="#0f1117",
    )

    tray_ref = {"icon": None}

    def _show_window():
        try:
            window.show()
            window.restore()
        except Exception:
            pass

    def _quit_app():
        try:
            api._quit_requested = True
        except Exception:
            pass
        try:
            api.request_quit()
        except Exception:
            pass
        try:
            window.destroy()
        except Exception:
            pass

    def _cancel_download():
        try:
            api.cancel_download()
        except Exception:
            pass

    tray = TrayIcon(
        f"Yandex Music Downloader v{APP_VERSION}",
        icon_path if os.path.isfile(icon_path) else None,
        on_show=_show_window,
        on_quit=_quit_app,
        on_cancel=_cancel_download,
    )
    tray_ref["icon"] = tray
    tray.start()
    api.set_tray(tray)

    def _on_closing():
        try:
            if api.should_quit():
                return True
            if getattr(api, "_minimize_on_close", False):
                try:
                    window.hide()
                except Exception:
                    pass
                return False
        except Exception:
            pass
        return True

    try:
        window.events.closing += _on_closing
    except Exception:
        try:
            window.closing += _on_closing
        except Exception:
            pass

    start_kwargs = {}
    if os.path.isfile(icon_path):
        start_kwargs["icon"] = icon_path

    try:
        webview.start(**start_kwargs)
    except TypeError:
        webview.start()

    try:
        tray.stop()
    except Exception:
        pass


if __name__ == "__main__":
    main()
