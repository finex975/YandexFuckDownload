"""Системный трей через pystray."""
import os
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
    HAVE_TRAY = True
except Exception:
    HAVE_TRAY = False


def _make_icon_image(color="#4fc3d9"):
    """Простая иконка-нота, если нет файла."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 40, 26, 58), fill=color)
    d.ellipse((38, 32, 56, 50), fill=color)
    d.rectangle((22, 20, 26, 50), fill=color)
    d.rectangle((52, 12, 56, 42), fill=color)
    d.polygon([(22, 20), (56, 12), (56, 20), (22, 28)], fill=color)
    return img


def _load_icon_image(icon_path: str | None):
    if icon_path and os.path.isfile(icon_path):
        try:
            return Image.open(icon_path).convert("RGBA")
        except Exception:
            pass
    return _make_icon_image()


class TrayIcon:
    """
    Обёртка над pystray. Запускается в отдельном потоке.
    on_show     — вернуть окно
    on_quit     — полный выход
    on_cancel   — отменить текущую загрузку (опционально)
    """

    def __init__(self, app_name: str, icon_path: str | None,
                 on_show, on_quit, on_cancel=None):
        self.app_name = app_name
        self.icon_path = icon_path
        self.on_show = on_show
        self.on_quit = on_quit
        self.on_cancel = on_cancel
        self._icon = None
        self._thread = None

    @property
    def available(self) -> bool:
        return HAVE_TRAY

    def start(self):
        if not HAVE_TRAY or self._icon is not None:
            return False

        img = _load_icon_image(self.icon_path)

        def _show(icon, item):
            try:
                self.on_show()
            except Exception:
                pass

        def _cancel(icon, item):
            try:
                if self.on_cancel:
                    self.on_cancel()
            except Exception:
                pass

        def _quit(icon, item):
            try:
                icon.stop()
            except Exception:
                pass
            try:
                self.on_quit()
            except Exception:
                pass

        menu_items = [
            pystray.MenuItem("Показать окно", _show, default=True),
        ]
        if self.on_cancel:
            menu_items.append(pystray.MenuItem("Отменить загрузку", _cancel))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem("Выход", _quit))

        self._icon = pystray.Icon(
            "ymd",
            img,
            self.app_name,
            pystray.Menu(*menu_items),
        )

        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        try:
            if self._icon:
                self._icon.stop()
        except Exception:
            pass
        self._icon = None