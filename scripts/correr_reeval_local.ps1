# scripts\correr_reeval_local.ps1
# Reevaluacion LOCAL (GPU, qwen3:8b) con la recuperacion ELEGIDA, de noche:
#   para P1, P2, P3 y P4: run_oferta --reusar-recuperacion <JSON de recuperacion>, es decir que qwen3:8b verifica EXACTAMENTE los mismos pares que la nube
#   (sin cargar embeddings ni reranker). Salida ...-local-qwen3-8b-elegido.
# Los JSON de recuperacion salen de datos\Resultados\recuperacion_elegido.json, que escribe correr_reeval_nube.ps1 (o correr_reeval_nube.ps1 -SoloRecuperar).
# Prompts, LLM y motor de reglas sin cambios. La evaluacion la hace evaluacion.tabla_comparativa (config_reeval.json).
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\correr_reeval_local.ps1 [-Apagar]
#
# -Apagar apaga la PC al final (shutdown /s /f /t 120; se cancela con: shutdown /a).
# Toda la salida va a datos\Resultados\reeval_local_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.
param([switch]$Apagar)

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:manifiesto = Join-Path $script:raiz "datos\Resultados\recuperacion_elegido.json"
$script:ofertas = @(
    @{ Nombre = "P1"; Archivo = "datos\ProyectoAnalizar\P1_oferta_TBP01.pdf" },
    @{ Nombre = "P2"; Archivo = "datos\ProyectoAnalizar\P2_oferta_PH400.pdf" },
    @{ Nombre = "P3"; Archivo = "datos\ProyectoAnalizar\P3_oferta_TV1600.pdf" },
    @{ Nombre = "P4"; Archivo = "datos\ProyectoAnalizar\P4_oferta_TPE800.pdf" }
)
$script:log = Join-Path $script:raiz ("datos\Resultados\reeval_local_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:recuperaciones = @{}   # "P3" -> JSON de recuperacion
$script:localJson = @{}        # "P3" -> JSON del analisis local
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
        if ($linea -match '^\s*JSON:\s+(.+)$') { $script:jsonActual = $Matches[1].Trim() }
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

function Leer-Manifiesto {
    if (Test-Path $script:manifiesto) {
        $m = Get-Content -Raw -Path $script:manifiesto | ConvertFrom-Json
        foreach ($o in $script:ofertas) {
            $ruta = $m.($o.Nombre)
            if ($ruta -and (Test-Path $ruta)) { $script:recuperaciones[$o.Nombre] = $ruta }
            else { Escribir-Log ("FALLO: el manifiesto no trae un JSON existente para {0}." -f $o.Nombre) }
        }
    }
    else { Escribir-Log ("FALLO: no existe {0}; corre antes correr_reeval_nube.ps1 (o con -SoloRecuperar)." -f $script:manifiesto) }
}

function Analizar-Oferta {
    param([hashtable]$Oferta)
    $rec = $script:recuperaciones[$Oferta.Nombre]
    if (-not $rec) { Escribir-Log ("{0}: sin recuperacion registrada, se omite." -f $Oferta.Nombre) }
    elseif (-not (Test-Path $Oferta.Archivo)) { Escribir-Log ("FALLO: no existe {0}." -f $Oferta.Archivo) }
    else {
        Ejecutar-Python @("-m", "scripts.run_oferta", $Oferta.Archivo, "--oferta", $Oferta.Nombre, "--reusar-recuperacion", $rec)
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:localJson[$Oferta.Nombre] = $script:jsonActual }
        else { Escribir-Log ("FALLO: el analisis local de {0} termino con codigo {1}; se sigue con lo que falta." -f $Oferta.Nombre, $script:codigo) }
    }
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Reevaluacion local (qwen3:8b) con la recuperacion elegida. Log: {0}" -f $script:log)

Medir-Etapa "leer recuperaciones registradas" { Leer-Manifiesto }
foreach ($o in $script:ofertas) {
    Medir-Etapa ("analisis local {0}" -f $o.Nombre) { Analizar-Oferta $o }
}

$relojTotal.Stop()
Escribir-Log "=== TIEMPOS POR ETAPA ==="
foreach ($etapa in $script:etapas.Keys) {
    Escribir-Log ("{0,-32} {1,10} s  ({2})" -f $etapa, $script:etapas[$etapa], [timespan]::FromSeconds($script:etapas[$etapa]).ToString("hh\:mm\:ss"))
}
Escribir-Log ("Tiempo total: {0} s  ({1})" -f [math]::Round($relojTotal.Elapsed.TotalSeconds, 1), $relojTotal.Elapsed.ToString("hh\:mm\:ss"))
foreach ($o in $script:ofertas) { if ($script:localJson.ContainsKey($o.Nombre)) { Escribir-Log ("{0}: {1}" -f $o.Nombre, $script:localJson[$o.Nombre]) } }
Escribir-Log "Para evaluacion\config_reeval.json (auto por sufijo): local-qwen3-8b-elegido."
Escribir-Log "Log completo en: $($script:log)"

if ($Apagar) {
    Escribir-Log "Apagando la PC en 120 s (para cancelar: shutdown /a)."
    shutdown /s /f /t 120
}
