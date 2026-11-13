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


COLUMNAS = (("orden", "Orden", 80), ("estado", "Estado", 150), ("cliente", "Cliente", 90),
            ("equipo", "Marca y modelo", 170), ("serie", "Serie", 120), ("ingreso", "Ingreso", 82))


def fila_orden(o: dict) -> tuple:
    eq = o.get("equipo") or {}
    return (o.get("orden", ""), o.get("estado_nombre") or o.get("estado", ""), o.get("cliente", ""),
            " ".join(x for x in (eq.get("marca"), eq.get("modelo")) if x), eq.get("serie", ""),
            pagina.fecha_corta(o.get("ingreso")))


class ElegirOrden:
    """
    Si la serie encontró la orden, la muestra para confirmar. Si no, o con 'Elegir otra orden', muestra la lista de
    órdenes abiertas de la empresa (acción 'listar') con un buscador. Al final: entrada o salida.
    """

    def __init__(self, app, ordenes: list[dict], al_elegir, mensaje: str = ""):
        from tkinter import ttk
        self.app, self.al_elegir, self.ordenes = app, al_elegir, []
        self._consulta = 0
        t = self.top = tk.Toplevel(app.root)
        t.title("Elegir orden de servicio")
        t.configure(bg="white", padx=18, pady=14)
        t.transient(app.root)
        t.grab_set()
        self.lbl = tk.Label(t, text=mensaje, font=("Segoe UI", 10, "bold"), bg="white", wraplength=700,
                            justify="left")
        self.lbl.pack(anchor="w")

        bus = tk.Frame(t, bg="white")
        bus.pack(fill="x", pady=(8, 0))
        tk.Label(bus, text="Buscar (número, nombre, marca, modelo, serie o QR):", font=("Segoe UI", 9), bg="white",
                 fg="#555").pack(anchor="w")
        self.ent = tk.Entry(bus, font=FUENTE, width=40)
        self.ent.pack(side="left")
        self.ent.bind("<Return>", lambda e: self._buscar())
        tk.Button(bus, text="Buscar", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=self._buscar).pack(side="left", padx=6)
        self.var_solo = tk.BooleanVar(value=False)
        tk.Checkbutton(bus, text="Solo las que están en pruebas", variable=self.var_solo, bg="white",
                       font=("Segoe UI", 9), command=self._buscar).pack(side="left", padx=6)

        marco = tk.Frame(t, bg="white")
        marco.pack(fill="both", expand=True, pady=8)
        estilo = ttk.Style(t)
        estilo.configure("Ordenes.Treeview", font=("Segoe UI", 10), rowheight=26)
        estilo.configure("Ordenes.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.tabla = ttk.Treeview(marco, columns=[c[0] for c in COLUMNAS], show="headings", height=10,
                                  selectmode="browse", style="Ordenes.Treeview")
        for col, titulo, ancho in COLUMNAS:
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor="w", stretch=col in ("equipo", "estado"))
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._sugerir())
        self.tabla.bind("<Double-1>", lambda e: self._usar())
        self.tabla.bind("<Return>", lambda e: self._usar())

        fila = tk.Frame(t, bg="white")
        fila.pack(fill="x")
        tk.Label(fila, text="Pruebas de:", font=("Segoe UI", 10, "bold"), bg="white").pack(side="left")
        self.var_tipo = tk.StringVar(value="entrada")
        for v, txt in (("entrada", "Entrada (cómo llegó)"), ("salida", "Salida (después de la reparación)")):
            tk.Radiobutton(fila, text=txt, value=v, variable=self.var_tipo, bg="white",
                           font=("Segoe UI", 10)).pack(side="left", padx=6)

        bot = tk.Frame(t, bg="white")
        bot.pack(fill="x", pady=(14, 0))
        tk.Button(bot, text="Seguir sin la página", font=("Segoe UI", 10), relief="flat", bg="#e3e6ea", padx=10,
                  command=lambda: self._fin(None)).pack(side="left")
        self.btn_otra = tk.Button(bot, text="Elegir otra orden", font=("Segoe UI", 10), relief="flat",
                                  bg="#e3e6ea", padx=10, command=self._lista_completa)
        self.btn_otra.pack(side="left", padx=8)
        tk.Button(bot, text="USAR ESTA ORDEN", font=("Segoe UI", 11, "bold"), relief="flat", bg="#0b5ed7",
                  fg="white", padx=16, command=self._usar).pack(side="right")
        t.protocol("WM_DELETE_WINDOW", lambda: self._fin(None))
        if ordenes:
            self._mostrar(ordenes)
            self.tabla.focus_set()
        else:
            self.btn_otra.pack_forget()
            self._consultar("", mensaje)
            self.ent.focus_set()

    def _mostrar(self, ordenes: list[dict]):
        self.ordenes = ordenes
        self.tabla.delete(*self.tabla.get_children())
        for i, o in enumerate(ordenes):
            self.tabla.insert("", "end", iid=str(i), values=fila_orden(o))
        if ordenes:
            self.tabla.selection_set("0")
            self.tabla.focus("0")
            self._sugerir()

    def _elegida(self) -> dict | None:
        sel = self.tabla.selection()
        return self.ordenes[int(sel[0])] if sel else None

    def _sugerir(self):
        o = self._elegida()
        if o:
            self.var_tipo.set(o.get("tipo_sugerido") or "entrada")

    def _lista_completa(self):
        self.btn_otra.pack_forget()
        self.ent.delete(0, "end")
        self._consultar("", "")

    def _buscar(self):
        self._consultar(self.ent.get().strip(), "")

    def _consultar(self, texto: str, mensaje: str):
        """El QR se busca con 'buscar' (código del comprobante); todo lo demás con 'listar'."""
        self._consulta += 1
        n, solo, clave = self._consulta, bool(self.var_solo.get()), self.app.clave_pagina
        self.lbl.configure(text=(mensaje + "\n" if mensaje else "") + "Cargando órdenes...", fg="#555")

        def hilo():
            try:
                if pagina.es_qr(texto):
                    res = pagina.buscar(clave, texto=texto)
                else:
                    res = pagina.listar(clave, texto=texto, solo_pruebas=solo)
                if res:
                    msg = f"{len(res)} orden(es) abierta(s){' con «' + texto + '»' if texto else ''}. Toca una:"
                else:
                    msg = (f"No hay órdenes abiertas con «{texto}»." if texto else
                           "No hay órdenes abiertas en la página.")
                self.app.ui_async(self._resultado, n, res, (mensaje + "\n" if mensaje else "") + msg)
            except pagina.ErrorPagina as e:
                if e.codigo == 401:
                    self.app.clave_pagina = None
                self.app.ui_async(self._resultado, n, [], e.para_tecnico())
        threading.Thread(target=hilo, daemon=True).start()

    def _resultado(self, n, res, msg):
        if n != self._consulta or not self.top.winfo_exists():
            return  # llegó la respuesta de una búsqueda anterior
        self.lbl.configure(text=msg, fg="#222" if res else "#d93025")
        self._mostrar(res)

    def _usar(self):
        o = self._elegida()
        if not o:
            self.lbl.configure(text="Elige una orden de la lista (o búscala arriba).", fg="#d93025")
            return
        self._fin((o, self.var_tipo.get()))

    def _fin(self, eleccion):
        self.top.grab_release()
        self.top.destroy()
        self.al_elegir(eleccion)
