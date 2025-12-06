@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 > nul 
:: Intenta forzar la codificación UTF-8 para evitar caracteres extraños

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
:: CONFIGURACION INICIAL Y CONEXIÓN AUTOMÁTICA WI-FI
:: =========================================================================================================

cls
set "USBDrive=%~d0\Pruebas"
set "WIFI_PROFILE_PATH=%USBDrive%\ProgramData\WIFI.xml"

if not exist "%USBDrive%\" (
    echo Error: La unidad "%~d0" no se encuentra o no contiene la carpeta "Pruebas".
    pause
    exit /b 1
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
echo --- 0. Ejecutar TODAS las pruebas en ORDEN
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
echo --- 16. ESTADO DE VIDA DEL DISCO (HDS - Se abre con opcion 0)
echo --- 17. ESTADO DE VIDA DEL DISCO (CDI - Se abre con opcion 0)
echo --- 18. PRUEBA SSD (HD Tune Pro - Se abre con opcion 0)
echo --- 19. Informe de Bateria (AUTOMATICO)
echo --- 20. AIDA64 (AUTOMATICO)
echo --- 21. Configurar Wi-Fi por defecto
echo --- 22. Prueba de estres de la CPU 
echo --- 23. Prueba de estres de la GPU NUCLEO
echo --- 24. Prueba de estres de la GPU MEMORIA

echo.
set /p "choice=Elige una opcion (0 para todas, o el numero de la prueba): "

if "%choice%"=="0" goto all_tests
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
if "%choice%"=="16" goto test_disco_hds_manual
if "%choice%"=="17" goto test_disco_cdi_manual
if "%choice%"=="18" goto test_ssd_hdtune_manual
if "%choice%"=="19" goto test_battery_report_manual
if "%choice%"=="20" goto test_aida64_manual
if "%choice%"=="21" goto configurar_wifi
if "%choice%"=="22" goto estres_cpu
if "%choice%"=="23" goto estres_gpu_nucleo
if "%choice%"=="24" goto estres_gpu_rams
echo Opcion invalida. Por favor, elige un numero del menu.
pause
goto menu

:: =========================================================================================================
:: ETIQUETA PARA EJECUTAR TODAS LAS PRUEBAS
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
echo === INICIANDO TAREAS EN SEGUNDO PLANO (¡RECUERDA CERRAR LAS VENTANAS DE DISCO!) ===
echo.

set "FullBatteryReportName=%ReportBaseName%_BATERY.html"
echo -> 1. Generando Informe de Bateria...
start "" /B powercfg /batteryreport /output "%USBDrive%\Informes\%FullBatteryReportName%"
echo -> (Proceso de bateria iniciado)

set "ReportName=%ReportBaseName%_AIDA.html"
echo -> 2. Generando Informe de AIDA64...
rmdir /s /q "%USBDrive%\ProgramData\aida64_All\data" >nul 2>&1
start "" /B "%USBDrive%\ProgramData\aida64_All\AIDA64EngineerPortable.exe" /R "%USBDrive%\Informes\%ReportName%" /HTML /QUICK /SILENT /EXIT

echo -> 3. Abriendo Hard Disk Sentinel...
start "" "%USBDrive%\ProgramData\HardDiskSentinel_All_Eng\HDSentinel.exe"

echo -> 4. Abriendo CrystalDiskInfo...
start "" "%USBDrive%\ProgramData\CrystalDiskInfo_All\DiskInfo32.exe"

echo -> 5. Abriendo HD Tune Pro...
rmdir /s /q "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\data" >nul 2>&1
start "" "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\HD Tune Pro.exe"

echo.
echo Los reportes y pruebas de disco se estan lanzando.
echo **DEBES REVISAR y CERRAR MANUALMENTE las 3 ventanas de DISCO (Sentinel, CDI, HD Tune) mientras avanzas.**
pause

goto test_teclado

:test_teclado
cls
echo =========================
echo === PASO 1: PRUEBA DE TECLADO ===
echo =========================
echo INSTRUCCION: Prueba CADA tecla, cierra el programa y presiona una tecla aqui.
echo.
start "" /WAIT "%USBDrive%\ProgramData\keyboardtestutility_All\keyboardtestutility.exe" -T:1 || echo Error al iniciar keyboardtestutility.exe
pause
if "%choice%"=="0" goto test_temperatura_HWMonitor
goto menu

:test_temperatura_HWMonitor
cls
echo =========================
echo === PASO 2: TEMPERATURA (CPU y GPU) - HWMonitor ===
echo =========================
echo INSTRUCCION: Revisa la temperatura, cierra el programa y presiona una tecla.
echo.
rmdir /s /q "%USBDrive%\ProgramData\HWMonitorPortable\Data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\HWMonitorPortable\HWMonitorPortable.exe"  || echo Error al iniciar HWMonitorPortable.exe
pause
if "%choice%"=="0" goto test_pantalla
goto menu

:test_pantalla
cls
echo =========================
echo === PASO 3: PRUEBA DE PANTALLA ===
echo =========================
echo INSTRUCCION: Busca pixeles muertos o fugas de luz. Cierra y presiona una tecla.
echo.
start "" /WAIT "%USBDrive%\ProgramData\IsMyLcdOK_All\IsMyLcdOK.exe" -8  || echo Error al iniciar IsMyLcdOK.exe
pause
if "%choice%"=="0" goto test_camara
goto menu

:test_camara
cls
echo =========================
echo === PASO 4: PRUEBA DE CAMARA ===
echo =========================
echo INSTRUCCION: Revisa que la camara funcione. Cierra la aplicacion y presiona una tecla.
echo.
start "" /WAIT microsoft.windows.camera: || echo Error al iniciar la aplicacion de Camara.
pause
if "%choice%"=="0" goto test_microfono
goto menu

:test_microfono
cls
echo =========================
echo === PASO 5: PRUEBA DE MICROFONO ===
echo =========================
echo INSTRUCCION: Graba algo para verificar el microfono. Cierra el programa y presiona una tecla.
echo.
start "" /WAIT "%USBDrive%\ProgramData\GRABACION\AudioRecorder.exe" || echo Error al iniciar AudioRecorder.exe
:: Elimina el mp3 del escritorio si existe
if exist "%USERPROFILE%\Desktop\Voice.mp3" (
    del /f /q "%USERPROFILE%\Desktop\Voice.mp3"
    echo Archivo Voice.mp3 eliminado del escritorio.
)
pause
if "%choice%"=="0" goto test_hdmi_vga
goto menu

:test_hdmi_vga
cls
echo =========================
echo === PASO 6: PRUEBA DE HDMI/VGA ===
echo =========================
echo INSTRUCCION: Conecta un monitor externo y verifica la imagen. Presiona una tecla.
echo.
pause
if "%choice%"=="0" goto test_carga
goto menu

:test_carga
cls
echo =========================
echo === PASO 7: CARGA ===
echo =========================
echo INSTRUCCION: Conecta el cargador y verifica que el equipo esta cargando. Presiona una tecla.
pause
if "%choice%"=="0" goto test_cable_red
goto menu

:test_cable_red
cls
echo =========================
echo === PASO 8: CABLE DE RED ===
echo =========================
echo INSTRUCCION: Conecta un cable de red y verifica la conectividad. Presiona una tecla.
pause
if "%choice%"=="0" goto test_wifi_manual
goto menu

:test_wifi_manual
cls
echo =========================
echo === PASO 9: VERIFICACION DE WIFI (MANUAL) ===
echo =========================
echo INSTRUCCION: Conectate manualmente a una red WiFi y verifica la navegacion. Presiona una tecla.
pause
if "%choice%"=="0" goto test_bluetooth
goto menu

:test_bluetooth
cls
echo =========================
echo === PASO 10: BLUETOOTH ===
echo =========================
echo INSTRUCCION: Empareja un dispositivo Bluetooth. Presiona una tecla.
pause
if "%choice%"=="0" goto test_usb_ports
goto menu

:test_usb_ports
cls
echo =========================
echo === PASO 11: PUERTOS USB ===
echo =========================
echo INSTRUCCION: Conecta una memoria USB a CADA puerto. Presiona una tecla.
pause
if "%choice%"=="0" goto test_sonido
goto menu

:test_sonido
cls
echo =========================
echo === PASO 12: PRUEBA DE SONIDO (PARLANTES Y JACK DE AUDIO) ===
echo =========================
echo INSTRUCCION: Se reproducirá un video para verificar el sonido tanto en los parlantes como en auriculares conectados al jack de audio. Cierra el reproductor y presiona una tecla.
echo.
start "" "%USBDrive%\ProgramData\PRUEBA DE SONIDO.mp4" || echo Error al iniciar PRUEBA DE SONIDO.mp4
pause
if "%choice%"=="0" goto test_dvd_cd
goto menu

:test_dvd_cd
cls
echo =========================
echo === PASO 13: UNIDAD DVD/CD (si aplica) ===
echo =========================
echo INSTRUCCION: Inserta un CD/DVD y verifica su lectura. Presiona una tecla.
pause
if "%choice%"=="0" goto test_devmgmt
goto menu

:test_devmgmt
cls
echo =========================
echo === PASO 14: ADMINISTRADOR DE DISPOSITIVOS ===
echo =========================
echo INSTRUCCION: Revisa si hay algun error de controlador. Cierra el Administrador y presiona una tecla.
echo.
start "" /WAIT devmgmt.msc || echo Error al iniciar el Administrador de Dispositivos.
pause
if "%choice%"=="0" goto test_licencias
goto menu

:test_licencias
cls
echo =========================
echo === PASO 15: LICENCIAS Y ACTIVACION (Windows/Office) ===
echo =========================
echo.
echo [1] Activacion ONLINE (recomendada)
echo [0] Volver al menu
echo.
set /p "opt=Elige una opcion: "

if "%opt%"=="0" goto menu

if "%opt%"=="1" (
    cls
    echo ========================================
    echo  ACTIVACION ONLINE (MAS via irm)
    echo ========================================
    echo.
    echo INICIANDO LA ACTIVACION ONLINE...
    echo.
    echo -> Se abrira una nueva ventana para el proceso de activacion.
    echo -> Mientras se activa, puedes seguir con otras pruebas.
    start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& {irm https://get.activated.win | iex; Write-Host '--- PROCESO DE ACTIVACION INICIADO Y CERRANDOSE EN 20 SEGUNDOS ---'; Start-Sleep -Seconds 20; Exit}"
    echo.
    echo -> Volviendo al menu inmediatamente...
    goto menu
)

cls
echo Opcion no valida. Por favor, elige 1 o 0.
pause
goto test_licencias

:test_licencias_manual
goto test_licencias

:test_disco_hds_manual
cls
echo =========================
echo === ESTADO DE VIDA DEL DISCO (Hard Disk Sentinel) - MANUAL ===
start "" /WAIT "%USBDrive%\ProgramData\HardDiskSentinel_All_Eng\HDSentinel.exe" || echo Error al iniciar HDSentinel.exe
pause
goto menu

:test_disco_cdi_manual
cls
echo =========================
echo === ESTADO DE VIDA DEL DISCO (CrystalDiskInfo) - MANUAL ===
start "" /WAIT "%USBDrive%\ProgramData\CrystalDiskInfo_All\DiskInfo32.exe" || echo Error al iniciar DiskInfo32.exe
pause
goto menu

:test_ssd_hdtune_manual
cls
echo =========================
echo === PRUEBA SSD (HD Tune Pro) - MANUAL ===
echo =========================
echo INSTRUCCION: Realiza la prueba de lectura/escritura del SSD, cierra el programa y presiona una tecla.
echo.
rmdir /s /q "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\HDTune_All_Eng\HD Tune Pro 6.00\HD Tune Pro.exe" || echo Error al iniciar HD Tune Pro.exe
pause
goto menu

:test_battery_report_manual
cls
echo =========================
echo === INFORME DE BATERIA (MANUAL) ===
echo.
set /p "BatteryReportName=Por favor, ingresa el nombre para el informe (ej: 03-bateria-portatil): "
echo.
echo Generando informe de bateria...
if not exist "%USBDrive%\Informes\" mkdir "%USBDrive%\Informes\" 
set "FullBatteryReportName=BATTERYREPORT_%BatteryReportName%.html"
powercfg /batteryreport /output "%USBDrive%\Informes\%FullBatteryReportName%"
echo.
echo El informe de bateria se ha generado exitosamente.
pause
goto menu

:test_aida64_manual
cls
echo =========================
echo === AIDA64 (MANUAL) ===
echo.
set /p "FileName=Por favor, ingresa el nombre para el informe (ej: reporte-pc-cliente): "
echo.
echo Generando informe rapido...
rmdir /s /q "%USBDrive%\ProgramData\aida64_All\data" >nul 2>&1
if not exist "%USBDrive%\Informes\" mkdir "%USBDrive%\Informes\" 
set "ReportName=%FileName%.html"
start "" /WAIT "%USBDrive%\ProgramData\aida64_All\AIDA64EngineerPortable.exe" /R "%USBDrive%\Informes\%ReportName%" /HTML /QUICK /SILENT /EXIT
echo.
echo El informe de AIDA64 se ha generado exitosamente.
pause
goto menu

:configurar_wifi
cls
echo ==========================================================
echo === CONFIGURACION DE WI-FI POR DEFECTO ===
echo ==========================================================
echo.
set /p "ssid=Ingresa el nombre de la nueva red Wi-Fi (SSID): "
set /p "password=Ingresa la contrasena de la red: "
echo.
echo Creando el archivo de perfil Wi-Fi (WIFI.xml)...

(
    echo ^<?xml version="1.0"?^>
    echo ^<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"^>
    echo  ^<name^>%ssid%^</name^>
    echo  ^<SSIDConfig^>
    echo  ^<SSID^>
    echo  ^<name^>%ssid%^</name^>
    echo  ^</SSID^>
    echo  ^</SSIDConfig^>
    echo  ^<connectionType^>ESS^</connectionType^>
    echo  ^<connectionMode^>auto^</connectionMode^>
    echo  ^<MSM^>
    echo  ^<security^>
    echo  ^<authEncryption^>
    echo  ^<authentication^>WPA2PSK^</authentication^>
    echo  ^<encryption^>AES^</encryption^>
    echo  ^<useOneX^>false^</useOneX^>
    echo  ^</authEncryption^>
    echo  ^<sharedKey^>
    echo  ^<keyType^>passPhrase^</keyType^>
    echo  ^<protected^>false^</protected^>
    echo  ^<keyMaterial^>%password%^</keyMaterial^>
    echo  ^</sharedKey^>
    echo  ^</security^>
    echo  ^</MSM^>
    echo  ^<MacRandomization xmlns="http://www.microsoft.com/networking/WLAN/profile/v3"^>
    echo  ^<enableRandomization^>false^</enableRandomization^>
    echo  ^</MacRandomization^>
    echo ^</WLANProfile^>
) > "%WIFI_PROFILE_PATH%"

echo.
echo Archivo WIFI.xml creado exitosamente.
echo.
pause
goto menu


:estres_cpu
cls
echo =========================
echo === PASO 22: Prueba de estres de la CPU  ===
echo =========================
echo INSTRUCCION: PRIME 95 SE EJECUTA Y USA 100% EL PROCESADOR VERIFIQUE TEMPERATURAS Y EL COMPORTAMIENTO DEL PC.
echo.
start "" /WAIT "%USBDrive%\ProgramData\p95\prime95.exe" || echo Error al iniciar prime95.exe
pause
goto menu


:estres_gpu_nucleo
cls
echo =========================
echo === PASO 23: Prueba de estres de la GPU NUCLEO  ===
echo =========================
echo INSTRUCCION: PRIME 95 SE EJECUTA Y USA 100% EL PROCESADOR VERIFIQUE TEMPERATURAS Y EL COMPORTAMIENTO DEL PC.
echo.
start "" /WAIT "%USBDrive%\ProgramData\FurMark\FurMark_GUI.exe" || echo Error al iniciar FurMark_GUI.exe
pause
goto menu

:estres_estres_gpu_nucleo
cls
echo =========================
echo === PASO 23: Prueba de estres de la GPU NUCLEO  ===
echo =========================
echo INSTRUCCION: FurMark SE EJECUTA Y SE DEBE CONFIGURAR LA RESOLUCION .
echo.
start "" /WAIT "%USBDrive%\ProgramData\FurMark\FurMark_GUI.exe" || echo Error al iniciar FurMark_GUI.exe
pause
goto menu


:estres_gpu_rams
cls
echo =========================
echo === PASO 23: Prueba de estres de la GPU MEMORIA  ===
echo =========================
echo INSTRUCCION: OCCT SE EJECUTA Y USA 100% EL PROCESADOR VERIFIQUE TEMPERATURAS Y EL COMPORTAMIENTO DEL PC.
echo.
rmdir /s /q "%USBDrive%\ProgramData\OCCT\Data" >nul 2>&1
start "" /WAIT "%USBDrive%\ProgramData\OCCT\OCCTPortable.exe" || echo Error al iniciar OCCT.exe
pause
goto menu

:end_all_tests
cls
echo ===========================================
echo === TODAS LAS PRUEBAS HAN SIDO EJECUTADAS ===
echo ===========================================
echo.
echo El script ha finalizado. Puedes cerrar esta ventana.
echo.
pause

endlocal
exit /b 0
