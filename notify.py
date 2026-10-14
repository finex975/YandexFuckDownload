"""Уведомления ОС с fallback'ами."""
import sys

def _notify_windows(title: str, message: str) -> bool:
    try:
        from win10toast import ToastNotifier  # type: ignore
        ToastNotifier().show_toast(title, message, duration=6, threaded=True)
        return True
    except Exception:
        pass
    try:
        # Fallback через powershell
        import subprocess
        ps = (
            f'[reflection.assembly]::loadwithpartialname("System.Windows.Forms");'
            f'[reflection.assembly]::loadwithpartialname("System.Drawing");'
            f'$n = New-Object System.Windows.Forms.NotifyIcon;'
            f'$n.Icon = [System.Drawing.SystemIcons]::Information;'
            f'$n.Visible = $true;'
            f'$n.ShowBalloonTip(5000, "{title}", "{message}", "Info");'
        )
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _notify_macos(title: str, message: str) -> bool:
    try:
        import subprocess
        script = f'display notification "{message}" with title "{title}"'
        subprocess.Popen(["osascript", "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _notify_linux(title: str, message: str) -> bool:
    try:
        import subprocess
        subprocess.Popen(["notify-send", title, message],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def notify(title: str, message: str) -> bool:
    """Кроссплатформенное уведомление. Возвращает True при успехе."""
    try:
        if sys.platform == "win32":
            return _notify_windows(title, message)
        if sys.platform == "darwin":
            return _notify_macos(title, message)
        return _notify_linux(title, message)
    except Exception:
        return False