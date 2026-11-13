@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 > nul 

:: =========================================================================================================
:: VERIFICACION Y SOLICITUD DE PERMISOS DE ADMINISTRADOR
:: =========================================================================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Solicitando permisos de administrador...
    echo.
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

:: =========================================================================================================
:: CONFIGURACION INICIAL
:: =========================================================================================================

cls
set "USBDrive=%~d0\Pruebas"
set "WIFI_PROFILE_PATH=%USBDrive%\ProgramData\WIFI.xml"

if not exist "%USBDrive%\" (
    echo Error: La unidad "%~d0" no se encuentra o no contiene la carpeta "Pruebas".
    pause
    exit /b 1
)

:: Inicialización de variables globales
set "running_all=0"
set "ReportBaseName=Reporte_General"

:: Inicialización de Arrays para el Checklist
for /L %%i in (1,1,26) do (
    set "test_results[%%i]="
    set "test_comments[%%i]="
)

echo.
echo ===========================================
echo === INICIO DE PRUEBAS DE DIAGNOSTICO ===
echo ===========================================
echo.

if exist "%WIFI_PROFILE_PATH%" (
    echo.
    echo === INTENTO DE CONEXIÓN WI-FI AUTOMÁTICA ===
    netsh wlan add profile filename="%WIFI_PROFILE_PATH%" >nul 2>&1
    if "%errorlevel%"=="0" (
        echo Perfil Wi-Fi agregado. Intentando conectar...
        netsh wlan connect name="WIFI" >nul 2>&1
        echo Conexión Wi-Fi inicializada.
    ) else (
        echo Error: No se pudo agregar el perfil Wi-Fi.
    )
    echo.
) else (
    echo No se encontro el archivo WIFI.xml. Omitiendo la conexion Wi-Fi automatica.
)

:menu
cls
echo ==========================================================
echo === MENU DE SELECCION DE PRUEBAS ===
echo ==========================================================
echo.
echo --- 0. Ejecutar TODAS las pruebas en ORDEN (Genera Reporte al final)
echo ----------------------------------------------------------
echo --- 1. Prueba de Teclado
echo --- 2. Prueba de Temperatura (HWMonitor)
echo --- 3. Prueba de Pantalla (IsMyLcdOK)
echo --- 4. Prueba de Camara (Windows App)
echo --- 5. Prueba de Microfono (AudioRecorder)
echo --- 6. Prueba de HDMI/VGA
echo --- 7. Carga de Bateria
echo --- 8. Prueba de Cable de Red
echo --- 9. Verificacion de WiFi (Manual)
echo --- 10. Prueba de Bluetooth
echo --- 11. Prueba de Puertos USB
echo --- 12. Prueba de Sonido (Parlantes y Jack de Audio)
echo --- 13. Prueba de Unidad DVD/CD
echo --- 14. Administrador de Dispositivos (Controladores)
echo ----------------------------------------------------------
echo --- 15. ACTIVACION DE LICENCIAS (Windows/Office)
echo ----------------------------------------------------------
echo --- 16. Prueba de Touchpad
echo ----------------------------------------------------------
echo --- 17. ESTADO DE VIDA DEL DISCO (HDS - Se abre con opcion 0)
echo --- 18. ESTADO DE VIDA DEL DISCO (CDI - Se abre con opcion 0)
echo --- 19. PRUEBA SSD (HD Tune Pro - Se abre con opcion 0)
echo --- 20. Informe de Bateria (AUTOMATICO)
echo --- 21. AIDA64 (AUTOMATICO)
echo --- 22. Configurar Wi-Fi por defecto
echo --- 23. Prueba de estres de la CPU 
echo --- 24. Prueba de estres de la GPU NUCLEO
echo --- 25. Prueba de estres de la GPU MEMORIA
echo ---------------------------------------------------------- 
echo --- 99. GENERAR REPORTE CHECKLIST ^(Manual^)
echo ==========================================================
echo.

set /p "choice=Elige una opcion (0 para todas, o el numero de la prueba): "

if "%choice%"=="0" (
    set "running_all=1"
    goto all_tests
)

if "%choice%"=="1" goto test_teclado
if "%choice%"=="2" goto test_temperatura_HWMonitor
if "%choice%"=="3" goto test_pantalla
if "%choice%"=="4" goto test_camara
if "%choice%"=="5" goto test_microfono
if "%choice%"=="6" goto test_hdmi_vga
if "%choice%"=="7" goto test_carga
if "%choice%"=="8" goto test_cable_red
if "%choice%"=="9" goto test_wifi_manual
if "%choice%"=="10" goto test_bluetooth
if "%choice%"=="11" goto test_usb_ports
if "%choice%"=="12" goto test_sonido
if "%choice%"=="13" goto test_dvd_cd
if "%choice%"=="14" goto test_devmgmt
if "%choice%"=="15" goto test_licencias
if "%choice%"=="16" goto test_touchpad
if "%choice%"=="17" goto test_disco_hds_manual
if "%choice%"=="18" goto test_disco_cdi_manual
if "%choice%"=="19" goto test_ssd_hdtune_manual
if "%choice%"=="20" goto test_battery_report_manual
if "%choice%"=="21" goto test_aida64_manual
if "%choice%"=="22" goto configurar_wifi
if "%choice%"=="23" goto estres_cpu
if "%choice%"=="24" goto estres_gpu_nucleo
if "%choice%"=="25" goto estres_gpu_rams
if "%choice%"=="99" (
    cls
    echo =====================================================
    echo === GENERAR REPORTE MANUAL ===
    echo =====================================================
    echo.
    set "order_manual="
    set /p "order_manual=Numero de orden ^(Ej: E123^): "
    if not defined order_manual (
        echo ERROR: Debes ingresar un nombre para el archivo.
        pause
        goto menu
    )
    set "ReportBaseName=!order_manual!"
    call :generate_report
    goto menu
)

echo Opcion invalida.
pause
goto menu

:: =========================================================================================================
:: SECUENCIA AUTOMATICA (OPCION 0)
:: =========================================================================================================
:all_tests
cls
echo =================================================
echo === INICIO AUTOMATICO DE PRUEBAS (Opcion 0) ===
echo =================================================
echo.

:get_order_number
set "order_number="
echo =====================================================
echo === SOLICITUD DE NOMBRE DE ARCHIVOS DE REPORTES ===
echo =====================================================
echo.
set /p "order_number=Numero de orden (Ej: E123 o S456): "

if not defined order_number (
    echo.
    echo ERROR: Debes ingresar el numero de orden.
    pause
    goto get_order_number
)

set "ReportBaseName=%order_number%"
echo.
echo Los reportes se nombraran con la base: %ReportBaseName%
echo.

if not exist "%USBDrive%\Informes\" mkdir "%USBDrive%\Informes\"

echo.
echo === INICIANDO TAREAS EN SEGUNDO PLANO ===
echo.

set "FullBatteryReportName=%ReportBaseName%_BATERY.html"
start "" /B powercfg /batteryreport /output "%USBDrive%\Informes\%FullBatteryReportName%"

set "ReportName=%ReportBaseName%_AIDA.html"
rmdir /s /q "%USBDrive%\ProgramData\aida64_All\data" >nul 2>&1
start "" /B "%USBDrive%\ProgramData\aida64_All\AIDA64EngineerPortable.exe" /R "%USBDrive%\Informes\%ReportName%" /HTML /QUICK /SILENT /EXIT

start "" "%USBDrive%\ProgramData\HardDiskSentinel_All_Eng\HDSentinel.exe"
start "" "%USBDrive%\ProgramData\CrystalDiskInfo_All\DiskInfo32.exe"
rmdir /s /q "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\data" >nul 2>&1
start "" "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\HD Tune Pro.exe"

echo.
echo Los reportes y pruebas de disco se estan lanzando.
pause

goto test_teclado

:test_teclado
cls
echo =========================
echo === PASO 1: PRUEBA DE TECLADO ===
echo =========================
start "" /WAIT "%USBDrive%\ProgramData\keyboardtestutility_All\keyboardtestutility.exe" -T:1 || echo Error al iniciar keyboardtestutility.exe
pause
call :check_test 1 "TECLADO"
if "%running_all%"=="1" goto test_touchpad
goto menu

:test_touchpad
cls
echo =========================
echo === PASO 2: PRUEBA DE TOUCHPAD ===
echo =========================
echo Mueve el puntero y verifica los clics izquierdo y derecho.
pause
call :check_test 16 "TOUCHPAD"
if "%running_all%"=="1" goto test_temperatura_HWMonitor
goto menu

:test_temperatura_HWMonitor
cls
echo =========================
echo === PASO 3: TEMPERATURA (CPU y GPU) ===
echo =========================
rmdir /s /q "%USBDrive%\ProgramData\HWMonitorPortable\Data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\HWMonitorPortable\HWMonitorPortable.exe" || echo Error al iniciar HWMonitorPortable.exe
pause
call :check_test 2 "TEMPERATURA CPU/GPU"
if "%running_all%"=="1" goto test_pantalla
goto menu

:test_pantalla
cls
echo =========================
echo === PASO 4: PRUEBA DE PANTALLA ===
echo =========================
start "" /WAIT "%USBDrive%\ProgramData\IsMyLcdOK_All\IsMyLcdOK.exe" -8 || echo Error al iniciar IsMyLcdOK.exe
pause
call :check_test 3 "PANTALLA"
if "%running_all%"=="1" goto test_camara
goto menu

:test_camara
cls
echo =========================
echo === PASO 5: PRUEBA DE CAMARA ===
echo =========================
start "" /WAIT microsoft.windows.camera: || echo Error al iniciar la aplicacion de Camara.
pause
call :check_test 4 "CAMARA"
if "%running_all%"=="1" goto test_microfono
goto menu

:test_microfono
cls
echo =========================
echo === PASO 6: PRUEBA DE MICROFONO ===
echo =========================
start "" /WAIT "%USBDrive%\ProgramData\GRABACION\AudioRecorder.exe" || echo Error al iniciar AudioRecorder.exe
pause
call :check_test 5 "MICROFONO"
if "%running_all%"=="1" goto test_hdmi_vga
goto menu

:test_hdmi_vga
cls
echo =========================
echo === PASO 7: PRUEBA DE HDMI/VGA ===
echo =========================
pause
call :check_test 6 "HDMI/VGA"
if "%running_all%"=="1" goto test_carga
goto menu

:test_carga
cls
echo =========================
echo === PASO 8: CARGA ===
echo =========================
pause
call :check_test 7 "CARGA BATERIA"
if "%running_all%"=="1" goto test_cable_red
goto menu

:test_cable_red
cls
echo =========================
echo === PASO 9: CABLE DE RED ===
echo =========================
pause
call :check_test 8 "CABLE RED"
if "%running_all%"=="1" goto test_wifi_manual
goto menu

:test_wifi_manual
cls
echo =========================
echo === PASO 10: WIFI (MANUAL) ===
echo =========================
pause
call :check_test 9 "WIFI MANUAL"
if "%running_all%"=="1" goto test_bluetooth
goto menu

:test_bluetooth
cls
echo =========================
echo === PASO 11: BLUETOOTH ===
echo =========================
pause
call :check_test 10 "BLUETOOTH"
if "%running_all%"=="1" goto test_usb_ports
goto menu

:test_usb_ports
cls
echo =========================
echo === PASO 12: PUERTOS USB ===
echo =========================
pause
call :check_test 11 "PUERTOS USB"
if "%running_all%"=="1" goto test_sonido
goto menu

:test_sonido
cls
echo =========================
echo === PASO 13: PRUEBA DE SONIDO ===
echo =========================
start "" "%USBDrive%\ProgramData\PRUEBA DE SONIDO.mp4"
pause
call :check_test 12 "SONIDO"
if "%running_all%"=="1" goto test_dvd_cd
goto menu

:test_dvd_cd
cls
echo =========================
echo === PASO 14: UNIDAD DVD/CD ===
echo =========================
pause
call :check_test 13 "DVD/CD"
if "%running_all%"=="1" goto test_devmgmt
goto menu

:test_devmgmt
cls
echo =========================
echo === PASO 15: ADMINISTRADOR DE DISPOSITIVOS ===
echo =========================
start "" /WAIT devmgmt.msc
pause
call :check_test 14 "CONTROLADORES"
if "%running_all%"=="1" goto test_licencias
goto menu

:test_licencias
cls
echo =========================
echo === PASO 16: LICENCIAS Y ACTIVACION ===
echo =========================
echo.
echo [1] Activacion ONLINE
echo [0] Continuar
echo.
set /p "opt=Elige una opcion: "
if "%opt%"=="1" start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& {irm https://get.activated.win | iex; Start-Sleep -Seconds 20}"
call :check_test 15 "LICENCIAS"
if "%running_all%"=="1" goto resumen_discos_final
goto menu

:resumen_discos_final
cls
echo =======================================================
echo === RESUMEN FINAL DISCOS ===
echo =======================================================
call :check_test 25 "ESTADO GENERAL HDD (HDS+CDI)"
call :check_test 26 "ESTADO GENERAL SSD (HDTune)"
call :generate_report
set "running_all=0"
goto menu

:: =========================================================================================================
:: FUNCIONES MANUALES
:: =========================================================================================================
:test_disco_hds_manual
start "" /WAIT "%USBDrive%\ProgramData\HardDiskSentinel_All_Eng\HDSentinel.exe"
goto menu
:test_disco_cdi_manual
start "" /WAIT "%USBDrive%\ProgramData\CrystalDiskInfo_All\DiskInfo32.exe"
goto menu
:test_ssd_hdtune_manual
rmdir /s /q "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\HD Tune Pro.exe"
goto menu
:test_battery_report_manual
cls
set /p "BatteryReportName=Nombre: "
powercfg /batteryreport /output "%USBDrive%\Informes\BATTERY_%BatteryReportName%.html"
pause
goto menu
:test_aida64_manual
cls
set /p "FileName=Nombre: "
rmdir /s /q "%USBDrive%\ProgramData\aida64_All\data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\aida64_All\AIDA64EngineerPortable.exe" /R "%USBDrive%\Informes\%FileName%.html" /HTML /QUICK /SILENT /EXIT
pause
goto menu
:configurar_wifi
cls
set /p "ssid=SSID: "
set /p "password=Password: "
(echo ^<?xml version="1.0"?^> & echo ^<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"^> & echo  ^<name^>%ssid%^</name^> & echo  ^<SSIDConfig^>^<SSID^>^<name^>%ssid%^</name^>^</SSID^>^</SSIDConfig^> & echo  ^<connectionType^>ESS^</connectionType^> & echo  ^<connectionMode^>auto^</connectionMode^> & echo  ^<MSM^>^<security^>^<authEncryption^>^<authentication^>WPA2PSK^</authentication^>^<encryption^>AES^</encryption^>^<useOneX^>false^</useOneX^>^</authEncryption^>^<sharedKey^>^<keyType^>passPhrase^</keyType^>^<protected^>false^</protected^>^<keyMaterial^>%password%^</keyMaterial^>^</sharedKey^>^</security^>^</MSM^> & echo ^</WLANProfile^>) > "%WIFI_PROFILE_PATH%"
pause
goto menu
:estres_cpu
start "" /WAIT "%USBDrive%\ProgramData\p95\prime95.exe"
call :check_test 22 "ESTRES CPU"
goto menu
:estres_gpu_nucleo
start "" /WAIT "%USBDrive%\ProgramData\FurMark\FurMark_GUI.exe"
call :check_test 23 "ESTRES GPU NUCLEO"
goto menu
:estres_gpu_rams
rmdir /s /q "%USBDrive%\ProgramData\OCCT\Data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\OCCT\OCCTPortable.exe"
call :check_test 24 "ESTRES GPU RAM"
goto menu

:: =========================================================================================================
:: SUBRUTINA: CHECKLIST INTERACTIVO
:: =========================================================================================================
:check_test
set "test_num=%~1"
set "test_name=%~2"
cls
echo =========================
echo === %test_name% ===
echo =========================
echo Resultado actual: !test_results[%test_num%]!
if defined test_comments[%test_num%] echo Comentario: !test_comments[%test_num%]!
echo.
:check_loop
echo Opciones: S=Si(OK) / N=No(FAIL) / A=No Aplica(N/A) / M=Modificar
set /p "check=¿FUNCIONA? : "
if /i "%check%"=="S" (set "test_results[%test_num%]=OK" & set "test_comments[%test_num%]=" & goto :eof)
if /i "%check%"=="N" (set "test_results[%test_num%]=FAIL" & set /p "comment=Detalle: " & set "test_comments[%test_num%]=!comment!" & goto :eof)
if /i "%check%"=="A" (set "test_results[%test_num%]=N/A" & set "test_comments[%test_num%]=No Aplica" & goto :eof)
if /i "%check%"=="M" (set /p "new_status=Estado (OK/FAIL/N/A): " & set "test_results[%test_num%]=!new_status!" & set /p "new_comment=Comentario: " & set "test_comments[%test_num%]=!new_comment!" & goto check_loop)
goto check_loop

:: =========================================================================================================
:: SUBRUTINA: GENERAR HTML (VERSION FINAL AUTO-AJUSTABLE)
:: =========================================================================================================
:generate_report
cls
echo =====================================================
echo [1/2] DETECTANDO HARDWARE Y GENERANDO REPORTE...
echo =====================================================

if "%ReportBaseName%"=="" set "ReportBaseName=REPORTE"
if not exist "%USBDrive%\Informes\" mkdir "%USBDrive%\Informes\"
set "ReportPath=%USBDrive%\Informes\%ReportBaseName%_CHECKLIST.html"

echo ^<!DOCTYPE html^>^<html^>^<head^>^<meta charset="UTF-8"^> > "%ReportPath%"
echo ^<style^> >> "%ReportPath%"
echo * { margin: 0; padding: 0; box-sizing: border-box; } >> "%ReportPath%"
echo html, body { height: 100vh; width: 100vw; font-family: 'Segoe UI', Tahoma, sans-serif; background: #fff; overflow: hidden; display: flex; flex-direction: column; } >> "%ReportPath%"
echo .header { padding: 10px 20px; flex-shrink: 0; border-bottom: 2px solid #eee; } >> "%ReportPath%"
echo .hw { background: #f8f9fa; padding: 10px 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 11px; border-bottom: 1px solid #ccc; flex-shrink: 0; } >> "%ReportPath%"
echo .hw b { color: #007bff; text-transform: uppercase; font-size: 10px; } >> "%ReportPath%"
echo .table { flex-grow: 1; display: flex; flex-direction: column; background: #fff; overflow: hidden; } >> "%ReportPath%"
echo .row { display: flex; width: 100%%; border-bottom: 1px solid #eee; flex: 1; align-items: center; min-height: 0; } >> "%ReportPath%"
echo .row.head { background: #333 !important; color: white !important; flex: 0 0 35px; font-size: 12px; font-weight: bold; } >> "%ReportPath%"
echo .cell { padding: 0 12px; font-size: 13px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; height: 100%%; display: flex; align-items: center; } >> "%ReportPath%"
echo .c1 { width: 50px; justify-content: center; border-right: 1px solid rgba^(0,0,0,0.05^); } >> "%ReportPath%"
echo .c2 { width: 35%%; border-right: 1px solid rgba^(0,0,0,0.05^); } >> "%ReportPath%"
echo .c3 { width: 110px; justify-content: center; border-right: 1px solid rgba^(0,0,0,0.05^); } >> "%ReportPath%"
echo .c4 { flex-grow: 1; } >> "%ReportPath%"
echo ^</style^>^</head^>^<body^> >> "%ReportPath%"

echo ^<div class="header"^>^<h1 style="font-size:22px"^>CHECKLIST: %ReportBaseName%^</h1^>^<p style="color:#888; font-size:11px"^>Generado: %date% %time%^</p^>^</div^> >> "%ReportPath%"
echo ^<div class="hw"^> >> "%ReportPath%"
for /f "tokens=2 delims==" %%a in ('wmic computersystem get model /value 2^>nul') do echo ^<div^>^<b^>MODELO:^</b^> %%a^</div^> >> "%ReportPath%"
for /f "tokens=2 delims==" %%a in ('wmic bios get serialnumber /value 2^>nul') do echo ^<div^>^<b^>SERIAL:^</b^> %%a^</div^> >> "%ReportPath%"
for /f "tokens=2 delims==" %%a in ('wmic cpu get name /value 2^>nul') do echo ^<div^>^<b^>CPU:^</b^> %%a^</div^> >> "%ReportPath%"
for /f "delims=" %%a in ('powershell -command "$m=Get-CimInstance Win32_PhysicalMemory; $t=[math]::round(($m|Measure-Object Capacity -Sum).Sum/1GB); $s=switch($m[0].MemoryType){20{'DDR2'} 21{'DDR2'} 24{'DDR3'} 26{'DDR4'} default{'RAM'}}; '{0} GB {1}' -f $t,$s" 2^>nul') do echo ^<div^>^<b^>RAM:^</b^> %%a^</div^> >> "%ReportPath%"
for /f "tokens=2 delims==" %%a in ('wmic path win32_VideoController get name /value 2^>nul') do echo ^<div^>^<b^>GPU:^</b^> %%a^</div^> >> "%ReportPath%"
for /f "tokens=2 delims==" %%a in ('wmic os get caption /value 2^>nul') do echo ^<div^>^<b^>SISTEMA:^</b^> %%a^</div^> >> "%ReportPath%"
for /f "delims=" %%a in ('powershell -command "(Get-CimInstance Win32_DiskDrive | foreach { '{0} ({1}GB)' -f $_.Model, [math]::round($_.Size/1GB) }) -join ' | '" 2^>nul') do echo ^<div style="grid-column: span 2; border-top: 1px solid #eee; padding-top:2px"^>^<b^>ALMACENAMIENTO:^</b^> %%a^</div^> >> "%ReportPath%"
echo ^</div^> >> "%ReportPath%"

echo ^<div class="table"^> >> "%ReportPath%"
echo ^<div class="row head"^>^<div class="cell c1"^>#^</div^>^<div class="cell c2"^>PRUEBA^</div^>^<div class="cell c3"^>ESTADO^</div^>^<div class="cell c4"^>COMENTARIO^</div^>^</div^> >> "%ReportPath%"

for /L %%i in (1,1,16) do (
    set "r=!test_results[%%i]!"
    set "c=!test_comments[%%i]!"
    if %%i==1 set "n=Teclado"
    if %%i==2 set "n=Temperatura"
    if %%i==3 set "n=Pantalla"
    if %%i==4 set "n=Camara Web"
    if %%i==5 set "n=Microfono"
    if %%i==6 set "n=Video HDMI/VGA"
    if %%i==7 set "n=Carga Bateria"
    if %%i==8 set "n=Puerto Red"
    if %%i==9 set "n=WiFi"
    if %%i==10 set "n=Bluetooth"
    if %%i==11 set "n=Puertos USB"
    if %%i==12 set "n=Audio/Jack"
    if %%i==13 set "n=DVD/CD"
    if %%i==14 set "n=Controladores"
    if %%i==15 set "n=Licencias"
    if %%i==16 set "n=Touchpad"

    set "cl=background-color: #fff3cd; color: #856404;"
    if /i "!r!"=="OK" set "cl=background-color: #d4edda; color: #155724;"
    if /i "!r!"=="FAIL" set "cl=background-color: #f8d7da; color: #721c24;"
    if /i "!r!"=="N/A" set "cl=background-color: #d1ecf1; color: #0c5460;"
    echo ^<div class="row" style="!cl!"^>^<div class="cell c1"^>%%i^</div^>^<div class="cell c2"^>!n!^</div^>^<div class="cell c3"^>!r!^</div^>^<div class="cell c4"^>!c!^</div^>^</div^> >> "%ReportPath%"
)

for /L %%i in (25,1,26) do (
    set "r=!test_results[%%i]!" & set "c=!test_comments[%%i]!"
    if %%i==25 set "n=Salud HDD"
    if %%i==26 set "n=Salud SSD"
    set "cl=background-color: #fff3cd; color: #856404;"
    if /i "!r!"=="OK" set "cl=background-color: #d4edda; color: #155724;"
    if /i "!r!"=="FAIL" set "cl=background-color: #f8d7da; color: #721c24;"
    if /i "!r!"=="N/A" set "cl=background-color: #d1ecf1; color: #0c5460;"
    echo ^<div class="row" style="!cl!"^>^<div class="cell c1"^>%%i^</div^>^<div class="cell c2"^>!n!^</div^>^<div class="cell c3"^>!r!^</div^>^<div class="cell c4"^>!c!^</div^>^</div^> >> "%ReportPath%"
)
echo ^</div^>^</body^>^</html^> >> "%ReportPath%"
start "" "%ReportPath%"
goto :eof
