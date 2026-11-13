"""
Compila PRUEBAS.exe (un solo archivo, pide administrador solo) con Nuitka.

    py construir_exe.py

Necesita (una vez):  py -m pip install nuitka pillow zstandard
Resultado: PRUEBAS.exe en esta carpeta, junto a ProgramData\\ (las herramientas) e Informes\\.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(APP_DIR, "src")
ICONO = os.path.join(SRC, "pruebas.ico")
BUILD = os.path.join(APP_DIR, "build")


def version() -> str:
    with open(os.path.join(SRC, "pruebas.py"), encoding="utf-8") as fh:
        return re.search(r'^VERSION = "([^"]+)"', fh.read(), re.M).group(1)


def crear_icono() -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=48, fill=(11, 94, 215))
    d.line((62, 132, 108, 180, 196, 82), fill="white", width=30, joint="curve")
    img.save(ICONO, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def main() -> int:
    ver = version()
    if not os.path.isfile(ICONO):
        crear_icono()
    v4 = ".".join((ver.split(".") + ["0", "0", "0"])[:4])
    cmd = [sys.executable, "-m", "nuitka", "--onefile", "--assume-yes-for-downloads",
           "--enable-plugin=tk-inter", "--windows-console-mode=disable", "--windows-uac-admin",
           "--windows-icon-from-ico=" + ICONO,
           # se descomprime una sola vez por equipo (las siguientes aperturas son inmediatas)
           "--onefile-tempdir-spec={CACHE_DIR}/PRUEBAS/" + ver,
           "--include-module=PIL.ImageGrab", "--include-module=PIL.JpegImagePlugin",
           "--nofollow-import-to=numpy", "--nofollow-import-to=PIL.ImageQt", "--nofollow-import-to=PIL.ImageTk",
           "--company-name=Servicio tecnico", "--product-name=PRUEBAS", "--file-version=" + v4,
           "--product-version=" + v4, "--file-description=Recorrido de diagnostico con evidencia",
           "--output-dir=" + BUILD, "--output-filename=PRUEBAS.exe", "--remove-output",
           os.path.join(SRC, "pruebas.py")]
    print(f"Compilando PRUEBAS {ver} con Nuitka (tarda varios minutos)...")
    if subprocess.run(cmd, cwd=SRC).returncode != 0:
        print("FALLA: Nuitka no pudo compilar (ver los mensajes de arriba).")
        return 1
    destino = os.path.join(APP_DIR, "PRUEBAS.exe")
    try:
        shutil.copy2(os.path.join(BUILD, "PRUEBAS.exe"), destino)
    except PermissionError:
        # está abierto: Windows deja renombrar un .exe en uso, así que se aparta y se pone el nuevo
        viejo = os.path.join(APP_DIR, "PRUEBAS_viejo.exe")
        try:
            os.remove(viejo)
        except OSError:
            viejo = os.path.join(APP_DIR, f"PRUEBAS_viejo_{os.getpid()}.exe")
        os.rename(destino, viejo)
        shutil.copy2(os.path.join(BUILD, "PRUEBAS.exe"), destino)
        print(f"PRUEBAS.exe estaba abierto: la versión anterior quedó como {os.path.basename(viejo)}")
    print("LISTO:", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
