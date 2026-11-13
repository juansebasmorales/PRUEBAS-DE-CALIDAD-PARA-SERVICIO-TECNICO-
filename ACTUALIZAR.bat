@echo off
chcp 65001 >nul
title Actualizador PRUEBAS
cd /d "%~dp0"
set "ACT_BAT=%~f0"
echo.
echo  ============================================
echo   ACTUALIZADOR PRUEBAS
echo   Baja de Google Drive solo lo que cambio.
echo   No toca Informes, config.json ni WIFI.xml.
echo  ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText($env:ACT_BAT); iex $t.Substring($t.LastIndexOf('#'+'##PS###'))"
echo.
if exist "%~dp0ACTUALIZAR.nuevo" (
    echo  El actualizador tambien se actualizo.
    pause
    (goto) 2>nul & move /y "%~dp0ACTUALIZAR.nuevo" "%~f0" >nul
)
pause
exit /b

###PS###
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # sin esto Invoke-WebRequest es lentisimo en PowerShell 5
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$CARPETA_DRIVE = '1fejlqjQvjjj25r3wRuCCRbNJX2Ad-c74'   # carpeta publica PRUEBASv2
$base = Split-Path -Parent $env:ACT_BAT
$rutaCache = Join-Path $base '.actualizacion_cache.json'
$listados = @{}

function Listar([string]$id) {
    if ($listados.ContainsKey($id)) { return $listados[$id] }
    $html = (Invoke-WebRequest -UseBasicParsing "https://drive.google.com/embeddedfolderview?id=$id").Content
    $r = @{}
    foreach ($m in [regex]::Matches($html, '<div class="flip-entry" id="entry-([^"]+)"[\s\S]*?<a href="([^"]+)"[\s\S]*?<div class="flip-entry-title">([^<]*)</div>')) {
        $r[[Net.WebUtility]::HtmlDecode($m.Groups[3].Value)] = $m.Groups[1].Value
    }
    $listados[$id] = $r
    return $r
}

function IdDe([string]$rel) {
    $id = $CARPETA_DRIVE
    foreach ($parte in ($rel -split '/')) {
        $l = Listar $id
        if (-not $l.ContainsKey($parte)) { return $null }
        $id = $l[$parte]
    }
    return $id
}

function Descargar([string]$id, [string]$destino) {
    Invoke-WebRequest -UseBasicParsing "https://drive.usercontent.google.com/download?id=$id&export=download&confirm=t" -OutFile $destino
}

function Hash([string]$ruta) { (Get-FileHash -LiteralPath $ruta -Algorithm SHA256).Hash }

try {
    Write-Host ' Buscando actualizaciones en Google Drive...'
    $idVersion = (Listar $CARPETA_DRIVE)['version.json']
    if (-not $idVersion) { throw 'No se encontro version.json en la carpeta de Drive.' }
    $tmpVersion = Join-Path $env:TEMP 'pruebas_version.json'
    Descargar $idVersion $tmpVersion
    $remoto = [IO.File]::ReadAllText($tmpVersion) | ConvertFrom-Json

    $local = $null
    $rutaVersionLocal = Join-Path $base 'version.json'
    if (Test-Path -LiteralPath $rutaVersionLocal) {
        try { $local = [IO.File]::ReadAllText($rutaVersionLocal) | ConvertFrom-Json } catch { }
    }
    $verLocal = if ($local) { $local.version } else { '(sin version)' }
    Write-Host (" Instalada: {0}   Disponible: {1} ({2})" -f $verLocal, $remoto.version, $remoto.fecha)

    # cache de hashes: no se vuelve a leer un archivo que no cambio desde la ultima revision
    $cache = @{}
    if (Test-Path -LiteralPath $rutaCache) {
        try { ([IO.File]::ReadAllText($rutaCache) | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $cache[$_.Name] = $_.Value } } catch { }
    }
    if ($cache.Count -eq 0) { Write-Host ' Primera revision: se comprueban todos los archivos (puede tardar 1-2 minutos)...' }

    $pendientes = @()
    $bytes = 0
    foreach ($p in $remoto.archivos.PSObject.Properties) {
        $rel = $p.Name; $info = $p.Value
        $ruta = Join-Path $base ($rel -replace '/', '\')
        $h = $null
        if (Test-Path -LiteralPath $ruta) {
            $it = Get-Item -LiteralPath $ruta
            $c = $cache[$rel]
            if ($c -and $c.n -eq $it.Length -and $c.t -eq $it.LastWriteTimeUtc.Ticks) { $h = $c.h }
            elseif ($it.Length -eq $info.tam) {
                $h = Hash $ruta
                $cache[$rel] = @{ n = $it.Length; t = $it.LastWriteTimeUtc.Ticks; h = $h }
            }
        }
        if ($h -ne $info.sha256) { $pendientes += $rel; $bytes += [int64]$info.tam }
    }

    if ($pendientes.Count -eq 0) {
        Write-Host ''
        Write-Host ' Ya esta al dia. No hay nada que descargar.' -ForegroundColor Green
    } else {
        Write-Host (" Archivos que cambiaron: {0} ({1:N1} MB)" -f $pendientes.Count, ($bytes / 1MB))
        Write-Host ''
        $i = 0; $fallos = 0
        foreach ($rel in $pendientes) {
            $i++
            $info = $remoto.archivos.$rel
            Write-Host (" [{0}/{1}] {2} ({3:N1} MB)" -f $i, $pendientes.Count, $rel, ($info.tam / 1MB))
            $id = IdDe $rel
            if (-not $id) { Write-Host '        no esta en Drive, se omite' -ForegroundColor Yellow; $fallos++; continue }
            $ruta = Join-Path $base ($rel -replace '/', '\')
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ruta) | Out-Null
            $tmp = "$ruta.descarga"
            try {
                Descargar $id $tmp
                if ((Hash $tmp) -ne $info.sha256) { throw 'el archivo descargado no coincide (descarga incompleta)' }
                if ($rel -eq 'ACTUALIZAR.bat') {
                    Move-Item -LiteralPath $tmp -Destination (Join-Path $base 'ACTUALIZAR.nuevo') -Force   # lo reemplaza el .bat al salir
                } else {
                    try { Move-Item -LiteralPath $tmp -Destination $ruta -Force }
                    catch {
                        # en uso (p. ej. PRUEBAS.exe abierto): Windows deja renombrarlo, asi que se aparta y se pone el nuevo
                        $viejo = "$ruta.viejo"
                        if (Test-Path -LiteralPath $viejo) { Remove-Item -LiteralPath $viejo -Force -ErrorAction SilentlyContinue }
                        if (Test-Path -LiteralPath $viejo) { $viejo = "$ruta.$(Get-Random).viejo" }
                        Rename-Item -LiteralPath $ruta -NewName (Split-Path -Leaf $viejo)
                        Move-Item -LiteralPath $tmp -Destination $ruta -Force
                        Write-Host '        estaba abierto: la version anterior quedo como .viejo' -ForegroundColor Yellow
                    }
                    $it = Get-Item -LiteralPath $ruta
                    $cache[$rel] = @{ n = $it.Length; t = $it.LastWriteTimeUtc.Ticks; h = $info.sha256 }
                }
            } catch {
                $fallos++
                Write-Host "        ERROR: $($_.Exception.Message)" -ForegroundColor Red
                if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
            }
        }
        Write-Host ''
        if ($fallos -eq 0) {
            Copy-Item -LiteralPath $tmpVersion -Destination $rutaVersionLocal -Force
            Write-Host (" Listo: PRUEBAS actualizado a la version {0}." -f $remoto.version) -ForegroundColor Green
        } else {
            Write-Host " Terminado con $fallos error(es). Vuelve a ejecutar ACTUALIZAR.bat para reintentar." -ForegroundColor Yellow
        }
    }
    ($cache | ConvertTo-Json -Compress) | Set-Content -LiteralPath $rutaCache -Encoding UTF8
} catch {
    Write-Host ''
    Write-Host " No se pudo actualizar: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ' Revisa la conexion a internet y vuelve a intentarlo.'
}
