import os
import sys
import importlib

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    RESOURCE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
    sys.path.insert(0, RESOURCE_DIR)
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = RESOURCE_DIR


def check_tkinter():
    try:
        import tkinter  # noqa: F401
        return True
    except ImportError:
        return False


NEEDED_PACKAGES = ["yandex-music", "requests"]


def check_and_install():
    if FROZEN:
        if not check_tkinter():
            sys.exit(1)
        return True

    if not check_tkinter():
        print("[!] Tkinter не найден.")
        sys.exit(1)

    missing = []
    for pkg in NEEDED_PACKAGES:
        module_name = pkg.replace("-", "_")
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return True

    print("[*] Устанавливаю зависимости:")
    for pkg in missing:
        print(f"    -> {pkg}")

    import subprocess
    ok = True
    for pkg in missing:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            print(f"    OK {pkg}")
        except subprocess.CalledProcessError:
            print(f"    FAIL {pkg}")
            ok = False

    if not ok:
        print("[!] Установите вручную:")
        print(f"    {sys.executable} -m pip install " + " ".join(missing))
        sys.exit(1)
    print("[*] Готово. Запускаю приложение...\n")
    return True


if __name__ == "__main__":
    check_and_install()

import os
import re
import json
import time
import random
import logging
import threading
import queue as queue_module
import traceback
import webbrowser
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox
import tkinter as tk
from yandex_music import Client
from yandex_music.exceptions import UnauthorizedError, DeviceAuthError

try:
    from translations import LANG_NAMES, NAME_TO_CODE, TRANSLATIONS
except ImportError:
    print("[!] Файл translations.py не найден рядом с main.py")
    sys.exit(1)

APP_VERSION = "1.2.1"
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
LOG_FILE = os.path.join(APP_DIR, "app.log")
UPDATE_URL = "https://api.github.com/repos/finex975/YandexFuckDownload/releases/latest"
KOFI_URL = "https://ko-fi.com/finex_studio"

DEFAULT_DELAY = 2.0
DEFAULT_RETRIES = 6
DEFAULT_RETRY_BASE = 8
MAX_WAIT = 60
MAX_METADATA_WORKERS = 5

BG      = "#0f1117"
BG2     = "#161923"
BG3     = "#1e2230"
BORDER  = "#2a2f42"

ACCENT  = "#4fc3d9"
ACCENT2 = "#c77dff"
SUCCESS = "#5cd68a"
WARN    = "#e6c465"
DANGER  = "#e07a8a"
TEXT    = "#d6dbe8"
TEXT_DIM= "#7b8298"

FONT       = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 17, "bold")
FONT_SUB   = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)
FONT_SECT  = ("Segoe UI", 9, "bold")
FONT_TINY  = ("Segoe UI", 7)
FONT_CODE  = ("Consolas", 28, "bold")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
    filemode="a",
)
logger = logging.getLogger("ymd")


def sanitize(name: str) -> str:
    name = "".join(c for c in str(name) if c.isalnum() or c in " .-_")
    return name.strip() or "unnamed"


def is_429(error: Exception) -> bool:
    resp = getattr(error, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None)
        if status == 429:
            return True
    text = str(error)
    return "429" in text or "Concurrency" in text or "Too Many Requests" in text


def calc_backoff(attempt: int, base: int = DEFAULT_RETRY_BASE) -> int:
    exponential = base * (2 ** (attempt - 1))
    jittered = exponential * random.uniform(0.7, 1.3)
    return int(min(jittered, MAX_WAIT))


def is_valid_file(filepath: str, min_size: int = 500_000) -> bool:
    try:
        return os.path.exists(filepath) and os.path.getsize(filepath) > min_size
    except OSError:
        return False


def parse_playlist_url(url: str) -> tuple[str, int]:
    m = re.search(r"/users/([^/]+)/playlists/(\d+)", url)
    if not m:
        raise ValueError("Invalid playlist URL")
    return m.group(1), int(m.group(2))


def parse_album_url(url: str) -> int:
    m = re.search(r"/album/(\d+)", url)
    if not m:
        raise ValueError("Invalid album URL")
    return int(m.group(1))


def parse_track_url(url: str) -> int:
    m = re.search(r"/track/(\d+)", url)
    if not m:
        raise ValueError("Invalid track URL")
    return int(m.group(1))


def check_updates() -> str | None:
    try:
        req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": "ymd-checker"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.load(r)
        tag = data.get("tag_name", "").lstrip("v")
        if tag and tag != APP_VERSION:
            return tag
    except Exception:
        pass
    return None


class AuthDialog:
    def __init__(self, parent, t, on_cancel=None):
        self.t = t
        self.on_cancel = on_cancel
        self.closed = False
        self.win = tk.Toplevel(parent)
        self.win.title(t("auth_title"))
        self.win.configure(bg=BG)
        self.win.geometry("500x420")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.update_idletasks()
        pw = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        ph = parent.winfo_y() + (parent.winfo_height() - 420) // 2
        self.win.geometry(f"+{max(pw, 0)}+{max(ph, 0)}")
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)

        header = tk.Frame(self.win, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(header, text=t("auth_title"), bg=BG, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(header, text=t("auth_subtitle"), bg=BG, fg=ACCENT,
                 font=FONT_SUB).pack(anchor="w", pady=(2, 0))
        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(12, 0))

        tk.Label(self.win, text=t("auth_code_label"),
                 bg=BG, fg=TEXT_DIM, font=FONT).pack(pady=(18, 6))

        code_frame = tk.Frame(self.win, bg=BORDER)
        code_frame.pack(padx=24, fill="x")
        self.code_var = tk.StringVar(value="— — — —")
        self.code_label = tk.Label(code_frame, textvariable=self.code_var,
                                   bg=BG2, fg=ACCENT2, font=FONT_CODE,
                                   padx=20, pady=14)
        self.code_label.pack(fill="x", padx=1, pady=1)

        self.link_row = tk.Frame(self.win, bg=BG)
        self.link_row.pack(pady=(14, 4))
        tk.Label(self.link_row, text=t("auth_opens_page") + " ",
                 bg=BG, fg=TEXT_DIM, font=FONT_TINY).pack(side="left")
        self.url_label = tk.Label(self.link_row, text="…", bg=BG, fg=ACCENT,
                                  font=("Segoe UI", 8, "underline"),
                                  cursor="hand2")
        self.url_label.pack(side="left")
        self.url_label.bind("<Button-1>", lambda e: self.open_browser())

        self.status_label = tk.Label(self.win, text=t("auth_waiting"),
                                     bg=BG, fg=WARN, font=FONT)
        self.status_label.pack(pady=(14, 0))

        btn_row = tk.Frame(self.win, bg=BG)
        btn_row.pack(pady=(20, 0), padx=24, fill="x")

        self.copy_btn = tk.Button(btn_row, text=t("auth_copy_code"),
                                  command=self.copy_code, bg=BG3, fg=SUCCESS,
                                  activebackground=BG2, activeforeground=SUCCESS,
                                  font=FONT_BOLD, bd=0, relief="flat",
                                  padx=16, pady=10, cursor="hand2",
                                  highlightthickness=1, highlightbackground=BORDER,
                                  disabledforeground=TEXT_DIM)
        self.copy_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.copy_btn.config(state="disabled")

        self.open_btn = tk.Button(btn_row, text=t("auth_open_yandex"),
                                  command=self.open_browser, bg=BG3, fg=ACCENT,
                                  activebackground=BG2, activeforeground=ACCENT,
                                  font=FONT_BOLD, bd=0, relief="flat",
                                  padx=16, pady=10, cursor="hand2",
                                  highlightthickness=1, highlightbackground=BORDER,
                                  disabledforeground=TEXT_DIM)
        self.open_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.open_btn.config(state="disabled")

        self.cancel_btn = tk.Button(self.win, text=t("auth_cancel"),
                                    command=self.cancel, bg=BG, fg=TEXT_DIM,
                                    activebackground=BG, activeforeground=DANGER,
                                    font=FONT_TINY, bd=0, relief="flat",
                                    padx=8, pady=4, cursor="hand2")
        self.cancel_btn.pack(pady=(12, 16))

        self.user_code = None
        self.verification_url = None
        self.browser_opened = False

    def set_code(self, user_code, verification_url):
        self.user_code = user_code
        self.verification_url = verification_url
        self.code_var.set(user_code)
        self.url_label.config(text=verification_url)
        self.copy_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self.status_label.config(text=self.t("auth_copy_and_open"), fg=ACCENT)
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(500, lambda: self.win.attributes("-topmost", False))

    def copy_code(self):
        if not self.user_code:
            return
        try:
            self.win.clipboard_clear()
            self.win.clipboard_append(self.user_code)
            self.status_label.config(text=self.t("auth_code_copied"), fg=SUCCESS)
        except Exception as e:
            self.status_label.config(text=f"{self.t('auth_copy_error')}: {e}",
                                     fg=DANGER)
            return
        self.win.after(600, self.open_browser)

    def open_browser(self):
        if not self.verification_url:
            return
        if not self.browser_opened:
            try:
                webbrowser.open(self.verification_url)
                self.browser_opened = True
            except Exception as e:
                self.status_label.config(
                    text=f"{self.t('auth_open_failed')}: {e}", fg=DANGER)
                return
        self.status_label.config(text=self.t("auth_waiting_confirm"), fg=WARN)

    def set_success(self):
        self.status_label.config(text=self.t("auth_success"), fg=SUCCESS)
        self.copy_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self.win.after(900, self.close)

    def set_error(self, msg):
        self.status_label.config(text=f"{msg}", fg=DANGER)
        self.copy_btn.config(state="disabled")
        self.open_btn.config(state="disabled")

    def cancel(self):
        if self.closed:
            return
        self.closed = True
        if self.on_cancel:
            self.on_cancel()
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.destroy()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.destroy()


class DonateDialog:
    def __init__(self, parent, t):
        self.win = tk.Toplevel(parent)
        self.win.title(t("donate_title"))
        self.win.configure(bg=BG)
        self.win.geometry("460x300")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.update_idletasks()
        pw = parent.winfo_x() + (parent.winfo_width() - 460) // 2
        ph = parent.winfo_y() + (parent.winfo_height() - 300) // 2
        self.win.geometry(f"+{max(pw, 0)}+{max(ph, 0)}")

        tk.Label(self.win, text=t("donate_title"), bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(pady=(24, 4))
        tk.Label(self.win, text=t("donate_powered"), bg=BG, fg=ACCENT,
                 font=FONT_SUB).pack()

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x", padx=30, pady=16)

        tk.Label(self.win, text=t("donate_text"),
                 bg=BG, fg=TEXT_DIM, font=FONT,
                 justify="center").pack(pady=(0, 20))

        btn_frame = tk.Frame(self.win, bg=BG)
        btn_frame.pack()

        donate_btn = tk.Button(
            btn_frame, text=t("donate_btn"),
            command=self.open_kofi, bg=BG3, fg=SUCCESS,
            activebackground=BG2, activeforeground=SUCCESS,
            font=FONT_BOLD, bd=0, relief="flat",
            padx=20, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=SUCCESS,
        )
        donate_btn.pack(side="left", padx=(0, 8))

        close_btn = tk.Button(
            btn_frame, text=t("donate_close"),
            command=self.win.destroy, bg=BG3, fg=TEXT_DIM,
            activebackground=BG2, activeforeground=TEXT,
            font=FONT_BOLD, bd=0, relief="flat",
            padx=20, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=BORDER,
        )
        close_btn.pack(side="left")

        tk.Label(self.win, text=KOFI_URL, bg=BG, fg=TEXT_DIM,
                 font=FONT_TINY).pack(pady=(16, 0))

    def open_kofi(self):
        try:
            webbrowser.open(KOFI_URL)
        except Exception:
            pass


class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Yandex Music Downloader v{APP_VERSION} — FinexStudio")
        self.root.geometry("960x1000")
        self.root.minsize(900, 800)
        self.root.configure(bg=BG)

        self.msg_queue = queue_module.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.auth_thread = None
        self.update_thread = None
        self.anim_phase = 0
        self.last_progress = (0, 0)
        self.progress_color = SUCCESS
        self.device_auth_cancel = threading.Event()
        self.auth_dialog = None
        self.sections_collapsed = False
        self.rate_limit_hint_shown = False

        self.settings = self.load_settings()
        self.current_lang = self.settings.get("lang", "ru")
        if self.current_lang not in TRANSLATIONS:
            self.current_lang = "ru"

        self.i18n_widgets = []
        self.build_ui()
        self.load_settings_into_ui()

        self.root.after(100, self.process_queue)
        self.root.after(80, self.animate)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.check_update_async()

    def t(self, key, **kwargs):
        lang_dict = TRANSLATIONS.get(self.current_lang, TRANSLATIONS["ru"])
        s = lang_dict.get(key)
        if s is None:
            s = TRANSLATIONS["ru"].get(key, key)
        if kwargs:
            try:
                return s.format(**kwargs)
            except Exception:
                return s
        return s

    def reg(self, widget, key, attr="text"):
        self.i18n_widgets.append((widget, key, attr))
        try:
            widget.configure(**{attr: self.t(key)})
        except Exception:
            pass

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self):
        save_url = self.save_url_var.get()
        data = {
            "token": self.token_var.get().strip(),
            "path": self.path_var.get().strip(),
            "mode": self.mode_var.get(),
            "lang": self.current_lang,
            "save_url": save_url,
            "url": self.url_var.get().strip() if save_url else "",
            "quality": self.quality_var.get(),
            "delay": self._safe_float(self.delay_var.get(), DEFAULT_DELAY),
            "retries": self._safe_int(self.retries_var.get(), DEFAULT_RETRIES),
            "retry_base": self._safe_int(self.retry_base_var.get(), DEFAULT_RETRY_BASE),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"[!] {e}")

    def _safe_float(self, s, default):
        try:
            return max(0.5, float(str(s).replace(",", ".")))
        except Exception:
            return default

    def _safe_int(self, s, default):
        try:
            return max(1, int(s))
        except Exception:
            return default

    def section(self, parent, key, color):
        f = tk.Frame(parent, bg=BG)
        bar = tk.Frame(f, bg=color, width=3, height=14)
        bar.pack(side="left", padx=(0, 8))
        bar.pack_propagate(False)
        lbl = tk.Label(f, bg=BG, fg=color, font=FONT_SECT)
        lbl.pack(side="left")
        self.reg(lbl, key)
        return f

    def input_field(self, parent, textvariable, show=None, disabled=False, width=None):
        outer = tk.Frame(parent, bg=BORDER)
        entry = tk.Entry(
            outer, textvariable=textvariable,
            bg=BG2, fg=TEXT, insertbackground=ACCENT,
            font=FONT, bd=0, relief="flat", highlightthickness=0,
            selectbackground=ACCENT, selectforeground=BG,
            disabledbackground=BG3, disabledforeground=TEXT_DIM,
        )
        if show:
            entry.config(show=show)
        if width:
            entry.config(width=width)
        if disabled:
            entry.config(state="disabled")
        entry.pack(fill="both", expand=True, padx=1, pady=1)
        outer.entry = entry
        return outer

    def flat_button(self, parent, key, command, accent=ACCENT, disabled=False):
        btn = tk.Button(
            parent, command=command,
            bg=BG3, fg=accent, activebackground=BG3, activeforeground=accent,
            font=FONT_BOLD, bd=0, relief="flat",
            padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=BORDER,
            disabledforeground=TEXT_DIM,
        )
        self.reg(btn, key)
        if disabled:
            btn.config(state="disabled", cursor="arrow")
        btn.bind("<Enter>", lambda e: btn.config(bg=BG2, highlightbackground=accent)
                 if str(btn["state"]) != "disabled" else None)
        btn.bind("<Leave>", lambda e: btn.config(bg=BG3, highlightbackground=BORDER)
                 if str(btn["state"]) != "disabled" else None)
        return btn

    def change_lang(self, *args):
        name = self.lang_var.get()
        code = NAME_TO_CODE.get(name, "ru")
        if code == self.current_lang:
            return
        self.current_lang = code
        for w, k, a in self.i18n_widgets:
            try:
                w.configure(**{a: self.t(k)})
            except Exception:
                pass
        self._refresh_mode_buttons()
        self._update_save_url_toggle()
        self._rebuild_quality_menu()
        self.status_var.set(self.t("status_ready"))
        self.save_settings()

    def _refresh_mode_buttons(self):
        for v, (btn, color, key) in self.mode_buttons.items():
            btn.config(text=self.t(key))
            if v == self.mode_var.get():
                btn.config(fg=color, highlightbackground=color, bg=BG2)
            else:
                btn.config(fg=TEXT_DIM, highlightbackground=BORDER, bg=BG3)

    def _update_save_url_toggle(self):
        if self.save_url_var.get():
            self.save_url_toggle.config(
                text=self.t("save_url_on"),
                fg=SUCCESS, activeforeground=SUCCESS,
                highlightbackground=SUCCESS)
        else:
            self.save_url_toggle.config(
                text=self.t("save_url_off"),
                fg=TEXT_DIM, activeforeground=WARN,
                highlightbackground=BORDER)

    def _rebuild_quality_menu(self):
        names = {
            "auto":    self.t("q_auto"),
            "mp3_320": self.t("q_mp3_320"),
            "mp3_192": self.t("q_mp3_192"),
            "flac":    self.t("q_flac"),
        }
        menu = self.quality_menu["menu"]
        menu.delete(0, "end")
        self._quality_display_to_code = {v: k for k, v in names.items()}
        current_code = self.quality_var.get()
        for code, disp in names.items():
            menu.add_command(label=disp,
                             command=lambda d=disp: self._set_quality(d))
        self.quality_display_var.set(names.get(current_code, names["auto"]))

    def _set_quality(self, display):
        code = self._quality_display_to_code.get(display, "auto")
        self.quality_var.set(code)
        self.quality_display_var.set(display)

    def collapse_sections(self, collapse):
        self.sections_collapsed = collapse
        if collapse:
            self.collapsible.pack_forget()
        else:
            self.collapsible.pack(fill="x", before=self.control_container)
            self.set_mode(self.mode_var.get())

    def build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 0))

        left = tk.Frame(header, bg=BG)
        left.pack(side="left", anchor="nw")
        title_lbl = tk.Label(left, text="", bg=BG, fg=TEXT, font=FONT_TITLE)
        title_lbl.pack(anchor="w")
        self.reg(title_lbl, "app_title")
        sub_lbl = tk.Label(left, text="", bg=BG, fg=ACCENT, font=FONT_SUB)
        sub_lbl.pack(anchor="w", pady=(2, 0))
        self.reg(sub_lbl, "powered_by")

        right = tk.Frame(header, bg=BG)
        right.pack(side="right", anchor="ne")

        version_lbl = tk.Label(right, text=f"v{APP_VERSION}", bg=BG,
                               fg=TEXT_DIM, font=FONT_TINY)
        version_lbl.pack(side="right", padx=(8, 0))

        tk.Label(right, text="🌐", bg=BG, fg=ACCENT, font=FONT).pack(side="right", padx=(0, 4))
        self.lang_var = tk.StringVar(value=LANG_NAMES.get(self.current_lang, "Русский"))
        self.lang_menu = tk.OptionMenu(right, self.lang_var, *LANG_NAMES.values(),
                                       command=self.change_lang)
        self.lang_menu.config(bg=BG3, fg=ACCENT, activebackground=BG2,
                              activeforeground=ACCENT, font=FONT,
                              bd=0, relief="flat", highlightthickness=0,
                              highlightbackground=BORDER,
                              width=12, anchor="w",
                              disabledforeground=TEXT_DIM)
        self.lang_menu["menu"].config(bg=BG3, fg=TEXT, activebackground=ACCENT,
                                      activeforeground=BG, font=FONT, bd=0)
        self.lang_menu.pack(side="right")

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=22,
                                                      pady=(12, 0))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=16)
        self.body = body

        self.collapsible = tk.Frame(body, bg=BG)
        self.collapsible.pack(fill="x")

        self.section(self.collapsible, "section_auth", ACCENT).pack(fill="x", pady=(0, 8))
        auth_row = tk.Frame(self.collapsible, bg=BG)
        auth_row.pack(fill="x", pady=(0, 16))
        token_lbl = tk.Label(auth_row, bg=BG, fg=TEXT_DIM, font=FONT,
                             width=10, anchor="w")
        token_lbl.pack(side="left")
        self.reg(token_lbl, "label_token")
        self.token_var = tk.StringVar()
        self.token_field = self.input_field(auth_row, self.token_var, show="•")
        self.token_field.pack(side="left", fill="x", expand=True)
        self.auth_btn = self.flat_button(auth_row, "btn_login",
                                         self.start_device_auth, accent=SUCCESS)
        self.auth_btn.pack(side="left", padx=(8, 0))

        self.section(self.collapsible, "section_source", ACCENT2).pack(fill="x", pady=(0, 8))
        mode_row = tk.Frame(self.collapsible, bg=BG)
        mode_row.pack(fill="x", pady=(0, 8))
        mode_lbl = tk.Label(mode_row, bg=BG, fg=TEXT_DIM, font=FONT,
                            width=10, anchor="w")
        mode_lbl.pack(side="left")
        self.reg(mode_lbl, "label_mode")

        self.mode_var = tk.StringVar(value="likes")
        self.mode_buttons = {}
        modes = [
            ("likes",    "mode_likes",    ACCENT),
            ("playlist", "mode_playlist", ACCENT2),
            ("album",    "mode_album",    SUCCESS),
            ("track",    "mode_track",    WARN),
        ]
        for value, key, color in modes:
            btn = tk.Button(mode_row, text="",
                            command=lambda v=value: self.set_mode(v),
                            bg=BG3, fg=TEXT_DIM, activebackground=BG3,
                            activeforeground=color, font=FONT, bd=0,
                            relief="flat", padx=14, pady=6, cursor="hand2",
                            highlightthickness=1, highlightbackground=BORDER,
                            disabledforeground=TEXT_DIM)
            btn.config(text=self.t(key))
            btn.pack(side="left", padx=(0, 6))
            self.mode_buttons[value] = (btn, color, key)

        quality_row = tk.Frame(self.collapsible, bg=BG)
        quality_row.pack(fill="x", pady=(0, 8))
        quality_lbl = tk.Label(quality_row, bg=BG, fg=TEXT_DIM, font=FONT,
                               width=10, anchor="w")
        quality_lbl.pack(side="left")
        self.reg(quality_lbl, "label_quality")

        self.quality_var = tk.StringVar(value="auto")
        self.quality_display_var = tk.StringVar(value="Авто")
        self.quality_menu = tk.OptionMenu(quality_row, self.quality_display_var, "Авто")
        self.quality_menu.config(bg=BG3, fg=ACCENT2, activebackground=BG2,
                                 activeforeground=ACCENT2, font=FONT,
                                 bd=0, relief="flat", highlightthickness=0,
                                 highlightbackground=BORDER,
                                 width=12, anchor="w",
                                 disabledforeground=TEXT_DIM)
        self.quality_menu["menu"].config(bg=BG3, fg=TEXT, activebackground=ACCENT2,
                                         activeforeground=BG, font=FONT, bd=0)
        self.quality_menu.pack(side="left")

        url_row = tk.Frame(self.collapsible, bg=BG)
        url_row.pack(fill="x", pady=(0, 18))
        url_lbl = tk.Label(url_row, bg=BG, fg=TEXT_DIM, font=FONT,
                           width=10, anchor="w")
        url_lbl.pack(side="left")
        self.reg(url_lbl, "label_url")
        self.url_label = url_lbl

        self.url_var = tk.StringVar()
        self.url_field = self.input_field(url_row, self.url_var)
        self.url_field.pack(side="left", fill="x", expand=True)

        self.paste_btn = self.flat_button(url_row, "btn_paste",
                                          self.paste_url, accent=ACCENT2)
        self.paste_btn.pack(side="left", padx=(8, 0))

        self.save_url_var = tk.BooleanVar(value=True)
        self.save_url_toggle = tk.Button(
            url_row, bg=BG3, activebackground=BG2,
            font=FONT_TINY, bd=0, relief="flat",
            padx=10, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=BORDER,
            disabledforeground=TEXT_DIM,
        )
        self.save_url_toggle.config(command=self.toggle_save_url)
        self._update_save_url_toggle()
        self.save_url_toggle.pack(side="left", padx=(8, 0))

        self.section(self.collapsible, "section_dest", SUCCESS).pack(fill="x", pady=(0, 8))
        path_row = tk.Frame(self.collapsible, bg=BG)
        path_row.pack(fill="x", pady=(0, 8))
        path_lbl = tk.Label(path_row, bg=BG, fg=TEXT_DIM, font=FONT,
                            width=10, anchor="w")
        path_lbl.pack(side="left")
        self.reg(path_lbl, "label_path")
        self.path_var = tk.StringVar()
        self.path_field = self.input_field(path_row, self.path_var)
        self.path_field.pack(side="left", fill="x", expand=True)
        self.browse_btn = self.flat_button(path_row, "btn_browse",
                                           self.browse_folder, accent=WARN)
        self.browse_btn.pack(side="left", padx=(8, 0))

        settings_row = tk.Frame(self.collapsible, bg=BG)
        settings_row.pack(fill="x", pady=(0, 18))

        delay_lbl = tk.Label(settings_row, bg=BG, fg=TEXT_DIM, font=FONT_TINY,
                             width=10, anchor="w")
        delay_lbl.pack(side="left")
        self.reg(delay_lbl, "label_delay")

        self.delay_var = tk.StringVar(value=str(DEFAULT_DELAY))
        delay_field = self.input_field(settings_row, self.delay_var, width=5)
        delay_field.pack(side="left")
        delay_field.entry.config(justify="center")

        tk.Label(settings_row, text="  ", bg=BG).pack(side="left")

        retries_lbl = tk.Label(settings_row, bg=BG, fg=TEXT_DIM, font=FONT_TINY)
        retries_lbl.pack(side="left")
        self.reg(retries_lbl, "label_retries")

        self.retries_var = tk.StringVar(value=str(DEFAULT_RETRIES))
        retries_field = self.input_field(settings_row, self.retries_var, width=4)
        retries_field.pack(side="left", padx=(4, 0))
        retries_field.entry.config(justify="center")

        tk.Label(settings_row, text="  ", bg=BG).pack(side="left")

        retry_base_lbl = tk.Label(settings_row, bg=BG, fg=TEXT_DIM, font=FONT_TINY)
        retry_base_lbl.pack(side="left")
        self.reg(retry_base_lbl, "label_retry_base")

        self.retry_base_var = tk.StringVar(value=str(DEFAULT_RETRY_BASE))
        retry_base_field = self.input_field(settings_row, self.retry_base_var, width=4)
        retry_base_field.pack(side="left", padx=(4, 0))
        retry_base_field.entry.config(justify="center")

        self.control_container = tk.Frame(body, bg=BG)
        self.control_container.pack(fill="both", expand=True)

        self.section(self.control_container, "section_ctrl", WARN).pack(fill="x", pady=(0, 8))
        ctrl_row = tk.Frame(self.control_container, bg=BG)
        ctrl_row.pack(fill="x", pady=(0, 14))
        self.start_btn = self.flat_button(ctrl_row, "btn_download",
                                          self.start_download, accent=SUCCESS)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = self.flat_button(ctrl_row, "btn_cancel",
                                           self.cancel_download,
                                           accent=DANGER, disabled=True)
        self.cancel_btn.pack(side="left")

        self.progress_canvas = tk.Canvas(self.control_container, height=24,
                                         bg=BG2, highlightthickness=1,
                                         highlightbackground=BORDER, bd=0)
        self.progress_canvas.pack(fill="x", pady=(0, 8))

        status_row = tk.Frame(self.control_container, bg=BG)
        status_row.pack(fill="x", pady=(0, 14))
        self.status_dot = tk.Label(status_row, text="●", bg=BG, fg=SUCCESS, font=FONT)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_var = tk.StringVar(value=self.t("status_ready"))
        tk.Label(status_row, textvariable=self.status_var, bg=BG, fg=TEXT,
                 font=FONT, anchor="w").pack(side="left", fill="x", expand=True)

        log_head = tk.Frame(self.control_container, bg=BG)
        log_head.pack(fill="x", pady=(0, 8))
        self.section(log_head, "section_log", ACCENT).pack(side="left")
        self.flat_button(log_head, "btn_copy_log",
                         self.copy_log, accent=ACCENT).pack(side="right")

        log_outer = tk.Frame(self.control_container, bg=BORDER)
        log_outer.pack(fill="both", expand=True)
        log_inner = tk.Frame(log_outer, bg=BG2)
        log_inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.log_text = tk.Text(
            log_inner, height=12, wrap="word", state="disabled",
            bg=BG2, fg=TEXT, insertbackground=ACCENT, font=FONT_MONO,
            bd=0, relief="flat", highlightthickness=0,
            selectbackground=ACCENT, selectforeground=BG,
            padx=8, pady=6,
        )
        scroll = tk.Scrollbar(log_inner, command=self.log_text.yview,
                              bg=BG3, troughcolor=BG2, activebackground=ACCENT,
                              bd=0, relief="flat", width=12)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.log_text.tag_config("info",  foreground=TEXT)
        self.log_text.tag_config("ok",    foreground=SUCCESS)
        self.log_text.tag_config("err",   foreground=DANGER)
        self.log_text.tag_config("warn",  foreground=WARN)
        self.log_text.tag_config("head",  foreground=ACCENT2)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=22, pady=(0, 12))
        fl = tk.Label(footer, bg=BG, fg=TEXT_DIM, font=FONT_TINY)
        fl.pack(side="left")
        self.reg(fl, "footer_left")
        fr = tk.Label(footer, text="yandex-music 3.2.2", bg=BG, fg=TEXT_DIM,
                      font=FONT_TINY)
        fr.pack(side="right")

        self._rebuild_quality_menu()
        self.set_mode("likes")

    def load_settings_into_ui(self):
        s = self.settings
        self.token_var.set(s.get("token", ""))

        save_url_on = s.get("save_url", True)
        if isinstance(save_url_on, str):
            save_url_on = save_url_on.lower() in ("1", "true", "yes", "on")
        self.save_url_var.set(save_url_on)
        self._update_save_url_toggle()

        if save_url_on:
            self.url_var.set(s.get("url", ""))
        else:
            self.url_var.set("")

        default_path = os.path.join(os.path.expanduser("~"), "Music", "YandexMusic")
        self.path_var.set(s.get("path", default_path))

        mode = s.get("mode", "likes")
        if mode in ("likes", "playlist", "album", "track"):
            self.set_mode(mode)

        q = s.get("quality", "auto")
        if q in ("auto", "mp3_320", "mp3_192", "flac"):
            self.quality_var.set(q)
            self._rebuild_quality_menu()
            names = {
                "auto":    self.t("q_auto"),
                "mp3_320": self.t("q_mp3_320"),
                "mp3_192": self.t("q_mp3_192"),
                "flac":    self.t("q_flac"),
            }
            self.quality_display_var.set(names.get(q, names["auto"]))

        self.delay_var.set(str(s.get("delay", DEFAULT_DELAY)))
        self.retries_var.set(str(s.get("retries", DEFAULT_RETRIES)))
        self.retry_base_var.set(str(s.get("retry_base", DEFAULT_RETRY_BASE)))

    def toggle_save_url(self):
        self.save_url_var.set(not self.save_url_var.get())
        self._update_save_url_toggle()
        key = "msg_save_url_on" if self.save_url_var.get() else "msg_save_url_off"
        self.log(self.t(key))

    def paste_url(self):
        try:
            text = self.root.clipboard_get()
        except Exception:
            self.log(self.t("msg_clipboard_error"))
            return
        text = text.strip()
        if not text:
            self.log(self.t("msg_clipboard_empty"))
            return
        self.url_var.set(text)
        short = text[:60] + ("…" if len(text) > 60 else "")
        self.log(self.t("msg_url_pasted", url=short))

    def copy_log(self):
        self.log_text.configure(state="normal")
        text = self.log_text.get("1.0", "end-1c")
        self.log_text.configure(state="disabled")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.append_log(self.t("msg_copied_log"))

    def check_update_async(self):
        if self.update_thread and self.update_thread.is_alive():
            return
        self.update_thread = threading.Thread(target=self._check_update_worker,
                                              daemon=True)
        self.update_thread.start()

    def _check_update_worker(self):
        new = check_updates()
        if new:
            self.msg_queue.put(("update_available", new))

    def start_device_auth(self):
        if self.auth_thread and self.auth_thread.is_alive():
            self.log(self.t("msg_auth_in_progress"))
            return
        self.device_auth_cancel.clear()
        self.auth_btn.config(state="disabled", text=self.t("btn_waiting"))
        if self.auth_dialog:
            try:
                self.auth_dialog.close()
            except Exception:
                pass
        self.auth_dialog = AuthDialog(self.root, self.t,
                                      on_cancel=self.cancel_device_auth)
        self.auth_thread = threading.Thread(target=self.device_auth_worker,
                                            daemon=True)
        self.auth_thread.start()

    def cancel_device_auth(self):
        self.device_auth_cancel.set()
        self.log(self.t("msg_auth_cancelled"))
        self.auth_btn.config(state="normal", text=self.t("btn_login"))
        self.auth_dialog = None

    def device_auth_worker(self):
        try:
            client = Client()

            def on_code(device_code):
                self.msg_queue.put(("auth_code", device_code))

            def should_cancel():
                return self.device_auth_cancel.is_set()

            self.log(self.t("msg_auth_request"))
            token = client.device_auth(on_code=on_code, poll_interval=2,
                                       timeout=300, should_cancel=should_cancel)
            if token is None:
                self.msg_queue.put(("auth_error", self.t("msg_auth_cancelled")))
                return
            self.msg_queue.put(("auth_token", token.access_token))
        except DeviceAuthError as e:
            self.msg_queue.put(("auth_error", f"OAuth: {e}"))
        except Exception as e:
            self.msg_queue.put(("auth_error", f"{type(e).__name__}: {e}"))

    def handle_auth_code(self, device_code):
        user_code = device_code.user_code
        url = device_code.verification_url
        self.log(self.t("msg_code_received", code=user_code))
        self.log(self.t("msg_code_page", url=url))
        if self.auth_dialog and not self.auth_dialog.closed:
            self.auth_dialog.set_code(user_code, url)
        else:
            try:
                webbrowser.open(url)
            except Exception:
                pass
            messagebox.showinfo(self.t("auth_title"), f"{url}\n\n{user_code}")

    def handle_auth_token(self, token):
        self.token_var.set(token)
        self.save_settings()
        self.log(self.t("msg_token_saved"))
        self.auth_btn.config(state="normal", text=self.t("btn_login"))
        if self.auth_dialog and not self.auth_dialog.closed:
            self.auth_dialog.set_success()
        self.auth_dialog = None

    def handle_auth_error(self, error):
        self.log(self.t("msg_auth_failed", e=error))
        self.auth_btn.config(state="normal", text=self.t("btn_login"))
        if self.auth_dialog and not self.auth_dialog.closed:
            self.auth_dialog.set_error(error)
        self.auth_dialog = None

    def set_mode(self, value):
        self.mode_var.set(value)
        for v, (btn, color, key) in self.mode_buttons.items():
            if v == value:
                btn.config(fg=color, highlightbackground=color, bg=BG2)
            else:
                btn.config(fg=TEXT_DIM, highlightbackground=BORDER, bg=BG3)
        if value == "likes":
            self.url_field.entry.configure(state="disabled")
            self.url_label.configure(fg=BORDER)
            self.url_field.configure(bg=BORDER)
        else:
            self.url_field.entry.configure(state="normal")
            self.url_label.configure(fg=TEXT_DIM)
            self.url_field.configure(bg=BORDER)

    def browse_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.path_var.get() or os.path.expanduser("~"))
        if folder:
            self.path_var.set(folder)

    def animate(self):
        self.anim_phase += 1
        busy = (self.worker_thread and self.worker_thread.is_alive()) or \
               (self.auth_thread and self.auth_thread.is_alive())
        if busy:
            if self.anim_phase % 8 == 0:
                self.status_dot.config(fg=ACCENT)
            elif self.anim_phase % 8 == 4:
                self.status_dot.config(fg=BORDER)
        else:
            self.status_dot.config(fg=SUCCESS)
        if self.anim_phase % 2 == 0:
            self.draw_progress(*self.last_progress)
        self.root.after(80, self.animate)

    def draw_progress(self, cur, total):
        c = self.progress_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2:
            w, h = 800, 24
        c.create_rectangle(0, 0, w, h, fill=BG2, outline="")
        if total <= 0:
            c.create_text(w // 2, h // 2, text="— / —",
                          fill=TEXT_DIM, font=FONT_BOLD)
            return
        pct = cur / total
        if pct < 0.5:
            self.progress_color = SUCCESS
        elif pct < 0.85:
            self.progress_color = ACCENT
        elif pct < 1.0:
            self.progress_color = WARN
        else:
            self.progress_color = ACCENT2
        fill_w = int((w - 4) * pct)
        if fill_w > 0:
            c.create_rectangle(2, 2, 2 + fill_w, h - 2,
                               fill=self.progress_color, outline="")
            shine_pos = 2 + ((self.anim_phase * 6) % max(fill_w, 1))
            c.create_line(shine_pos - 10, 3, shine_pos, 3,
                          fill="#ffffff", width=1)
            c.create_line(shine_pos - 10, h - 4, shine_pos, h - 4,
                          fill="#ffffff", width=1)
        txt = f"{int(pct*100):>3}%   {cur} / {total}"
        c.create_text(w // 2, h // 2, text=txt,
                      fill=TEXT if pct < 0.6 else BG, font=FONT_BOLD)

    def log(self, msg):
        self.msg_queue.put(("log", msg))

    def set_status(self, msg):
        self.msg_queue.put(("status", msg))

    def set_progress(self, current, total):
        self.msg_queue.put(("progress", (current, total)))

    def set_total(self, total):
        self.msg_queue.put(("total", total))

    def process_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self.append_log(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "progress":
                    self.last_progress = payload
                    self.draw_progress(*payload)
                elif kind == "total":
                    self.last_progress = (0, payload)
                    self.draw_progress(0, payload)
                elif kind == "done":
                    self.on_download_finished(payload)
                elif kind == "auth_code":
                    self.handle_auth_code(payload)
                elif kind == "auth_token":
                    self.handle_auth_token(payload)
                elif kind == "auth_error":
                    self.handle_auth_error(payload)
                elif kind == "update_available":
                    self.log(self.t("msg_update_found", v=payload))
        except queue_module.Empty:
            pass
        self.root.after(80, self.process_queue)

    def append_log(self, msg):
        tag = "info"
        if "[OK]" in msg:
            tag = "ok"
        elif "[ERR]" in msg or "[!]" in msg:
            tag = "err"
        elif "429" in msg:
            tag = "warn"
        elif "[i]" in msg:
            tag = "head"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        logger.info(msg)

    def start_download(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror(self.t("err_title"), self.t("err_no_token"))
            return
        mode = self.mode_var.get()
        url = self.url_var.get().strip()
        if mode in ("playlist", "album", "track") and not url:
            messagebox.showerror(self.t("err_title"), self.t("err_no_url"))
            return
        path = self.path_var.get().strip()
        if not path:
            messagebox.showerror(self.t("err_title"), self.t("err_no_path"))
            return

        delay = self._safe_float(self.delay_var.get(), DEFAULT_DELAY)
        retries = self._safe_int(self.retries_var.get(), DEFAULT_RETRIES)
        retry_base = self._safe_int(self.retry_base_var.get(), DEFAULT_RETRY_BASE)
        quality = self.quality_var.get()

        self.rate_limit_hint_shown = False

        self.save_settings()
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.collapse_sections(True)
        self.last_progress = (0, 0)
        self.draw_progress(0, 0)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        logger.info(f"=== Start download: mode={mode} quality={quality} "
                    f"delay={delay} retries={retries} base={retry_base} ===")
        self.worker_thread = threading.Thread(
            target=self.download_worker,
            args=(token, mode, url, path, quality, delay, retries, retry_base),
            daemon=True,
        )
        self.worker_thread.start()

    def cancel_download(self):
        self.stop_event.set()
        self.log(self.t("msg_cancel_requested"))
        self.cancel_btn.config(state="disabled")

    def fetch_metadata_parallel(self, items, total, extractor):
        tracks = [None] * len(items)
        done_count = 0
        with ThreadPoolExecutor(max_workers=MAX_METADATA_WORKERS) as executor:
            futures = {executor.submit(extractor, it): i for i, it in enumerate(items)}
            for fut in as_completed(futures):
                if self.stop_event.is_set():
                    break
                idx = futures[fut]
                try:
                    tracks[idx] = fut.result()
                except Exception as e:
                    self.log(self.t("msg_track_fail", i=idx + 1, e=e))
                done_count += 1
                if done_count % 5 == 0 or done_count == total:
                    self.set_status(self.t("status_meta", i=done_count, n=total))
        return [t for t in tracks if t]

    def download_worker(self, token, mode, url, path, quality, delay, retries, retry_base):
        try:
            self.log(self.t("msg_auth_start"))
            client = Client(token).init()
            self.log(self.t("msg_auth_ok"))

            if mode == "likes":
                self.log(self.t("msg_loading_likes"))
                liked = client.users_likes_tracks()
                if not liked:
                    self.log(self.t("msg_no_tracks"))
                    self.finish(0, 0)
                    return
                total_liked = len(liked)
                self.set_total(total_liked)

                def extract(lt):
                    try:
                        return lt.fetch_track()
                    except Exception:
                        return None

                tracks = self.fetch_metadata_parallel(list(liked), total_liked, extract)
                title = "Liked"

            elif mode == "playlist":
                self.log(self.t("msg_loading_playlist", url=url))
                clean_url = url.split("?")[0].split("#")[0]
                user_id, kind = parse_playlist_url(clean_url)

                playlist_obj = None
                try:
                    result = client.users_playlists(kind, user_id)
                    if isinstance(result, list) and result:
                        playlist_obj = result[0]
                    elif hasattr(result, "fetch_tracks"):
                        playlist_obj = result
                    elif isinstance(result, dict) and result:
                        first = next(iter(result.values()))
                        if hasattr(first, "fetch_tracks"):
                            playlist_obj = first
                except Exception as e1:
                    self.log(f"[!] {type(e1).__name__}: {e1!r}")

                if playlist_obj is None:
                    try:
                        pid = f"{user_id}:{kind}"
                        result = client.playlists_list([pid])
                        if isinstance(result, list) and result:
                            playlist_obj = result[0]
                        elif hasattr(result, "fetch_tracks"):
                            playlist_obj = result
                    except Exception as e2:
                        self.log(f"[!] {type(e2).__name__}: {e2!r}")

                if playlist_obj is None:
                    self.log(self.t("msg_playlist_fail"))
                    self.finish(0, 0)
                    return

                title = getattr(playlist_obj, "title", None) or f"playlist_{kind}"

                try:
                    fetched = playlist_obj.fetch_tracks()
                    if isinstance(fetched, list):
                        raw_tracks = fetched
                    elif hasattr(fetched, "tracks"):
                        raw_tracks = fetched.tracks
                    else:
                        raw_tracks = []
                except Exception as e3:
                    self.log(f"[ERR] {type(e3).__name__}: {e3!r}")
                    self.finish(0, 0)
                    return

                total_pl = len(raw_tracks)
                self.set_total(total_pl)
                self.log(self.t("msg_playlist", title=title, n=total_pl))

                def extract(item):
                    try:
                        if hasattr(item, "fetch_track"):
                            return item.fetch_track()
                        return item
                    except Exception:
                        return None

                tracks = self.fetch_metadata_parallel(raw_tracks, total_pl, extract)

            elif mode == "album":
                self.log(self.t("msg_loading_album", url=url))
                clean_url = url.split("?")[0].split("#")[0]
                album_id = parse_album_url(clean_url)
                album = client.albums_with_tracks(album_id)
                title = album.title or f"album_{album_id}"
                tracks = [t for vol in album.volumes for t in vol]
                self.set_total(len(tracks))

            elif mode == "track":
                self.log(self.t("msg_loading_track", url=url))
                clean_url = url.split("?")[0].split("#")[0]
                track_id = parse_track_url(clean_url)
                tracks_result = client.tracks([track_id])
                if not tracks_result:
                    self.log(self.t("msg_track_not_found"))
                    self.finish(0, 0)
                    return
                track = tracks_result[0]
                artist_name = track.artists[0].name if track.artists else "Unknown"
                title = f"{artist_name} - {track.title}"
                tracks = [track]
                self.set_total(1)

            else:
                self.log(f"[ERR] mode={mode}")
                self.finish(0, 0)
                return

            if not tracks:
                self.log(self.t("msg_no_tracks_found"))
                self.finish(0, 0)
                return

            folder = os.path.join(path, sanitize(title))
            os.makedirs(folder, exist_ok=True)
            self.log(self.t("msg_folder", path=folder))
            self.log(self.t("msg_tracks_count", n=len(tracks)))
            self.set_status(self.t("status_downloading", i=0, n=len(tracks)))

            ok, failed, skipped = 0, 0, 0
            total = len(tracks)

            for i, track in enumerate(tracks, 1):
                if self.stop_event.is_set():
                    self.log(self.t("msg_stopped_at", i=i - 1, n=total))
                    break
                self.set_progress(i - 1, total)

                artist_name = track.artists[0].name if track.artists else "Unknown Artist"
                ext = "flac" if quality == "flac" else "mp3"
                filename = f"{sanitize(artist_name)} - {sanitize(track.title)}.{ext}"
                filepath = os.path.join(folder, filename)

                if is_valid_file(filepath):
                    self.log(f"[{i}/{total}] {self.t('msg_skip')}: {filename}")
                    skipped += 1
                    self.set_progress(i, total)
                    continue

                self.set_status(self.t("status_downloading", i=i, n=total))
                self.log(f"[{i}/{total}] {filename}")

                success = False
                for attempt in range(1, retries + 1):
                    if self.stop_event.is_set():
                        break
                    try:
                        self._download_track(track, filepath, quality)
                        success = True
                        break
                    except Exception as e:
                        err_text = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
                        if is_429(e):
                            if not self.rate_limit_hint_shown:
                                self.log(self.t("msg_rate_limit_hint"))
                                self.rate_limit_hint_shown = True
                            wait = calc_backoff(attempt, retry_base)
                            if attempt < retries:
                                self.log("    " + self.t("msg_retry_429",
                                                         wait=wait,
                                                         attempt=attempt,
                                                         max=retries))
                            else:
                                self.log(self.t("msg_last_attempt"))
                            for _ in range(wait):
                                if self.stop_event.is_set():
                                    break
                                time.sleep(1)
                        else:
                            self.log(f"    [ERR] {type(e).__name__}: {err_text}")
                            break

                if success:
                    ok += 1
                else:
                    failed += 1

                self.set_progress(i, total)

                if i < total and not self.stop_event.is_set():
                    for _ in range(int(delay)):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)

            self.log(self.t("msg_summary", ok=ok, skip=skipped, fail=failed))
            self.finish(ok + skipped, failed)

        except UnauthorizedError:
            self.log(self.t("msg_bad_token"))
            self.finish(0, 0)
        except ValueError as e:
            self.log(f"[ERR] {e}")
            self.finish(0, 0)
        except Exception as e:
            self.log(self.t("msg_critical", e=f"{type(e).__name__}: {e!r}"))
            self.log(self.t("msg_traceback"))
            for line in traceback.format_exc().splitlines():
                self.log("   " + line)
            logger.exception("Critical error")
            self.finish(0, 0)

    def _download_track(self, track, filepath, quality):
        if quality == "flac":
            try:
                track.download(filepath, codec="flac")
                return
            except Exception:
                pass
        if quality == "mp3_320":
            try:
                track.download(filepath, codec="mp3", bitrate_in_kbps=320)
                return
            except Exception:
                pass
        if quality == "mp3_192":
            try:
                track.download(filepath, codec="mp3", bitrate_in_kbps=192)
                return
            except Exception:
                pass
        track.download(filepath)

    def finish(self, ok, failed):
        self.msg_queue.put(("done", (ok, failed)))

    def on_download_finished(self, payload):
        ok, failed = payload
        self.collapse_sections(False)
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.set_status(self.t("status_done", ok=ok, fail=failed))
        if failed > 0:
            self.log(self.t("msg_restart_hint"))
        if ok > 0:
            DonateDialog(self.root, self.t)

    def on_close(self):
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno(self.t("confirm_close_title"),
                                       self.t("confirm_close")):
                return
            self.stop_event.set()
            self.worker_thread.join(timeout=3)
        if self.auth_thread and self.auth_thread.is_alive():
            self.device_auth_cancel.set()
            self.auth_thread.join(timeout=3)
        if self.auth_dialog and not self.auth_dialog.closed:
            try:
                self.auth_dialog.close()
            except Exception:
                pass
        self.save_settings()
        logger.info("App closed")
        self.root.destroy()


def main():
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
