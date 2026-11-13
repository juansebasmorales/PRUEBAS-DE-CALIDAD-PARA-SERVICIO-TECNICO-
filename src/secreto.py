"""
Clave de la página cifrada con un PIN del taller.

PRUEBAS corre desde la USB en cada portátil, así que DPAPI (que cifra para un solo Windows) no sirve: la clave va en
config.json cifrada con AES-256-CBC (Windows CNG) + HMAC-SHA256, con llaves sacadas del PIN con PBKDF2-SHA256.
Sin el PIN el texto guardado no sirve; con un PIN equivocado la verificación HMAC falla (no se descifra basura).
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import hashlib
import hmac
import os

ITERACIONES = 600_000
VERSION = b"P1"

_bc = ctypes.WinDLL("bcrypt")
_bc.BCryptOpenAlgorithmProvider.argtypes = [ctypes.POINTER(wt.HANDLE), wt.LPCWSTR, wt.LPCWSTR, wt.ULONG]
_bc.BCryptSetProperty.argtypes = [wt.HANDLE, wt.LPCWSTR, ctypes.c_void_p, wt.ULONG, wt.ULONG]
_bc.BCryptGenerateSymmetricKey.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HANDLE), ctypes.c_void_p, wt.ULONG,
                                           ctypes.c_char_p, wt.ULONG, wt.ULONG]
for _f in ("BCryptEncrypt", "BCryptDecrypt"):
    getattr(_bc, _f).argtypes = [wt.HANDLE, ctypes.c_char_p, wt.ULONG, ctypes.c_void_p, ctypes.c_void_p, wt.ULONG,
                                 ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG), wt.ULONG]
_bc.BCryptDestroyKey.argtypes = [wt.HANDLE]
_bc.BCryptCloseAlgorithmProvider.argtypes = [wt.HANDLE, wt.ULONG]
for _f in ("BCryptOpenAlgorithmProvider", "BCryptSetProperty", "BCryptGenerateSymmetricKey", "BCryptEncrypt",
           "BCryptDecrypt"):
    getattr(_bc, _f).restype = ctypes.c_long


class PinIncorrecto(ValueError):
    pass


def _ok(estado: int) -> None:
    if estado != 0:
        raise OSError(f"Error de cifrado de Windows 0x{estado & 0xFFFFFFFF:08X}")


def _aes_cbc(llave: bytes, iv: bytes, datos: bytes, cifrar: bool) -> bytes:
    alg = wt.HANDLE()
    _ok(_bc.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "AES", None, 0))
    try:
        modo = ctypes.create_unicode_buffer("ChainingModeCBC")
        _ok(_bc.BCryptSetProperty(alg, "ChainingMode", modo, ctypes.sizeof(modo), 0))
        hk = wt.HANDLE()
        _ok(_bc.BCryptGenerateSymmetricKey(alg, ctypes.byref(hk), None, 0, llave, len(llave), 0))
        try:
            fn = _bc.BCryptEncrypt if cifrar else _bc.BCryptDecrypt
            n = wt.ULONG()
            vec = ctypes.create_string_buffer(iv, len(iv))
            _ok(fn(hk, datos, len(datos), None, vec, len(iv), None, 0, ctypes.byref(n), 1))  # 1 = con relleno
            salida = ctypes.create_string_buffer(n.value)
            vec = ctypes.create_string_buffer(iv, len(iv))  # CNG modifica el IV: uno nuevo para la pasada real
            _ok(fn(hk, datos, len(datos), None, vec, len(iv), salida, n.value, ctypes.byref(n), 1))
            return salida.raw[:n.value]
        finally:
            _bc.BCryptDestroyKey(hk)
    finally:
        _bc.BCryptCloseAlgorithmProvider(alg, 0)


def _llaves(pin: str, sal: bytes) -> tuple[bytes, bytes]:
    m = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), sal, ITERACIONES, 64)
    return m[:32], m[32:]


def cifrar(texto: str, pin: str) -> str:
    sal, iv = os.urandom(16), os.urandom(16)
    k_aes, k_mac = _llaves(pin, sal)
    ct = _aes_cbc(k_aes, iv, texto.encode("utf-8"), True)
    cuerpo = VERSION + sal + iv + ct
    return base64.b64encode(cuerpo + hmac.new(k_mac, cuerpo, hashlib.sha256).digest()).decode("ascii")


def descifrar(guardado: str, pin: str) -> str:
    try:
        crudo = base64.b64decode(guardado)
    except ValueError as exc:
        raise PinIncorrecto("La clave guardada está dañada") from exc
    if len(crudo) < 2 + 16 + 16 + 16 + 32 or not crudo.startswith(VERSION):
        raise PinIncorrecto("La clave guardada está dañada")
    cuerpo, etiqueta = crudo[:-32], crudo[-32:]
    sal, iv, ct = cuerpo[2:18], cuerpo[18:34], cuerpo[34:]
    k_aes, k_mac = _llaves(pin, sal)
    if not hmac.compare_digest(hmac.new(k_mac, cuerpo, hashlib.sha256).digest(), etiqueta):
        raise PinIncorrecto("PIN incorrecto")
    return _aes_cbc(k_aes, iv, ct, False).decode("utf-8")
