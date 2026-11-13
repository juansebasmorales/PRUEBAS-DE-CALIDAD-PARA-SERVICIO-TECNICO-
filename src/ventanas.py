"""Funciones de Windows (ctypes, sin dependencias): ventanas, monitores, energía, unidades y capturas."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    dwmapi = ctypes.WinDLL("dwmapi")
except OSError:  # pragma: no cover
    dwmapi = None

WM_CLOSE = 0x0010
SW_RESTORE = 9
SW_MAXIMIZE = 3

_EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [_EnumProc, wt.LPARAM]
for _f in ("IsWindowVisible", "IsIconic", "IsWindow", "GetWindowTextLengthW", "SetForegroundWindow",
           "BringWindowToTop"):
    getattr(user32, _f).argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetForegroundWindow.restype = wt.HWND
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]


def activar_dpi() -> None:
    """Coordenadas y capturas en píxeles reales (si no, en pantallas al 125-150 % la foto sale recortada)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _oculta(hwnd) -> bool:
    """Ventanas UWP 'cloaked' (suspendidas): aparecen como visibles pero no se ven."""
    if dwmapi is None:
        return False
    val = ctypes.c_int(0)
    try:
        dwmapi.DwmGetWindowAttribute(wt.HWND(hwnd), 14, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        return False
    return val.value != 0


def ventanas() -> dict[int, str]:
    """Ventanas principales visibles con título (sin las de este programa): {hwnd: título}."""
    propio = os.getpid()
    res: dict[int, str] = {}

    def cb(hwnd, _lp):
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == propio:
            return True
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        if (r.right - r.left) < 80 or (r.bottom - r.top) < 60 or _oculta(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        res[int(hwnd)] = buf.value
        return True

    user32.EnumWindows(_EnumProc(cb), 0)
    return res


kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]

# Ventanas que aparecen solas y no son de la prueba (AIDA trabaja en segundo plano, notificaciones, menú inicio)
IGNORAR = {"aida64.exe", "aida64engineerportable.exe", "shellexperiencehost.exe", "searchhost.exe",
           "startmenuexperiencehost.exe", "textinputhost.exe", "lockapp.exe", "searchapp.exe"}


def exe_de(hwnd: int) -> str:
    """Nombre del .exe dueño de la ventana, en minúsculas ('' si no se puede leer)."""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.EnumChildWindows.argtypes = [wt.HWND, _EnumProc, wt.LPARAM]


def clase(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def es_dialogo(hwnd: int) -> bool:
    return clase(hwnd) == "#32770"


def esperar_nuevas(antes: set[int], timeout: float = 15.0, cancelar=None) -> list[int]:
    """
    Espera a que aparezca(n) ventana(s) nueva(s) respecto a 'antes'. Si solo aparece un cuadro de diálogo
    (aviso de actualización, licencia), sigue esperando la ventana principal. [] si no apareció ninguna.
    """
    def nuevas_ahora():
        return [h for h in ventanas() if h not in antes and exe_de(h) not in IGNORAR]

    fin = time.time() + timeout
    dialogos: list[int] = []
    while time.time() < fin:
        if cancelar is not None and cancelar():
            return []
        nuevas = nuevas_ahora()
        principales = [h for h in nuevas if not es_dialogo(h)]
        if principales:
            time.sleep(0.6)  # que termine de dibujarse (y aparezcan las demás del mismo programa)
            return [h for h in nuevas_ahora() if not es_dialogo(h)] or principales
        dialogos = nuevas or dialogos
        time.sleep(0.25)
    return [h for h in dialogos if existe(h)]


def _hijos(hwnd: int) -> list[int]:
    res: list[int] = []

    def cb(h, _lp):
        res.append(int(h))
        return True
    user32.EnumChildWindows(hwnd, _EnumProc(cb), 0)
    return res


# Botones que se pueden pulsar solos en un aviso, por orden de preferencia. Nunca 'actualizar', 'descargar' ni 'sí'.
CONTINUAR = ("continue", "continuar", "later", "más tarde", "mas tarde", "remind me later", "no", "cancel",
             "cancelar", "close", "cerrar", "ok", "aceptar")
NUNCA = ("update", "actualizar", "download", "descargar", "yes", "sí", "si", "install", "instalar", "buy", "comprar")


def pulsar_continuar(hwnd: int) -> str:
    """Pulsa el botón 'Continuar' (o el más inofensivo) de un cuadro de diálogo. Devuelve el texto pulsado o ''."""
    botones = {}
    for h in _hijos(hwnd):
        if clase(h).lower() != "button":
            continue
        n = user32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, buf, n + 1)
        txt = buf.value.replace("&", "").strip().lower()
        if txt and not any(txt == x or txt.startswith(x + " ") for x in NUNCA):
            botones[txt] = h
    for objetivo in CONTINUAR:
        if objetivo in botones:
            user32.PostMessageW(botones[objetivo], 0x00F5, 0, 0)  # BM_CLICK
            return objetivo
    return ""


def auto_continuar(exes: set[str], segundos: float = 30.0) -> list[str]:
    """Durante 'segundos', pulsa 'Continuar' en los avisos (#32770) que abran esos programas."""
    vistos: set[int] = set()
    pulsados: list[str] = []
    fin = time.time() + segundos
    while time.time() < fin:
        for h in list(ventanas()):
            if h in vistos or not es_dialogo(h) or exe_de(h) not in exes:
                continue
            time.sleep(0.4)  # que termine de crear sus botones
            txt = pulsar_continuar(h)
            if txt:
                vistos.add(h)
                pulsados.append(txt)
        time.sleep(0.4)
    return pulsados


def minimizar(hwnd: int) -> None:
    if hwnd and user32.IsWindow(hwnd):
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE


try:
    _GetLong = user32.GetWindowLongPtrW
    _SetLong = user32.SetWindowLongPtrW
except AttributeError:  # pragma: no cover (Windows de 32 bits)
    _GetLong = user32.GetWindowLongW
    _SetLong = user32.SetWindowLongW
_GetLong.argtypes = [wt.HWND, ctypes.c_int]
_GetLong.restype = ctypes.c_ssize_t
_SetLong.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
_SetLong.restype = ctypes.c_ssize_t


def no_activar(hwnd: int, activo: bool) -> None:
    """Con WS_EX_NOACTIVATE, hacer clic en la barra no le quita el teclado a la herramienta que se está probando."""
    if not hwnd:
        return
    ex = _GetLong(hwnd, -20)  # GWL_EXSTYLE
    ex = (ex | 0x08000000) if activo else (ex & ~0x08000000)
    _SetLong(hwnd, -20, ex)


def area(hwnd: int) -> int:
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return max(0, r.right - r.left) * max(0, r.bottom - r.top)


def al_frente(hwnd: int, maximizar: bool = False) -> None:
    if not hwnd or not user32.IsWindow(hwnd):
        return
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    if maximizar:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
    fg = user32.GetForegroundWindow()
    t_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    t_yo = kernel32.GetCurrentThreadId()
    if t_fg and t_fg != t_yo:
        user32.AttachThreadInput(t_yo, t_fg, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if t_fg and t_fg != t_yo:
        user32.AttachThreadInput(t_yo, t_fg, False)


def cerrar(hwnds) -> None:
    for h in hwnds or []:
        if h and user32.IsWindow(h):
            user32.PostMessageW(h, WM_CLOSE, 0, 0)


def existe(hwnd: int) -> bool:
    return bool(hwnd) and bool(user32.IsWindow(hwnd))


def monitores() -> int:
    return int(user32.GetSystemMetrics(80))  # SM_CMONITORS


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wt.DWORD), ("BatteryFullLifeTime", wt.DWORD)]


def energia() -> dict:
    """{'cargador': bool, 'cargando': bool, 'bateria': bool, 'porcentaje': int|None}"""
    s = _PowerStatus()
    if not kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return {"cargador": False, "cargando": False, "bateria": False, "porcentaje": None}
    sin_bateria = s.BatteryFlag == 128 or s.BatteryFlag == 255
    return {"cargador": s.ACLineStatus == 1,
            "cargando": bool(s.BatteryFlag & 8) and not sin_bateria,
            "bateria": not sin_bateria,
            "porcentaje": None if s.BatteryLifePercent == 255 else int(s.BatteryLifePercent)}


def unidades() -> set[str]:
    """Letras de unidad presentes (para detectar memorias USB que se conectan)."""
    mask = kernel32.GetLogicalDrives()
    return {chr(65 + i) for i in range(26) if mask & (1 << i)}


def tipo_unidad(letra: str) -> int:
    """2 = extraíble, 3 = fija, 4 = red, 5 = CD/DVD."""
    return int(kernel32.GetDriveTypeW(f"{letra}:\\"))


def capturar(ruta: str, todas_las_pantallas: bool = False) -> str | None:
    """Foto de la pantalla en JPG. Devuelve la ruta o None si falló."""
    global ultimo_error
    from PIL import ImageGrab
    for intento in range(3):  # falla si la pantalla está bloqueada o cambiando de modo (HDMI recién conectado)
        try:
            img = ImageGrab.grab(all_screens=todas_las_pantallas).convert("RGB")
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            img.save(ruta, "JPEG", quality=82, optimize=True)
            return ruta
        except Exception as exc:  # noqa: BLE001
            ultimo_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.6 * (intento + 1))
    return None


ultimo_error = ""
