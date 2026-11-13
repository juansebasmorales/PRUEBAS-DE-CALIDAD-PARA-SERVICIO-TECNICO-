"""
Publica PRUEBAS en la carpeta de Google Drive (la que baja ACTUALIZAR.bat).

    py publicar.py                       -> copia solo lo que cambió y escribe version.json
    py publicar.py --ver                 -> solo muestra qué se copiaría
    py publicar.py --sobrantes           -> lista lo que hay en Drive y no es parte del programa (no borra)

Drive para escritorio sube solo lo que se copia a la carpeta local. Para no descargar de Drive lo que ya está
publicado, se guarda en build\\publicado.json la huella de cada archivo subido.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DRIVE = r"Z:\Mi unidad\PRUEBASv2"
CACHE = os.path.join(APP_DIR, "build", "hash_cache.json")
PUBLICADO = os.path.join(APP_DIR, "build", "publicado.json")

# Lo que NO se publica: privado (Informes, config, Wi-Fi), desarrollo, y lo que cada equipo modifica al usarse
# (si se publicara, el actualizador lo volvería a bajar cada vez).
EXCLUIR = [
    ".git/*", "build/*", "src/*", "Informes/*", "__pycache__/*", "*.pyc", "*.py",
    "config.json", "version.json", ".actualizacion_cache.json", ".gitignore", ".gitattributes", "desktop.ini",
    "PRUEBAS_viejo*.exe", "*.viejo", "*.descarga", "ACTUALIZAR.nuevo", "PRUEBAS v21.BAT",
    "ProgramData/WIFI.xml",
    "ProgramData/HardDiskSentinel_All_Eng/HDSData/*", "ProgramData/HardDiskSentinel_All_Eng/*.ini",
    "ProgramData/CrystalDiskInfo_All/Smart/*", "ProgramData/CrystalDiskInfo_All/DiskInfo.txt",
    "ProgramData/CrystalDiskInfo_All/DiskInfo.ini",
    "ProgramData/*/Data/*", "ProgramData/*/*/Data/*",          # ajustes de los portables (PortableApps / FC)
    "ProgramData/aida64_All/data/*", "ProgramData/OCCT/Data/*",
    "*.log", "*.tmp",
]


def excluido(rel: str) -> bool:
    r = rel.lower()
    return any(fnmatch.fnmatch(r, p.lower()) for p in EXCLUIR)


def archivos() -> list[str]:
    res = []
    for raiz, dirs, nombres in os.walk(APP_DIR):
        rel_dir = os.path.relpath(raiz, APP_DIR).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirs[:] = [d for d in dirs if not excluido(rel_dir + d + "/x")]
        for n in nombres:
            rel = rel_dir + n
            if not excluido(rel):
                res.append(rel)
    return sorted(res, key=str.lower)


def cargar(ruta: str) -> dict:
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def guardar(ruta: str, datos: dict) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=0)


def sha256(ruta: str, cache: dict, rel: str) -> str:
    st = os.stat(ruta)
    c = cache.get(rel)
    if c and c["n"] == st.st_size and c["t"] == st.st_mtime_ns:
        return c["h"]
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    cache[rel] = {"n": st.st_size, "t": st.st_mtime_ns, "h": h.hexdigest().upper()}
    return cache[rel]["h"]


def version() -> str:
    with open(os.path.join(APP_DIR, "src", "pruebas.py"), encoding="utf-8") as fh:
        return re.search(r'^VERSION = "([^"]+)"', fh.read(), re.M).group(1)


def main() -> int:
    solo_ver = "--ver" in sys.argv
    if not os.path.isdir(DRIVE):
        print(f"No se encuentra la carpeta de Drive: {DRIVE}\n(¿Google Drive para escritorio está abierto?)")
        return 1
    if "--sobrantes" in sys.argv:
        propios = {a.lower() for a in archivos()} | {"version.json", "desktop.ini"}
        for raiz, _dirs, nombres in os.walk(DRIVE):
            for n in nombres:
                rel = os.path.relpath(os.path.join(raiz, n), DRIVE).replace("\\", "/")
                if rel.lower() not in propios:
                    print("  sobra en Drive:", rel)
        return 0

    cache, publicado = cargar(CACHE), cargar(PUBLICADO)
    lista = archivos()
    manifiesto = {"version": version(), "fecha": time.strftime("%Y-%m-%d %H:%M"), "archivos": {}}
    cambios, total = [], 0
    t0 = time.time()
    for rel in lista:
        ruta = os.path.join(APP_DIR, rel.replace("/", os.sep))
        h = sha256(ruta, cache, rel)
        tam = os.path.getsize(ruta)
        manifiesto["archivos"][rel] = {"sha256": h, "tam": tam}
        destino = os.path.join(DRIVE, rel.replace("/", os.sep))
        if rel not in publicado and os.path.exists(destino):
            # ya estaba en Drive (copiado a mano): mismo tamaño y fecha = mismo archivo, sin tener que leerlo
            st_o, st_d = os.stat(ruta), os.stat(destino)
            if st_o.st_size == st_d.st_size and abs(st_o.st_mtime - st_d.st_mtime) < 2.1:
                publicado[rel] = h
        if publicado.get(rel) != h or not os.path.exists(destino):
            cambios.append(rel)
            total += tam
    guardar(CACHE, cache)
    print(f"{len(lista)} archivos revisados en {time.time() - t0:.1f}s · versión {manifiesto['version']}")
    print(f"Cambiaron {len(cambios)} ({total / 1048576:.1f} MB):")
    for rel in cambios[:40]:
        print("  ", rel)
    if len(cambios) > 40:
        print(f"   ... y {len(cambios) - 40} más")
    if solo_ver:
        return 0

    for rel in cambios:
        origen = os.path.join(APP_DIR, rel.replace("/", os.sep))
        destino = os.path.join(DRIVE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copy2(origen, destino)
        publicado[rel] = manifiesto["archivos"][rel]["sha256"]
    # version.json al final: el actualizador solo ve la versión nueva cuando ya están todos los archivos
    with open(os.path.join(DRIVE, "version.json"), "w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, ensure_ascii=False, separators=(",", ":"))
    guardar(PUBLICADO, publicado)
    print(f"LISTO: publicado en {DRIVE}. Drive lo sube en unos minutos (mira el ícono de Drive en la barra).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
