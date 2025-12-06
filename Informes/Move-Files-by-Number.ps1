# Definir la carpeta de destino principal
$DestinationFolder = "C:\Users\PC\OneDrive\FOTOS EVIDENCIA"

# Definir la carpeta de origen (la carpeta donde se encuentra este script)
# Nota: La variable $PSScriptRoot contiene la ruta del script actual.
$SourceFolder = $PSScriptRoot

# Expresión Regular para encontrar el primer número de 1 o más dígitos en el nombre del archivo (sin extensión)
# Se busca un número sin importar los caracteres que lo rodean.
$RegexPattern = '\d+'

Write-Host "Iniciando la organización de archivos desde: $SourceFolder"
Write-Host "Carpeta de destino principal: $DestinationFolder"
Write-Host "--------------------------------------------------------"

# 1. Crear la carpeta de destino principal si no existe
if (-not (Test-Path $DestinationFolder)) {
    Write-Host "Creando carpeta de destino: $DestinationFolder"
    New-Item -Path $DestinationFolder -ItemType Directory | Out-Null
}

# 2. Iterar sobre cada archivo en la carpeta de origen
# Se usa -File para asegurar que solo se procesen archivos, no subcarpetas.
Get-ChildItem -Path $SourceFolder -File | ForEach-Object {
    $File = $_
    $FileNameWithoutExtension = $File.BaseName
    
    # Intentar encontrar el número en el nombre del archivo
    $Match = [regex]::Match($FileNameWithoutExtension, $RegexPattern)
    
    # 3. Verificar si se encontró un número
    if ($Match.Success) {
        $Number = $Match.Value
        $TargetFolder = Join-Path -Path $DestinationFolder -ChildPath $Number
        
        Write-Host "Archivo: $($File.Name) -> Número identificado: $Number"
        
        # 4. Crear la carpeta de destino basada en el número si no existe
        if (-not (Test-Path $TargetFolder)) {
            Write-Host "   Creando subcarpeta: $TargetFolder"
            New-Item -Path $TargetFolder -ItemType Directory | Out-Null
        }
        
        # 5. Mover el archivo
        try {
            Move-Item -Path $File.FullName -Destination $TargetFolder -Force -ErrorAction Stop
            Write-Host "   Movido a: $TargetFolder" -ForegroundColor Green
        } catch {
            Write-Host "   ERROR al mover $($File.Name): $($_.Exception.Message)" -ForegroundColor Red
        }
    } else {
        Write-Host "Archivo: $($File.Name) -> No se encontró un número en el nombre. Saltando." -ForegroundColor Yellow
    }
    Write-Host "---"
}

Write-Host "Proceso de organización finalizado."

Write-Host "Proceso de organización finalizado."

# Agregar esta línea para que la ventana no se cierre inmediatamente
Write-Host "Presiona cualquier tecla para cerrar la ventana..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeypress") | Out-Null