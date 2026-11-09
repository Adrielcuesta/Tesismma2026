# scripts\cerrar_evaluacion.ps1
# Cierra la evaluacion de todas las configuraciones de un archivo de configuracion (el mismo de evaluacion\tabla_comparativa.py):
#   Para cada configuracion:
#     1. evaluar --resultado de cada oferta con JSON (genera <json>_extras.csv).
#     2. juez externo sobre todas las ofertas de la configuracion (un solo comando, un solo freno de gasto; genera <json>_juez.csv).
#     3. evaluar --resultado de nuevo (ahora con precision segun el juez, F1/F2 y kappa).
#   Al final: tabla comparativa y graficos en evaluacion\resultados_finales\.
#   Las ofertas sin JSON (ruta vacia o inexistente) se omiten y queda avisado.
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\cerrar_evaluacion.ps1 -Config evaluacion\config_tabla.json [-SoloHumo]
#
# -SoloHumo corre el juez con --max-items 5 por JSON (prueba de humo, gasto minimo).
# Toda la salida va a datos\Resultados\cerrar_evaluacion_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.
param([string]$Config, [switch]$SoloHumo)

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:log = Join-Path $script:raiz ("datos\Resultados\cerrar_evaluacion_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:gastoJuez = 0.0
$script:codigo = 0

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
    # Corre python con los argumentos dados; cada linea va al log y a la consola. Deja el codigo de salida en $script:codigo y suma al gasto
    # acumulado la linea "Gasto del juez: <usd> USD" si la salida la trae. No devuelve nada.
    param([string[]]$Argumentos)
    & $script:python @Argumentos 2>&1 | ForEach-Object {
        $linea = "$_"
        if ($linea -match '^\s*Gasto del juez:\s+([0-9]+(\.[0-9]+)?)\s+USD') {
            $script:gastoJuez += [double]::Parse($Matches[1], [System.Globalization.CultureInfo]::InvariantCulture)
        }
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

function Jsons-De-Configuracion {
    # Hashtable oferta -> ruta con los JSON que existen de una configuracion (las demas se avisan y se omiten). Se guarda en $script:jsons.
    param([string]$Nombre, $Ofertas)
    $script:jsons = [ordered]@{}
    foreach ($p in $Ofertas.PSObject.Properties) {
        if ($p.Value -and (Test-Path $p.Value)) { $script:jsons[$p.Name] = $p.Value }
        else { Escribir-Log ("{0} / {1}: sin JSON en '{2}'; se omite." -f $Nombre, $p.Name, $p.Value) }
    }
}

function Evaluar-Ofertas {
    param([string]$Nombre, $Jsons)
    foreach ($oferta in $Jsons.Keys) {
        Ejecutar-Python @("-m", "evaluacion.evaluar", "--resultado", $Jsons[$oferta], "--oferta", $oferta)
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: evaluar {0} / {1} termino con codigo {2}; se sigue." -f $Nombre, $oferta, $script:codigo) }
    }
}

function Juzgar-Ofertas {
    param([string]$Nombre, $Jsons)
    $argumentos = @("-m", "evaluacion.juez")
    foreach ($oferta in $Jsons.Keys) { $argumentos += ("{0}={1}" -f $oferta, $Jsons[$oferta]) }
    if ($SoloHumo) { $argumentos += @("--max-items", "5") }
    Ejecutar-Python $argumentos
    if ($script:codigo -ne 0) { Escribir-Log ("FALLO: el juez de {0} termino con codigo {1}; se sigue." -f $Nombre, $script:codigo) }
    Escribir-Log ("Gasto del juez acumulado: {0:N4} USD" -f $script:gastoJuez)
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Cierre de evaluacion{0}. Log: {1}" -f $(if ($SoloHumo) { " (solo humo)" } else { "" }), $script:log)

if (-not $Config -or -not (Test-Path $Config)) {
    Escribir-Log ("FALLO: indica -Config <json> con una ruta que exista (recibido: '{0}')." -f $Config)
}
else {
    $cfg = Get-Content -Raw -Encoding UTF8 $Config | ConvertFrom-Json
    foreach ($c in $cfg.configuraciones.PSObject.Properties) {
        $nombre = $c.Name
        Jsons-De-Configuracion $nombre $c.Value
        if ($script:jsons.Count -eq 0) { Escribir-Log ("{0}: sin ningun JSON; se omite la configuracion." -f $nombre) }
        else {
            $jsons = $script:jsons
            Medir-Etapa ("evaluar (1) {0}" -f $nombre) { Evaluar-Ofertas $nombre $jsons }
            Medir-Etapa ("juez {0}" -f $nombre) { Juzgar-Ofertas $nombre $jsons }
            Medir-Etapa ("evaluar (2) {0}" -f $nombre) { Evaluar-Ofertas $nombre $jsons }
        }
    }
    Medir-Etapa "tabla comparativa" {
        Ejecutar-Python @("-m", "evaluacion.tabla_comparativa", "--config", $Config)
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: la tabla comparativa termino con codigo {0}." -f $script:codigo) }
    }
}

$relojTotal.Stop()
Escribir-Log "=== TIEMPOS POR ETAPA ==="
foreach ($etapa in $script:etapas.Keys) {
    Escribir-Log ("{0,-40} {1,10} s  ({2})" -f $etapa, $script:etapas[$etapa], [timespan]::FromSeconds($script:etapas[$etapa]).ToString("hh\:mm\:ss"))
}
Escribir-Log ("Tiempo total: {0} s  ({1})" -f [math]::Round($relojTotal.Elapsed.TotalSeconds, 1), $relojTotal.Elapsed.ToString("hh\:mm\:ss"))
Escribir-Log ("Gasto del juez acumulado: {0:N4} USD" -f $script:gastoJuez)
Escribir-Log "Log completo en: $($script:log)"
