"""Ventanas de la conexión con la página: configurar la clave, pedir el PIN y elegir la orden."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

import pagina
import secreto

FUENTE = ("Segoe UI", 11)


def _etiqueta(padre, texto, fila, **kw):
    tk.Label(padre, text=texto, font=("Segoe UI", 10, "bold"), bg="white").grid(row=fila, column=0, sticky="w",
                                                                              pady=(10, 0), **kw)


class ConfigPagina:
    """Pegar la clave tp_ (la crea el administrador en la página), ponerle un PIN y probar la conexión."""

    def __init__(self, app, al_guardar):
        self.app, self.al_guardar = app, al_guardar
        cfg = app.cfg.setdefault("pagina", {})
        t = self.top = tk.Toplevel(app.root)
        t.title("Página de órdenes de servicio")
        t.configure(bg="white", padx=18, pady=14)
        t.transient(app.root)
        t.resizable(False, False)
        tk.Label(t, text="La clave la crea el administrador en la página: Ajustes → Programa de pruebas de calidad → "
                         "Crear clave. Se muestra una sola vez.", font=("Segoe UI", 9), bg="white", fg="#555",
                 wraplength=460, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
        _etiqueta(t, "Clave (tp_...)" + ("  — déjala vacía para conservar la guardada" if cfg.get("clave") else ""), 1)
        self.ent_clave = tk.Entry(t, font=FUENTE, width=44, show="•")
        self.ent_clave.grid(row=2, column=0, columnspan=2, sticky="we")
        _etiqueta(t, "PIN del taller (mínimo 6 caracteres; se pide al abrir PRUEBAS)", 3)
        self.ent_pin = tk.Entry(t, font=FUENTE, width=20, show="•")
        self.ent_pin.grid(row=4, column=0, sticky="w")
        self.ent_pin2 = tk.Entry(t, font=FUENTE, width=20, show="•")
        self.ent_pin2.grid(row=4, column=1, sticky="w", padx=(8, 0))
        tk.Label(t, text="repetir PIN", font=("Segoe UI", 8), bg="white", fg="#777").grid(row=5, column=1, sticky="w",
                                                                                        padx=(8, 0))
        _etiqueta(t, "Nombre de esta USB / banco (sale en la página)", 6)
        self.ent_pc = tk.Entry(t, font=FUENTE, width=24)
        self.ent_pc.insert(0, cfg.get("pc") or "USB taller")
        self.ent_pc.grid(row=7, column=0, sticky="w")
        self.lbl = tk.Label(t, text=(f"Conectado a: {cfg['empresa']}" if cfg.get("empresa") else ""),
                            font=("Segoe UI", 10), bg="white", fg="#1e8e3e", wraplength=460, justify="left")
        self.lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 0))
        bot = tk.Frame(t, bg="white")
        bot.grid(row=9, column=0, columnspan=2, sticky="we", pady=(14, 0))
        tk.Button(bot, text="Probar conexión", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=self._probar).pack(side="left")
        if cfg.get("clave"):
            tk.Button(bot, text="Quitar conexión", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                      command=self._quitar).pack(side="left", padx=8)
        tk.Button(bot, text="Cancelar", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=t.destroy).pack(side="right")
        tk.Button(bot, text="Guardar", font=("Segoe UI", 10, "bold"), relief="flat", bg="#0b5ed7", fg="white",
                  padx=14, command=self._guardar).pack(side="right", padx=8)
        self.ent_clave.focus_set()

    def _mensaje(self, txt, color="#555"):
        if self.top.winfo_exists():
            self.lbl.configure(text=txt, fg=color)

    def _clave_actual(self) -> str | None:
        """La clave escrita, o la guardada (si ya se desbloqueó con el PIN en esta sesión)."""
        escrita = self.ent_clave.get().strip()
        return escrita or self.app.clave_pagina

    def _probar(self):
        clave = self._clave_actual()
        if not clave:
            self._mensaje("Pega la clave (o desbloquea la guardada con el PIN al iniciar).", "#d93025")
            return
        self._mensaje("Probando conexión...")

        def hilo():
            try:
                r = pagina.llamar(clave, "probar")
                txt = f"Conectado a: {r.get('empresa') or r.get('nombre') or 'empresa sin nombre'}"
                if r.get("pc"):
                    txt += f"  ·  clave: {r['pc']}"
                self.app.ui_async(self._mensaje, txt, "#1e8e3e")
                self._empresa = r.get("empresa") or r.get("nombre") or ""
                self._limites = r.get("limites")
            except pagina.ErrorPagina as e:
                self.app.ui_async(self._mensaje, e.para_tecnico(), "#d93025")
        threading.Thread(target=hilo, daemon=True).start()

    def _guardar(self):
        cfg = self.app.cfg.setdefault("pagina", {})
        clave = self.ent_clave.get().strip()
        pin, pin2 = self.ent_pin.get(), self.ent_pin2.get()
        if clave and not clave.startswith("tp_"):
            self._mensaje("La clave empieza por tp_ (cópiala completa desde la página).", "#d93025")
            return
        if clave or pin:
            if len(pin) < 6:
                self._mensaje("El PIN debe tener al menos 6 caracteres.", "#d93025")
                return
            if pin != pin2:
                self._mensaje("Los dos PIN no coinciden.", "#d93025")
                return
            clave = clave or self.app.clave_pagina
            if not clave:
                self._mensaje("Para cambiar el PIN, pega la clave otra vez.", "#d93025")
                return
            cfg["clave"] = secreto.cifrar(clave, pin)
            self.app.clave_pagina = clave
        elif not cfg.get("clave"):
            self._mensaje("Pega la clave y ponle un PIN.", "#d93025")
            return
        cfg["pc"] = self.ent_pc.get().strip() or "USB taller"
        if getattr(self, "_empresa", ""):
            cfg["empresa"] = self._empresa
        if getattr(self, "_limites", None):
            cfg["limites"] = self._limites
        self.al_guardar()
        self.top.destroy()

    def _quitar(self):
        if messagebox.askyesno("PRUEBAS", "¿Quitar la clave de la página de esta USB?", parent=self.top):
            self.app.cfg["pagina"] = {}
            self.app.clave_pagina = None
            self.al_guardar()
            self.top.destroy()


def pedir_pin(app) -> str | None:
    """Pide el PIN hasta 3 veces y devuelve la clave descifrada (None si se cancela)."""
    guardada = (app.cfg.get("pagina") or {}).get("clave")
    if not guardada:
        return None
    from tkinter import simpledialog
    for intento in range(3):
        pin = simpledialog.askstring("Página de órdenes", "PIN del taller:" if intento == 0 else
                                     "PIN incorrecto. Vuelve a escribirlo:", show="•", parent=app.root)
        if pin is None:
            return None
        try:
            return secreto.descifrar(guardada, pin)
        except secreto.PinIncorrecto:
            continue
    messagebox.showwarning("PRUEBAS", "PIN incorrecto. Se sigue sin enviar a la página.", parent=app.root)
    return None


class ElegirOrden:
    """Confirma la orden encontrada por la serie (o deja buscar por número / QR) y si es entrada o salida."""

    def __init__(self, app, ordenes: list[dict], al_elegir, mensaje: str = ""):
        self.app, self.al_elegir, self.ordenes = app, al_elegir, ordenes
        t = self.top = tk.Toplevel(app.root)
        t.title("Orden de servicio")
        t.configure(bg="white", padx=18, pady=14)
        t.transient(app.root)
        t.grab_set()
        self.lbl = tk.Label(t, text=mensaje, font=("Segoe UI", 10, "bold"), bg="white", wraplength=560,
                            justify="left")
        self.lbl.pack(anchor="w")
        self.lista = tk.Listbox(t, font=FUENTE, height=5, width=62, activestyle="none")
        self.lista.pack(fill="x", pady=8)
        self.lista.bind("<<ListboxSelect>>", lambda e: self._sugerir())
        fila = tk.Frame(t, bg="white")
        fila.pack(fill="x")
        tk.Label(fila, text="Pruebas de:", font=("Segoe UI", 10, "bold"), bg="white").pack(side="left")
        self.var_tipo = tk.StringVar(value="entrada")
        for v, txt in (("entrada", "Entrada (cómo llegó)"), ("salida", "Salida (después de la reparación)")):
            tk.Radiobutton(fila, text=txt, value=v, variable=self.var_tipo, bg="white",
                           font=("Segoe UI", 10)).pack(side="left", padx=6)
        otra = tk.Frame(t, bg="white")
        otra.pack(fill="x", pady=(12, 0))
        tk.Label(otra, text="Buscar por número de orden o QR del comprobante:", font=("Segoe UI", 9), bg="white",
                 fg="#555").pack(anchor="w")
        self.ent = tk.Entry(otra, font=FUENTE, width=40)
        self.ent.pack(side="left")
        self.ent.bind("<Return>", lambda e: self._buscar())
        tk.Button(otra, text="Buscar", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=self._buscar).pack(side="left", padx=6)
        bot = tk.Frame(t, bg="white")
        bot.pack(fill="x", pady=(14, 0))
        tk.Button(bot, text="Seguir sin la página", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=lambda: self._fin(None)).pack(side="left")
        tk.Button(bot, text="USAR ESTA ORDEN", font=("Segoe UI", 11, "bold"), relief="flat", bg="#0b5ed7",
                  fg="white", padx=16, command=self._usar).pack(side="right")
        t.protocol("WM_DELETE_WINDOW", lambda: self._fin(None))
        self._mostrar(ordenes)
        (self.lista if ordenes else self.ent).focus_set()

    def _mostrar(self, ordenes: list[dict]):
        self.ordenes = ordenes
        self.lista.delete(0, "end")
        for o in ordenes:
            self.lista.insert("end", pagina.describir(o))
        if ordenes:
            self.lista.selection_set(0)
            self._sugerir()

    def _sugerir(self):
        sel = self.lista.curselection()
        if sel:
            self.var_tipo.set(self.ordenes[sel[0]].get("tipo_sugerido") or "entrada")

    def _buscar(self):
        texto = self.ent.get().strip()
        if not texto:
            return
        self.lbl.configure(text="Buscando...", fg="#555")

        def hilo():
            try:
                res = pagina.buscar(self.app.clave_pagina, texto=texto)
                msg = (f"{len(res)} orden(es) encontrada(s)." if res else
                       "No se encontró ninguna orden abierta con ese número o QR.")
                self.app.ui_async(self._resultado, res, msg)
            except pagina.ErrorPagina as e:
                self.app.ui_async(self._resultado, [], e.para_tecnico())
        threading.Thread(target=hilo, daemon=True).start()

    def _resultado(self, res, msg):
        if self.top.winfo_exists():
            self.lbl.configure(text=msg, fg="#222" if res else "#d93025")
            self._mostrar(res)

    def _usar(self):
        sel = self.lista.curselection()
        if not sel:
            self.lbl.configure(text="Elige una orden de la lista (o busca por número / QR).", fg="#d93025")
            return
        self._fin((self.ordenes[sel[0]], self.var_tipo.get()))

    def _fin(self, eleccion):
        self.top.grab_release()
        self.top.destroy()
        self.al_elegir(eleccion)
