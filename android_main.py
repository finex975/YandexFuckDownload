import os
import re
import sys
import json
import time
import random
import threading
import traceback
import queue as queue_module
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.window import Window

try
    from translations import LANG_NAMES, NAME_TO_CODE, TRANSLATIONS
except ImportError
    print([!] translations.py не найден рядом)
    sys.exit(1)

try
    from yandex_music import Client
    from yandex_music.exceptions import UnauthorizedError, DeviceAuthError
except ImportError
    print([!] Установите pip install yandex-music)
    sys.exit(1)

# ============================================================
#  ANDROID PERMISSIONS
# ============================================================
if platform == android
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path

    def get_music_path()
        try
            base = primary_external_storage_path()
            return os.path.join(base, Music, YandexMusic)
        except Exception
            return sdcardMusicYandexMusic

    def request_android_permissions()
        try
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])
        except Exception
            pass
else
    def get_music_path()
        return os.path.join(os.path.expanduser(~), Music, YandexMusic)

    def request_android_permissions()
        pass

APP_VERSION = 1.2.1
SETTINGS_FILE = ymd_settings.json
KOFI_URL = httpsko-fi.comfinex_studio

DEFAULT_DELAY = 2.0
DEFAULT_RETRIES = 6
DEFAULT_RETRY_BASE = 8
MAX_WAIT = 60
MAX_METADATA_WORKERS = 5

# ============================================================
#  ЦВЕТА (как в десктопной версии)
# ============================================================
def hex_rgba(h, a=1.0)
    h = h.lstrip(#)
    return tuple(int(h[ii+2], 16)  255 for i in (0, 2, 4)) + (a,)

BG      = hex_rgba(0f1117)
BG2     = hex_rgba(161923)
BG3     = hex_rgba(1e2230)
BORDER  = hex_rgba(2a2f42)
ACCENT  = hex_rgba(4fc3d9)
ACCENT2 = hex_rgba(c77dff)
SUCCESS = hex_rgba(5cd68a)
WARN    = hex_rgba(e6c465)
DANGER  = hex_rgba(e07a8a)
TEXT    = hex_rgba(d6dbe8)
TEXT_DIM= hex_rgba(7b8298)

Window.clearcolor = BG
if platform != android
    Window.size = (400, 800)


# ============================================================
#  УТИЛИТЫ
# ============================================================
def sanitize(name)
    name = .join(c for c in str(name) if c.isalnum() or c in  .-_)
    return name.strip() or unnamed


def is_429(error)
    resp = getattr(error, response, None)
    if resp is not None and getattr(resp, status_code, None) == 429
        return True
    text = str(error)
    return 429 in text or Concurrency in text or Too Many Requests in text


def calc_backoff(attempt, base=DEFAULT_RETRY_BASE)
    exponential = base  (2  (attempt - 1))
    jittered = exponential  random.uniform(0.7, 1.3)
    return int(min(jittered, MAX_WAIT))


def is_valid_file(filepath, min_size=100_000)
    try
        return os.path.exists(filepath) and os.path.getsize(filepath)  min_size
    except OSError
        return False


def parse_playlist_url(url)
    m = re.search(rusers([^]+)playlists(d+), url)
    if not m
        raise ValueError(Invalid playlist URL)
    return m.group(1), int(m.group(2))


def parse_album_url(url)
    m = re.search(ralbum(d+), url)
    if not m
        raise ValueError(Invalid album URL)
    return int(m.group(1))


def parse_track_url(url)
    m = re.search(rtrack(d+), url)
    if not m
        raise ValueError(Invalid track URL)
    return int(m.group(1))


# ============================================================
#  UI-ХЕЛПЕРЫ
# ============================================================
def make_button(text, on_press, color=ACCENT, height=48)
    btn = Button(
        text=text,
        size_hint_y=None,
        height=dp(height),
        background_normal=,
        background_color=BG3,
        color=color,
        font_size=sp(14),
        bold=True,
    )
    btn.bind(on_press=on_press)
    return btn


def make_label(text, color=TEXT, size=14, height=24, halign=left)
    lbl = Label(
        text=text,
        color=color,
        font_size=sp(size),
        size_hint_y=None,
        height=dp(height),
        halign=halign,
        valign=middle,
    )
    lbl.bind(size=lambda s, v setattr(s, text_size, (v[0], None)))
    return lbl


def make_input(text=, password=False, height=44)
    ti = TextInput(
        text=text,
        password=password,
        multiline=False,
        size_hint_y=None,
        height=dp(height),
        background_color=BG2,
        foreground_color=TEXT,
        cursor_color=ACCENT,
        font_size=sp(13),
        padding=[dp(10), dp(10)],
    )
    return ti


def make_section(title, color=ACCENT)
    lbl = Label(
        text=f▎ {title},
        color=color,
        font_size=sp(13),
        bold=True,
        size_hint_y=None,
        height=dp(28),
        halign=left,
        valign=middle,
    )
    lbl.bind(size=lambda s, v setattr(s, text_size, (v[0], None)))
    return lbl


class Card(BoxLayout)
    def __init__(self, kwargs)
        super().__init__(kwargs)
        self.orientation = vertical
        self.padding = dp(12)
        self.spacing = dp(6)
        self.size_hint_y = None
        with self.canvas.before
            Color(BG2)
            self.bg = RoundedRectangle(radius=[dp(8)])
        self.bind(pos=self._update, size=self._update)
        self.bind(minimum_height=self.setter(height))

    def _update(self, args)
        self.bg.pos = self.pos
        self.bg.size = self.size


# ============================================================
#  ГЛАВНЫЙ ЭКРАН
# ============================================================
class MainScreen(Screen)
    def __init__(self, app, kwargs)
        super().__init__(kwargs)
        self.app = app
        self.build()

    def build(self)
        root = BoxLayout(orientation=vertical, padding=dp(10), spacing=dp(8))

        # Заголовок
        header = BoxLayout(orientation=horizontal, size_hint_y=None, height=dp(50))
        title_box = BoxLayout(orientation=vertical)
        title_box.add_widget(make_label(YANDEX MUSIC, color=TEXT, size=18, height=24))
        title_box.add_widget(make_label(DOWNLOADER, color=ACCENT, size=14, height=20))
        header.add_widget(title_box)

        self.lang_spinner = Spinner(
            text=LANG_NAMES.get(self.app.current_lang, Русский),
            values=list(LANG_NAMES.values()),
            size_hint=(None, None),
            size=(dp(130), dp(40)),
            background_color=BG3,
            color=ACCENT,
            font_size=sp(12),
        )
        self.lang_spinner.bind(text=self.on_lang_change)
        header.add_widget(self.lang_spinner)
        root.add_widget(header)

        # Скролл
        scroll = ScrollView()
        self.content = BoxLayout(
            orientation=vertical,
            spacing=dp(10),
            size_hint_y=None,
            padding=[0, dp(6), 0, dp(6)],
        )
        self.content.bind(minimum_height=self.content.setter(height))
        scroll.add_widget(self.content)
        root.add_widget(scroll)

        self.build_auth_section()
        self.build_source_section()
        self.build_dest_section()
        self.build_control_section()
        self.build_log_section()

        self.add_widget(root)
        self.load_settings_into_ui()

    # ---------- СЕКЦИИ ----------
    def build_auth_section(self)
        self.content.add_widget(make_section(self.app.t(section_auth), ACCENT))
        card = Card()

        card.add_widget(make_label(self.app.t(label_token), color=TEXT_DIM, size=11, height=18))
        row = BoxLayout(orientation=horizontal, spacing=dp(8), size_hint_y=None, height=dp(44))
        self.token_input = make_input(self.app.settings.get(token, ), password=True)
        row.add_widget(self.token_input)
        row.add_widget(make_button(self.app.t(btn_login), self.on_login,
                                   color=SUCCESS, height=44))
        card.add_widget(row)
        self.content.add_widget(card)

    def build_source_section(self)
        self.content.add_widget(make_section(self.app.t(section_source), ACCENT2))
        card = Card()

        card.add_widget(make_label(self.app.t(label_mode), color=TEXT_DIM, size=11, height=18))
        mode_row = BoxLayout(orientation=horizontal, spacing=dp(6), size_hint_y=None, height=dp(42))
        self.mode_buttons = {}
        for value, key, color in [
            (likes, mode_likes, ACCENT),
            (playlist, mode_playlist, ACCENT2),
            (album, mode_album, SUCCESS),
            (track, mode_track, WARN),
        ]
            btn = make_button(self.app.t(key), lambda a, v=value self.on_mode(v),
                              color=color, height=42)
            btn.font_size = sp(11)
            mode_row.add_widget(btn)
            self.mode_buttons[value] = btn
        card.add_widget(mode_row)

        card.add_widget(make_label(self.app.t(label_quality), color=TEXT_DIM, size=11, height=18))
        self.quality_spinner = Spinner(
            text=self.app.t(q_auto),
            values=[
                self.app.t(q_auto),
                self.app.t(q_mp3_320),
                self.app.t(q_mp3_192),
                self.app.t(q_flac),
            ],
            size_hint_y=None,
            height=dp(40),
            background_color=BG3,
            color=ACCENT2,
            font_size=sp(12),
        )
        card.add_widget(self.quality_spinner)

        card.add_widget(make_label(self.app.t(label_url), color=TEXT_DIM, size=11, height=18))
        url_row = BoxLayout(orientation=horizontal, spacing=dp(6), size_hint_y=None, height=dp(44))
        self.url_input = make_input(self.app.settings.get(url, ))
        url_row.add_widget(self.url_input)
        url_row.add_widget(make_button(self.app.t(btn_paste), self.on_paste,
                                       color=ACCENT2, height=44))
        card.add_widget(url_row)

        self.content.add_widget(card)

    def build_dest_section(self)
        self.content.add_widget(make_section(self.app.t(section_dest), SUCCESS))
        card = Card()

        card.add_widget(make_label(self.app.t(label_path), color=TEXT_DIM, size=11, height=18))
        default_path = self.app.settings.get(path, get_music_path())
        self.path_input = make_input(default_path)
        card.add_widget(self.path_input)

        # Настройки retry
        row = BoxLayout(orientation=horizontal, spacing=dp(6), size_hint_y=None, height=dp(38))
        row.add_widget(make_label(self.app.t(label_delay), color=TEXT_DIM, size=10, height=38))
        self.delay_input = make_input(str(self.app.settings.get(delay, DEFAULT_DELAY)), height=38)
        self.delay_input.input_filter = float
        row.add_widget(self.delay_input)
        row.add_widget(make_label(self.app.t(label_retries), color=TEXT_DIM, size=10, height=38))
        self.retries_input = make_input(str(self.app.settings.get(retries, DEFAULT_RETRIES)), height=38)
        self.retries_input.input_filter = int
        row.add_widget(self.retries_input)
        card.add_widget(row)

        self.content.add_widget(card)

    def build_control_section(self)
        self.content.add_widget(make_section(self.app.t(section_ctrl), WARN))
        card = Card()

        btn_row = BoxLayout(orientation=horizontal, spacing=dp(8), size_hint_y=None, height=dp(48))
        self.start_btn = make_button(self.app.t(btn_download), self.on_start,
                                     color=SUCCESS, height=48)
        self.cancel_btn = make_button(self.app.t(btn_cancel), self.on_cancel,
                                      color=DANGER, height=48)
        self.cancel_btn.disabled = True
        btn_row.add_widget(self.start_btn)
        btn_row.add_widget(self.cancel_btn)
        card.add_widget(btn_row)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(20))
        card.add_widget(self.progress)

        self.status_label = make_label(self.app.t(status_ready), color=TEXT, size=12, height=22)
        card.add_widget(self.status_label)

        self.content.add_widget(card)

    def build_log_section(self)
        self.content.add_widget(make_section(self.app.t(section_log), ACCENT))
        card = Card()

        scroll = ScrollView(size_hint_y=None, height=dp(180))
        self.log_label = Label(
            text=,
            color=TEXT,
            font_size=sp(10),
            size_hint_y=None,
            halign=left,
            valign=top,
            markup=True,
        )
        self.log_label.bind(
            width=lambda s, v setattr(s, text_size, (v, None)),
            texture_size=lambda s, v setattr(s, height, v[1]),
        )
        scroll.add_widget(self.log_label)
        card.add_widget(scroll)

        self.content.add_widget(card)

    # ---------- ДЕЙСТВИЯ ----------
    def on_lang_change(self, spinner, text)
        code = NAME_TO_CODE.get(text, ru)
        if code != self.app.current_lang
            self.app.current_lang = code
            self.app.save_settings()
            self.app.rebuild_ui()

    def on_mode(self, value)
        self.app.mode = value
        self.update_mode_buttons()

    def update_mode_buttons(self)
        for v, btn in self.mode_buttons.items()
            if v == self.app.mode
                btn.background_color = (BG2[3], 1)
                btn.color = ACCENT if v != track else WARN
            else
                btn.background_color = (BG3[3], 1)
                btn.color = TEXT_DIM
        if self.app.mode == likes
            self.url_input.disabled = True
        else
            self.url_input.disabled = False

    def on_paste(self, args)
        try
            from kivy.core.clipboard import Clipboard
            text = Clipboard.paste()
            if text
                self.url_input.text = text.strip()
                self.app.log_msg(self.app.t(msg_url_pasted, url=text[60]))
        except Exception as e
            self.app.log_msg(f[!] Clipboard {e})

    def on_login(self, args)
        self.app.start_device_auth()

    def on_start(self, args)
        token = self.token_input.text.strip()
        if not token
            self.app.toast(self.app.t(err_no_token))
            return
        self.app.mode = self.app.mode
        self.app.url = self.url_input.text.strip()
        self.app.path = self.path_input.text.strip() or get_music_path()
        self.app.delay = self._safe_float(self.delay_input.text, DEFAULT_DELAY)
        self.app.retries = self._safe_int(self.retries_input.text, DEFAULT_RETRIES)
        self.app.quality = self._quality_code()
        self.app.token = token
        self.app.save_settings()
        self.app.start_download()

    def _safe_float(self, s, default)
        try
            return max(0.5, float(str(s).replace(,, .)))
        except Exception
            return default

    def _safe_int(self, s, default)
        try
            return max(1, int(s))
        except Exception
            return default

    def _quality_code(self)
        t = self.quality_spinner.text
        if t == self.app.t(q_flac)
            return flac
        if t == self.app.t(q_mp3_320)
            return mp3_320
        if t == self.app.t(q_mp3_192)
            return mp3_192
        return auto

    def on_cancel(self, args)
        self.app.stop_event.set()
        self.app.log_msg(self.app.t(msg_cancel_requested))
        self.cancel_btn.disabled = True

    def load_settings_into_ui(self)
        self.update_mode_buttons()
        mode = self.app.settings.get(mode, likes)
        if mode in self.mode_buttons
            self.app.mode = mode
            self.update_mode_buttons()

    def set_downloading(self, active)
        self.start_btn.disabled = active
        self.cancel_btn.disabled = not active

    def set_progress(self, cur, total)
        if total  0
            self.progress.value = (cur  total)  100
        else
            self.progress.value = 0

    def set_status(self, text)
        self.status_label.text = text


# ============================================================
#  ЭКРАН АВТОРИЗАЦИИ
# ============================================================
class AuthScreen(Screen)
    def __init__(self, app, kwargs)
        super().__init__(kwargs)
        self.app = app
        root = BoxLayout(orientation=vertical, padding=dp(16), spacing=dp(12))

        root.add_widget(make_label(self.app.t(auth_title), color=TEXT, size=18, height=40))
        root.add_widget(make_label(self.app.t(auth_subtitle), color=ACCENT, size=12, height=24))

        root.add_widget(make_label(self.app.t(auth_code_label),
                                   color=TEXT_DIM, size=12, height=24))

        self.code_label = Label(
            text=— — — —,
            color=ACCENT2,
            font_size=sp(32),
            bold=True,
            size_hint_y=None,
            height=dp(70),
        )
        root.add_widget(self.code_label)

        self.url_label = make_label(, color=ACCENT, size=10, height=22)
        root.add_widget(self.url_label)

        self.status_label = make_label(self.app.t(auth_waiting), color=WARN, size=12, height=24)
        root.add_widget(self.status_label)

        row = BoxLayout(orientation=horizontal, spacing=dp(8), size_hint_y=None, height=dp(48))
        row.add_widget(make_button(self.app.t(auth_copy_code), self.copy_code,
                                   color=SUCCESS, height=48))
        row.add_widget(make_button(self.app.t(auth_open_yandex), self.open_browser,
                                   color=ACCENT, height=48))
        root.add_widget(row)

        root.add_widget(make_button(self.app.t(auth_cancel), self.cancel,
                                    color=TEXT_DIM, height=44))

        self.add_widget(root)
        self.user_code = None
        self.verification_url = None

    def set_code(self, user_code, url)
        self.user_code = user_code
        self.verification_url = url
        self.code_label.text = user_code
        self.url_label.text = url
        self.status_label.text = self.app.t(auth_copy_and_open)
        self.status_label.color = ACCENT

    def copy_code(self, args)
        if not self.user_code
            return
        try
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(self.user_code)
            self.status_label.text = self.app.t(auth_code_copied)
            self.status_label.color = SUCCESS
        except Exception as e
            self.status_label.text = fОшибка {e}
            self.status_label.color = DANGER
        Clock.schedule_once(lambda dt self.open_browser(), 0.6)

    def open_browser(self, args)
        if not self.verification_url
            return
        try
            webbrowser.open(self.verification_url)
        except Exception
            pass
        self.status_label.text = self.app.t(auth_waiting_confirm)
        self.status_label.color = WARN

    def cancel(self, args)
        self.app.cancel_device_auth()

    def set_success(self)
        self.status_label.text = self.app.t(auth_success)
        self.status_label.color = SUCCESS
        Clock.schedule_once(lambda dt self.app.go_main(), 1.0)

    def set_error(self, msg)
        self.status_label.text = msg
        self.status_label.color = DANGER


# ============================================================
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
class YMDApp(App)
    def __init__(self, kwargs)
        super().__init__(kwargs)
        self.settings = {}
        self.current_lang = ru
        self.msg_queue = queue_module.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.auth_thread = None
        self.device_auth_cancel = threading.Event()
        self.rate_limit_hint_shown = False

        self.token = 
        self.mode = likes
        self.url = 
        self.path = get_music_path()
        self.delay = DEFAULT_DELAY
        self.retries = DEFAULT_RETRIES
        self.quality = auto

    def t(self, key, kwargs)
        lang_dict = TRANSLATIONS.get(self.current_lang, TRANSLATIONS[ru])
        s = lang_dict.get(key) or TRANSLATIONS[ru].get(key, key)
        if kwargs
            try
                return s.format(kwargs)
            except Exception
                return s
        return s

    def load_settings(self)
        try
            with open(SETTINGS_FILE, r, encoding=utf-8) as f
                self.settings = json.load(f)
        except Exception
            self.settings = {}
        self.current_lang = self.settings.get(lang, ru)
        if self.current_lang not in TRANSLATIONS
            self.current_lang = ru
        self.token = self.settings.get(token, )
        self.mode = self.settings.get(mode, likes)
        self.url = self.settings.get(url, )
        self.path = self.settings.get(path, get_music_path())
        self.delay = self.settings.get(delay, DEFAULT_DELAY)
        self.retries = self.settings.get(retries, DEFAULT_RETRIES)
        self.quality = self.settings.get(quality, auto)

    def save_settings(self)
        data = {
            token self.token,
            mode self.mode,
            url self.url,
            path self.path,
            lang self.current_lang,
            delay self.delay,
            retries self.retries,
            quality self.quality,
        }
        try
            with open(SETTINGS_FILE, w, encoding=utf-8) as f
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e
            print(fsave settings {e})

    def build(self)
        self.load_settings()
        self.sm = ScreenManager()
        self.main_screen = MainScreen(self, name=main)
        self.auth_screen = AuthScreen(self, name=auth)
        self.sm.add_widget(self.main_screen)
        self.sm.add_widget(self.auth_screen)
        Clock.schedule_interval(self.process_queue, 0.1)
        return self.sm

    def on_start(self)
        request_android_permissions()
        Clock.schedule_once(lambda dt self.main_screen.update_mode_buttons(), 0.3)

    def rebuild_ui(self)
        self.sm.clear_widgets()
        self.main_screen = MainScreen(self, name=main)
        self.auth_screen = AuthScreen(self, name=auth)
        self.sm.add_widget(self.main_screen)
        self.sm.add_widget(self.auth_screen)

    def go_main(self)
        self.sm.current = main
        if self.token
            self.main_screen.token_input.text = self.token

    def toast(self, msg)
        self.log_msg(f[!] {msg})

    # ---------- ЛОГ ----------
    def log_msg(self, msg)
        self.msg_queue.put((log, msg))

    def set_status(self, text)
        self.msg_queue.put((status, text))

    def set_progress(self, cur, total)
        self.msg_queue.put((progress, (cur, total)))

    def process_queue(self, dt)
        try
            while True
                kind, payload = self.msg_queue.get_nowait()
                if kind == log
                    self._append_log(payload)
                elif kind == status
                    self.main_screen.set_status(payload)
                elif kind == progress
                    self.main_screen.set_progress(payload)
                elif kind == done
                    self.on_finished(payload)
                elif kind == auth_code
                    self.auth_screen.set_code(payload.user_code, payload.verification_url)
                elif kind == auth_token
                    self.on_auth_token(payload)
                elif kind == auth_error
                    self.auth_screen.set_error(payload)
        except queue_module.Empty
            pass

    def _append_log(self, msg)
        current = self.main_screen.log_label.text
        lines = (current + n + msg).split(n)[-80]
        self.main_screen.log_label.text = n.join(lines)

    # ---------- АВТОРИЗАЦИЯ ----------
    def start_device_auth(self)
        if self.auth_thread and self.auth_thread.is_alive()
            return
        self.device_auth_cancel.clear()
        self.sm.current = auth
        self.auth_screen.status_label.text = self.t(auth_waiting)
        self.auth_screen.status_label.color = WARN
        self.auth_thread = threading.Thread(target=self._device_auth_worker, daemon=True)
        self.auth_thread.start()

    def cancel_device_auth(self)
        self.device_auth_cancel.set()
        self.go_main()

    def _device_auth_worker(self)
        try
            client = Client()

            def on_code(device_code)
                self.msg_queue.put((auth_code, device_code))

            def should_cancel()
                return self.device_auth_cancel.is_set()

            self.log_msg(self.t(msg_auth_request))
            token = client.device_auth(on_code=on_code, poll_interval=2,
                                       timeout=300, should_cancel=should_cancel)
            if token is None
                self.msg_queue.put((auth_error, self.t(msg_auth_cancelled)))
                return
            self.msg_queue.put((auth_token, token.access_token))
        except DeviceAuthError as e
            self.msg_queue.put((auth_error, fOAuth {e}))
        except Exception as e
            self.msg_queue.put((auth_error, f{type(e).__name__} {e}))

    def on_auth_token(self, token)
        self.token = token
        self.save_settings()
        self.log_msg(self.t(msg_token_saved))
        self.auth_screen.set_success()

    # ---------- СКАЧИВАНИЕ ----------
    def start_download(self)
        self.stop_event.clear()
        self.rate_limit_hint_shown = False
        self.main_screen.set_downloading(True)
        self.worker_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.worker_thread.start()

    def on_finished(self, ok, failed)
        self.main_screen.set_downloading(False)
        self.set_status(self.t(status_done, ok=ok, fail=failed))
        if failed  0
            self.log_msg(self.t(msg_restart_hint))
        if ok  0
            self.show_donate_popup()

    def show_donate_popup(self)
        content = BoxLayout(orientation=vertical, padding=dp(16), spacing=dp(12))
        content.add_widget(make_label(self.t(donate_title), color=TEXT, size=16,
                                      height=32, halign=center))
        content.add_widget(make_label(self.t(donate_text), color=TEXT_DIM,
                                      size=12, height=60, halign=center))

        row = BoxLayout(orientation=horizontal, spacing=dp(8), size_hint_y=None, height=dp(48))
        row.add_widget(make_button(self.t(donate_btn), lambda a self._open_kofi(),
                                   color=SUCCESS, height=48))
        row.add_widget(make_button(self.t(donate_close), lambda a popup.dismiss(),
                                   color=TEXT_DIM, height=48))
        content.add_widget(row)

        popup = Popup(title=, content=content, size_hint=(0.9, 0.4),
                      background_color=BG2, separator_color=ACCENT)
        popup.open()

    def _open_kofi(self)
        try
            webbrowser.open(KOFI_URL)
        except Exception
            pass

    def _fetch_metadata(self, items, total, extractor)
        results = [None]  len(items)
        done = [0]
        lock = threading.Lock()

        def worker(i, item)
            if self.stop_event.is_set()
                return
            try
                results[i] = extractor(item)
            except Exception as e
                self.log_msg(self.t(msg_track_fail, i=i + 1, e=e))
            with lock
                done[0] += 1
                if done[0] % 5 == 0 or done[0] == total
                    self.set_status(self.t(status_meta, i=done[0], n=total))

        threads = []
        for i, item in enumerate(items)
            if len(threads) = MAX_METADATA_WORKERS
                threads[0].join()
                threads.pop(0)
            t = threading.Thread(target=worker, args=(i, item), daemon=True)
            t.start()
            threads.append(t)
        for t in threads
            t.join()
        return [r for r in results if r]

    def _download_worker(self)
        try
            self.log_msg(self.t(msg_auth_start))
            client = Client(self.token).init()
            self.log_msg(self.t(msg_auth_ok))

            if self.mode == likes
                self.log_msg(self.t(msg_loading_likes))
                liked = client.users_likes_tracks()
                if not liked
                    self.log_msg(self.t(msg_no_tracks))
                    self.msg_queue.put((done, (0, 0)))
                    return
                total_liked = len(liked)
                self.set_progress(0, total_liked)
                tracks = self._fetch_metadata(
                    list(liked), total_liked,
                    lambda lt lt.fetch_track() if lt else None
                )
                title = Liked

            elif self.mode == playlist
                self.log_msg(self.t(msg_loading_playlist, url=self.url))
                clean_url = self.url.split()[0].split(#)[0]
                user_id, kind = parse_playlist_url(clean_url)
                pls = client.users_playlists(kind, user_id)
                if not pls
                    self.log_msg(self.t(msg_playlist_fail))
                    self.msg_queue.put((done, (0, 0)))
                    return
                pl = pls[0] if isinstance(pls, list) else pls
                title = getattr(pl, title, None) or fplaylist_{kind}
                fetched = pl.fetch_tracks()
                raw = fetched if isinstance(fetched, list) else getattr(fetched, tracks, [])
                total_pl = len(raw)
                self.set_progress(0, total_pl)
                self.log_msg(self.t(msg_playlist, title=title, n=total_pl))
                tracks = self._fetch_metadata(
                    raw, total_pl,
                    lambda it it.fetch_track() if hasattr(it, fetch_track) else it
                )

            elif self.mode == album
                self.log_msg(self.t(msg_loading_album, url=self.url))
                clean_url = self.url.split()[0].split(#)[0]
                album_id = parse_album_url(clean_url)
                album = client.albums_with_tracks(album_id)
                title = album.title or falbum_{album_id}
                tracks = [t for vol in album.volumes for t in vol]
                self.set_progress(0, len(tracks))

            elif self.mode == track
                self.log_msg(self.t(msg_loading_track, url=self.url))
                clean_url = self.url.split()[0].split(#)[0]
                track_id = parse_track_url(clean_url)
                tr = client.tracks([track_id])
                if not tr
                    self.log_msg(self.t(msg_track_not_found))
                    self.msg_queue.put((done, (0, 0)))
                    return
                track = tr[0]
                artist = track.artists[0].name if track.artists else Unknown
                title = f{artist} - {track.title}
                tracks = [track]
                self.set_progress(0, 1)
            else
                self.msg_queue.put((done, (0, 0)))
                return

            if not tracks
                self.log_msg(self.t(msg_no_tracks_found))
                self.msg_queue.put((done, (0, 0)))
                return

            folder = os.path.join(self.path, sanitize(title))
            os.makedirs(folder, exist_ok=True)
            self.log_msg(self.t(msg_folder, path=folder))
            self.log_msg(self.t(msg_tracks_count, n=len(tracks)))

            ok = 0
            failed = 0
            skipped = 0
            total = len(tracks)

            for i, track in enumerate(tracks, 1)
                if self.stop_event.is_set()
                    self.log_msg(self.t(msg_stopped_at, i=i - 1, n=total))
                    break
                self.set_progress(i - 1, total)

                artist = track.artists[0].name if track.artists else Unknown Artist
                ext = flac if self.quality == flac else mp3
                filename = f{sanitize(artist)} - {sanitize(track.title)}.{ext}
                filepath = os.path.join(folder, filename)

                if is_valid_file(filepath)
                    self.log_msg(f[{i}{total}] {self.t('msg_skip')} {filename})
                    skipped += 1
                    self.set_progress(i, total)
                    continue

                self.set_status(self.t(status_downloading, i=i, n=total))
                self.log_msg(f[{i}{total}] {filename})

                success = False
                for attempt in range(1, self.retries + 1)
                    if self.stop_event.is_set()
                        break
                    try
                        self._download_track(track, filepath, self.quality)
                        success = True
                        break
                    except Exception as e
                        if is_429(e)
                            if not self.rate_limit_hint_shown
                                self.log_msg(self.t(msg_rate_limit_hint))
                                self.rate_limit_hint_shown = True
                            wait = calc_backoff(attempt, DEFAULT_RETRY_BASE)
                            if attempt  self.retries
                                self.log_msg(     + self.t(msg_retry_429,
                                                            wait=wait,
                                                            attempt=attempt,
                                                            max=self.retries))
                            else
                                self.log_msg(self.t(msg_last_attempt))
                            for _ in range(wait)
                                if self.stop_event.is_set()
                                    break
                                time.sleep(1)
                        else
                            self.log_msg(f    [ERR] {type(e).__name__} {e})
                            break

                if success
                    ok += 1
                else
                    failed += 1

                self.set_progress(i, total)

                if i  total and not self.stop_event.is_set()
                    for _ in range(int(self.delay))
                        if self.stop_event.is_set()
                            break
                        time.sleep(1)

            self.log_msg(self.t(msg_summary, ok=ok, skip=skipped, fail=failed))
            self.msg_queue.put((done, (ok + skipped, failed)))

        except UnauthorizedError
            self.log_msg(self.t(msg_bad_token))
            self.msg_queue.put((done, (0, 0)))
        except ValueError as e
            self.log_msg(f[ERR] {e})
            self.msg_queue.put((done, (0, 0)))
        except Exception as e
            self.log_msg(self.t(msg_critical, e=f{type(e).__name__} {e!r}))
            for line in traceback.format_exc().splitlines()
                self.log_msg(    + line)
            self.msg_queue.put((done, (0, 0)))

    def _download_track(self, track, filepath, quality)
        if quality == flac
            try
                track.download(filepath, codec=flac)
                return
            except Exception
                pass
        if quality == mp3_320
            try
                track.download(filepath, codec=mp3, bitrate_in_kbps=320)
                return
            except Exception
                pass
        if quality == mp3_192
            try
                track.download(filepath, codec=mp3, bitrate_in_kbps=192)
                return
            except Exception
                pass
        track.download(filepath)


if __name__ == __main__
    YMDApp().run()