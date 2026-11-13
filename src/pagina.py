"""
Conexión con la página "Gestor de Órdenes de Servicio": buscar la orden del equipo, mandar los resultados,
subir el reporte PDF y las fotos de las fallas, y confirmar.

La clave tp_ nunca se escribe en registros, reportes ni mensajes de error: solo va en el cuerpo de cada petición.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = os.environ.get("PRUEBAS_API_URL") or \
    "https://yuapwlriaercxrbzwvum.supabase.co/functions/v1/pagos/taller/api/pruebas"
PROGRAMA = "PRUEBAS"
REINTENTOS = (30, 120, 600)          # segundos entre reintentos si no hay internet o el servidor no responde
MAX_ARCHIVOS = 10
MAX_BYTES = 15 * 1024 * 1024
SIN_VENTANA = 0x08000000

# prueba del programa -> (id en la página, nombre por defecto en la página)
EQUIVALENCIAS = [
    ("teclado", "p01", "Prueba de teclado"),
    ("discos", "p02", "Prueba de disco (Hard Disk Sentinel)"),
    ("discos", "p03", "Prueba de disco (CrystalDiskInfo)"),
    ("hdtune", "p04", "Prueba de SSD (HD Tune Pro)"),
    ("temperatura", "p05", "Prueba de temperatura (HWiNFO)"),
    ("pantalla", "p06", "Prueba de pantalla (IsMyLcdOK)"),
    ("camara", "p07", "Prueba de cámara (aplicación de Windows)"),
    ("microfono", "p08", "Prueba de micrófono (AudioRecorder)"),
    ("hdmi", "p09", "Prueba de HDMI / VGA"),
    ("licencia+office", "p10", "Activación de licencias (Windows / Office)"),
    ("carga", "p11", "Carga de batería"),
    ("bateria", "p12", "Informe de batería"),
    ("red", "p13", "Prueba de cable de red"),
    ("wifi", "p14", "Verificación de WiFi (manual)"),
    ("bluetooth", "p15", "Prueba de Bluetooth"),
    ("usb", "p16", "Prueba de puertos USB"),
    ("aida", "p17", "AIDA64 (revisión de hardware)"),
    ("sonido", "p18", "Prueba de sonido (altavoces)"),
    ("jack", "p19", "Prueba de jack de audio (auriculares)"),
    ("dvd", "p20", "Prueba de unidad DVD / CD"),
    ("controladores", "p21", "Administrador de dispositivos (controladores)"),
    ("touchpad", "p22", "Prueba de touchpad"),
]
A_PAGINA = {"OK": "ok", "FALLA": "falla", "N/A": "na"}

RELLENO = re.compile(r"^(to be filled.*|default string|system serial number|not specified|none|n/?a|o\.?e\.?m\.?|"
                     r"0+|1234567890?|123456789|serial|chassis serial number|\s*)$", re.I)


# ------------------------------------------------------------------------------------------- errores
class ErrorPagina(Exception):
    """codigo = HTTP (0 = sin conexión). 'reintentar' = vale la pena volver a intentar con el mismo envío."""

    def __init__(self, codigo: int, motivo: str, datos: dict | None = None):
        super().__init__(motivo)
        self.codigo, self.motivo, self.datos = codigo, motivo, datos or {}

    @property
    def reintentar(self) -> bool:
        return self.codigo in (0, 429, 500, 502, 503, 504)

    def para_tecnico(self) -> str:
        if self.codigo == 401:
            return "La clave ya no sirve: pide una nueva al administrador."
        if self.codigo == 404:
            return "La orden no existe en esta empresa: vuelve a buscarla."
        if self.codigo == 409:
            return f"La página no lo aceptó: {self.motivo}"
        if self.codigo == 413:
            return "El envío es muy grande (comentarios muy largos)."
        if self.codigo == 429:
            return "Demasiadas peticiones: se reintenta en unos minutos."
        if self.codigo == 0:
            return "Sin conexión con la página: se reintentará solo."
        if self.codigo >= 500:
            return "La página no respondió: se reintentará solo."
        return f"Error de la página ({self.codigo}): {self.motivo}"


def llamar(clave: str, accion: str, **campos) -> dict:
    cuerpo = json.dumps({"v": 1, "clave": clave, "accion": accion, **campos}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API, data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": f"{PROGRAMA}"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            texto = r.read()
    except urllib.error.HTTPError as e:
        try:
            datos = json.loads(e.read() or b"{}")
        except ValueError:
            datos = {}
        raise ErrorPagina(e.code, str(datos.get("motivo") or datos.get("error") or e.reason), datos) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErrorPagina(0, "Sin conexión con la página") from None
    try:
        datos = json.loads(texto or b"{}")
    except ValueError:
        raise ErrorPagina(502, "Respuesta no válida de la página") from None
    if not datos.get("ok"):
        raise ErrorPagina(200, str(datos.get("motivo") or datos.get("error") or "La página respondió sin ok"), datos)
    if isinstance(datos.get("limites"), dict):   # llega en probar, buscar y listar: el programa se ajusta solo
        LIMITES.clear()
        LIMITES.update(datos["limites"])
    return datos


LIMITES: dict = {}   # los últimos 'limites' que informó la página


def subir(url: str, ruta: str, tipo: str) -> None:
    with open(ruta, "rb") as fh:
        datos = fh.read()
    req = urllib.request.Request(url, data=datos, method="PUT", headers={"Content-Type": tipo})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            if r.status not in (200, 201):
                raise ErrorPagina(r.status, "No se pudo subir el archivo")
    except urllib.error.HTTPError as e:
        raise ErrorPagina(e.code if e.code != 400 else 503, "No se pudo subir el archivo") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErrorPagina(0, "Sin conexión al subir el archivo") from None


# ------------------------------------------------------------------------------------------- orden
def serie_del_equipo(hw: dict) -> str:
    for s in (hw.get("serial", ""), hw.get("serial_producto", "")):
        s = (s or "").strip()
        if s and not RELLENO.match(s):
            return s
    return ""


def buscar(clave: str, texto: str = "", serie: str = "") -> list[dict]:
    """Por serie (automático), por número de orden ('OS-0012' / '12') o por el QR del comprobante (URL)."""
    texto = (texto or "").strip()
    if serie:
        campos = {"serie": serie}
    elif es_qr(texto):
        campos = {"codigo": texto}
    else:
        campos = {"orden": texto}
    return llamar(clave, "buscar", **campos).get("ordenes", [])


def es_qr(texto: str) -> bool:
    return bool(re.match(r"^https?://", texto or "", re.I) or "?s=" in (texto or ""))


def listar(clave: str, texto: str = "", solo_pruebas: bool = False, limite: int = 50) -> list[dict]:
    """Órdenes abiertas de la empresa (primero las que están en pruebas). 'texto' filtra por número, nombre,
    marca, modelo o serie."""
    return llamar(clave, "listar", texto=(texto or "").strip(), solo_pruebas=bool(solo_pruebas),
                  limite=max(1, min(100, int(limite)))).get("ordenes", [])


def fecha_corta(valor) -> str:
    """'2026-11-13T15:05:00Z' -> '13/11/2026'."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(valor or ""))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(valor or "")


def describir(o: dict) -> str:
    eq = o.get("equipo") or {}
    partes = [o.get("orden", ""), o.get("cliente", ""),
              " ".join(x for x in (eq.get("marca"), eq.get("modelo")) if x),
              f"S/N {eq['serie']}" if eq.get("serie") else ""]
    return " · ".join(p for p in partes if p)


# ------------------------------------------------------------------------------------------- resultados
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _id_en_lista(lista: list[dict], pid: str, nombre: str) -> str | None:
    """La lista de la orden manda: primero por id, si no por nombre (sin tildes, mayúsculas ni signos)."""
    if any(x.get("id") == pid for x in lista):
        return pid
    n = _norm(nombre)
    return next((x.get("id") for x in lista if _norm(x.get("nombre", "")) == n), None)


def _combinar(items: list[dict]) -> dict | None:
    """Varias pruebas del programa en una de la página (licencia de Windows + Office)."""
    hechos = [i for i in items if i.get("estado") in A_PAGINA]
    if not hechos:
        return None
    fallas = [i for i in hechos if i["estado"] == "FALLA"]
    if fallas:
        estado = "FALLA"
    elif all(i["estado"] == "N/A" for i in hechos):
        estado = "N/A"
    else:
        estado = "OK"
    detalle = " | ".join(x for x in (f"{i['nombre']}: {i.get('detalle') or i.get('comentario') or i['estado']}"
                                     for i in (fallas or hechos)) if x)
    return {"estado": estado, "detalle": detalle, "comentario": "",
            "fotos": [f for i in fallas for f in i.get("fotos", [])]}


def armar_resultados(pasos: list[dict], lista: list[dict], aida_existe: bool) -> tuple[list[dict], dict]:
    """
    -> (resultados para 'enviar', {id_pagina: paso del programa}) solo de las pruebas que están en la lista de la
    orden. Las pruebas del programa que no están en la página van solo en el reporte PDF.
    """
    por_id = {p["id"]: p for p in pasos}
    resultados, origen = [], {}
    for programa, pid, nombre in EQUIVALENCIAS:
        destino = _id_en_lista(lista, pid, nombre)
        if not destino or destino in origen:
            continue
        if programa == "aida":
            if not aida_existe:
                continue
            paso = {"nombre": "AIDA64", "estado": "OK", "detalle": "Informe AIDA64 adjunto", "fotos": []}
        elif "+" in programa:
            paso = _combinar([por_id[x] for x in programa.split("+") if x in por_id])
        else:
            paso = por_id.get(programa)
        if paso and programa == "discos" and len(paso.get("fotos", [])) >= 2:
            # 'Salud de discos' toma CrystalDiskInfo (1.ª foto) y Hard Disk Sentinel (2.ª): cada una a su prueba
            paso = {**paso, "fotos": paso["fotos"][1:] if pid == "p02" else paso["fotos"][:1]}
        if not paso or paso.get("estado") not in A_PAGINA:
            continue  # pendiente o no se corrió: no se manda (se respeta lo que haya en la página)
        r = {"id": destino, "r": A_PAGINA[paso["estado"]]}
        c = paso.get("comentario") or ""
        if paso["estado"] == "FALLA":
            c = " · ".join(x for x in (c, paso.get("detalle", "")) if x) or "Falla detectada por el programa"
        elif paso.get("detalle"):
            c = " · ".join(x for x in (paso.get("detalle", ""), c) if x)
        if c:
            r["c"] = c[:240]
        resultados.append(r)
        origen[destino] = paso
    return resultados, origen


# ------------------------------------------------------------------------------------------- PDF
def _navegador() -> str:
    for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            ruta = os.path.join(base, rel)
            if base and os.path.isfile(ruta):
                return ruta
    return ""


def a_pdf(html: str, pdf: str) -> bool:
    """HTML -> PDF con Edge (o Chrome) sin ventana. La página no acepta .html."""
    nav = _navegador()
    if not nav or not os.path.isfile(html):
        return False
    perfil = tempfile.mkdtemp(prefix="pruebas_pdf_")  # perfil aparte: no choca con el Edge que esté abierto
    try:
        if os.path.exists(pdf):
            os.remove(pdf)
        subprocess.run([nav, "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
                        "--no-sandbox", f"--user-data-dir={perfil}", "--no-pdf-header-footer",
                        "--virtual-time-budget=5000", f"--print-to-pdf={pdf}", Path(html).resolve().as_uri()],
                       capture_output=True, timeout=120, creationflags=SIN_VENTANA)
        return os.path.isfile(pdf) and os.path.getsize(pdf) > 0
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        shutil.rmtree(perfil, ignore_errors=True)


_CLAVE_PRODUCTO = re.compile(r"\b[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}\b")
_ID_PRODUCTO = re.compile(r"\b\d{5}-\d{5}-\d{5}-[A-Z0-9]{5}\b")


def tapar_claves(html: str) -> str:
    """Quita claves de Windows/Office e ids de producto (AIDA64 los muestra) antes de mandar el informe."""
    html = _CLAVE_PRODUCTO.sub("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX", html)
    return _ID_PRODUCTO.sub("XXXXX-XXXXX-XXXXX-XXXXX", html)


def _foto_liviana(origen: str, destino: str) -> str:
    """Las fotos de las fallas se mandan reducidas (máx. 1600 px) para no pasar de 15 MB."""
    try:
        from PIL import Image
        with Image.open(origen) as img:
            img = img.convert("RGB")
            img.thumbnail((1600, 1600))
            img.save(destino, "JPEG", quality=80, optimize=True)
        return destino
    except Exception:
        return origen


def armar_archivos(carpeta: str, orden: str, origen: dict, html_reporte: str,
                   limite: int = MAX_ARCHIVOS) -> list[tuple[dict, str]]:
    """
    [(datos del archivo para 'enviar', ruta local)], por prioridad hasta 'limite' (lo que acepte la página):
      1. el reporte PDF (lleva adentro TODAS las fotos, así llegan aunque no quepan sueltas),
      2. una foto por cada prueba en falla (la página la exige),
      3. los informes de batería y AIDA64 en PDF (con las claves de producto tapadas),
      4. una foto de cada prueba OK/N/A, y después las fotos extra (p. ej. las páginas de HWMonitor).
    """
    salida = os.path.join(carpeta, "pagina")
    os.makedirs(salida, exist_ok=True)
    archivos: list[tuple[dict, str]] = []

    try:
        max_bytes = int(float(LIMITES.get("mb_archivo") or 15) * 1024 * 1024)
    except (TypeError, ValueError):
        max_bytes = MAX_BYTES

    def agregar(meta: dict, ruta: str) -> bool:
        if len(archivos) < limite and os.path.isfile(ruta) and 0 < os.path.getsize(ruta) <= max_bytes:
            archivos.append(({**meta, "tam": os.path.getsize(ruta)}, ruta))
            return True
        return False

    def foto(pid: str, rel: str, k: int, falla: bool):
        liviana = _foto_liviana(os.path.join(carpeta, rel.replace("/", os.sep)),
                                os.path.join(salida, f"{'falla' if falla else 'foto'}-{pid}-{k}.jpg"))
        agregar({"nombre": os.path.basename(liviana), "tipo": "image/jpeg", "prueba": pid}, liviana)

    pdf = os.path.join(salida, f"reporte-{orden}.pdf")
    if a_pdf(html_reporte, pdf):
        agregar({"nombre": os.path.basename(pdf), "tipo": "application/pdf", "reporte": True}, pdf)

    for pid, paso in origen.items():
        if paso.get("estado") == "FALLA" and paso.get("fotos"):
            foto(pid, paso["fotos"][0], 1, True)

    for pid, nombre_html, nombre_pdf in (("p12", f"{orden}_BATERIA.html", "informe-bateria.pdf"),
                                         ("p17", f"{orden}_AIDA.html", "informe-aida64.pdf")):
        if pid not in origen or len(archivos) >= limite:
            continue
        html = os.path.join(carpeta, nombre_html)
        if not os.path.isfile(html):
            continue
        tapado = os.path.join(salida, "tmp_" + nombre_html)
        from reporte import _leer_html
        with open(tapado, "w", encoding="utf-8") as fh:
            fh.write(tapar_claves(_leer_html(html)))
        destino = os.path.join(salida, nombre_pdf)
        if a_pdf(tapado, destino):
            agregar({"nombre": nombre_pdf, "tipo": "application/pdf", "prueba": pid}, destino)
        os.remove(tapado)

    for pid, paso in origen.items():  # primera foto de las demás pruebas
        if paso.get("estado") != "FALLA" and paso.get("fotos"):
            foto(pid, paso["fotos"][0], 1, False)
    for pid, paso in origen.items():  # el resto de fotos
        for k, rel in enumerate(paso.get("fotos", [])[1:], 2):
            foto(pid, rel, k, paso.get("estado") == "FALLA")
    return archivos


def limite_archivos(respuesta: dict) -> int:
    """Si la página informa su límite ('limites': {'archivos': N}), se usa; si no, 10."""
    try:
        lim = LIMITES or respuesta.get("limites") or {}
        return max(1, int(lim.get("archivos") or MAX_ARCHIVOS))
    except (TypeError, ValueError):
        return MAX_ARCHIVOS


# ------------------------------------------------------------------------------------------- envío con cola
def nuevo_envio(carpeta: str, enlace: dict, tipo: str, pc: str, version: str, resultados: list[dict],
                archivos: list[tuple[dict, str]]) -> dict:
    """Guarda el envío en Informes\\<orden>\\pagina_<tipo>.json (sin la clave) para poder reintentarlo."""
    envio = {"envio_id": str(uuid.uuid4()), "orden_id": enlace["id"], "orden": enlace.get("orden", ""),
             "tipo": tipo, "pc": pc, "programa": PROGRAMA, "version": version, "resultados": resultados,
             "archivos": [m for m, _r in archivos], "rutas": [r for _m, r in archivos],
             "estado": "pendiente", "intentos": 0, "creado": time.strftime("%Y-%m-%d %H:%M:%S")}
    guardar_envio(carpeta, envio)
    return envio


def ruta_envio(carpeta: str, tipo: str) -> str:
    return os.path.join(carpeta, f"pagina_{tipo}.json")


def guardar_envio(carpeta: str, envio: dict) -> None:
    with open(ruta_envio(carpeta, envio["tipo"]), "w", encoding="utf-8") as fh:
        json.dump(envio, fh, ensure_ascii=False, indent=1)


def pendientes(informes: str) -> list[tuple[str, dict]]:
    """Envíos sin confirmar de cualquier orden (por si se cerró el programa o no había internet)."""
    res = []
    if not os.path.isdir(informes):
        return res
    for orden in os.listdir(informes):
        for tipo in ("entrada", "salida"):
            ruta = os.path.join(informes, orden, f"pagina_{tipo}.json")
            try:
                with open(ruta, encoding="utf-8") as fh:
                    e = json.load(fh)
            except (OSError, ValueError):
                continue
            if e.get("estado") not in ("confirmado", "rechazado"):
                res.append((os.path.join(informes, orden), e))
    return res


def ejecutar_envio(clave: str, carpeta: str, envio: dict, aviso=lambda txt: None) -> dict:
    """
    enviar -> PUT de cada archivo -> confirmar. Si falla por red, lanza ErrorPagina con reintentar=True y el
    envío queda guardado: se reintenta con el MISMO envio_id (la página no duplica).
    """
    campos = {k: envio[k] for k in ("orden_id", "envio_id", "tipo", "pc", "programa", "version", "resultados",
                                    "archivos")}
    envio["intentos"] = envio.get("intentos", 0) + 1
    aviso(f"Enviando {len(envio['resultados'])} pruebas a {envio['orden']}...")
    try:
        resp = llamar(clave, "enviar", **campos)
    except ErrorPagina as e:
        if e.codigo == 413 and any("c" in r for r in envio["resultados"]):
            for r in envio["resultados"]:   # comentarios largos: se recortan y se reintenta una vez
                if r.get("r") != "falla":
                    r.pop("c", None)
                elif "c" in r:
                    r["c"] = r["c"][:80]
            guardar_envio(carpeta, envio)
            resp = llamar(clave, "enviar", **{**campos, "resultados": envio["resultados"]})
        else:
            if not e.reintentar:
                envio["estado"], envio["error"] = "rechazado", e.para_tecnico()
            guardar_envio(carpeta, envio)
            raise
    envio["estado"] = "enviado"
    envio["respuesta"] = {k: resp.get(k) for k in ("orden", "aplicadas", "cuenta", "ignorados", "faltan_evidencia")}
    guardar_envio(carpeta, envio)

    subir_urls = resp.get("subir") or {}
    for pos, url in sorted(subir_urls.items(), key=lambda kv: int(kv[0])):
        i = int(pos)
        aviso(f"Subiendo {envio['archivos'][i]['nombre']}...")
        subir(url, envio["rutas"][i], envio["archivos"][i]["tipo"])

    conf = llamar(clave, "confirmar", envio_id=envio["envio_id"])
    if conf.get("pendientes"):  # alguno no llegó: se vuelve a pedir la URL con el mismo envío
        raise ErrorPagina(503, "Faltan archivos por llegar a la página")
    envio["estado"] = "confirmado"
    envio["confirmacion"] = {k: conf.get(k) for k in ("guardados", "rechazados", "faltan_evidencia")}
    guardar_envio(carpeta, envio)
    return envio


def resumen(envio: dict) -> str:
    c = (envio.get("respuesta") or {}).get("cuenta") or {}
    return (f"Listo: {envio.get('orden')} actualizada ({c.get('ok', 0)} funcionan, {c.get('falla', 0)} en falla, "
            f"{c.get('na', 0)} no aplica)")
