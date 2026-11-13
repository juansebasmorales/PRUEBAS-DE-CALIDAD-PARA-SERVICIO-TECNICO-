"""Detección automática del equipo. Todo corre en segundo plano y sin ventanas."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import xml.etree.ElementTree as ET

SIN_VENTANA = 0x08000000  # CREATE_NO_WINDOW

_PS_HARDWARE = r"""
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$r=[ordered]@{}
$cs=Get-CimInstance Win32_ComputerSystem
$csp=Get-CimInstance Win32_ComputerSystemProduct
$bios=Get-CimInstance Win32_BIOS
$r.fabricante="$($cs.Manufacturer)".Trim()
$r.modelo="$($cs.Model)".Trim()
if($cs.Manufacturer -match 'LENOVO' -and $csp.Version){$r.modelo="$($csp.Version) ($($cs.Model))"}
$r.serial="$($bios.SerialNumber)".Trim()
$r.bios="$($bios.SMBIOSBIOSVersion)".Trim()
$r.cpu=(@(Get-CimInstance Win32_Processor | % { $_.Name.Trim() }) -join ' | ')
$m=@(Get-CimInstance Win32_PhysicalMemory)
$tot=($m | Measure-Object Capacity -Sum).Sum
$tipos=@{20='DDR';21='DDR2';24='DDR3';26='DDR4';29='LPDDR3';30='LPDDR4';34='DDR5';35='LPDDR5'}
$tp=$null; if($m.Count){$tp=$tipos[[int]$m[0].SMBIOSMemoryType]}; if(-not $tp){$tp='RAM'}
$vel=''; if($m.Count -and $m[0].Speed){$vel=" $($m[0].Speed) MHz"}
$r.ram=('{0} GB {1}{2} - {3} modulo(s)' -f [math]::Round($tot/1GB),$tp,$vel,$m.Count)
$r.gpu=@(Get-CimInstance Win32_VideoController | % { $_.Name })
$os=Get-CimInstance Win32_OperatingSystem
$r.sistema="$($os.Caption) $($os.OSArchitecture) (build $($os.BuildNumber))"
$d=@()
foreach($x in Get-PhysicalDisk){
  $rc=$x | Get-StorageReliabilityCounter
  $d+=[ordered]@{modelo="$($x.FriendlyName)".Trim(); gb=[math]::Round($x.Size/1GB); tipo="$($x.MediaType)"; bus="$($x.BusType)"; salud="$($x.HealthStatus)"; desgaste=$rc.Wear; temp=$rc.Temperature; horas=$rc.PowerOnHours}
}
$r.discos=$d
$r.bateria=(@(Get-CimInstance Win32_Battery).Count -gt 0)
$ad=@(Get-NetAdapter -Physical)
$r.ethernet=@($ad | ? { $_.PhysicalMediaType -match '802\.3' -or $_.MediaType -eq '802.3' } | ? { $_.PhysicalMediaType -notmatch '802\.11' } | % { [ordered]@{nombre=$_.InterfaceDescription; estado="$($_.Status)"} })
$r.wifi=@($ad | ? { $_.PhysicalMediaType -match '802\.11' -or $_.InterfaceDescription -match 'Wi-?Fi|Wireless|WLAN|802\.11' } | % { [ordered]@{nombre=$_.InterfaceDescription; estado="$($_.Status)"} })
$pnp=@(Get-CimInstance Win32_PnPEntity -Filter "PNPClass='Bluetooth' OR PNPClass='Camera' OR PNPClass='Image' OR ConfigManagerErrorCode<>0")
$r.bluetooth=@($pnp | ? { $_.PNPClass -eq 'Bluetooth' -and $_.PNPDeviceID -match '^(USB|PCI)\\' } | % { [ordered]@{nombre=$_.Name; estado="$($_.Status)"} })
$r.dispositivos_error=@($pnp | ? { $_.ConfigManagerErrorCode -gt 0 } | % { [ordered]@{nombre=$(if($_.Name){$_.Name}else{$_.DeviceID}); codigo=$_.ConfigManagerErrorCode} })
$r.dvd=@(Get-CimInstance Win32_CDROMDrive | % { [ordered]@{nombre=$_.Name; letra=$_.Drive} })
$r.camara=@($pnp | ? { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } | % { $_.Name })
$r | ConvertTo-Json -Depth 4 -Compress
"""

_PS_LICENCIA = r"""
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$p=@(Get-CimInstance SoftwareLicensingProduct -Filter "ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL")
$a=$p | ? { $_.LicenseStatus -eq 1 } | select -First 1
if(-not $a){$a=$p | select -First 1}
[ordered]@{nombre="$($a.Name)"; estado=[int]$a.LicenseStatus; canal="$($a.ProductKeyChannel)"; descripcion="$($a.Description)"} | ConvertTo-Json -Compress
"""

_PS_OFFICE = r"""
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$r=[ordered]@{instalado=$false; nombre=''; version=''; activado=$false; cuenta=$false; estado=-1; canal=''; licencias=@()}
$c2r=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration'
if($c2r.ProductReleaseIds){$r.instalado=$true; $r.nombre="$($c2r.ProductReleaseIds)"; $r.version="$($c2r.VersionToReport)"}
$un=@(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' | ? { $_.DisplayName -match '^(Microsoft Office|Microsoft 365|Aplicaciones de Microsoft 365|Microsoft Office \w+ 20\d\d)' -and $_.DisplayName -notmatch 'Add-in|Extensibility|Proofing|Language|Idioma|Herramientas' })
if($un.Count){$r.instalado=$true; $r.nombre=$un[0].DisplayName; if(-not $r.version){$r.version="$($un[0].DisplayVersion)"}}
$p=@(Get-CimInstance SoftwareLicensingProduct -Filter "ApplicationID='0ff1ce15-a989-479d-af46-f275c6370663' AND PartialProductKey IS NOT NULL")
$p+=@(Get-CimInstance OfficeSoftwareProtectionProduct -Filter "PartialProductKey IS NOT NULL")
$r.licencias=@($p | % { [ordered]@{nombre="$($_.Name)"; estado=[int]$_.LicenseStatus; canal="$($_.ProductKeyChannel)"} })
$ok=$p | ? { $_.LicenseStatus -eq 1 } | select -First 1
if($ok){$r.activado=$true; $r.estado=1; $r.canal="$($ok.ProductKeyChannel)"; $r.nombre="$($ok.Name)"}
elseif($p.Count){$r.estado=[int]$p[0].LicenseStatus; $r.canal="$($p[0].ProductKeyChannel)"}
# Microsoft 365 por suscripcion: la licencia va en la cuenta (vNext), no en el registro clasico
$v=@(Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Office\Licenses" -Recurse -File)
if($v.Count -gt 0){$r.cuenta=$true}
$r | ConvertTo-Json -Depth 3 -Compress
"""

_PS_ETHERNET = r"""
$ErrorActionPreference='SilentlyContinue'
@(Get-NetAdapter -Physical | ? { ($_.PhysicalMediaType -match '802\.3' -or $_.MediaType -eq '802.3') -and $_.PhysicalMediaType -notmatch '802\.11' } | % { "$($_.Status)|$($_.LinkSpeed)" }) -join ';'
"""

ESTADO_LICENCIA = {0: "Sin licencia", 1: "Activado", 2: "Periodo de gracia", 3: "Gracia (cambio de hardware)",
                   4: "Gracia (no genuino)", 5: "Notificación (no activado)", 6: "Gracia extendida"}


def powershell(script: str, timeout: int = 90) -> str:
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", script], capture_output=True, timeout=timeout, creationflags=SIN_VENTANA)
        return r.stdout.decode("utf-8", errors="replace").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _lista(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def hardware() -> dict:
    try:
        d = json.loads(powershell(_PS_HARDWARE) or "{}")
    except ValueError:
        d = {}
    for k in ("gpu", "discos", "ethernet", "wifi", "bluetooth", "dispositivos_error", "dvd", "camara"):
        d[k] = _lista(d.get(k))
    return d


def licencia() -> dict:
    try:
        d = json.loads(powershell(_PS_LICENCIA) or "{}")
    except ValueError:
        d = {}
    d["texto"] = ESTADO_LICENCIA.get(d.get("estado"), "Desconocido") if d.get("nombre") else "Sin clave instalada"
    return d


def office() -> dict:
    """{'estado': 'OK'|'FALLA'|'N/A', 'texto': ...} más los datos crudos."""
    try:
        d = json.loads(powershell(_PS_OFFICE) or "{}")
    except ValueError:
        d = {}
    d["licencias"] = _lista(d.get("licencias"))
    nombre = d.get("nombre") or "Office"
    if not d.get("instalado") and not d["licencias"]:
        d["resultado"], d["texto"] = "N/A", "Office no instalado"
    elif d.get("activado"):
        canal = d.get("canal") or ""
        d["resultado"], d["texto"] = "OK", f"{nombre}: activado" + (f" ({canal})" if canal else "")
    elif d.get("cuenta"):
        d["resultado"], d["texto"] = "OK", f"{nombre}: licencia de Microsoft 365 por cuenta"
    else:
        est = ESTADO_LICENCIA.get(d.get("estado"), "sin clave instalada")
        d["resultado"], d["texto"] = "FALLA", f"{nombre}: no activado ({est})"
    return d


def ethernet_conectado() -> tuple[bool, str]:
    """(algún puerto con cable conectado, texto)."""
    salida = powershell(_PS_ETHERNET, timeout=20)
    for item in filter(None, salida.split(";")):
        estado, _, vel = item.partition("|")
        if estado.strip().lower() == "up":
            return True, f"Conectado a {vel.strip()}"
    return False, "Sin cable conectado"


def _netsh(*args: str, timeout: int = 15) -> str:
    """Salida de netsh en la página de códigos de consola (cp850 en Windows en español)."""
    try:
        import ctypes
        cp = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        cp = "cp850"
    try:
        r = subprocess.run(["netsh", *args], capture_output=True, timeout=timeout, creationflags=SIN_VENTANA)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    try:
        return r.stdout.decode("utf-8")  # Windows 11 reciente
    except UnicodeDecodeError:
        try:
            return r.stdout.decode(cp, errors="replace")
        except LookupError:
            return r.stdout.decode("cp850", errors="replace")


def redes_cercanas() -> list[dict]:
    """Redes Wi-Fi visibles: [{ssid, seguridad, senal}] ordenadas por señal (sin repetir)."""
    txt = _netsh("wlan", "show", "networks", "mode=bssid")
    redes: dict[str, dict] = {}
    actual = None
    for linea in txt.splitlines():
        m = re.match(r"^SSID \d+\s*:\s*(.*)$", linea.strip())
        if m:
            actual = {"ssid": m.group(1).strip(), "seguridad": "", "senal": 0}
            if actual["ssid"]:
                redes.setdefault(actual["ssid"], actual)
                actual = redes[actual["ssid"]]
            continue
        if actual is None:
            continue
        m = re.match(r"^\s*(?:Autenticaci\S{1,3}n|Authentication)\s*:\s*(.+)$", linea)
        if m and not actual["seguridad"]:
            actual["seguridad"] = m.group(1).strip()
        m = re.match(r"^\s*(?:Se\S{1,3}al|Signal)\s*:\s*(\d+)\s*%", linea)
        if m:
            actual["senal"] = max(actual["senal"], int(m.group(1)))
    return sorted(redes.values(), key=lambda r: -r["senal"])


def red_guardada(xml_path: str) -> str:
    """Nombre de la red de WIFI.xml ('' si no hay)."""
    try:
        return ET.parse(xml_path).getroot().find("{*}name").text or ""
    except Exception:
        return ""


def wifi_estado() -> tuple[bool, str]:
    """(conectado a una red, texto con el nombre de la red y la señal)."""
    txt = _netsh("wlan", "show", "interfaces", timeout=10)
    if not txt:
        return False, "No se pudo consultar"
    ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", txt, re.M)
    senal = re.search(r"^\s*(?:Se\S{1,3}al|Signal)\s*:\s*(\d+)\s*%", txt, re.M)
    if ssid and ssid.group(1).strip():
        return True, f"Red {ssid.group(1).strip()}" + (f", señal {senal.group(1)} %" if senal else "")
    return False, "No conectado"


def internet() -> bool:
    for host in (("1.1.1.1", 53), ("8.8.8.8", 53)):
        try:
            with socket.create_connection(host, timeout=2):
                return True
        except OSError:
            continue
    return False


def conectar_wifi(xml_path: str) -> str:
    """Agrega el perfil WIFI.xml y se conecta. No muestra la contraseña."""
    if not os.path.isfile(xml_path):
        return "Sin WIFI.xml"
    try:
        nombre = ET.parse(xml_path).getroot().find("{*}name").text
    except Exception:
        return "WIFI.xml dañado"
    try:
        subprocess.run(["netsh", "wlan", "add", "profile", f"filename={xml_path}"], capture_output=True,
                       timeout=15, creationflags=SIN_VENTANA)
        r = subprocess.run(["netsh", "wlan", "connect", f"name={nombre}"], capture_output=True, timeout=15,
                           creationflags=SIN_VENTANA)
        return f"Conectando a {nombre}" if r.returncode == 0 else f"No se pudo conectar a {nombre}"
    except (OSError, subprocess.TimeoutExpired):
        return "netsh no respondió"


SEGURIDAD = {  # texto que muestra Windows -> (authentication, encryption) del perfil
    "WPA2-Personal": ("WPA2PSK", "AES"),
    "WPA3-Personal": ("WPA3SAE", "AES"),
    "WPA-Personal": ("WPAPSK", "TKIP"),
    "Abierta": ("open", "none"),
}


def seguridad_de(texto_windows: str) -> str:
    t = (texto_windows or "").lower()
    if "wpa3" in t:
        return "WPA3-Personal"
    if "wpa2" in t:
        return "WPA2-Personal"
    if "wpa" in t:
        return "WPA-Personal"
    if "abierta" in t or "open" in t:
        return "Abierta"
    return "WPA2-Personal"


def crear_perfil_wifi(xml_path: str, ssid: str, clave: str, seguridad: str = "WPA2-Personal") -> None:
    from xml.sax.saxutils import escape
    s, k = escape(ssid), escape(clave)
    auth, enc = SEGURIDAD.get(seguridad, SEGURIDAD["WPA2-Personal"])
    llave = ("" if auth == "open" else
             f"\n    <sharedKey><keyType>passPhrase</keyType><protected>false</protected>"
             f"<keyMaterial>{k}</keyMaterial></sharedKey>")
    contenido = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{s}</name>
  <SSIDConfig><SSID><name>{s}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM><security>
    <authEncryption><authentication>{auth}</authentication><encryption>{enc}</encryption><useOneX>false</useOneX></authEncryption>{llave}
  </security></MSM>
</WLANProfile>
"""
    os.makedirs(os.path.dirname(xml_path), exist_ok=True)
    with open(xml_path, "w", encoding="utf-8") as fh:
        fh.write(contenido)


def crystaldiskinfo(exe: str, timeout: int = 60) -> list[dict]:
    """Ejecuta CrystalDiskInfo /CopyExit (sin ventana) y lee DiskInfo.txt: [{modelo, salud, porcentaje, temp}]."""
    if not os.path.isfile(exe):
        return []
    carpeta = os.path.dirname(exe)
    txt = os.path.join(carpeta, "DiskInfo.txt")
    try:
        if os.path.exists(txt):
            os.remove(txt)
        # oculto: si no, su ventana aparece al abrir PRUEBAS y parece que CrystalDiskInfo se abre dos veces
        oculto = subprocess.STARTUPINFO()
        oculto.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        oculto.wShowWindow = 0  # SW_HIDE
        subprocess.run([exe, "/CopyExit"], cwd=carpeta, timeout=timeout, startupinfo=oculto)
    except (OSError, subprocess.TimeoutExpired):
        return []
    try:
        with open(txt, "rb") as fh:
            crudo = fh.read()
    except OSError:
        return []
    if crudo[:2] in (b"\xff\xfe", b"\xfe\xff"):
        contenido = crudo.decode("utf-16", errors="replace")
    else:
        contenido = crudo.decode("utf-8-sig", errors="replace")
    contenido = contenido.replace("\r\n", "\n")
    discos = []
    for bloque in re.split(r"\n-{20,}\n\s*\(\d+\)", contenido)[1:]:
        modelo = re.search(r"^\s*Model\s*:\s*(.+)$", bloque, re.M)
        salud = re.search(r"^\s*Health Status\s*:\s*(.+)$", bloque, re.M)
        temp = re.search(r"^\s*Temperature\s*:\s*(\d+)", bloque, re.M)
        if not modelo:
            continue
        s = salud.group(1).strip() if salud else "Unknown"
        pct = re.search(r"(\d+)\s*%", s)
        discos.append({"modelo": modelo.group(1).strip(), "salud": s.split("(")[0].strip(),
                       "porcentaje": int(pct.group(1)) if pct else None,
                       "temp": int(temp.group(1)) if temp else None})
    return discos


def reporte_bateria(html_path: str, xml_path: str) -> dict:
    """Genera el informe de batería (HTML para el cliente, XML para leer la salud)."""
    for args in (["/output", html_path], ["/output", xml_path, "/xml"]):
        try:
            subprocess.run(["powercfg", "/batteryreport", *args], capture_output=True, timeout=60,
                           creationflags=SIN_VENTANA)
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        raiz = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError):
        return {}
    bats = []
    for b in raiz.iter():
        if not b.tag.endswith("}Battery"):
            continue
        campos = {c.tag.split("}")[-1]: (c.text or "").strip() for c in b}
        try:
            dis = int(campos.get("DesignCapacity") or 0)
            full = int(campos.get("FullChargeCapacity") or 0)
        except ValueError:
            continue
        if dis <= 0:
            continue
        bats.append({"modelo": campos.get("Id", ""), "fabricante": campos.get("Manufacturer", ""),
                     "diseno_mwh": dis, "actual_mwh": full, "salud": round(full * 100 / dis),
                     "ciclos": campos.get("CycleCount", "")})
    return {"baterias": bats}
