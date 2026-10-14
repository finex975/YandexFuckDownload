"""
Автопроверка при старте приложения.
Проверяет: папки, настройки, токен, историю докачки, БД, логи, ресурсы.
"""
import os
import sys
import json
import shutil
import sqlite3


class StartupChecker:
    def __init__(self, api):
        self.api = api
        self.app_dir = api.app_dir
        self.results = []

    # ─────────── helpers ───────────
    def _add(self, id_, status, text, detail=""):
        self.results.append({
            "id": id_,
            "status": status,   # ok | warn | fail | info
            "text": text,
            "detail": detail or "",
        })

    # ─────────── checks ───────────
    def _check_app_dir(self):
        try:
            test = os.path.join(self.app_dir, ".write_test")
            with open(test, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test)
            self._add("app_dir", "ok", "Папка приложения доступна для записи",
                      self.app_dir)
        except Exception as e:
            self._add("app_dir", "fail", "Нет доступа к папке приложения",
                      f"{self.app_dir} — {e}")

    def _check_settings(self):
        p = self.api.settings_path
        if not os.path.isfile(p):
            self._add("settings", "info",
                      "settings.json не найден — будут дефолтные настройки", p)
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("не словарь")
            self._add("settings", "ok",
                      f"Настройки загружены ({len(data)} ключей)", p)
        except Exception as e:
            self._add("settings", "fail", "settings.json повреждён",
                      f"{p} — {e}")

    def _check_token_present(self):
        tok = ""
        try:
            tok = self.api.get_token() or ""
        except Exception:
            pass
        if not tok:
            self._add("token", "warn",
                      "OAuth-токен не задан — войдите в Яндекс", "")
        else:
            masked = tok[:6] + "…" + tok[-4:] if len(tok) > 12 else "…"
            self._add("token", "ok", f"Токен найден ({masked})", "")

    def _check_history(self):
        h = self.api._history
        summary = h.summary()
        if not summary:
            self._add("history", "info", "Незавершённых загрузок нет", "")
            return
        pending = summary.get("pending", 0)
        total = summary.get("total", 0)
        if pending > 0:
            self._add("history", "warn",
                      f"Найдена незавершённая загрузка: {pending} из {total}",
                      summary.get("folder_title", "") or "")
        else:
            self._add("history", "ok", "История загрузок чистая", "")

    def _check_target_path(self):
        target = self.api._history.target_path()
        if not target:
            self._add("target_path", "info",
                      "Целевая папка ещё не задавалась", "")
            return
        if not os.path.isdir(target):
            try:
                os.makedirs(target, exist_ok=True)
                self._add("target_path", "ok", "Целевая папка создана", target)
            except Exception as e:
                self._add("target_path", "fail",
                          "Не удалось создать целевую папку",
                          f"{target} — {e}")
        else:
            self._add("target_path", "ok", "Целевая папка существует", target)

    def _check_pending_files(self):
        h = self.api._history
        if not h.has_unfinished():
            return
        target = h.target_path()
        folder = h.folder_title()
        if not target or not folder:
            return
        full = os.path.join(target, folder)
        if not os.path.isdir(full):
            self._add("pending_files", "warn",
                      "Папка докачки не найдена на диске", full)
            return
        try:
            files = [f for f in os.listdir(full)
                     if f.lower().endswith((".mp3", ".flac"))]
            self._add("pending_files", "ok",
                      f"В папке докачки найдено файлов: {len(files)}", full)
        except Exception as e:
            self._add("pending_files", "warn",
                      "Не удалось прочитать папку докачки",
                      f"{full} — {e}")

    def _check_stats_db(self):
        p = os.path.join(self.app_dir, "stats.db")
        try:
            conn = sqlite3.connect(p)
            cur = conn.execute("SELECT COUNT(*) FROM downloads")
            cnt = cur.fetchone()[0]
            conn.close()
            self._add("stats_db", "ok",
                      f"База статистики доступна ({cnt} записей)", p)
        except Exception as e:
            self._add("stats_db", "warn",
                      "База статистики повреждена или пуста",
                      f"{p} — {e}")

    def _check_logs_dir(self):
        p = os.path.join(self.app_dir, "logs")
        try:
            os.makedirs(p, exist_ok=True)
            self._add("logs_dir", "ok", "Папка логов доступна", p)
        except Exception as e:
            self._add("logs_dir", "warn",
                      "Не удалось создать папку логов", f"{p} — {e}")

    def _check_web_resources(self):
        base = sys._MEIPASS if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base, "web", "index.html"),
            os.path.join(base, "index.html"),
        ]
        found = next((p for p in candidates if os.path.isfile(p)), None)
        if found:
            self._add("web", "ok", "Ресурсы интерфейса найдены", found)
        else:
            self._add("web", "fail",
                      "Не найдены ресурсы интерфейса (index.html)", base)

    def _check_ffmpeg_hint(self):
        if shutil.which("ffmpeg"):
            self._add("ffmpeg", "ok",
                      "ffmpeg доступен в PATH (необязательно)", "")
        else:
            self._add("ffmpeg", "info", "ffmpeg не найден (не требуется)", "")

    # ─────────── public ───────────
    def run(self):
        self.results = []
        self._check_app_dir()
        self._check_settings()
        self._check_token_present()
        self._check_history()
        self._check_target_path()
        self._check_pending_files()
        self._check_stats_db()
        self._check_logs_dir()
        self._check_web_resources()
        self._check_ffmpeg_hint()
        return self.results