@echo off
REM Definir la ruta del script de PowerShell (debe estar en la misma carpeta)
set "PsScript=%~dp0Move-Files-by-Number.ps1"

REM Comprobar si el script de PowerShell existe
if not exist "%PsScript%" (
    echo ERROR: No se encuentra el script de PowerShell:
    echo "%PsScript%"
    pause
    exit /b 1
)

REM Ejecutar el script de PowerShell con permisos de administrador.
REM La línea a continuacion eleva la ventana y ejecuta el script:

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%PsScript%\"' -Verb RunAs"

REM Nota: El script de PowerShell se abrirá en una nueva ventana con permisos de administrador.