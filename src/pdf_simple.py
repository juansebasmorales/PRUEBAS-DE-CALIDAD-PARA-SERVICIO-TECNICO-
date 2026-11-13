"""
PDF de texto hecho a mano (sin Edge ni librerías): el reporte del checklist sin fotos y los informes de batería y
AIDA64 pasados a texto. Courier (ancho fijo, así las tablas quedan alineadas), A4, páginas automáticas.
"""

from __future__ import annotations

import re
import textwrap
import zlib
from html.parser import HTMLParser

ANCHO, ALTO, MARGEN = 595, 842, 40
COLORES = {"verde": (0.12, 0.56, 0.24), "rojo": (0.85, 0.19, 0.15), "gris": (0.37, 0.42, 0.48),
           "azul": (0.04, 0.37, 0.84), "negro": (0, 0, 0)}


def _esc(t: str) -> bytes:
    b = t.encode("cp1252", errors="replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class Documento:
    """Líneas de texto: escribir(texto, tamaño, negrita, color). Parte las líneas largas y las páginas."""

    def __init__(self):
        self.paginas: list[list[bytes]] = [[]]
        self.y = ALTO - MARGEN

    def escribir(self, texto: str = "", tam: float = 9, negrita: bool = False, color: str = "negro",
                 sangria: int = 0):
        ancho_chars = max(20, int((ANCHO - 2 * MARGEN - sangria) / (tam * 0.6)))
        lineas = textwrap.wrap(texto, ancho_chars, replace_whitespace=False, drop_whitespace=True,
                               break_long_words=True) if texto.strip() else [""]
        r, g, b = COLORES.get(color, COLORES["negro"])
        for ln in lineas:
            alto = tam * 1.35
            if self.y - alto < MARGEN:
                self.paginas.append([])
                self.y = ALTO - MARGEN
            self.y -= alto
            fuente = b"/F2" if negrita else b"/F1"
            self.paginas[-1].append(b"BT %s %.1f Tf %.2f %.2f %.2f rg %d %.1f Td (%s) Tj ET" % (
                fuente, tam, r, g, b, MARGEN + sangria, self.y, _esc(ln)))

    def espacio(self, puntos: float = 6):
        self.y -= puntos

    def guardar(self, ruta: str) -> str:
        objetos: list[bytes] = []

        def nuevo(contenido: bytes) -> int:
            objetos.append(contenido)
            return len(objetos)

        catalogo = nuevo(b"")   # se llena al final
        raiz_paginas = nuevo(b"")
        f1 = nuevo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
        f2 = nuevo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>")
        hojas = []
        total = len(self.paginas)
        for n, ops in enumerate(self.paginas, 1):
            ops = ops + [b"BT /F1 7 Tf 0.5 0.5 0.5 rg %d %d Td (%s) Tj ET" % (ANCHO - MARGEN - 60, 20,
                                                                               _esc(f"Página {n} de {total}"))]
            datos = zlib.compress(b"\n".join(ops))
            cont = nuevo(b"<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream" % (len(datos), datos))
            hojas.append(nuevo(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
                               b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>"
                               % (raiz_paginas, ANCHO, ALTO, cont, f1, f2)))
        objetos[catalogo - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % raiz_paginas
        objetos[raiz_paginas - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
            b" ".join(b"%d 0 R" % h for h in hojas), len(hojas))
        salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posiciones = []
        for i, obj in enumerate(objetos, 1):
            posiciones.append(len(salida))
            salida += b"%d 0 obj\n%s\nendobj\n" % (i, obj)
        xref = len(salida)
        salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
        salida += b"".join(b"%010d 00000 n \n" % p for p in posiciones)
        salida += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, catalogo,
                                                                                      xref)
        with open(ruta, "wb") as fh:
            fh.write(salida)
        return ruta


# ------------------------------------------------------------------------------------------- HTML -> texto
class _ATexto(HTMLParser):
    BLOQUE = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "hr", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lineas: list[str] = []
        self.actual: list[str] = []
        self.saltar = 0

    def _cortar(self):
        txt = re.sub(r"[ \t\r\n\xa0]+", " ", "".join(self.actual)).strip(" |")
        if txt:
            self.lineas.append(txt)
        self.actual = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.saltar += 1
        elif tag in self.BLOQUE:
            self._cortar()
        elif tag in ("td", "th") and self.actual and "".join(self.actual).strip():
            self.actual.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.saltar = max(0, self.saltar - 1)
        elif tag in self.BLOQUE:
            self._cortar()

    def handle_data(self, data):
        if not self.saltar:
            self.actual.append(data)


def html_a_lineas(html: str) -> list[str]:
    p = _ATexto()
    p.feed(html)
    p.close()
    p._cortar()
    return p.lineas


def informe_pdf(titulo: str, html: str, ruta: str, maximo_lineas: int = 20000) -> str:
    """Un informe HTML de otro programa (powercfg, AIDA64) pasado a PDF de texto."""
    doc = Documento()
    doc.escribir(titulo, 13, True, "azul")
    doc.espacio()
    for ln in html_a_lineas(html)[:maximo_lineas]:
        doc.escribir(ln, 8)
    return doc.guardar(ruta)


def checklist_pdf(datos: dict, ruta: str) -> str:
    """Reporte del recorrido (sin fotos): equipo, licencias, batería y cada prueba con su resultado."""
    doc = Documento()
    hw = datos.get("hardware") or {}
    doc.escribir(f"REPORTE DE PRUEBAS - ORDEN {datos.get('orden', '')}", 14, True, "azul")
    doc.escribir(f"Fecha: {datos.get('fecha', '')}    Técnico: {datos.get('tecnico', '') or '-'}    "
                 f"PRUEBAS v{datos.get('version', '')}", 8, color="gris")
    doc.espacio(8)
    equipo = [("Equipo", " ".join(x for x in (hw.get("fabricante"), hw.get("modelo")) if x)),
              ("Serie", hw.get("serial", "")), ("Procesador", hw.get("cpu", "")),
              ("Memoria RAM", hw.get("ram", "")), ("Sistema", hw.get("sistema", "")),
              ("Video", ", ".join(g.get("nombre", "") if isinstance(g, dict) else str(g) for g in hw.get("gpu") or [])),
              ("Discos", ", ".join(f"{d.get('modelo', '')} {d.get('gb', '')} GB".strip()
                                   for d in hw.get("discos") or [] if isinstance(d, dict))),
              ("Windows", datos.get("licencia_texto", "")), ("Office", datos.get("office_texto", "")),
              ("Batería", datos.get("bateria_texto", ""))]
    for k, v in equipo:
        if v:
            doc.escribir(f"{k + ':':<13}{v}", 9)
    doc.espacio(8)
    pasos = datos.get("pasos") or []
    cuenta = {e: sum(1 for p in pasos if p.get("estado") == e) for e in ("OK", "FALLA", "N/A")}
    doc.escribir(f"Resultado: {cuenta['OK']} funcionan, {cuenta['FALLA']} en falla, {cuenta['N/A']} no aplica, "
                 f"{len(pasos) - sum(cuenta.values())} pendientes", 10, True)
    doc.espacio(4)
    color = {"OK": "verde", "FALLA": "rojo", "N/A": "gris"}
    for n, p in enumerate(pasos, 1):
        estado = p.get("estado") or "PENDIENTE"
        doc.escribir(f"{n:>2}. {p.get('nombre', ''):<38} {estado}", 9, True, color.get(estado, "negro"))
        for extra in (p.get("detalle"), p.get("comentario")):
            if extra:
                doc.escribir(str(extra), 8, sangria=26)
    doc.espacio(10)
    doc.escribir("Las fotos de cada prueba están en la orden, en su prueba.", 8, color="gris")
    return doc.guardar(ruta)
