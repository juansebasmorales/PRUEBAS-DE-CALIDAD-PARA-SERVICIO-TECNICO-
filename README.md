# PRUEBAS v22 — recorrido de diagnóstico con evidencia automática

`PRUEBAS.exe` guía al técnico por todas las pruebas de un equipo, **detecta sola** todo lo que se puede detectar
y **toma una foto de la pantalla** como evidencia de cada prueba. Al terminar deja el checklist en HTML con las
fotos, el informe de batería y el de AIDA64, todo en `Informes\<orden>\`.

## Estructura

```
PRUEBAS\
├── PRUEBAS.exe        <- el programa (pide administrador solo)
├── config.json        <- se crea la primera vez (técnico, carpeta de copia, rutas de herramientas)
├── ProgramData\       <- herramientas portables (no van en el repositorio)
└── Informes\<orden>\  <- checklist, fotos\, informes de batería y AIDA64, resultado.json
```

## Cómo funciona

1. Al abrir, ya empieza a detectar el hardware y la licencia y a conectar el Wi-Fi (`ProgramData\WIFI.xml`).
2. Escribe el **número de orden** y pulsa **INICIAR** (o Enter). Se minimiza y aparece una **barra flotante**.
3. En segundo plano: informe de batería, AIDA64 y HWMonitor (este registra los máximos de temperatura de todo el
   recorrido).
4. Cada prueba:
   - **Automática** (se resuelve sola y abre la ventana que lo demuestra para la foto): controladores,
     licencia de Windows, salud de discos (CrystalDiskInfo + Hard Disk Sentinel), Bluetooth, red, Wi-Fi, DVD (N/A si
     no hay), salud de batería.
   - **Se aprueba sola cuando la detecta**: touchpad (prueba propia), cargador, cable de red, Wi-Fi, monitor
     HDMI/VGA.
   - **Manual**: se abre la herramienta y el técnico pulsa **OK / FALLA / N/A** en la barra. Al pulsar se toma la
     foto con la herramienta en pantalla. Con FALLA pide qué falla. **FOTO EXTRA** agrega otra foto.
5. Al terminar queda la tabla de revisión: se puede cambiar cualquier estado, poner comentarios, **repetir una
   prueba** o seguir con las pendientes. El reporte se genera solo y con **GENERAR REPORTE** se vuelve a generar.

Si se cierra a la mitad, al escribir la misma orden pregunta si continuar donde quedó.

## config.json

- `carpeta_copia`: si se llena (p. ej. `C:\\Users\\PC\\OneDrive\\FOTOS EVIDENCIA`), al generar el reporte se copia
  la carpeta de la orden allí.
- `umbral_bateria`: % de salud mínimo para marcar la batería OK (60 por defecto).
- `herramientas`: ruta (relativa a `ProgramData`) y argumentos de cada herramienta.

## Página de órdenes de servicio

En la pantalla principal, **Página de órdenes → Configurar**: pegar la clave `tp_…` (la crea el administrador en
la página: Ajustes → Programa de pruebas de calidad → Crear clave), ponerle un **PIN del taller** (mínimo 6) y el
nombre de la USB, y **Probar conexión**. La clave queda **cifrada con el PIN** en `config.json` (AES-256 + HMAC);
sin el PIN no sirve.

Con la página configurada, **INICIAR** pide el PIN (una vez por sesión) y busca la orden **por la serie del
equipo**. Si no la encuentra, se escribe el número de orden (`OS-0012` o `12`) o se escanea el QR del comprobante.
Se confirma la orden y si son pruebas de **entrada** o de **salida**. Al terminar el recorrido se envían solos los
resultados, el **reporte PDF con todas las fotos**, las fotos de cada prueba (primero las de las fallas) y los
informes de batería y AIDA64 en PDF (con las claves de producto tapadas). Si no hay internet queda en cola y se
reintenta con el mismo envío (no duplica). En la revisión está el botón **ENVIAR A LA PÁGINA** para mandarlo de
nuevo. Cada envío queda anotado en `Informes\<orden>\pagina_registro.txt`.

## Actualizar (en cada USB o PC)

Doble clic en **`ACTUALIZAR.bat`**. Compara con la carpeta pública de Google Drive y baja **solo los archivos que
cambiaron** (comprueba cada uno con SHA-256). No toca `Informes`, `config.json` ni `WIFI.xml`. Si `PRUEBAS.exe`
está abierto, el anterior queda como `PRUEBAS.exe.viejo`. La primera vez revisa todo (1-2 minutos); después tarda
unos segundos.

## Compilar y publicar (solo en el PC de desarrollo)

```
py -m pip install nuitka pillow zstandard
py construir_exe.py
py publicar.py
```

`publicar.py` copia lo que cambió a `Z:\Mi unidad\PRUEBASv2` (Google Drive para escritorio lo sube) y escribe
`version.json`, la lista que usa `ACTUALIZAR.bat`. `py publicar.py --ver` muestra qué se publicaría sin copiar, y
`py publicar.py --sobrantes` lista lo que hay en Drive y no es parte del programa.
