🔗 Enlace de Descarga Directa
Haga clic en el siguiente enlace para descargar el archivo ZIP/RAR que contiene la carpeta /Pruebas/ completa y funcional:

[LINK DE DESCARGA AQUÍ] (https://drive.google.com/drive/folders/1WuQ9IhrIqhadb2H8vC64Akm4YXoNaR2h?usp=sharing)

🛠️ Suite de Diagnóstico y Pruebas para Servicio Técnico (PRUEBAS v10)
Esta herramienta es un suite de diagnóstico por lotes (.bat) diseñado para estandarizar y optimizar la verificación y documentación del estado de hardware y software en equipos informáticos.

Su principal objetivo es garantizar que cada componente sea probado y que se genere evidencia clara y organizada para el reporte final de servicio.

🛑 Requisito de Ejecución y Estructura del Directorio
El script solo funcionará si toda la estructura de archivos (incluyendo programas portables y carpetas de datos) se mantiene dentro del directorio /Pruebas/.

Archivo Principal: PRUEBAS v10.BAT

Ubicación Requerida: Debe estar dentro de la carpeta /Pruebas/ en la raíz de cualquier unidad (ej: C:\Pruebas\PRUEBAS v10.BAT).

Estructura Mínima Requerida:

/Pruebas/

├── Informes/            <- Aquí se guardan los reportes (AIDA64, Batería, etc.)

├── ProgramData/         <- Contiene todos los ejecutables portables (HWMonitor, Prime95, etc.)

└── PRUEBAS v10.BAT      <- Archivo principal del menú

🚀 Flujo de Trabajo Automatizado (Opción 0)
Al seleccionar la Opción 0 (Ejecutar TODAS las pruebas en ORDEN), el programa inicia un flujo de trabajo optimizado:

Solicitud de Orden: Pide un Número de Orden (Ej: E123) para nombrar todos los archivos de reporte.

Generación de Informes en Segundo Plano: Lanza automáticamente procesos no interactivos:

Informe de Batería (powercfg /batteryreport).

Informe AIDA64 (/QUICK /SILENT /EXIT).

Diagnóstico de Discos Concurrente: Abre automáticamente utilidades como Hard Disk Sentinel, CrystalDiskInfo y HD Tune Pro para que el técnico pueda iniciar las pruebas de SSD/HDD mientras comienza la secuencia de verificación manual.

📋 Secuencia de Pruebas Manuales Guiadas (Pasos 1-14)
El script guía al técnico paso a paso a través de las verificaciones esenciales, abriendo las herramientas necesarias y esperando la confirmación manual:

Paso 1: Prueba de Teclado (keyboardtestutility).

Paso 2: Temperatura (CPU y GPU) con HWMonitor.

Paso 3: Prueba de Pantalla (IsMyLcdOK) para píxeles muertos/fugas de luz.

Paso 4: Prueba de Cámara (Aplicación de Windows).

Paso 5: Prueba de Micrófono (Grabación y AudioRecorder).

Paso 6: Prueba de Puertos HDMI/VGA (Conexión de monitor externo).

Paso 7: Prueba de Carga (Verificar conexión del cargador).

Paso 8: Prueba de Cable de Red.

Paso 9: Verificación de WiFi (Conexión manual y navegación).

Paso 10: Prueba de Bluetooth (Emparejar dispositivo).

Paso 11: Prueba de Puertos USB (Conexión de memoria a cada puerto).

Paso 12: Prueba de Sonido (Parlantes y Jack de Audio).

Paso 13: Prueba de Unidad DVD/CD (Si aplica).

Paso 14: Administrador de Dispositivos (devmgmt.msc) para revisar controladores.

⚙️ Configuración y Utilidades Avanzadas
Opción 21: Configurar Wi-Fi por defecto

Función: Crea un archivo WIFI.xml en la ruta /ProgramData/.

Propósito: Permite que el script se conecte automáticamente a la red Wi-Fi configurada cada vez que se ejecute la secuencia de pruebas, eliminando la necesidad de ingresar la contraseña repetidamente.

Opción 22: Prueba de Estrés CPU

Herramienta: Lanza Prime95.

Objetivo: Verificar la estabilidad de la CPU bajo carga intensa (100% de uso) y monitorear temperaturas máximas.

Opción 23: Prueba de Estrés GPU Núcleo

Herramienta: Lanza FurMark.

Objetivo: Carga intensa del núcleo del procesador gráfico para detectar fallos o throttling.

Opción 24: Prueba de Estrés GPU Memoria

Herramienta: Lanza OCCT.

Objetivo: Prueba específica para la memoria de video (VRAM) de la tarjeta gráfica para detectar errores de integridad.

📂 Informes y Evidencia
El programa se enfoca en la documentación:

Registro Fotográfico: El script recuerda al técnico que debe tomar fotos de evidencia de componentes que no pueden ser probados por software (como los puertos físicos).

Ubicación de Reportes: Todos los informes generados (AIDA64, Batería, etc.) se almacenan en:

/Pruebas/Informes/

🚀 Flujo de Trabajo (Opción 0)
Al seleccionar la Opción 0, el programa inicia un flujo automatizado:

Identificación de Orden: Solicita un número (ej. E123) para nombrar todos los informes.

Segundo Plano: Lanza automáticamente powercfg (Batería) y AIDA64 en modo silencioso.

Diagnóstico de Discos: Abre Hard Disk Sentinel, CrystalDiskInfo y HD Tune Pro simultáneamente para que analicen el estado de salud mientras avanzas con las pruebas manuales.

📋 Secuencia de Pruebas Manuales
El script guía al técnico paso a paso, abriendo la herramienta necesaria y solicitando el estado (OK / FAIL / N/A):

Paso 1: Prueba de Teclado.

Paso 16 (NUEVO): Prueba de Touchpad (Verificación de puntero y botones).

Pasos 2-5: Temperatura (HWMonitor), Pantalla (IsMyLcdOK), Cámara y Micrófono.

Pasos 6-11: HDMI/VGA, Carga de Batería, Cable de Red, WiFi, Bluetooth y Puertos USB.

Pasos 12-14: Sonido (Parlantes/Jack), Unidad DVD y Administrador de Dispositivos.

Paso 15: Activación de Licencias (Windows/Office vía MAS).

💎 Características Especiales Implementadas
🖥️ Motor de Detección de Hardware (Zero-Error)
Se ha mejorado la extracción de datos mediante wmic y PowerShell para evitar cierres inesperados:

Detección de GPU: Nombre exacto de la tarjeta de video (Intel, NVIDIA, AMD).

Tipo de RAM: Identifica automáticamente si es DDR3, DDR4 o DDR5.

Almacenamiento: Muestra todos los modelos de disco y sus capacidades en el encabezado.

📊 Reporte HTML "Elastic Design"
El informe final generado en /Informes/ cuenta con tecnología CSS Flexbox:

Ajuste Automático: El checklist ocupa exactamente el 100% de la pantalla sin necesidad de hacer scroll ni zoom, sin importar si el monitor es de 13" o 4K.

Código de Colores Profesional: Verde para estados OK, Rojo para FALLAS (con detalle del técnico) y Azul para No Aplica.

⚙️ Herramientas de Estrés (Opciones 22-24)
CPU: Prime95 para estabilidad térmica al 100%.

GPU Núcleo: FurMark para detectar throttling o apagados.

GPU Memoria: OCCT para verificar la integridad de la VRAM.

📂 Evidencia y Documentación
Todos los resultados se consolidan en la carpeta /Pruebas/Informes/. Se recomienda al técnico realizar el registro fotográfico de los daños físicos que el software no puede detectar (puertos rotos, bisagras, etc.) para complementar el checklist generado.

Desarrollado para optimizar el soporte técnico de nivel componente. 🛠️✅
