"""Reporte HTML del checklist con fotos de evidencia (y resultado.json para subirlo después)."""

from __future__ import annotations

import json
import os
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
