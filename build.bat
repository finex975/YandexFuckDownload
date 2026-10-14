@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ═══════════════════════════════════════════════════════════
echo   Yandex Music Downloader — локальная сборка EXE
echo ═══════════════════════════════════════════════════════════
echo.

REM ── 1. Проверка Python ──
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python не найден в PATH.
    echo     Установи Python 3.9+ с https://python.org
    echo     Обязательно отметь "Add Python to PATH" при установке!
    pause
    exit /b 1
)

echo [*] Python:
python --version
echo.

REM ── 2. Виртуальное окружение ──
if not exist ".venv" (
    echo [*] Создаю виртуальное окружение .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [!] Не удалось создать .venv
        pause
        exit /b 1
    )
) else (
    echo [*] Виртуальное окружение .venv уже существует.
)

call .venv\Scripts\activate.bat

REM ── 3. Зависимости ──
echo.
echo [*] Обновляю pip ...
python -m pip install --upgrade pip

echo.
echo [*] Устанавливаю зависимости из requirements.txt ...
pip install -r requirements.txt
if errorlevel 1 (
    echo [!] Ошибка установки зависимостей
    pause
    exit /b 1
)

echo.
echo [*] Проверяю PyInstaller ...
pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [*] Устанавливаю PyInstaller ...
    pip install pyinstaller
)

REM ── 4. Проверка файлов ──
echo.
echo [*] Проверка структуры проекта ...

if not exist "main.py" (
    echo [!] Не найден main.py
    pause
    exit /b 1
)
if not exist "yandex_music_downloader.spec" (
    echo [!] Не найден yandex_music_downloader.spec
    pause
    exit /b 1
)
if not exist "web\index.html" (
    echo [!] Не найден web\index.html
    echo     Перемести index.html, style.css, app.js в папку web\
    pause
    exit /b 1
)
if not exist "web\style.css" (
    echo [!] Не найден web\style.css
    pause
    exit /b 1
)
if not exist "web\app.js" (
    echo [!] Не найден web\app.js
    pause
    exit /b 1
)
if not exist "icon.ico" (
    echo [i] icon.ico не найден — сборка будет с дефолтной иконкой
)

echo [OK] Все файлы на месте.
echo.

REM ── 5. Чистка ──
echo [*] Чищу старые сборки ...
if exist "build" rmdir /s /q build
if exist "dist"  rmdir /s /q dist

REM ── 6. Сборка ──
echo.
echo [*] Собираю exe (это займёт 1-3 минуты) ...
echo.
pyinstaller --clean --noconfirm yandex_music_downloader.spec

if errorlevel 1 (
    echo.
    echo [!] СБОРКА НЕ УДАЛАСЬ. Смотри лог выше.
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════
echo   ГОТОВО!
echo ═══════════════════════════════════════════════════════════
echo.
echo Артефакт: dist\YandexMusicDownloader\
echo Запуск:   dist\YandexMusicDownloader\YandexMusicDownloader.exe
echo.

REM ── 7. Открыть папку с результатом ──
if exist "dist\YandexMusicDownloader" (
    echo [*] Открываю папку с результатом ...
    explorer "dist\YandexMusicDownloader"
)

echo.
echo [i] Можно запускать exe прямо сейчас.
echo [i] Рядом с exe будут создаваться: settings.json, history.json, stats.db, logs\, token.dat
echo.
pause
endlocal