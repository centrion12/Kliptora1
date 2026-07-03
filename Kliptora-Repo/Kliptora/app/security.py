from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import os
import sys
from ctypes import wintypes

PBKDF2_ROUNDS = 240_000


def create_pin_record(pin: str) -> tuple[str, str]:
    value = pin.strip().encode("utf-8")
    if len(value) < 4:
        raise ValueError("Yönetici parolası en az 4 karakter olmalı.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", value, salt, PBKDF2_ROUNDS)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")


def verify_pin(pin: str, salt_b64: str, digest_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", pin.strip().encode("utf-8"), salt, PBKDF2_ROUNDS)
    return hmac.compare_digest(actual, expected)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect_secret(secret: str) -> str:
    if not secret:
        return ""
    raw = secret.encode("utf-8")
    if sys.platform != "win32":
        return "plain:" + base64.b64encode(raw).decode("ascii")

    in_blob, in_buffer = _blob(raw)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Kliptora",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    _ = in_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return "dpapi:" + base64.b64encode(data).decode("ascii")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def unprotect_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("plain:"):
        return base64.b64decode(value[6:]).decode("utf-8")
    if not value.startswith("dpapi:") or sys.platform != "win32":
        return ""

    encrypted = base64.b64decode(value[6:])
    in_blob, in_buffer = _blob(encrypted)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    _ = in_buffer
    if not ok:
        return ""
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)
