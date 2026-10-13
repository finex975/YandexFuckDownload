<div align="center">

<img src="screenshots/icon.png" width="120" alt="Yandex Fuck Downloader"/>

# Yandex Fuck Downloader

**Скачивай свои любимые треки из Яндекс.Музыки на локальный ПК**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.2.1-8b5cf6?style=for-the-badge&logo=github&logoColor=white)](https://github.com/finex975/YandexFuckDownload/releases)

[![Download](https://img.shields.io/badge/⬇_Download_for_Windows-FF5E5B?style=for-the-badge)](https://github.com/finex975/YandexFuckDownload/releases)
[![Ko-fi](https://img.shields.io/badge/☕_Support_on_Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/finex_studio)

</div>

---

## ✨ Возможности

<table>
<tr>
<td width="50%" valign="top">

### 🎵 Скачивание

- **🎧 Мне нравится** — вся коллекция лайков одной кнопкой
- **📀 Плейлисты** — по ссылке на публичный плейлист
- **💿 Альбомы** — целиком, со всеми треками
- **🎼 Один трек** — по ссылке вида `/track/12345`

### 🎚 Качество звука

- **Auto** — оптимальное доступное
- **MP3 320 kbps** — высокое
- **MP3 192 kbps** — стандартное
- **FLAC** — lossless

</td>
<td width="50%" valign="top">

### 🔐 Авторизация

- **OAuth Device Flow** — вход через браузер
- Без ручного копирования токенов
- Токен сохраняется автоматически

### 🎨 Интерфейс

- Тёмная тема с неоновыми акцентами
- **14 языков** — от русского до корейского
- Плавные анимации, кастомный прогресс-бар

### ⚙️ Умное скачивание

- **Авто-retry** при лимитах Яндекса
- **Докачка** — уже скачанное пропускается
- **Автоустановка** зависимостей при первом запуске
- Логирование в `app.log`

</td>
</tr>
</table>

---

## 📸 Скриншоты

<div align="center">

### Главное окно

<img width="880" src="screenshots/main.png" alt="Yandex Music Downloader — главное окно"/>

### Авторизация через OAuth Device Flow

<table>
<tr>
<td width="50%">
<img src="screenshots/auth-code.png" alt="Код авторизации"/>
<p align="center"><sub>1. Код показывается в приложении</sub></p>
</td>
<td width="50%">
<img src="screenshots/auth-yandex.png" alt="Страница Яндекса"/>
<p align="center"><sub>2. Вводится на странице Яндекса</sub></p>
</td>
</tr>
</table>

### 14 языков интерфейса

<img width="280" src="screenshots/languages.png" alt="Выбор языка"/>

### Скачивание в процессе

<img width="880" src="screenshots/downloading.png" alt="Скачивание в процессе"/>

</div>

---

## 🚀 Быстрый старт

### Вариант 1 — Готовый `.exe` (рекомендуется)

1. Скачай последний релиз: [**Releases**](https://github.com/finex975/YandexFuckDownload/releases)
2. Запусти `YandexFuckDownload.exe`
3. Готово

> [!NOTE]
> **Windows SmartScreen** может показать предупреждение — это нормально для приложений без платной цифровой подписи.
> Нажми **«Подробнее»** → **«Выполнить в любом случае»**.

### Вариант 2 — Из исходников

**Требуется:** Python 3.9+ | Windows / Linux / macOS

```bash
git clone https://github.com/finex975/YandexFuckDownload.git
cd YandexFuckDownload
python main.py
```

При первом запуске скрипт **сам установит зависимости** — `yandex-music` и `requests`.

---

## 📖 Как пользоваться

### 1. Авторизация

<table>
<tr><td width="30"><b>1.</b></td><td>Нажми <b>🚀 Войти в Яндекс</b></td></tr>
<tr><td><b>2.</b></td><td>В открывшемся окне скопируй код кнопкой <b>📋 Копировать код</b></td></tr>
<tr><td><b>3.</b></td><td>Браузер откроется сам — вставь код на странице Яндекса</td></tr>
<tr><td><b>4.</b></td><td>Токен подставится автоматически, авторизация завершена</td></tr>
</table>

### 2. Выбор источника

| Режим | Что вводить |
|:------|:------------|
| **🎧 Мне нравится** | Ничего — вся коллекция лайков |
| **📀 Плейлист** | `https://music.yandex.ru/users/USER/playlists/ID` |
| **💿 Альбом** | `https://music.yandex.ru/album/ID` |
| **🎼 Один трек** | `https://music.yandex.ru/track/ID` |

### 3. Папка сохранения

По умолчанию: `C:\Users\Имя\Music\YandexMusic\`

Каждый плейлист — в **отдельной подпапке** со своим названием.

---

## ⚠️ Ограничения

> [!WARNING]
> **Только личное использование.** Распространение скачанных треков нарушает авторские права и правила сервиса Яндекс.Музыки.

- **429 Concurrency limit** — Яндекс ограничивает частоту запросов. Программа сама пережидает лимит (экспоненциальная задержка 8 → 60 секунд с джиттером).
- **Неофициальный API** — при изменениях на стороне Яндекса возможны перебои в работе.

---

## 🛠️ Технологии

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-FF6F00?style=flat-square)
![Requests](https://img.shields.io/badge/Requests-2CA5E0?style=flat-square)
![yandex-music](https://img.shields.io/badge/yandex--music-FF0000?style=flat-square)

</div>

- **Python 3.9+** — язык разработки
- **Tkinter** — нативный GUI без внешних зависимостей
- [**yandex-music**](https://github.com/MarshalX/yandex-music-api) — неофициальная библиотека API Яндекс.Музыки
- **requests** — HTTP-запросы

---

## 🗺️ Планы развития

- [x] Скачивание «Мне нравится», плейлистов, альбомов, треков
- [x] OAuth Device Flow
- [x] 14 языков интерфейса
- [x] Выбор качества MP3 / FLAC
- [x] Автопроверка обновлений
- [ ] Вшивание обложек и метаданных в MP3
- [ ] Прогресс-бар с ETA
- [ ] Цифровая подпись `.exe` (SignPath Foundation)
- [ ] Сборка `.exe` через GitHub Actions

---

## ☕ Поддержать разработчика

<div align="center">

Если программа оказалась полезной — можешь угостить меня кофе.

<a href="https://ko-fi.com/finex_studio">
<img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="40" alt="Buy Me a Coffee at ko-fi.com"/>
</a>

</div>

---

## 📄 Лицензия

Распространяется под лицензией **MIT**. См. [LICENSE](LICENSE) для подробностей.

**Музыка принадлежит её правообладателям.** Программа предоставляет только инструмент для скачивания в личных целях.

---

<div align="center">

**Made with ❤️ by [FinexStudio](https://github.com/finex975)**

<sub>© 2026 FinexStudio. Не связан с Яндекс.Музыкой.</sub>

</div>
