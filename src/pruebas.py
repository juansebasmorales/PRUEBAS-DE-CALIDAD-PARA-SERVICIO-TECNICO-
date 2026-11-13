"""
PRUEBAS - recorrido de diagnóstico del taller.

Detecta solo lo que se puede detectar, guía al técnico en lo demás con una barra flotante
(OK / FALLA / N/A) y toma una foto de la pantalla como evidencia de cada prueba.
Resultado: Informes\\<orden>\\  (checklist HTML con fotos, informe de batería, AIDA64, resultado.json).
"""

from __future__ import annotations

import ctypes
import datetime
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from dataclasses import dataclass, field
from tkinter import messagebox, simpledialog, ttk

import detectar
import reporte
import ventanas as win

VERSION = "22.0"

if "__compiled__" in globals():
    BASE = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERR = os.path.join(BASE, "ProgramData")
INFORMES = os.path.join(BASE, "Informes")
CONFIG = os.path.join(BASE, "config.json")
WIFI_XML = os.path.join(HERR, "WIFI.xml")

CONFIG_DEF = {
    "tecnico": "",
    "carpeta_copia": "",          # p. ej. C:\\Users\\PC\\OneDrive\\FOTOS EVIDENCIA (se copia la orden al terminar)
    "umbral_bateria": 60,         # % de salud mínimo para marcar la batería OK
    "estres": False,
    "herramientas": {
        "teclado": ["keyboardtestutility_All\\keyboardtestutility.exe", "-T:1"],
        "pantalla": ["IsMyLcdOK_All\\IsMyLcdOK.exe", "-8"],
        "microfono": ["GRABACION\\AudioRecorder.exe"],
        "sonido": ["PRUEBA DE SONIDO.mp4"],
        "temperatura": ["HWMonitorPortable\\HWMonitorPortable.exe"],
        "hdtune": ["HDTune_All_Eng\\HD Tune Pro 6.00\\HD Tune Pro.exe"],
        "cdi": ["CrystalDiskInfo_All\\DiskInfo64.exe"],
        "hdsentinel": ["HardDiskSentinel_All_Eng\\HDSentinel.exe"],
        "aida": ["aida64_All\\AIDA64EngineerPortable.exe"],
        "estres_cpu": ["p95\\prime95.exe"],
        "estres_gpu": ["FurMark\\FurMark_GUI.exe"],
        "estres_vram": ["OCCT\\OCCTPortable.exe"],
    },
}

HWMONITOR_EXES = {"hwmonitor_x64.exe", "hwmonitor_x32.exe", "hwmonitorportable.exe", "hwmonitor.exe"}
ESTADOS = ("OK", "FALLA", "N/A")
COLOR = {"OK": "#1e8e3e", "FALLA": "#d93025", "N/A": "#5f6c7b", "": "#b06000"}


def cargar_config() -> dict:
    cfg = json.loads(json.dumps(CONFIG_DEF))
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            usuario = json.load(fh)
        herr = usuario.pop("herramientas", {})
        cfg.update(usuario)
        cfg["herramientas"].update(herr)
    except (OSError, ValueError):
        pass
    guardar_config(cfg)
    return cfg


def guardar_config(cfg: dict) -> None:
    try:
        with open(CONFIG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def es_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# =====================================================================================================
# Definición de las pruebas
# =====================================================================================================
@dataclass
class Paso:
    id: str
    nombre: str
    texto: str = ""                 # instrucción para el técnico
    herramienta: str = ""           # clave de cfg["herramientas"] o URI (ms-settings:..., devmgmt.msc)
    tipo: str = "normal"            # normal | fondo | preparar | revisar
    ref: str = ""                   # para 'revisar': id del paso 'fondo'/'preparar' que dejó la ventana abierta
    auto: object = None             # función -> (estado|None, detalle)
    poll: object = None             # función -> (detectado: bool, texto)
    evidencia: list = field(default_factory=list)   # [(destino, segundos)] para la foto de un resultado automático
    todas: bool = False             # foto de todas las pantallas (HDMI)
    maximizar: bool = False
    en_reporte: bool = True


class Touchpad:
    """Prueba de touchpad propia: se aprueba sola al mover, hacer clic izquierdo, derecho y desplazar."""

    def __init__(self, root: tk.Tk):
        self.f = {"mover": False, "izq": False, "der": False, "scroll": False}
        self.dist = 0.0
        self.ultimo = None
        t = self.top = tk.Toplevel(root)
        t.title("Prueba de touchpad")
        t.configure(bg="white")
        t.state("zoomed")
        self.c = tk.Canvas(t, bg="white", highlightthickness=0, cursor="crosshair")
        self.c.pack(fill="both", expand=True)
        self.c.create_text(30, 30, anchor="nw", font=("Segoe UI", 20, "bold"), fill="#222",
                           text="PRUEBA DE TOUCHPAD: dibuja, clic izquierdo, clic derecho y desplaza con dos dedos")
        self.estado_txt = self.c.create_text(30, 80, anchor="nw", font=("Segoe UI", 16), fill="#555", text="")
        self.c.bind("<Motion>", self._mover)
        self.c.bind("<Button-1>", lambda e: self._clic(e, "izq", "#0b5ed7"))
        self.c.bind("<Button-3>", lambda e: self._clic(e, "der", "#d93025"))
        for w in (t, self.c):
            w.bind("<MouseWheel>", self._scroll)
            w.bind("<Shift-MouseWheel>", self._scroll)
        self._pintar()
        t.focus_force()

    def _mover(self, e):
        if self.ultimo:
            x, y = self.ultimo
            self.c.create_line(x, y, e.x, e.y, fill="#1e8e3e", width=3)
            self.dist += abs(e.x - x) + abs(e.y - y)
            if self.dist > 1500 and not self.f["mover"]:
                self.f["mover"] = True
                self._pintar()
        self.ultimo = (e.x, e.y)

    def _clic(self, e, k, color):
        self.c.create_oval(e.x - 14, e.y - 14, e.x + 14, e.y + 14, outline=color, width=4)
        self.f[k] = True
        self._pintar()

    def _scroll(self, _e):
        self.f["scroll"] = True
        self._pintar()

    def _pintar(self):
        nombres = {"mover": "Mover", "izq": "Clic izquierdo", "der": "Clic derecho", "scroll": "Desplazamiento"}
        self.c.itemconfigure(self.estado_txt, text="     ".join(
            f"{'✔' if self.f[k] else '✖'} {n}" for k, n in nombres.items()))

    def texto(self) -> str:
        faltan = [n for k, n in (("mover", "mover"), ("izq", "clic izq."), ("der", "clic der."),
                                 ("scroll", "desplazar")) if not self.f[k]]
        return "Todo detectado" if not faltan else "Falta: " + ", ".join(faltan)

    def completo(self) -> bool:
        return all(self.f.values())

    def cerrar(self):
        try:
            self.top.destroy()
        except tk.TclError:
            pass


class WifiDialogo:
    """Elegir una red cercana (o escribirla), su contraseña, y dejarla como red por defecto del taller."""

    def __init__(self, app: "App"):
        self.app = app
        t = self.top = tk.Toplevel(app.root)
        t.title("Configurar nueva red Wi-Fi")
        t.configure(bg="white", padx=18, pady=14)
        t.transient(app.root)
        t.resizable(False, False)
        f = ("Segoe UI", 11)
        tk.Label(t, text="Red (SSID)", font=("Segoe UI", 10, "bold"), bg="white").grid(row=0, column=0, sticky="w")
        self.var_ssid = tk.StringVar(value=detectar.red_guardada(WIFI_XML))
        self.cmb = ttk.Combobox(t, textvariable=self.var_ssid, font=f, width=34)
        self.cmb.grid(row=1, column=0, sticky="we")
        self.cmb.bind("<<ComboboxSelected>>", self._elegida)
        tk.Button(t, text="Buscar redes", font=("Segoe UI", 9), relief="flat", bg="#e3e6ea",
                  command=self._buscar).grid(row=1, column=1, padx=(8, 0))
        tk.Label(t, text="Seguridad", font=("Segoe UI", 10, "bold"), bg="white").grid(row=2, column=0, sticky="w",
                                                                                      pady=(10, 0))
        self.var_seg = tk.StringVar(value="WPA2-Personal")
        ttk.Combobox(t, textvariable=self.var_seg, values=list(detectar.SEGURIDAD), state="readonly", font=f,
                     width=20).grid(row=3, column=0, sticky="w")
        tk.Label(t, text="Contraseña", font=("Segoe UI", 10, "bold"), bg="white").grid(row=4, column=0, sticky="w",
                                                                                       pady=(10, 0))
        self.ent_clave = tk.Entry(t, font=f, width=36, show="•")
        self.ent_clave.grid(row=5, column=0, sticky="we")
        self.var_ver = tk.BooleanVar(value=False)
        tk.Checkbutton(t, text="Mostrar", variable=self.var_ver, bg="white",
                       command=lambda: self.ent_clave.configure(show="" if self.var_ver.get() else "•")).grid(
            row=5, column=1, padx=(8, 0))
        self.lbl = tk.Label(t, text="", font=("Segoe UI", 9), bg="white", fg="#555")
        self.lbl.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        botones = tk.Frame(t, bg="white")
        botones.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))
        tk.Button(botones, text="Cancelar", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=t.destroy).pack(side="right")
        tk.Button(botones, text="Guardar y conectar", font=("Segoe UI", 10, "bold"), relief="flat", bg="#0b5ed7",
                  fg="white", padx=12, command=self._guardar).pack(side="right", padx=8)
        self.ent_clave.bind("<Return>", lambda e: self._guardar())
        self.redes: dict[str, dict] = {}
        self._buscar()
        self.cmb.focus_set()

    def _buscar(self):
        self.lbl.configure(text="Buscando redes cercanas...")

        def hilo():
            redes = detectar.redes_cercanas()
            self.app.ui_async(self._mostrar_redes, redes)
        threading.Thread(target=hilo, daemon=True).start()

    def _mostrar_redes(self, redes):
        if not self.top.winfo_exists():
            return
        self.redes = {r["ssid"]: r for r in redes}
        self.cmb.configure(values=[r["ssid"] for r in redes])
        self.lbl.configure(text=f"{len(redes)} red(es) encontrada(s). Elige una o escribe el nombre."
                           if redes else "No se encontraron redes (¿Wi-Fi apagado?). Puedes escribir el nombre.")
        if self.var_ssid.get() in self.redes:
            self._elegida()

    def _elegida(self, _e=None):
        r = self.redes.get(self.var_ssid.get())
        if r:
            self.var_seg.set(detectar.seguridad_de(r["seguridad"]))
            self.lbl.configure(text=f"{r['seguridad'] or 'Seguridad desconocida'} · señal {r['senal']} %")
        self.ent_clave.focus_set()

    def _guardar(self):
        ssid, clave, seg = self.var_ssid.get().strip(), self.ent_clave.get(), self.var_seg.get()
        if not ssid:
            self.lbl.configure(text="Escribe o elige el nombre de la red.", fg="#d93025")
            return
        if seg != "Abierta" and len(clave) < 8:
            self.lbl.configure(text="La contraseña Wi-Fi tiene al menos 8 caracteres.", fg="#d93025")
            return
        detectar.crear_perfil_wifi(WIFI_XML, ssid, clave, seg)
        self.top.destroy()
        self.app._reconectar_wifi()


# =====================================================================================================
# Barra flotante
# =====================================================================================================
class Barra:
    FONDO = "#1f2430"

    def __init__(self, app: "App"):
        self.app = app
        t = self.top = tk.Toplevel(app.root)
        t.withdraw()
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.configure(bg=self.FONDO, highlightthickness=3, highlightbackground="#0b5ed7")
        esc = app.escala
        self.ancho = int(820 * esc)
        self.lbl_paso = tk.Label(t, font=("Segoe UI", 13, "bold"), fg="white", bg=self.FONDO, anchor="w")
        self.lbl_info = tk.Label(t, font=("Segoe UI", 10), fg="#c9d1e0", bg=self.FONDO, anchor="w",
                                 justify="left", wraplength=self.ancho - int(30 * esc))
        self.lbl_paso.pack(fill="x", padx=12, pady=(8, 0))
        self.lbl_info.pack(fill="x", padx=12, pady=(2, 6))
        self.marco_btn = tk.Frame(t, bg=self.FONDO)
        self.marco_com = tk.Frame(t, bg=self.FONDO)
        tk.Label(self.marco_com, text="¿Qué falla?", fg="white", bg=self.FONDO,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.ent = tk.Entry(self.marco_com, font=("Segoe UI", 11), width=48)
        self.ent.pack(side="left", fill="x", expand=True)
        self.ent.bind("<Return>", lambda e: self._guardar_com())
        tk.Button(self.marco_com, text="GUARDAR", bg="#0b5ed7", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=12, command=self._guardar_com).pack(side="left", padx=6)
        self.pos = None
        for w in (self.lbl_paso, self.lbl_info, t):
            w.bind("<ButtonPress-1>", self._ini_arrastre)
            w.bind("<B1-Motion>", self._arrastrar)
        self._hwnd = 0

    # --- arrastrar la barra (si tapa algo) ---
    def _ini_arrastre(self, e):
        self._dx, self._dy = e.x_root - self.top.winfo_x(), e.y_root - self.top.winfo_y()

    def _arrastrar(self, e):
        self.pos = (e.x_root - self._dx, e.y_root - self._dy)
        self.top.geometry(f"+{self.pos[0]}+{self.pos[1]}")

    def _boton(self, texto, color, valor):
        tk.Button(self.marco_btn, text=texto, bg=color, fg="white", activebackground=color,
                  activeforeground="white", relief="flat", font=("Segoe UI", 11, "bold"), padx=16, pady=3,
                  cursor="hand2", command=lambda: self.app.decidir(valor)).pack(side="left", padx=(0, 8))

    def mostrar(self, titulo: str, info: str, modo: str):
        for w in self.marco_btn.winfo_children():
            w.destroy()
        self.marco_com.pack_forget()
        self.marco_btn.pack_forget()
        self.top.configure(highlightbackground="#0b5ed7")
        self.lbl_paso.configure(text=titulo, fg="white")
        self.lbl_info.configure(text=info)
        if modo == "decision":
            self._boton("✔  OK", "#1e8e3e", "OK")
            self._boton("✖  FALLA", "#d93025", "FALLA")
            self._boton("N/A", "#5f6c7b", "N/A")
            self._boton("FOTO EXTRA", "#3c4454", "FOTO")
            self._boton("TERMINAR", "#3c4454", "TERMINAR")
        elif modo == "continuar":
            self._boton("CONTINUAR  ▶", "#0b5ed7", "CONTINUAR")
            self._boton("TERMINAR", "#3c4454", "TERMINAR")
        if modo != "auto":
            self.marco_btn.pack(fill="x", padx=12, pady=(0, 10))
        self._colocar()
        self.top.deiconify()
        self.top.lift()
        self.top.update_idletasks()
        if not self._hwnd:
            try:
                self._hwnd = int(self.top.wm_frame(), 16)
            except (tk.TclError, ValueError):
                self._hwnd = 0
        win.no_activar(self._hwnd, True)

    def _colocar(self):
        self.top.update_idletasks()
        alto = self.top.winfo_reqheight()
        if self.pos:
            x, y = self.pos
        else:
            x = (self.top.winfo_screenwidth() - self.ancho) // 2
            y = self.top.winfo_screenheight() - alto - int(60 * self.app.escala)
        self.top.geometry(f"{self.ancho}x{alto}+{x}+{y}")

    def info(self, txt: str):
        self.lbl_info.configure(text=txt)
        self._colocar()

    def marcar(self, estado: str, txt: str = ""):
        color = COLOR.get(estado, "#0b5ed7")
        self.top.configure(highlightbackground=color)
        actual = self.lbl_paso.cget("text").split("   →")[0]
        self.lbl_paso.configure(text=f"{actual}   →  {estado}", fg="white")
        if txt:
            self.lbl_info.configure(text=txt)
        self._colocar()
        self.top.update()

    def pedir_comentario(self):
        self.marco_btn.pack_forget()
        self.ent.delete(0, "end")
        self.marco_com.pack(fill="x", padx=12, pady=(0, 10))
        self._colocar()
        win.no_activar(self._hwnd, False)
        self.top.focus_force()
        self.ent.focus_set()

    def _guardar_com(self):
        self.app.comentario = self.ent.get().strip()
        self.app.ev_comentario.set()

    def ocultar(self):
        self.top.withdraw()


# =====================================================================================================
# Aplicación
# =====================================================================================================
class App:
    def __init__(self):
        win.activar_dpi()
        self.cfg = cargar_config()
        self.root = tk.Tk()
        self.root.title(f"PRUEBAS v{VERSION}")
        self.escala = self.root.winfo_fpixels("1i") / 96.0
        self.root.geometry(f"{int(980 * self.escala)}x{int(680 * self.escala)}")
        self.root.configure(bg="#f4f5f7")
        self.root.protocol("WM_DELETE_WINDOW", self._salir)
        estilo = ttk.Style(self.root)
        estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=int(26 * self.escala), font=("Segoe UI", 10))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.q: queue.Queue = queue.Queue()
        self.hw: dict = {}
        self.lic: dict = {}
        self.cdi: list = []
        self.bat: dict = {}
        self.office: dict = {}
        self.ev_hw, self.ev_lic, self.ev_cdi, self.ev_bat, self.ev_office = (threading.Event() for _ in range(5))
        self.estado_wifi = "Wi-Fi: conectando..." if os.path.isfile(WIFI_XML) else "Wi-Fi: sin WIFI.xml"

        self.orden = ""
        self.carpeta = ""
        self.resultados: dict[str, dict] = {}
        self.pasos: list[Paso] = []
        self.largas: dict[str, list[int]] = {}
        self.decision = None
        self.ev_decision = threading.Event()
        self.comentario = ""
        self.ev_comentario = threading.Event()
        self.cancelar = False
        self.trabajando = False
        self.touch: Touchpad | None = None
        self.usb_base: set[str] = set()
        self.usb_vistas: list[str] = []
        self.monitores_base = 1

        self.barra = Barra(self)
        self.cuerpo = tk.Frame(self.root, bg="#f4f5f7")
        self.cuerpo.pack(fill="both", expand=True, padx=18, pady=14)
        self._pantalla_inicio()
        threading.Thread(target=self._detectar_inicio, daemon=True).start()
        self.root.after(40, self._bombear)

    # ------------------------------------------------------------------ hilos <-> interfaz
    def _bombear(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(40, self._bombear)

    def ui(self, fn, *a):
        """Ejecuta fn en el hilo de la interfaz y espera el resultado (solo desde hilos de trabajo)."""
        ev, caja = threading.Event(), {}

        def correr():
            try:
                caja["r"] = fn(*a)
            except Exception as exc:  # noqa: BLE001
                caja["e"] = exc
            finally:
                ev.set()
        self.q.put(correr)
        ev.wait()
        if "e" in caja:
            raise caja["e"]
        return caja.get("r")

    def ui_async(self, fn, *a):
        self.q.put(lambda: fn(*a))

    def decidir(self, valor: str):
        self.decision = valor
        self.ev_decision.set()

    # ------------------------------------------------------------------ detección al abrir
    def _detectar_inicio(self):
        def wifi():
            if os.path.isfile(WIFI_XML):
                self.estado_wifi = "Wi-Fi: " + detectar.conectar_wifi(WIFI_XML)
                self.ui_async(self._refrescar_resumen)

        def hw():
            self.hw = detectar.hardware()
            self.ev_hw.set()
            self.ui_async(self._refrescar_resumen)

        def lic():
            self.lic = detectar.licencia()
            self.ev_lic.set()
            self.ui_async(self._refrescar_resumen)

        def cdi():
            self.cdi = detectar.crystaldiskinfo(self._ruta("cdi"))
            self.ev_cdi.set()

        def office():
            self.office = detectar.office()
            self.ev_office.set()
            self.ui_async(self._refrescar_resumen)

        for f in (wifi, hw, lic, cdi, office):
            threading.Thread(target=f, daemon=True).start()

    def _ruta(self, clave: str) -> str:
        val = self.cfg["herramientas"].get(clave) or [""]
        r = val[0]
        return r if os.path.isabs(r) or not r else os.path.join(HERR, r)

    def _args(self, clave: str) -> list[str]:
        return list((self.cfg["herramientas"].get(clave) or [""])[1:])

    # ------------------------------------------------------------------ pantalla de inicio
    def _limpiar(self):
        for w in self.cuerpo.winfo_children():
            w.destroy()

    def _pantalla_inicio(self):
        self._limpiar()
        c = self.cuerpo
        tk.Label(c, text="PRUEBAS", font=("Segoe UI", 26, "bold"), bg="#f4f5f7", fg="#0b5ed7").pack(anchor="w")
        tk.Label(c, text=f"Recorrido de diagnóstico con evidencia automática · v{VERSION}",
                 font=("Segoe UI", 11), bg="#f4f5f7", fg="#555").pack(anchor="w")
        if not es_admin():
            tk.Label(c, text="Sin permisos de administrador: algunas lecturas (discos, batería) pueden fallar.",
                     font=("Segoe UI", 10, "bold"), bg="#f4f5f7", fg="#d93025").pack(anchor="w", pady=(6, 0))

        form = tk.Frame(c, bg="white", highlightthickness=1, highlightbackground="#ddd")
        form.pack(fill="x", pady=14)
        tk.Label(form, text="Número de orden", font=("Segoe UI", 11, "bold"), bg="white").grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 4))
        self.ent_orden = tk.Entry(form, font=("Segoe UI", 16), width=18)
        self.ent_orden.grid(row=1, column=0, sticky="w", padx=14)
        tk.Label(form, text="Técnico", font=("Segoe UI", 11, "bold"), bg="white").grid(
            row=0, column=1, sticky="w", padx=14, pady=(14, 4))
        self.ent_tec = tk.Entry(form, font=("Segoe UI", 16), width=16)
        self.ent_tec.insert(0, self.cfg.get("tecnico", ""))
        self.ent_tec.grid(row=1, column=1, sticky="w", padx=14)
        self.var_estres = tk.BooleanVar(value=bool(self.cfg.get("estres")))
        tk.Checkbutton(form, text="Incluir pruebas de estrés (CPU, GPU, VRAM)", variable=self.var_estres,
                       bg="white", font=("Segoe UI", 10)).grid(row=2, column=0, columnspan=2, sticky="w",
                                                              padx=10, pady=8)
        tk.Button(form, text="INICIAR  ▶", font=("Segoe UI", 15, "bold"), bg="#0b5ed7", fg="white",
                  relief="flat", padx=26, pady=6, cursor="hand2", command=self._iniciar).grid(
            row=1, column=2, rowspan=2, padx=18, pady=(0, 14), sticky="e")
        form.grid_columnconfigure(2, weight=1)
        self.ent_orden.bind("<Return>", lambda e: self._iniciar())
        self.ent_orden.focus_set()

        red = tk.Frame(c, bg="white", highlightthickness=1, highlightbackground="#ddd")
        red.pack(fill="x", pady=(0, 12))
        tk.Label(red, text="Red Wi-Fi", font=("Segoe UI", 11, "bold"), bg="white").pack(side="left", padx=(14, 10),
                                                                                       pady=10)
        self.lbl_wifi = tk.Label(red, text="", font=("Segoe UI", 10), bg="white", fg="#333", anchor="w")
        self.lbl_wifi.pack(side="left", fill="x", expand=True)
        tk.Button(red, text="Conectar", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=self._reconectar_wifi).pack(side="right", padx=(0, 14))
        tk.Button(red, text="Configurar nueva red", font=("Segoe UI", 10, "bold"), relief="flat", bg="#0b5ed7",
                  fg="white", padx=12, command=self._config_wifi).pack(side="right", padx=8)

        tk.Label(c, text="Equipo detectado", font=("Segoe UI", 12, "bold"), bg="#f4f5f7").pack(anchor="w")
        self.lbl_resumen = tk.Label(c, text="", font=("Consolas", 10), bg="white", fg="#222", justify="left",
                                    anchor="nw", padx=14, pady=10, highlightthickness=1,
                                    highlightbackground="#ddd")
        self.lbl_resumen.pack(fill="both", expand=True, pady=(4, 10))
        barra = tk.Frame(c, bg="#f4f5f7")
        barra.pack(fill="x")
        for texto, fn in (("Abrir carpeta Informes", self._abrir_informes),
                          ("Editar configuración", lambda: os.startfile(CONFIG))):
            tk.Button(barra, text=texto, font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                      command=fn).pack(side="left", padx=(0, 8))
        self._refrescar_resumen()

    def _refrescar_resumen(self):
        if not hasattr(self, "lbl_resumen") or not self.lbl_resumen.winfo_exists():
            return
        h = self.hw
        if not self.ev_hw.is_set():
            txt = "Detectando hardware..."
        else:
            discos = "\n".join(f"{'':14}{d.get('modelo')} · {d.get('gb')} GB · {d.get('tipo')} · {d.get('bus')}"
                               f" · {d.get('salud')}" for d in h.get("discos", []))
            txt = "\n".join([
                f"{'Equipo':14}{h.get('fabricante', '')} {h.get('modelo', '')}",
                f"{'Serial':14}{h.get('serial', '')}",
                f"{'CPU':14}{h.get('cpu', '')}",
                f"{'RAM':14}{h.get('ram', '')}",
                f"{'GPU':14}{' | '.join(h.get('gpu', []))}",
                f"{'Sistema':14}{h.get('sistema', '')}",
                f"{'Discos':14}" + discos.lstrip(),
                f"{'Errores disp.':14}{len(h.get('dispositivos_error', []))}",
            ])
        lic = self.lic.get("texto", "consultando...") if self.ev_lic.is_set() else "consultando..."
        off = self.office.get("texto", "") if self.ev_office.is_set() else "consultando..."
        txt += f"\n{'Windows':14}{lic}\n{'Office':14}{off}"
        self.lbl_resumen.configure(text=txt)
        if hasattr(self, "lbl_wifi") and self.lbl_wifi.winfo_exists():
            guardada = detectar.red_guardada(WIFI_XML)
            self.lbl_wifi.configure(text=(f"Por defecto: {guardada}   ·   " if guardada else
                                          "Sin red por defecto   ·   ") + self.estado_wifi.replace("Wi-Fi: ", ""))

    def _config_wifi(self):
        WifiDialogo(self)

    def _reconectar_wifi(self):
        if not os.path.isfile(WIFI_XML):
            self._config_wifi()
            return
        self.estado_wifi = "Wi-Fi: conectando..."
        self._refrescar_resumen()

        def hilo():
            self.estado_wifi = "Wi-Fi: " + detectar.conectar_wifi(WIFI_XML)
            time.sleep(4)  # netsh responde antes de terminar de conectar
            ok, txt = detectar.wifi_estado()
            if ok:
                self.estado_wifi = "Wi-Fi: conectado · " + txt
            self.ui_async(self._refrescar_resumen)
        threading.Thread(target=hilo, daemon=True).start()

    def _abrir_informes(self):
        os.makedirs(INFORMES, exist_ok=True)
        os.startfile(INFORMES)

    # ------------------------------------------------------------------ iniciar orden
    def _iniciar(self):
        if self.trabajando:
            return
        orden = re.sub(r"[^A-Za-z0-9_-]", "", self.ent_orden.get().strip().upper())
        if not orden:
            messagebox.showwarning("PRUEBAS", "Escribe el número de orden (ej: E123).", parent=self.root)
            return
        self.cfg["tecnico"] = self.ent_tec.get().strip()
        self.cfg["estres"] = bool(self.var_estres.get())
        guardar_config(self.cfg)
        self.orden = orden
        self.carpeta = os.path.join(INFORMES, orden)
        os.makedirs(os.path.join(self.carpeta, "fotos"), exist_ok=True)
        self.resultados = {}
        estado_previo = os.path.join(self.carpeta, "estado.json")
        if os.path.isfile(estado_previo):
            if messagebox.askyesno("PRUEBAS", f"La orden {orden} ya tiene pruebas guardadas.\n\n"
                                   "¿Continuar donde quedó? (No = empezar de cero)", parent=self.root):
                try:
                    with open(estado_previo, encoding="utf-8") as fh:
                        self.resultados = json.load(fh).get("resultados", {})
                except (OSError, ValueError):
                    self.resultados = {}
        self.pasos = self._armar_pasos()
        self._lanzar_informes()
        self._pantalla_revision(en_curso=True)
        self.root.iconify()
        self._trabajar(self._recorrido)

    def _lanzar_informes(self):
        """Informe de batería y AIDA64 en segundo plano (no necesitan al técnico)."""
        def bateria():
            self.bat = detectar.reporte_bateria(os.path.join(self.carpeta, f"{self.orden}_BATERIA.html"),
                                                os.path.join(self.carpeta, "bateria.xml"))
            self.ev_bat.set()
        self.ev_bat.clear()
        threading.Thread(target=bateria, daemon=True).start()
        aida = self._ruta("aida")
        destino = os.path.join(self.carpeta, f"{self.orden}_AIDA.html")
        if os.path.isfile(aida) and not os.path.isfile(destino):
            try:
                subprocess.Popen([aida, "/R", destino, "/HTML", "/QUICK", "/SILENT", "/EXIT"],
                                 cwd=os.path.dirname(aida))
            except OSError:
                pass

    def _trabajar(self, fn, *a):
        def hilo():
            self.trabajando = True
            self.cancelar = False
            try:
                fn(*a)
            except Exception:  # noqa: BLE001
                err = traceback.format_exc()
                try:
                    with open(os.path.join(INFORMES, "pruebas_error.log"), "a", encoding="utf-8") as fh:
                        fh.write(f"\n[{datetime.datetime.now()}] v{VERSION}\n{err}")
                except OSError:
                    pass
                self.ui_async(messagebox.showerror, "PRUEBAS", "Ocurrió un error (se guardó en "
                              "Informes\\pruebas_error.log):\n\n" + err.splitlines()[-1])
            finally:
                self.trabajando = False
                self.ui_async(self.barra.ocultar)
                self.ui_async(self._fin_trabajo)
        threading.Thread(target=hilo, daemon=True).start()

    # ------------------------------------------------------------------ las pruebas
    def _armar_pasos(self) -> list[Paso]:
        P = Paso
        pasos = [
            P("fondo_temp", "HWMonitor (registra máximos todo el recorrido)", herramienta="temperatura",
              tipo="fondo", en_reporte=False),
            P("prep_hdtune", "HD Tune", tipo="preparar", herramienta="hdtune", en_reporte=False,
              texto="Pulsa START en la pestaña Benchmark y luego CONTINUAR. Sigue corriendo mientras haces "
                    "las demás pruebas."),
            P("teclado", "Teclado", "Presiona todas las teclas. Cuando estén todas marcadas pulsa OK.", "teclado"),
            P("touchpad", "Touchpad", "Dibuja, clic izquierdo, clic derecho y desplaza con dos dedos. "
              "Se aprueba sola.", poll=self._poll_touchpad),
            P("pantalla", "Pantalla", "Revisa píxeles muertos, manchas y fugas de luz en cada color.", "pantalla"),
            P("camara", "Cámara web", "Comprueba que se vea la imagen. La foto queda con la vista de la cámara.",
              "microsoft.windows.camera:", auto=self._auto_camara),
            P("microfono", "Micrófono", "Graba unos segundos y reproduce.", "microfono"),
            P("sonido", "Sonido (parlantes y jack)", "Escucha ambos parlantes y prueba el jack de audífonos.",
              "sonido"),
            P("carga", "Carga de batería", "Conecta el cargador. Se aprueba sola al detectar que carga.",
              auto=self._auto_carga, poll=self._poll_carga),
            P("red", "Puerto de red (cable)", "Conecta el cable de red. Se aprueba sola al detectar enlace.",
              auto=self._auto_red, poll=self._poll_red, evidencia=[("ms-settings:network-ethernet", 1.5)]),
            P("wifi", "Wi-Fi", "Conéctate a una red Wi-Fi. Se aprueba sola al tener internet.",
              auto=self._auto_wifi, poll=self._poll_wifi, evidencia=[("ms-settings:network-wifi", 1.5)]),
            P("bluetooth", "Bluetooth", "Si el equipo no trae Bluetooth, marca N/A.", "ms-settings:bluetooth",
              auto=self._auto_bluetooth, evidencia=[("ms-settings:bluetooth", 1.5)]),
            P("hdmi", "Video HDMI/VGA", "Conecta un monitor por HDMI/VGA. Se aprueba sola al detectarlo.",
              auto=self._auto_hdmi, poll=self._poll_hdmi, todas=True),
            P("usb", "Puertos USB", "Conecta una memoria en cada puerto, uno por uno, y pulsa OK.",
              auto=self._auto_usb, poll=self._poll_usb),
            P("dvd", "Unidad DVD/CD", "Inserta un disco y comprueba que se lea.", auto=self._auto_dvd),
            P("controladores", "Controladores", auto=self._auto_controladores,
              evidencia=[("devmgmt.msc", 1.5)]),
            P("licencia", "Licencia de Windows", auto=self._auto_licencia,
              evidencia=[("ms-settings:activation", 2.0)]),
            P("office", "Licencia de Office", auto=self._auto_office),
            P("discos", "Salud de discos (SMART)", auto=self._auto_discos,
              evidencia=[("cdi", 2.0), ("hdsentinel", 5.0)]),
            P("hdtune", "Rendimiento de disco (HD Tune)", "Revisa la gráfica: sin caídas a cero ni bloques "
              "dañados.", "hdtune", tipo="revisar", ref="prep_hdtune"),
            P("bateria", "Salud de batería", auto=self._auto_bateria),
        ]
        if self.cfg.get("estres"):
            pasos += [
                P("estres_cpu", "Estrés CPU (Prime95)", "Deja correr unos minutos y vigila la temperatura.",
                  "estres_cpu"),
                P("estres_gpu", "Estrés GPU núcleo (FurMark)", "Deja correr unos minutos sin artefactos.",
                  "estres_gpu"),
                P("estres_vram", "Estrés GPU memoria (OCCT)", "Prueba de VRAM sin errores.", "estres_vram"),
            ]
        pasos.append(P("temperatura", "Temperatura CPU/GPU", "Revisa la columna Max de HWMonitor "
                       "(registró todo el recorrido).", "temperatura", tipo="revisar", ref="fondo_temp",
                       maximizar=True))
        return pasos

    def _recorrido(self, solo: Paso | None = None):
        pasos = [solo] if solo else self.pasos
        for paso in pasos:
            if self.cancelar:
                break
            if not solo and paso.en_reporte and self.resultados.get(paso.id, {}).get("estado"):
                continue  # ya hecho (continuar orden)
            self.ui_async(self._marcar_actual, paso.id)
            self._ejecutar(paso)
        for hwnds in self.largas.values():
            win.cerrar(hwnds)
        self.largas = {}
        self._guardar_estado()
        self.ui(self._generar_reporte, False)

    def _titulo(self, paso: Paso) -> str:
        visibles = [p for p in self.pasos if p.en_reporte]
        n = visibles.index(paso) + 1 if paso in visibles else 0
        return f"{n}/{len(visibles)} · {paso.nombre.upper()}" if n else paso.nombre.upper()

    def _ejecutar(self, paso: Paso):
        if paso.tipo == "fondo":
            hw = self._abrir(paso.herramienta)
            self.largas[paso.id] = hw or []
            for h in hw or []:
                win.minimizar(h)
            return
        if paso.tipo == "preparar":
            hw = self._abrir(paso.herramienta)
            if hw is None:
                return  # herramienta no instalada
            self.largas[paso.id] = hw
            self._barra(paso, paso.texto, "continuar", foco=hw)
            return

        detalle, info = "", paso.texto
        if paso.auto:
            estado, detalle = paso.auto()
            if estado:
                self.ui(self.barra.mostrar, self._titulo(paso), detalle, "auto")
                self.ui(self.barra.marcar, estado, "Automático: " + detalle)
                fotos = self._evidencia(paso) if estado != "N/A" else []
                self._guardar(paso, estado, detalle, "", fotos)
                return
            if detalle:
                info = detalle + ("\n" + paso.texto if paso.texto else "")

        if paso.tipo == "revisar":
            # la herramienta quedó abierta desde el inicio (HWMonitor, HD Tune): se trae al frente
            hw = [h for h in self.largas.pop(paso.ref, []) if win.existe(h)] or self._abrir(paso.herramienta) or []
        elif paso.id == "touchpad":
            self.touch = self.ui(Touchpad, self.root)
            hw = []
        elif paso.herramienta:
            hw = self._abrir(paso.herramienta)
            if hw is None:
                info = f"No se encontró la herramienta ({paso.herramienta}).\n" + info
                hw = []
        else:
            hw = []
        if hw:
            win.al_frente(max(hw, key=win.area), maximizar=paso.maximizar)

        estado, comentario, fotos, ultimo = self._barra(paso, info, "decision", foco=hw, poll=paso.poll)
        if paso.id == "touchpad" and self.touch:
            self.ui(self.touch.cerrar)
            self.touch = None
        win.cerrar(hw)
        if estado == "TERMINAR":
            self.cancelar = True
            return
        if paso.poll and ultimo:
            detalle = ultimo
        self._guardar(paso, estado, detalle, comentario, fotos)

    def _barra(self, paso: Paso, info: str, modo: str, foco=None, poll=None):
        """Muestra la barra y espera al técnico (o a que 'poll' detecte la prueba). Toma las fotos."""
        self.ev_decision.clear()
        self.decision = None
        self.ui(self.barra.mostrar, self._titulo(paso), info, modo)
        if foco:
            time.sleep(0.2)
            win.al_frente(max(foco, key=win.area))
        fotos: list[str] = []
        ultimo, t_poll, d = "", 0.0, None
        while True:
            if self.ev_decision.wait(0.3):
                d = self.decision
                self.ev_decision.clear()
                if d == "FOTO":
                    f = self._foto(paso)
                    if f:
                        fotos.append(f)
                    continue
                break
            if poll and time.time() - t_poll > 1.2:
                t_poll = time.time()
                ok, txt = poll()
                if txt != ultimo:
                    ultimo = txt
                    self.ui_async(self.barra.info, txt + ("\n" + paso.texto if paso.texto else ""))
                if ok:
                    d = "OK"
                    break
        if modo == "continuar" or d == "TERMINAR":
            return d, "", fotos, ultimo
        comentario = ""
        if d in ("OK", "FALLA"):
            self.ui(self.barra.marcar, d, ultimo if d == "OK" and ultimo else "")
            time.sleep(0.35)
            f = self._foto(paso)
            if f:
                fotos.append(f)
        if d == "FALLA":
            self.ev_comentario.clear()
            self.ui(self.barra.pedir_comentario)
            self.ev_comentario.wait()
            comentario = self.comentario
        return d, comentario, fotos, ultimo

    def _evidencia(self, paso: Paso) -> list[str]:
        """Abre la ventana que demuestra un resultado automático, le toma la foto y la cierra."""
        fotos = []
        for destino, espera in paso.evidencia:
            antes = set(win.ventanas())
            if not self._lanzar(destino):
                continue
            nuevas = win.esperar_nuevas(antes, timeout=12)
            if nuevas:
                win.al_frente(max(nuevas, key=win.area))
            time.sleep(espera if nuevas else 2.0)
            f = self._foto(paso)
            if f:
                fotos.append(f)
            win.cerrar(nuevas)
            time.sleep(0.3)
        if not fotos:
            time.sleep(0.4)
            f = self._foto(paso)
            if f:
                fotos.append(f)
        return fotos

    def _foto(self, paso: Paso) -> str | None:
        visibles = [p for p in self.pasos if p.en_reporte]
        n = visibles.index(paso) + 1 if paso in visibles else 0
        k = len([f for f in os.listdir(os.path.join(self.carpeta, "fotos")) if f.startswith(f"{n:02d}_{paso.id}_")])
        rel = f"fotos/{n:02d}_{paso.id}_{k + 1}.jpg"
        if win.capturar(os.path.join(self.carpeta, rel), paso.todas):
            return rel
        self.ui_async(self.barra.info, "⚠ No se pudo tomar la foto (¿pantalla bloqueada?). Usa FOTO EXTRA.")
        return None

    def _lanzar(self, destino: str) -> bool:
        if destino.startswith(("ms-settings:", "microsoft.windows.camera:")) or destino.endswith(".msc"):
            try:
                os.startfile(destino)
                return True
            except OSError:
                return False
        ruta, args = self._ruta(destino), self._args(destino)
        if not ruta or not os.path.exists(ruta):
            return False
        try:
            if ruta.lower().endswith(".exe"):
                try:
                    subprocess.Popen([ruta, *args], cwd=os.path.dirname(ruta))
                except OSError as exc:
                    if getattr(exc, "winerror", None) != 740:  # 740 = pide administrador: que Windows pregunte
                        raise
                    os.startfile(ruta, "open", subprocess.list2cmdline(args), os.path.dirname(ruta))
            else:
                os.startfile(ruta)
            return True
        except OSError:
            return False

    def _abrir(self, destino: str) -> list[int] | None:
        """Abre la herramienta y devuelve sus ventanas nuevas (None si no está instalada)."""
        if destino == "temperatura":
            self._preparar_hwmonitor()
        antes = set(win.ventanas())
        if not self._lanzar(destino):
            return None
        if destino == "temperatura":
            # si aun así sale el aviso de actualización, se le da 'Continuar' solo
            threading.Thread(target=win.auto_continuar, args=(HWMONITOR_EXES, 40), daemon=True).start()
        return win.esperar_nuevas(antes, timeout=20)

    def _preparar_hwmonitor(self):
        """
        HWMonitor pregunta por actualizaciones cuando no encuentra su configuración (el .BAT viejo borraba Data).
        Se deja UPDATES=0 en la configuración actual y en la de fábrica del portable.
        """
        carpeta = os.path.dirname(self._ruta("temperatura"))
        for rel in (("Data", "hwmonitorw.ini"), ("App", "DefaultData", "hwmonitorw.ini"),
                    ("App", "HWMonitor", "hwmonitorw.ini")):
            ruta = os.path.join(carpeta, *rel)
            if rel[-2] == "HWMonitor" and not os.path.isfile(ruta):
                continue  # solo existe mientras HWMonitor está abierto
            if not os.path.isfile(ruta):
                try:  # nuevo en UTF-16 con BOM, como los crea HWMonitor
                    os.makedirs(os.path.dirname(ruta), exist_ok=True)
                    with open(ruta, "w", encoding="utf-16") as fh:
                        fh.write("[HWMonitor]\r\n")
                except OSError:
                    continue
            # la API de Windows respeta la codificación del .ini (UTF-16 o ANSI)
            ctypes.windll.kernel32.WritePrivateProfileStringW("HWMonitor", "UPDATES", "0", ruta)

    def _guardar(self, paso: Paso, estado: str, detalle: str, comentario: str, fotos: list[str]):
        self.resultados[paso.id] = {"estado": estado, "detalle": detalle, "comentario": comentario,
                                    "fotos": fotos}
        self._guardar_estado()
        self.ui_async(self._refrescar_tabla)

    def _guardar_estado(self):
        try:
            with open(os.path.join(self.carpeta, "estado.json"), "w", encoding="utf-8") as fh:
                json.dump({"orden": self.orden, "resultados": self.resultados}, fh, ensure_ascii=False, indent=1)
        except OSError:
            pass

    # ------------------------------------------------------------------ detecciones de cada prueba
    def _auto_camara(self):
        self.ev_hw.wait(60)
        if not self.hw.get("camara"):
            return None, "⚠ Windows no detecta ninguna cámara."
        return None, ""

    def _auto_carga(self):
        e = win.energia()
        if not e["bateria"]:
            self.ev_hw.wait(60)
            if not self.hw.get("bateria"):
                return "N/A", "Equipo sin batería"
        ok, txt = self._poll_carga()
        return ("OK", txt) if ok else (None, txt)

    def _poll_carga(self):
        e = win.energia()
        p = e["porcentaje"]
        if e["cargador"] and e["cargando"]:
            return True, f"Cargador conectado, cargando ({p} %)"
        if e["cargador"] and p is not None and p >= 95:
            return True, f"Cargador conectado, batería llena ({p} %)"
        if e["cargador"]:
            return False, f"⚠ Cargador conectado pero NO carga ({p} %)"
        return False, f"Sin cargador ({p} %)"

    def _auto_red(self):
        self.ev_hw.wait(60)
        if not self.hw.get("ethernet"):
            return "N/A", "El equipo no tiene puerto de red"
        ok, txt = detectar.ethernet_conectado()
        return ("OK", txt) if ok else (None, txt)

    def _poll_red(self):
        return detectar.ethernet_conectado()

    def _auto_wifi(self):
        self.ev_hw.wait(60)
        ok, txt = self._poll_wifi()
        if ok:
            return "OK", txt
        if not self.hw.get("wifi"):
            return None, "⚠ Windows no detecta adaptador Wi-Fi"
        return None, txt

    def _poll_wifi(self):
        ok, txt = detectar.wifi_estado()
        if ok and detectar.internet():
            return True, txt + ", con internet"
        return False, (txt + ", sin internet") if ok else "Wi-Fi no conectado"

    def _auto_bluetooth(self):
        self.ev_hw.wait(60)
        bt = self.hw.get("bluetooth", [])
        bien = [b for b in bt if str(b.get("estado")).upper() == "OK"]
        if bien:
            return "OK", bien[0].get("nombre", "Bluetooth")
        if bt:
            return "FALLA", f"{bt[0].get('nombre')}: controlador con error ({bt[0].get('estado')})"
        return None, "⚠ No se detectó adaptador Bluetooth"

    def _auto_hdmi(self):
        self.monitores_base = win.monitores()
        return None, f"Pantallas detectadas: {self.monitores_base}"

    def _poll_hdmi(self):
        n = win.monitores()
        if n > self.monitores_base:
            return True, f"Pantalla externa detectada ({n} pantallas)"
        return False, f"Pantallas detectadas: {n}"

    def _auto_usb(self):
        self.usb_base = win.unidades()
        self.usb_vistas = []
        return None, "Conexiones detectadas: 0"

    def _poll_usb(self):
        ahora = win.unidades()
        for letra in sorted(ahora - self.usb_base):
            if win.tipo_unidad(letra) in (2, 3):
                self.usb_vistas.append(f"{letra}:")
        self.usb_base = ahora  # al retirar la memoria, la próxima conexión cuenta de nuevo
        if self.usb_vistas:
            return False, f"Conexiones detectadas: {len(self.usb_vistas)} ({', '.join(self.usb_vistas)})"
        return False, "Conexiones detectadas: 0"

    def _auto_dvd(self):
        self.ev_hw.wait(60)
        dvd = self.hw.get("dvd", [])
        if not dvd:
            return "N/A", "Sin unidad óptica"
        return None, f"Unidad: {dvd[0].get('nombre')} ({dvd[0].get('letra')})"

    def _auto_controladores(self):
        self.ev_hw.wait(60)
        err = self.hw.get("dispositivos_error", [])
        if not err:
            return "OK", "Sin dispositivos con error"
        nombres = "; ".join(f"{e.get('nombre')} (código {e.get('codigo')})" for e in err[:6])
        return "FALLA", f"{len(err)} con error: {nombres}"

    def _auto_licencia(self):
        self.ev_lic.wait(90)
        texto = self.lic.get("texto", "Desconocido")
        if self.lic.get("estado") == 1:
            canal = self.lic.get("canal") or ""
            return "OK", f"Activado{' (' + canal + ')' if canal else ''}"
        return "FALLA", texto

    def _auto_office(self):
        self.ev_office.wait(90)
        return self.office.get("resultado") or "FALLA", self.office.get("texto", "No se pudo consultar")

    def _auto_discos(self):
        self.ev_hw.wait(60)
        self.ev_cdi.wait(60)
        lineas, peor = [], "OK"
        internos = [d for d in self.hw.get("discos", []) if str(d.get("bus")).upper() != "USB"]
        for d in internos:
            modelo = d.get("modelo", "")
            cdi = next((c for c in self.cdi if c["modelo"] and (c["modelo"] in modelo or modelo in c["modelo"])),
                       None)
            tipo = d.get("tipo") if d.get("tipo") in ("SSD", "HDD") else (
                "SSD" if str(d.get("bus")).upper() == "NVME" or "SSD" in modelo.upper() else "Disco")
            if cdi:
                salud = cdi["salud"] + (f" {cdi['porcentaje']} %" if cdi["porcentaje"] is not None else "")
                malo = cdi["salud"].lower() in ("bad", "caution")
            else:
                salud = d.get("salud", "?")
                malo = str(salud).lower() in ("warning", "unhealthy")
            if malo:
                peor = "FALLA"
            extra = f", {d['horas']} h" if d.get("horas") else ""
            lineas.append(f"{tipo} {modelo} {d.get('gb')} GB: {salud}{extra}")
        if not internos:
            return None, "⚠ No se detectaron discos internos"
        return peor, " · ".join(lineas)

    def _auto_bateria(self):
        self.ev_bat.wait(90)
        bats = self.bat.get("baterias", [])
        if not bats:
            if not win.energia()["bateria"]:
                return "N/A", "Equipo sin batería"
            return None, "⚠ No se pudo leer la salud de la batería. Revisa el informe."
        b = bats[0]
        txt = (f"Salud {b['salud']} % ({b['actual_mwh']} de {b['diseno_mwh']} mWh"
               + (f", {b['ciclos']} ciclos" if b.get("ciclos") else "") + ")")
        return ("OK" if b["salud"] >= int(self.cfg.get("umbral_bateria", 60)) else "FALLA"), txt

    def _poll_touchpad(self):
        t = self.touch
        if not t:
            return False, ""
        return t.completo(), t.texto()

    # ------------------------------------------------------------------ revisión y reporte
    def _pantalla_revision(self, en_curso: bool = False):
        self._limpiar()
        c = self.cuerpo
        cab = tk.Frame(c, bg="#f4f5f7")
        cab.pack(fill="x")
        tk.Label(cab, text=f"Orden {self.orden}", font=("Segoe UI", 20, "bold"), bg="#f4f5f7").pack(side="left")
        self.lbl_estado = tk.Label(cab, text="Recorrido en curso..." if en_curso else "", font=("Segoe UI", 11),
                                   bg="#f4f5f7", fg="#555")
        self.lbl_estado.pack(side="left", padx=16)
        self.tabla = ttk.Treeview(c, columns=("n", "prueba", "estado", "detalle"), show="headings",
                                  selectmode="browse")
        for col, txt, ancho in (("n", "#", 40), ("prueba", "Prueba", 230), ("estado", "Estado", 90),
                                ("detalle", "Detalle / comentario", 560)):
            self.tabla.heading(col, text=txt)
            self.tabla.column(col, width=int(ancho * self.escala), stretch=(col == "detalle"),
                              anchor="center" if col in ("n", "estado") else "w")
        for est, color in (("OK", "#d4edda"), ("FALLA", "#f8d7da"), ("N/A", "#d1ecf1"), ("", "#fff3cd")):
            self.tabla.tag_configure(est or "PEND", background=color)
        self.tabla.tag_configure("ACTUAL", background="#cfe2ff")
        self.tabla.pack(fill="both", expand=True, pady=10)
        self.tabla.bind("<Double-1>", lambda e: self._editar_comentario())
        self.botonera = tk.Frame(c, bg="#f4f5f7")
        self.botonera.pack(fill="x")
        self._refrescar_tabla()
        self._botones_revision(en_curso)

    def _botones_revision(self, en_curso: bool):
        for w in self.botonera.winfo_children():
            w.destroy()
        if en_curso:
            tk.Button(self.botonera, text="Detener recorrido", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea",
                      padx=10, command=lambda: self.decidir("TERMINAR")).pack(side="left")
            return
        for texto, fn, color in (("OK", lambda: self._marcar("OK"), "#1e8e3e"),
                                 ("FALLA", lambda: self._marcar("FALLA"), "#d93025"),
                                 ("N/A", lambda: self._marcar("N/A"), "#5f6c7b")):
            tk.Button(self.botonera, text=texto, font=("Segoe UI", 10, "bold"), fg="white", bg=color,
                      relief="flat", padx=14, command=fn).pack(side="left", padx=(0, 6))
        for texto, fn in (("Comentario...", self._editar_comentario), ("Repetir prueba", self._repetir),
                          ("Continuar pendientes", self._continuar)):
            tk.Button(self.botonera, text=texto, font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                      command=fn).pack(side="left", padx=(0, 6))
        tk.Button(self.botonera, text="Nueva orden", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea",
                  padx=10, command=self._nueva_orden).pack(side="right")
        tk.Button(self.botonera, text="GENERAR REPORTE", font=("Segoe UI", 11, "bold"), fg="white",
                  bg="#0b5ed7", relief="flat", padx=16,
                  command=lambda: self._generar_reporte(True)).pack(side="right", padx=8)

    def _refrescar_tabla(self, actual: str = ""):
        if not hasattr(self, "tabla") or not self.tabla.winfo_exists():
            return
        sel = self.tabla.selection()
        self.tabla.delete(*self.tabla.get_children())
        n = 0
        for p in self.pasos:
            if not p.en_reporte:
                continue
            n += 1
            r = self.resultados.get(p.id, {})
            est = r.get("estado") or ""
            det = " · ".join(x for x in (r.get("detalle", ""), r.get("comentario", "")) if x)
            fotos = len(r.get("fotos", []))
            tag = "ACTUAL" if p.id == actual else (est or "PEND")
            self.tabla.insert("", "end", iid=p.id, values=(n, p.nombre, est or "pendiente",
                                                             det + (f"   [{fotos} foto(s)]" if fotos else "")),
                              tags=(tag,))
        if sel and self.tabla.exists(sel[0]):
            self.tabla.selection_set(sel[0])

    def _marcar_actual(self, pid: str):
        self._refrescar_tabla(actual=pid)

    def _seleccion(self) -> Paso | None:
        sel = self.tabla.selection() if hasattr(self, "tabla") else ()
        if not sel:
            messagebox.showinfo("PRUEBAS", "Selecciona una prueba de la lista.", parent=self.root)
            return None
        return next((p for p in self.pasos if p.id == sel[0]), None)

    def _marcar(self, estado: str):
        p = self._seleccion()
        if not p:
            return
        r = self.resultados.setdefault(p.id, {"detalle": "", "comentario": "", "fotos": []})
        r["estado"] = estado
        if estado == "FALLA" and not r.get("comentario"):
            r["comentario"] = simpledialog.askstring("FALLA", f"¿Qué falla en {p.nombre}?", parent=self.root) or ""
        self._guardar_estado()
        self._refrescar_tabla()

    def _editar_comentario(self):
        p = self._seleccion()
        if not p or self.trabajando:
            return
        r = self.resultados.setdefault(p.id, {"estado": "", "detalle": "", "comentario": "", "fotos": []})
        txt = simpledialog.askstring("Comentario", p.nombre, initialvalue=r.get("comentario", ""), parent=self.root)
        if txt is not None:
            r["comentario"] = txt.strip()
            self._guardar_estado()
            self._refrescar_tabla()

    def _repetir(self):
        p = self._seleccion()
        if not p or self.trabajando:
            return
        self.resultados.pop(p.id, None)
        if p.tipo == "revisar":
            ref = next((x for x in self.pasos if x.id == p.ref), None)
            if ref and ref.tipo == "preparar":
                p = Paso(**{**p.__dict__, "tipo": "normal"})  # sin esperar el benchmark de nuevo
        self._botones_revision(True)
        self.root.iconify()
        self._trabajar(self._recorrido, p)

    def _continuar(self):
        if self.trabajando:
            return
        self._botones_revision(True)
        self.root.iconify()
        self._trabajar(self._recorrido)

    def _fin_trabajo(self):
        self.root.deiconify()
        self.root.lift()
        if hasattr(self, "botonera") and self.botonera.winfo_exists():
            self._botones_revision(False)
            self._refrescar_tabla()

    def _datos_reporte(self) -> dict:
        b = (self.bat.get("baterias") or [None])[0]
        pasos = []
        for p in self.pasos:
            if p.en_reporte:
                r = self.resultados.get(p.id, {})
                pasos.append({"id": p.id, "nombre": p.nombre, "estado": r.get("estado") or "",
                              "detalle": r.get("detalle", ""), "comentario": r.get("comentario", ""),
                              "fotos": r.get("fotos", [])})
        return {"orden": self.orden, "tecnico": self.cfg.get("tecnico", ""), "version": VERSION,
                "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "hardware": self.hw,
                "licencia_texto": self.lic.get("texto", ""),
                "office_texto": self.office.get("texto", ""),
                "bateria_texto": f"{b['salud']} % de salud ({b['actual_mwh']}/{b['diseno_mwh']} mWh)" if b else "",
                "pasos": pasos,
                "adjuntos": [("Informe de batería", f"{self.orden}_BATERIA.html"),
                             ("Informe AIDA64", f"{self.orden}_AIDA.html")]}

    def _generar_reporte(self, abrir: bool):
        ruta = reporte.generar(self.carpeta, self._datos_reporte())
        copia = self.cfg.get("carpeta_copia", "").strip()
        aviso = ""
        if copia:
            try:
                shutil.copytree(self.carpeta, os.path.join(copia, self.orden), dirs_exist_ok=True)
                aviso = f" · copiado a {copia}"
            except OSError as exc:
                aviso = f" · NO se pudo copiar a {copia}: {exc}"
        if hasattr(self, "lbl_estado") and self.lbl_estado.winfo_exists():
            self.lbl_estado.configure(text=f"Reporte listo: {os.path.basename(ruta)}{aviso}")
        if abrir:
            os.startfile(ruta)
        return ruta

    def _nueva_orden(self):
        if self.trabajando:
            return
        self.orden, self.carpeta, self.resultados = "", "", {}
        self._pantalla_inicio()

    def _salir(self):
        if self.trabajando and not messagebox.askyesno("PRUEBAS", "Hay un recorrido en curso. ¿Salir?",
                                                       parent=self.root):
            return
        self.cancelar = True
        self.decidir("TERMINAR")
        self.ev_comentario.set()
        self.root.destroy()

    def correr(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().correr()
