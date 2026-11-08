# scripts\correr_prueba_B5.ps1
# Prueba B5 para dejar corriendo de noche: P1 y P2 con RAG en modo verificacion, evaluacion de cada una y evaluacion agregada.
# Sin RAG y la repeticion de estabilidad NO van aca (van en la corrida final).
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\correr_prueba_B5.ps1
#
# Toda la salida va a datos\Resultados\prueba_B5_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script: (una funcion que devuelve la salida
# de consola mezcla texto con sus resultados, y ese fue el error del script anterior).
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:ofertas = @(
    @{ Nombre = "P1"; Archivo = "datos\ProyectoAnalizar\P1_oferta_TBP01.pdf" },
    @{ Nombre = "P2"; Archivo = "datos\ProyectoAnalizar\P2_oferta_PH400.pdf" }
)
$script:log = Join-Path $script:raiz ("datos\Resultados\prueba_B5_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:json = @{}                                                              # oferta -> ruta del JSON del analisis (solo si salio bien)
$script:jsonActual = $null

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $script:log) | Out-Null
New-Item -ItemType File -Force -Path $script:log | Out-Null

filter Registrar {
    # Etapa de pipeline: agrega cada linea al log con Tee-Object (o con Add-Content si esta version de PowerShell no tiene -Append) y la deja pasar.
    if ($script:teeAppend) { $_ | Tee-Object -FilePath $script:log -Append }
    else { Add-Content -Path $script:log -Value $_; $_ }
}

function Escribir-Log {
    param([string]$Texto)
    $linea = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Texto
    $linea | Registrar | Out-Host
}

function Ejecutar-Python {
    # Corre python con los argumentos dados; cada linea va al log y a la consola. Deja el codigo de salida en $script:codigo
    # y, si la salida trae una linea "JSON: <ruta>", la ruta en $script:jsonActual. No devuelve nada.
    param([string[]]$Argumentos)
    $script:jsonActual = $null
    & $script:python @Argumentos 2>&1 | ForEach-Object {
        $linea = "$_"
        if ($linea -match '^JSON:\s+(.+)$') { $script:jsonActual = $Matches[1].Trim() }
        $linea
    } | Registrar | Out-Host
    $script:codigo = $LASTEXITCODE
}

function Medir-Etapa {
    # Ejecuta el bloque, anota su duracion en $script:etapas y escribe en el log si fallo. No devuelve nada.
    param([string]$Nombre, [scriptblock]$Bloque)
    Escribir-Log ("=== INICIO: {0} ===" -f $Nombre)
    $reloj = [System.Diagnostics.Stopwatch]::StartNew()
    try { & $Bloque | Out-Null }
    catch { Escribir-Log ("FALLO en {0}: {1}" -f $Nombre, $_.Exception.Message) }
    $reloj.Stop()
    $script:etapas[$Nombre] = [math]::Round($reloj.Elapsed.TotalSeconds, 1)
    Escribir-Log ("=== FIN: {0} ({1} s) ===" -f $Nombre, $script:etapas[$Nombre])
}

function Analizar-Oferta {
    param([hashtable]$Oferta)
    if (Test-Path $Oferta.Archivo) {
        Ejecutar-Python @("-m", "scripts.run_oferta", $Oferta.Archivo, "--oferta", $Oferta.Nombre)
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:json[$Oferta.Nombre] = $script:jsonActual }
        else { Escribir-Log ("FALLO: el analisis de {0} termino con codigo {1}; se sigue con la otra oferta." -f $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("FALLO: no existe {0}; se sigue con la otra oferta." -f $Oferta.Archivo) }
}

function Evaluar-Oferta {
    param([string]$Nombre)
    if ($script:json.ContainsKey($Nombre)) {
        Ejecutar-Python @("-m", "evaluacion.evaluar", "--resultado", $script:json[$Nombre], "--oferta", $Nombre)
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: la evaluacion de {0} termino con codigo {1}." -f $Nombre, $script:codigo) }
    }
    else { Escribir-Log ("{0}: sin analisis, no se evalua." -f $Nombre) }
}

function Evaluar-Agregado {
    if ($script:json.Count -ge 2) {
        $argumentos = @("-m", "evaluacion.evaluar", "--agregado")
        foreach ($o in $script:ofertas) { $argumentos += $script:json[$o.Nombre] }
        Ejecutar-Python $argumentos
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: la evaluacion agregada termino con codigo {0}." -f $script:codigo) }
    }
    else { Escribir-Log "Evaluacion agregada omitida: hace falta el analisis de las dos ofertas." }
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Prueba B5. Log: {0}" -f $script:log)

foreach ($o in $script:ofertas) {
    Medir-Etapa ("analisis {0}" -f $o.Nombre) { Analizar-Oferta $o }
}
foreach ($o in $script:ofertas) {
    Medir-Etapa ("evaluacion {0}" -f $o.Nombre) { Evaluar-Oferta $o.Nombre }
}
Medir-Etapa "evaluacion agregada" { Evaluar-Agregado }

$relojTotal.Stop()
Escribir-Log "=== TIEMPOS POR ETAPA ==="
foreach ($etapa in $script:etapas.Keys) {
    Escribir-Log ("{0,-24} {1,10} s  ({2})" -f $etapa, $script:etapas[$etapa], [timespan]::FromSeconds($script:etapas[$etapa]).ToString("hh\:mm\:ss"))
}
Escribir-Log ("Tiempo total: {0} s  ({1})" -f [math]::Round($relojTotal.Elapsed.TotalSeconds, 1), $relojTotal.Elapsed.ToString("hh\:mm\:ss"))
Escribir-Log "Log completo en: $($script:log)"
