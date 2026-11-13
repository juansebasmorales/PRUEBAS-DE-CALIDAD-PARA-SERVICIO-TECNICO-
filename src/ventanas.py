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


# Botones que se pueden pulsar solos en un aviso, por orden de preferencia. Nunca 'actualizar', 'descargar',
# 'registrar' ni 'sí'.
CONTINUAR = ("continue", "continuar", "later", "más tarde", "mas tarde", "remind me later", "no", "cancel",
             "cancelar", "close", "cerrar", "ok", "aceptar")
NUNCA_EXACTO = ("yes", "sí", "si")
NUNCA_CONTIENE = ("update", "actualiz", "download", "descarg", "install", "registr", "buy", "compra", "order",
                  "purchase", "upgrade")

user32.IsWindowEnabled.argtypes = [wt.HWND]


def _texto(h: int) -> str:
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, buf, n + 1)
    return buf.value


def _botones(hwnd: int) -> dict[str, int]:
    """{texto en minúsculas sin '&': hwnd} de los botones de la ventana (Win32 'Button' y Delphi 'TButton'...)."""
    res = {}
    for h in _hijos(hwnd):
        if "button" not in clase(h).lower():
            continue
        txt = _texto(h).replace("&", "").strip().lower()
        if txt:
            res[txt] = h
    return res


def es_aviso(hwnd: int) -> bool:
    """Cuadro de diálogo, o ventana de evaluación/registro (p. ej. 'Enter Registration Key' + 'Close')."""
    return es_dialogo(hwnd) or any("registr" in t for t in _botones(hwnd))


def pulsar_continuar(hwnd: int) -> str:
    """
    Pulsa 'Continuar' (o el botón más inofensivo) de un aviso. Devuelve el texto pulsado, '' si no hay ninguno
    permitido, o 'espera' si el botón todavía está desactivado (cuenta regresiva).
    """
    permitidos = {t: h for t, h in _botones(hwnd).items()
                  if t not in NUNCA_EXACTO and not any(x in t for x in NUNCA_CONTIENE)}
    for objetivo in CONTINUAR:
        h = permitidos.get(objetivo)
        if h:
            if not user32.IsWindowEnabled(h):
                return "espera"
            user32.PostMessageW(h, 0x00F5, 0, 0)  # BM_CLICK
            return objetivo
    return ""


def auto_continuar(exes: set[str], segundos: float = 30.0) -> list[str]:
    """Durante 'segundos', pulsa 'Continuar' / 'Close' en los avisos que abran esos programas."""
    vistos: set[int] = set()
    pulsados: list[str] = []
    fin = time.time() + segundos
    while time.time() < fin:
        for h in list(ventanas()):
            if h in vistos or exe_de(h) not in exes or not es_aviso(h):
                continue
            time.sleep(0.4)  # que termine de crear sus botones
            txt = pulsar_continuar(h)
            if txt and txt != "espera":
                vistos.add(h)
                pulsados.append(txt)
        time.sleep(0.4)
    return pulsados


def esperar_sin_avisos(exes: set[str], timeout: float = 30.0) -> list[int]:
    """
    Cierra con 'Continuar'/'Close' los avisos de esos programas (esperando su cuenta regresiva) y devuelve sus
    ventanas principales cuando ya no queda ningún aviso.
    """
    fin = time.time() + timeout
    while time.time() < fin:
        propias = [h for h in ventanas() if exe_de(h) in exes]
        avisos = [h for h in propias if es_aviso(h)]
        for h in avisos:
            pulsar_continuar(h)
        principales = [h for h in propias if h not in avisos]
        if principales and not avisos:
            return principales
        time.sleep(0.5)
    return [h for h in ventanas() if exe_de(h) in exes]


def ruta_exe_de(hwnd: int) -> str:
    """Ruta completa del .exe dueño de la ventana ('' si no se puede leer)."""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wt.DWORD(1024)
        return buf.value if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
    finally:
        kernel32.CloseHandle(h)


def pid_de(hwnd: int) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def cerrar_del_todo(hwnds, carpeta_herramientas: str, espera: float = 2.0) -> None:
    """
    Cierra las ventanas (WM_CLOSE) y, si el programa sigue vivo (p. ej. se fue a la bandeja como Hard Disk
    Sentinel), termina su proceso. Solo termina programas de la carpeta de herramientas: nunca Windows ni apps.
    """
    hwnds = [h for h in (hwnds or []) if existe(h)]
    procesos = {}
    base = os.path.normcase(os.path.abspath(carpeta_herramientas))
    for h in hwnds:
        ruta = ruta_exe_de(h)
        if ruta and os.path.normcase(ruta).startswith(base):
            procesos[pid_de(h)] = ruta
    cerrar(hwnds)
    if not procesos:
        return
    time.sleep(espera)
    import subprocess
    for pid in procesos:
        h = kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            continue  # ya terminó
        codigo = wt.DWORD()
        kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
        kernel32.CloseHandle(h)
        if codigo.value != 259:  # STILL_ACTIVE
            continue
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=0x08000000)


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


class _Punto(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
user32.GetCursorPos.argtypes = [ctypes.POINTER(_Punto)]


def rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def rueda(hwnd: int, clics: int) -> None:
    """
    Desplaza la ventana con la rueda del mouse (clics > 0 sube, < 0 baja). Pone el puntero en el centro de la
    ventana mientras tanto y luego lo devuelve a donde estaba.
    """
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    antes = _Punto()
    user32.GetCursorPos(ctypes.byref(antes))
    user32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    time.sleep(0.05)
    paso = 1 if clics > 0 else -1
    for _ in range(abs(clics)):
        user32.mouse_event(0x0800, 0, 0, (120 * paso) & 0xFFFFFFFF, 0)  # MOUSEEVENTF_WHEEL
        time.sleep(0.02)
    time.sleep(0.35)  # que termine de redibujar
    user32.SetCursorPos(antes.x, antes.y)


def captura_imagen(todas_las_pantallas: bool = False):
    """La imagen de la pantalla (PIL) o None."""
    from PIL import ImageGrab
    for intento in range(3):
        try:
            return ImageGrab.grab(all_screens=todas_las_pantallas).convert("RGB")
        except Exception:
            time.sleep(0.6 * (intento + 1))
    return None


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


# ------------------------------------------------------------------ árbol de HWMonitor (SysTreeView32)
_u = ctypes.WinDLL("user32", use_last_error=True)
_u.SendMessageW.argtypes = [wt.HWND, wt.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
_u.SendMessageW.restype = ctypes.c_ssize_t
_k = ctypes.WinDLL("kernel32", use_last_error=True)
_k.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k.OpenProcess.restype = wt.HANDLE
_k.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
_k.VirtualAllocEx.restype = ctypes.c_void_p
_k.VirtualFreeEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
_k.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
_k.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(ctypes.c_size_t)]
_k.IsWow64Process.argtypes = [wt.HANDLE, ctypes.POINTER(wt.BOOL)]
_k.CloseHandle.argtypes = [wt.HANDLE]

TVM_EXPAND, TVM_GETNEXTITEM, TVM_SELECTITEM, TVM_GETITEMW = 0x1102, 0x110A, 0x110B, 0x113E
TVGN_ROOT, TVGN_NEXT, TVGN_CHILD, TVGN_FIRSTVISIBLE = 0, 1, 4, 5
TVE_COLLAPSE, TVE_EXPAND = 1, 2


class _TVITEMW(ctypes.Structure):   # 64 bits
    _fields_ = [("mask", wt.UINT), ("hItem", ctypes.c_void_p), ("state", wt.UINT), ("stateMask", wt.UINT),
                ("pszText", ctypes.c_void_p), ("cchTextMax", ctypes.c_int), ("iImage", ctypes.c_int),
                ("iSelectedImage", ctypes.c_int), ("cChildren", ctypes.c_int), ("lParam", ctypes.c_void_p)]


def arbol_de(hwnd: int) -> int:
    """El SysTreeView32 más grande de la ventana (0 si no tiene)."""
    arboles = [h for h in _hijos(hwnd) if clase(h) == "SysTreeView32"]
    return max(arboles, key=area) if arboles else 0


class _LectorArbol:
    """Lee los textos de un árbol de otro proceso (memoria prestada en ese proceso)."""

    def __init__(self, tree: int):
        self.tree = tree
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(tree, ctypes.byref(pid))
        self.h = _k.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid.value)  # VM_OP|READ|WRITE|QUERY
        if not self.h:
            raise OSError("no se pudo abrir el proceso")
        wow = wt.BOOL()
        _k.IsWow64Process(self.h, ctypes.byref(wow))
        if wow.value or ctypes.sizeof(ctypes.c_void_p) != 8:
            _k.CloseHandle(self.h)
            raise OSError("proceso de 32 bits")
        self.mem = _k.VirtualAllocEx(self.h, None, 4096, 0x3000, 0x04)  # MEM_COMMIT|RESERVE, PAGE_READWRITE
        if not self.mem:
            _k.CloseHandle(self.h)
            raise OSError("sin memoria")

    def texto(self, item: int) -> str:
        it = _TVITEMW(mask=0x0001 | 0x0010, hItem=item, pszText=self.mem + 128, cchTextMax=900)
        n = ctypes.c_size_t()
        _k.WriteProcessMemory(self.h, self.mem, ctypes.byref(it), ctypes.sizeof(it), ctypes.byref(n))
        if not _u.SendMessageW(self.tree, TVM_GETITEMW, 0, self.mem):
            return ""
        buf = ctypes.create_unicode_buffer(900)
        _k.ReadProcessMemory(self.h, self.mem + 128, buf, 1800, ctypes.byref(n))
        return buf.value

    def cerrar(self):
        _k.VirtualFreeEx(self.h, self.mem, 0, 0x8000)
        _k.CloseHandle(self.h)


def _hijos_arbol(tree: int, item: int) -> list[int]:
    res, h = [], _u.SendMessageW(tree, TVM_GETNEXTITEM, TVGN_CHILD, item)
    while h and len(res) < 500:
        res.append(h)
        h = _u.SendMessageW(tree, TVM_GETNEXTITEM, TVGN_NEXT, h)
    return res


import re as _re  # noqa: E402
_CATEGORIA = _re.compile(r"^(temp|volt|power|potenc|clock|frec|util|fan|ventil|speed|veloc|capac|level|nivel|"
                         r"current|corrient|wear|desgast|charge|carga)", _re.I)
_TEMP = _re.compile(r"^temp", _re.I)
_GPU = _re.compile(r"nvidia|geforce|quadro|radeon|graphics|gráficos|\brtx\b|\bgtx\b|\barc\b|\bmx\d{3}\b", _re.I)
_CPU = _re.compile(r"\bcore\b|ryzen|athlon|celeron|pentium|xeon|atom|processor|\bcpu\b|\bapu\b|core\s?ultra|"
                   r"i[3579]-\d|snapdragon", _re.I)


def solo_temperaturas(hwnd: int) -> bool:
    """
    En HWMonitor deja abiertas solo las temperaturas del procesador y de la tarjeta de video y cierra lo demás,
    para que quepan en una foto. False si no se pudo (y el árbol queda como estaba).
    """
    tree = arbol_de(hwnd)
    if not tree:
        return False
    try:
        lector = _LectorArbol(tree)
    except OSError:
        return False
    try:
        # equipos = nodos que tienen categorías (Temperatures, Voltages...) como hijos
        equipos: list[tuple[int, str, list[tuple[int, str]]]] = []
        pila = _hijos_arbol(tree, 0)   # raíces
        vistos = 0
        while pila and vistos < 400:
            item = pila.pop(0)
            vistos += 1
            hijos = _hijos_arbol(tree, item)
            if not hijos:
                continue
            textos = [(h, lector.texto(h)) for h in hijos]
            if any(_CATEGORIA.match(t.strip()) for _h, t in textos):
                equipos.append((item, lector.texto(item), textos))
            else:
                pila.extend(hijos)
        if not equipos:
            return False
        quedan = [e for e in equipos if (_GPU.search(e[1]) or _CPU.search(e[1]))
                  and any(_TEMP.match(t.strip()) for _h, t in e[2])]
        if not quedan:
            return False
        for item, _nombre, categorias in equipos:
            if not any(item == q[0] for q in quedan):
                _u.SendMessageW(tree, TVM_EXPAND, TVE_COLLAPSE, item)
                continue
            _u.SendMessageW(tree, TVM_EXPAND, TVE_EXPAND, item)
            for h, t in categorias:
                _u.SendMessageW(tree, TVM_EXPAND, TVE_EXPAND if _TEMP.match(t.strip()) else TVE_COLLAPSE, h)
        _u.SendMessageW(tree, TVM_SELECTITEM, TVGN_FIRSTVISIBLE, _hijos_arbol(tree, 0)[0])  # arriba del todo
        user32.InvalidateRect(tree, None, True)
        time.sleep(0.4)
        return True
    finally:
        lector.cerrar()
