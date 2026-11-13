@echo off
chcp 65001 >nul
title Actualizar memoria USB - PRUEBAS
set "ACT_USB_BAT=%~f0"
set "ACT_USB_ARG=%~1"
echo.
echo  ============================================
echo   ACTUALIZAR MEMORIA USB - PRUEBAS
echo   Baja de Google Drive a la memoria solo lo
echo   que falta o es diferente.
echo   No toca Informes, config.json ni WIFI.xml.
echo  ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText($env:ACT_USB_BAT); iex $t.Substring($t.LastIndexOf('#'+'##PS###'))"
echo.
pause
exit /b

###PS###
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$CARPETA_DRIVE = '1fejlqjQvjjj25r3wRuCCRbNJX2Ad-c74'   # carpeta publica PRUEBASv2

function CarpetaPruebas([string]$raiz) {
    # la carpeta de PRUEBAS que ya tenga la memoria (en la raiz o un nivel adentro)
    if (Test-Path -LiteralPath (Join-Path $raiz 'PRUEBAS.exe')) { return $raiz.TrimEnd('\') }
    foreach ($d in (Get-ChildItem -LiteralPath $raiz -Directory -ErrorAction SilentlyContinue)) {
        if (Test-Path -LiteralPath (Join-Path $d.FullName 'PRUEBAS.exe')) { return $d.FullName }
    }
    return $null
}

try {
    # 1. a que carpeta
    $destino = $null
    if ($env:ACT_USB_ARG) {
        # se puede arrastrar una carpeta encima del .bat
        $destino = (Resolve-Path -LiteralPath $env:ACT_USB_ARG).Path
    } else {
        $sistema = $env:SystemDrive
        $opciones = @()
        foreach ($u in (Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -ne $sistema -and $_.Size -and $_.DriveType -in 2, 3 })) {
            $raiz = $u.DeviceID + '\'
            $existe = CarpetaPruebas $raiz
            if ($u.DriveType -eq 2 -or $existe) {
                $carpeta = if ($existe) { $existe } else { Join-Path $raiz 'PRUEBASv2' }
                $nombre = if ($u.VolumeName) { $u.VolumeName } else { 'sin nombre' }
                $opciones += [pscustomobject]@{ carpeta = $carpeta; texto = ("{0} ({1}, {2:N1} GB libres)  ->  {3}{4}" -f $u.DeviceID, $nombre, ($u.FreeSpace / 1GB), $carpeta, $(if ($existe) { '' } else { '   (nueva)' })) }
            }
        }
        if ($opciones.Count -eq 0) {
            Write-Host ' No se encontro ninguna memoria USB. Conectala y vuelve a abrir este archivo.' -ForegroundColor Yellow
            Write-Host ' (Tambien puedes arrastrar la carpeta de destino encima de ACTUALIZAR_USB.bat)'
            return
        }
        for ($i = 0; $i -lt $opciones.Count; $i++) { Write-Host (" [{0}] {1}" -f ($i + 1), $opciones[$i].texto) }
        Write-Host ''
        $r = Read-Host (' Numero de la memoria a actualizar (Enter = 1, 0 = salir)')
        if ($r -eq '0') { return }
        $n = if ($r) { [int]$r } else { 1 }
        if ($n -lt 1 -or $n -gt $opciones.Count) { Write-Host ' Opcion no valida.' -ForegroundColor Red; return }
        $destino = $opciones[$n - 1].carpeta
    }
    New-Item -ItemType Directory -Force -Path $destino | Out-Null
    Write-Host ''
    Write-Host " Actualizando: $destino" -ForegroundColor Cyan

    # 2. se baja el ACTUALIZAR.bat mas nuevo de Drive y se usa su motor con esa carpeta como destino
    $html = (Invoke-WebRequest -UseBasicParsing "https://drive.google.com/embeddedfolderview?id=$CARPETA_DRIVE").Content
    $idMotor = $null
    foreach ($m in [regex]::Matches($html, '<div class="flip-entry" id="entry-([^"]+)"[\s\S]*?<a href="([^"]+)"[\s\S]*?<div class="flip-entry-title">([^<]*)</div>')) {
        if ([Net.WebUtility]::HtmlDecode($m.Groups[3].Value) -eq 'ACTUALIZAR.bat') { $idMotor = $m.Groups[1].Value }
    }
    if (-not $idMotor) { throw 'No se encontro ACTUALIZAR.bat en la carpeta de Drive.' }
    $motor = Join-Path $env:TEMP 'pruebas_actualizar_motor.bat'
    Invoke-WebRequest -UseBasicParsing "https://drive.usercontent.google.com/download?id=$idMotor&export=download&confirm=t" -OutFile $motor
    $texto = [IO.File]::ReadAllText($motor)
    $marca = $texto.LastIndexOf('#' + '##PS###')
    if ($marca -lt 0 -or $texto.IndexOf('ACT_DESTINO') -lt 0) { throw 'El ACTUALIZAR.bat de Drive es de una version anterior: publica de nuevo.' }
    $env:ACT_BAT = $motor
    $env:ACT_DESTINO = $destino
    iex $texto.Substring($marca)
    Remove-Item -LiteralPath $motor -Force -ErrorAction SilentlyContinue
    Write-Host ''
    Write-Host ' Antes de sacar la memoria usa "Quitar hardware de forma segura".'
} catch {
    Write-Host ''
    Write-Host " No se pudo actualizar la memoria: $($_.Exception.Message)" -ForegroundColor Red
}
