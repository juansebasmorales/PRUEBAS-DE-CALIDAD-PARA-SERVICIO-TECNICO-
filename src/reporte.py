"""Reporte HTML del checklist con fotos de evidencia (y resultado.json para subirlo después)."""

from __future__ import annotations

import base64
import json
import os
import re
from html import escape

ESTILO = {"OK": ("#d4edda", "#155724"), "FALLA": ("#f8d7da", "#721c24"), "N/A": ("#d1ecf1", "#0c5460"),
          "": ("#fff3cd", "#856404")}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f4f5f7;color:#222;padding:20px}
.hoja{max-width:1100px;margin:0 auto;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.08);overflow:hidden}
.cab{padding:18px 24px;border-bottom:3px solid #0b5ed7;display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap}
.cab h1{font-size:24px}.cab p{color:#777;font-size:12px}
.res{display:flex;gap:8px}.res span{padding:6px 12px;border-radius:6px;font-weight:700;font-size:13px}
.hw{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:4px 20px;padding:14px 24px;background:#f8f9fa;font-size:12.5px;border-bottom:1px solid #e3e3e3}
.hw b{color:#0b5ed7;font-size:10.5px;text-transform:uppercase;display:inline-block;min-width:110px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{background:#333;color:#fff;text-align:left;padding:8px 10px;font-size:12px}
td{padding:7px 10px;border-bottom:1px solid #eee;vertical-align:top}
td.e{font-weight:700;text-align:center;width:80px}
td.n{font-weight:600;width:26%}
.det{color:#555;font-size:12px}
.fotos{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}
.fotos img{height:70px;border-radius:4px;border:1px solid #ccc}
.galeria{padding:20px 24px}.galeria h2{font-size:16px;margin-bottom:10px}
.galeria figure{display:inline-block;width:32%;margin:0 1% 14px 0;vertical-align:top}
.galeria img{width:100%;border-radius:6px;border:1px solid #ddd}
.galeria figcaption{font-size:12px;color:#444;margin-top:3px}
.adj{padding:10px 24px 20px;font-size:13px}.adj a{margin-right:16px}
@media print{body{background:#fff;padding:0}.hoja{box-shadow:none}.galeria figure{width:48%}}
"""


def _fila_hw(etiqueta: str, valor) -> str:
    if isinstance(valor, list):
        valor = " | ".join(str(v) for v in valor if v)
    if not valor:
        return ""
    return f"<div><b>{escape(etiqueta)}</b> {escape(str(valor))}</div>"


def generar(carpeta: str, datos: dict) -> str:
    """Escribe <orden>_CHECKLIST.html y resultado.json en 'carpeta'. Devuelve la ruta del HTML."""
    orden = datos.get("orden", "SIN_ORDEN")
    hw = datos.get("hardware", {}) or {}
    pasos = datos.get("pasos", [])

    conteo = {"OK": 0, "FALLA": 0, "N/A": 0, "": 0}
    for p in pasos:
        conteo[p.get("estado", "") if p.get("estado", "") in conteo else ""] += 1

    discos = [f"{d.get('modelo', '')} {d.get('gb', '')} GB {d.get('tipo', '')}".strip()
              for d in hw.get("discos", [])]
    partes = ["<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>",
              f"<title>Checklist {escape(orden)}</title><style>{CSS}</style></head><body><div class='hoja'>",
              "<div class='cab'><div>",
              f"<h1>CHECKLIST · Orden {escape(orden)}</h1>",
              f"<p>Generado: {escape(datos.get('fecha', ''))}"
              + (f" · Técnico: {escape(datos['tecnico'])}" if datos.get("tecnico") else "") + "</p></div>",
              "<div class='res'>"]
    for k, etiqueta in (("OK", "OK"), ("FALLA", "FALLA"), ("N/A", "N/A"), ("", "PENDIENTE")):
        if conteo[k]:
            fondo, txt = ESTILO[k]
            partes.append(f"<span style='background:{fondo};color:{txt}'>{conteo[k]} {etiqueta}</span>")
    partes.append("</div></div><div class='hw'>")
    for etiqueta, valor in (("Fabricante", hw.get("fabricante")), ("Modelo", hw.get("modelo")),
                            ("Serial", hw.get("serial")), ("BIOS", hw.get("bios")), ("CPU", hw.get("cpu")),
                            ("RAM", hw.get("ram")), ("GPU", hw.get("gpu")), ("Sistema", hw.get("sistema")),
                            ("Almacenamiento", discos), ("Licencia Windows", datos.get("licencia_texto")),
                            ("Licencia Office", datos.get("office_texto")),
                            ("Batería", datos.get("bateria_texto"))):
        partes.append(_fila_hw(etiqueta, valor))
    partes.append("</div><table><tr><th>#</th><th>PRUEBA</th><th>ESTADO</th><th>DETALLE / COMENTARIO</th></tr>")

    for i, p in enumerate(pasos, 1):
        est = p.get("estado", "")
        fondo, txt = ESTILO.get(est, ESTILO[""])
        det = " · ".join(x for x in (p.get("detalle", ""), p.get("comentario", "")) if x)
        miniaturas = "".join(f"<a href='{escape(f)}' target='_blank'><img src='{escape(f)}' alt=''></a>"
                             for f in p.get("fotos", []))
        partes.append(f"<tr style='background:{fondo}'><td>{i}</td><td class='n'>{escape(p.get('nombre', ''))}</td>"
                      f"<td class='e' style='color:{txt}'>{escape(est or 'PENDIENTE')}</td>"
                      f"<td><div class='det'>{escape(det)}</div>"
                      + (f"<div class='fotos'>{miniaturas}</div>" if miniaturas else "") + "</td></tr>")
    partes.append("</table>")

    adjuntos = [(n, r) for n, r in datos.get("adjuntos", []) if os.path.exists(os.path.join(carpeta, r))]
    if adjuntos:
        partes.append("<div class='adj'><b>Informes adjuntos:</b> "
                      + "".join(f"<a href='{escape(r)}' target='_blank'>{escape(n)}</a>" for n, r in adjuntos)
                      + "</div>")

    fotos = [(p.get("nombre", ""), f) for p in pasos for f in p.get("fotos", [])]
    if fotos:
        partes.append("<div class='galeria'><h2>Evidencia fotográfica</h2>")
        for nombre, f in fotos:
            partes.append(f"<figure><a href='{escape(f)}' target='_blank'><img src='{escape(f)}' alt=''></a>"
                          f"<figcaption>{escape(nombre)}</figcaption></figure>")
        partes.append("</div>")
    partes.append("</div></body></html>")

    ruta = os.path.join(carpeta, f"{orden}_CHECKLIST.html")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(partes))
    with open(os.path.join(carpeta, "resultado.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)
    return ruta


def _leer_html(ruta: str) -> str:
    """HTML de otro programa en el texto correcto (powercfg usa UTF-8/UTF-16, AIDA64 suele usar ANSI)."""
    with open(ruta, "rb") as fh:
        crudo = fh.read()
    if crudo[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return crudo.decode("utf-16", errors="replace")
    try:
        return crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return crudo.decode("cp1252", errors="replace")


def _incrustar_fotos(html: str, carpeta: str) -> str:
    """Cambia fotos/xxx.jpg por la imagen dentro del HTML (data:), para que el archivo funcione solo."""
    cache: dict[str, str] = {}

    def data(rel: str) -> str:
        if rel not in cache:
            try:
                with open(os.path.join(carpeta, rel), "rb") as fh:
                    cache[rel] = "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode("ascii")
            except OSError:
                cache[rel] = rel
        return cache[rel]

    # el enlace a la foto grande duplicaría el peso: se quita y la foto se amplía con un clic
    html = re.sub(r"<a href='(fotos/[^']+)' target='_blank'>(<img [^>]*>)</a>", r"\2", html)
    return re.sub(r"src='(fotos/[^']+)'", lambda m: f"src='{data(m.group(1))}'", html)


AMPLIAR = ("<script>document.querySelectorAll('img').forEach(function(i){i.style.cursor='zoom-in';"
           "i.onclick=function(){var w=window.open('');w.document.write('<title>Foto</title><body style=\"margin:0;"
           "background:#111\"><img src=\"'+i.src+'\" style=\"max-width:100%;display:block;margin:auto\">');};});"
           "</script>")


def unir(carpeta: str, orden: str) -> str | None:
    """
    Junta checklist + informe de batería + AIDA64 en <orden>_REPORTE_COMPLETO.html: un solo archivo con pestañas
    y las fotos adentro (para enviarlo o subirlo sin perder nada). None si no hay checklist todavía.
    """
    partes = []
    for nombre, archivo in (("Checklist", f"{orden}_CHECKLIST.html"), ("Batería", f"{orden}_BATERIA.html"),
                            ("AIDA64", f"{orden}_AIDA.html")):
        ruta = os.path.join(carpeta, archivo)
        if not os.path.isfile(ruta):
            continue
        try:
            html = _leer_html(ruta)
        except OSError:
            continue
        if nombre == "Checklist":
            html = _incrustar_fotos(html, carpeta).replace("</body>", AMPLIAR + "</body>")
        partes.append((nombre, html))
    if not partes or partes[0][0] != "Checklist":
        return None

    botones = "".join(f"<button onclick='ver({i})' id='b{i}'>{escape(n)}</button>" for i, (n, _h) in enumerate(partes))
    marcos = "".join(f"<iframe id='f{i}' srcdoc=\"{escape(h, quote=True)}\"></iframe>" for i, (_n, h) in enumerate(partes))
    pagina = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte completo {escape(orden)}</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;background:#f4f5f7}}
nav{{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 16px;background:#1f2430}}
nav b{{color:#fff;margin-right:12px;font-size:15px}}
nav button{{border:0;border-radius:6px;padding:8px 16px;font:600 14px 'Segoe UI',sans-serif;background:#3c4454;color:#fff;cursor:pointer}}
nav button.activo{{background:#0b5ed7}}
iframe{{display:none;width:100%;height:calc(100vh - 56px);border:0;background:#fff}}iframe.activo{{display:block}}
@media print{{nav{{display:none}}iframe{{height:auto;min-height:100vh}}}}
</style></head><body>
<nav><b>Orden {escape(orden)}</b>{botones}<button onclick="document.getElementById('f'+actual).contentWindow.print()">Imprimir pestaña</button></nav>
{marcos}
<script>var actual=0;function ver(i){{document.querySelectorAll('iframe,nav button[id]').forEach(function(e){{e.classList.remove('activo')}});
document.getElementById('f'+i).classList.add('activo');document.getElementById('b'+i).classList.add('activo');actual=i;}}ver(0);</script>
</body></html>"""
    salida = os.path.join(carpeta, f"{orden}_REPORTE_COMPLETO.html")
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write(pagina)
    return salida
