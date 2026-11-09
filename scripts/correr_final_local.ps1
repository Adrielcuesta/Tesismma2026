# scripts\correr_final_local.ps1
# Corrida final LOCAL (GPU, qwen3:8b):
#   1. run_oferta CON RAG (modo verificacion, configuracion actual) para P3 y P4.
#   2. run_oferta SIN RAG para P1, P2, P3 y P4.
#   3. Evaluacion individual de cada JSON generado.
#   4. Evaluacion agregada CON RAG de P1-P4 (P1 y P2: los reclasificados de la prueba B5) y de P3-P4 (conjunto de prueba),
#      cada una con la comparacion con / sin RAG y la prueba de McNemar (--comparar).
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\correr_final_local.ps1 [-Apagar]
#
# -Apagar apaga la PC al final (shutdown /s /f /t 120; se cancela con: shutdown /a).
# Toda la salida va a datos\Resultados\final_local_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.
param([switch]$Apagar)

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:ofertas = @(
    @{ Nombre = "P1"; Archivo = "datos\ProyectoAnalizar\P1_oferta_TBP01.pdf" },
    @{ Nombre = "P2"; Archivo = "datos\ProyectoAnalizar\P2_oferta_PH400.pdf" },
    @{ Nombre = "P3"; Archivo = "datos\ProyectoAnalizar\P3_oferta_TV1600.pdf" },
    @{ Nombre = "P4"; Archivo = "datos\ProyectoAnalizar\P4_oferta_TPE800.pdf" }
)
$script:reclasificados = @{
    P1 = "datos\Resultados\P1_oferta_TBP01\analisis_riesgos_P1_oferta_TBP01_20261108_151743_reclasificado.json"
    P2 = "datos\Resultados\P2_oferta_PH400\analisis_riesgos_P2_oferta_PH400_20261108_172507_reclasificado.json"
}
$script:log = Join-Path $script:raiz ("datos\Resultados\final_local_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:conRag = @{}      # oferta -> JSON con RAG generado en esta corrida (solo si salio bien)
$script:sinRag = @{}      # oferta -> JSON sin RAG generado en esta corrida
$script:agregadoP1P4 = @{}
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

function Analizar-Oferta {
    # $Destino: hashtable oferta -> JSON (se llena solo si el analisis termino bien).
    param([hashtable]$Oferta, [bool]$SinRag, [hashtable]$Destino)
    if (Test-Path $Oferta.Archivo) {
        $argumentos = @("-m", "scripts.run_oferta", $Oferta.Archivo, "--oferta", $Oferta.Nombre)
        if ($SinRag) { $argumentos += "--sin-rag" }
        Ejecutar-Python $argumentos
        if ($script:codigo -eq 0 -and $script:jsonActual) { $Destino[$Oferta.Nombre] = $script:jsonActual }
        else { Escribir-Log ("FALLO: el analisis de {0} termino con codigo {1}; se sigue con lo que falta." -f $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("FALLO: no existe {0}; se sigue con lo que falta." -f $Oferta.Archivo) }
}

function Evaluar-Individual {
    param([string]$Nombre, [hashtable]$Origen)
    if ($Origen.ContainsKey($Nombre)) {
        Ejecutar-Python @("-m", "evaluacion.evaluar", "--resultado", $Origen[$Nombre], "--oferta", $Nombre)
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: la evaluacion de {0} termino con codigo {1}." -f $Nombre, $script:codigo) }
    }
    else { Escribir-Log ("{0}: sin analisis, no se evalua." -f $Nombre) }
}

function Evaluar-Agregado {
    # Agregado de $Nombres con $Con (oferta -> JSON). Si $Sin tiene el sin RAG de TODAS esas ofertas, agrega --comparar (tabla con / sin RAG y McNemar).
    param([string]$Titulo, [string[]]$Nombres, [hashtable]$Con, [hashtable]$Sin)
    $faltanCon = @($Nombres | Where-Object { -not ($Con.ContainsKey($_) -and (Test-Path $Con[$_])) })
    if ($faltanCon.Count -gt 0) {
        Escribir-Log ("Agregado {0} omitido: faltan los JSON con RAG de {1}." -f $Titulo, ($faltanCon -join ", "))
    }
    else {
        $argumentos = @("-m", "evaluacion.evaluar", "--agregado")
        foreach ($n in $Nombres) { $argumentos += ("{0}={1}" -f $n, $Con[$n]) }
        $faltanSin = @($Nombres | Where-Object { -not $Sin.ContainsKey($_) })
        if ($faltanSin.Count -eq 0) {
            $argumentos += "--comparar"
            foreach ($n in $Nombres) { $argumentos += ("{0}={1}" -f $n, $Sin[$n]) }
        }
        else { Escribir-Log ("Agregado {0}: sin comparacion ni McNemar, faltan los JSON sin RAG de {1}." -f $Titulo, ($faltanSin -join ", ")) }
        Ejecutar-Python $argumentos
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: el agregado {0} termino con codigo {1}." -f $Titulo, $script:codigo) }
    }
}

function Armar-AgregadoP1P4 {
    # P1 y P2: los reclasificados de la prueba B5; P3 y P4: los de esta corrida.
    foreach ($n in @("P1", "P2")) {
        if (Test-Path $script:reclasificados[$n]) { $script:agregadoP1P4[$n] = $script:reclasificados[$n] }
        else { Escribir-Log ("FALLO: no existe {0}." -f $script:reclasificados[$n]) }
    }
    foreach ($n in @("P3", "P4")) {
        if ($script:conRag.ContainsKey($n)) { $script:agregadoP1P4[$n] = $script:conRag[$n] }
    }
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Corrida final local. Log: {0}" -f $script:log)

foreach ($o in $script:ofertas) {
    if ($o.Nombre -eq "P3" -or $o.Nombre -eq "P4") {
        Medir-Etapa ("analisis CON RAG {0}" -f $o.Nombre) { Analizar-Oferta $o $false $script:conRag }
    }
}
foreach ($o in $script:ofertas) {
    Medir-Etapa ("analisis SIN RAG {0}" -f $o.Nombre) { Analizar-Oferta $o $true $script:sinRag }
}
foreach ($n in @("P3", "P4")) {
    Medir-Etapa ("evaluacion CON RAG {0}" -f $n) { Evaluar-Individual $n $script:conRag }
}
foreach ($o in $script:ofertas) {
    Medir-Etapa ("evaluacion SIN RAG {0}" -f $o.Nombre) { Evaluar-Individual $o.Nombre $script:sinRag }
}
Medir-Etapa "agregado P1-P4 con RAG" {
    Armar-AgregadoP1P4
    Evaluar-Agregado "P1-P4" @("P1", "P2", "P3", "P4") $script:agregadoP1P4 $script:sinRag
}
Medir-Etapa "agregado P3-P4 con RAG" { Evaluar-Agregado "P3-P4" @("P3", "P4") $script:conRag $script:sinRag }

$relojTotal.Stop()
Escribir-Log "=== TIEMPOS POR ETAPA ==="
foreach ($etapa in $script:etapas.Keys) {
    Escribir-Log ("{0,-32} {1,10} s  ({2})" -f $etapa, $script:etapas[$etapa], [timespan]::FromSeconds($script:etapas[$etapa]).ToString("hh\:mm\:ss"))
}
Escribir-Log ("Tiempo total: {0} s  ({1})" -f [math]::Round($relojTotal.Elapsed.TotalSeconds, 1), $relojTotal.Elapsed.ToString("hh\:mm\:ss"))
Escribir-Log "Log completo en: $($script:log)"

if ($Apagar) {
    Escribir-Log "Apagando la PC en 120 s (para cancelar: shutdown /a)."
    shutdown /s /f /t 120
}
