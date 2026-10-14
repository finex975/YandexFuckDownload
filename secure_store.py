"""
Безопасное хранение токена.
Пробуем системный keychain через keyring, при неудаче — obfuscated fallback.
"""
import os
import sys
import json
import base64
import hashlib


SERVICE_NAME = "FinexStudio.YandexMusicDownloader"
KEY_NAME = "yandex_oauth_token"

# ─────────── Попытка использовать keyring ───────────

def _get_keyring():
    try:
        import keyring
        # Проверяем, что backend доступен
        keyring.get_keyring()
        return keyring
    except Exception:
        return None


# ─────────── Fallback: XOR + base64 ───────────

def _machine_salt() -> bytes:
    """
    Соль, зависящая от машины — чтобы чужой settings.json
    не расшифровывался на другой машине.
    """
    raw = f"{sys.platform}|{os.environ.get('COMPUTERNAME', '')}|{os.environ.get('USERNAME', '')}"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ key[i % len(key)]
    return bytes(out)


def _obfuscate(plain: str) -> str:
    raw = plain.encode("utf-8")
    key = _machine_salt()
    return base64.urlsafe_b64encode(_xor(raw, key)).decode("ascii")


def _deobfuscate(enc: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(enc.encode("ascii"))
        key = _machine_salt()
        return _xor(raw, key).decode("utf-8")
    except Exception:
        return ""


# ─────────── Публичный API ───────────

def save_token(token: str, fallback_path: str | None = None) -> bool:
    """Сохраняет токен. Возвращает True если использован keyring."""
    if not token:
        delete_token(fallback_path)
        return True

    kr = _get_keyring()
    if kr:
        try:
            kr.set_password(SERVICE_NAME, KEY_NAME, token)
            # Убираем старый fallback если был
            if fallback_path and os.path.isfile(fallback_path):
                try:
                    os.remove(fallback_path)
                except Exception:
                    pass
            return True
        except Exception:
            pass

    # Fallback
    if fallback_path:
        try:
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(_obfuscate(token))
        except Exception:
            return False
    return False


def load_token(fallback_path: str | None = None) -> str:
    """Загружает токен из keyring, при неудаче — из fallback-файла."""
    kr = _get_keyring()
    if kr:
        try:
            token = kr.get_password(SERVICE_NAME, KEY_NAME)
            if token:
                return token
        except Exception:
            pass

    if fallback_path and os.path.isfile(fallback_path):
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                return _deobfuscate(f.read().strip())
        except Exception:
            pass

    return ""


def delete_token(fallback_path: str | None = None) -> None:
    kr = _get_keyring()
    if kr:
        try:
            kr.delete_password(SERVICE_NAME, KEY_NAME)
        except Exception:
            pass
    if fallback_path and os.path.isfile(fallback_path):
        try:
            os.remove(fallback_path)
        except Exception:
            pass