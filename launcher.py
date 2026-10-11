import os
import sys
import subprocess
import shutil

DEPS = ["yandex-music>=3.2.2", "requests>=2.28.0"]


def find_python():
    for name in ["python", "python3", "py"]:
        path = shutil.which(name)
        if path:
            return path
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
            r"C:\Python312", r"C:\Python311",
            r"C:\Python310", r"C:\Python39",
        ]
        for base in candidates:
            if os.path.isdir(base):
                for entry in os.listdir(base):
                    exe = os.path.join(base, entry, "python.exe")
                    if os.path.isfile(exe):
                        return exe
    return None


def script_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    here = script_dir()
    main_py = os.path.join(here, "main.py")

    if not os.path.isfile(main_py):
        print(f"[!] main.py не найден рядом с .exe: {here}")
        input("Enter для выхода...")
        return

    python = find_python()
    if not python:
        print("[!] Python не найден. Установи Python 3.9+ с python.org")
        print("    Обязательно поставь галочку 'Add Python to PATH'!")
        input("Enter для выхода...")
        return

    print(f"[*] Python: {python}\n[*] Установка зависимостей...")
    for pkg in DEPS:
        print(f"    -> {pkg}")
        subprocess.run([python, "-m", "pip", "install", "--upgrade", pkg])

    print("\n[*] Запуск main.py...\n")
    subprocess.run([python, main_py], cwd=here)
    input("Enter для выхода...")


if __name__ == "__main__":
    main()