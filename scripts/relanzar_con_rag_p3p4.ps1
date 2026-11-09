# scripts\relanzar_con_rag_p3p4.ps1
# Relanza SOLO lo que fallo de la corrida final local (el analisis CON RAG de P3 y P4) y cierra las evaluaciones:
#   1. run_oferta CON RAG de P3 y P4 (se captura la ruta "JSON:" de cada corrida).
#   2. Evaluacion individual de esos dos JSON.
#   3. Elegir los SIN RAG de P1-P4 por la condicion que trae el JSON (configuracion_analisis.condicion = sin_rag; el mas reciente por oferta,
#      sin reclasificados, parciales ni deepinfra). El log dice que archivo se eligio para cada oferta.
#   4. Agregada CON RAG P1-P4 (P1 y P2: los reclasificados de la prueba B5) y agregada P3-P4, cada una con --comparar (tabla con / sin RAG y McNemar).
#   Si falta algun JSON, la agregada correspondiente se omite y queda avisado.
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\relanzar_con_rag_p3p4.ps1 [-Apagar]
#
# -Apagar apaga la PC al final (shutdown /s /f /t 120; se cancela con: shutdown /a).
# Toda la salida va a datos\Resultados\relanzar_con_rag_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.
param([switch]$Apagar)

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:ofertas = @(
    @{ Nombre = "P1"; Archivo = "datos\ProyectoAnalizar\P1_oferta_TBP01.pdf"; Carpeta = "datos\Resultados\P1_oferta_TBP01" },
    @{ Nombre = "P2"; Archivo = "datos\ProyectoAnalizar\P2_oferta_PH400.pdf"; Carpeta = "datos\Resultados\P2_oferta_PH400" },
    @{ Nombre = "P3"; Archivo = "datos\ProyectoAnalizar\P3_oferta_TV1600.pdf"; Carpeta = "datos\Resultados\P3_oferta_TV1600" },
    @{ Nombre = "P4"; Archivo = "datos\ProyectoAnalizar\P4_oferta_TPE800.pdf"; Carpeta = "datos\Resultados\P4_oferta_TPE800" }
)
$script:reclasificados = @{
    P1 = "datos\Resultados\P1_oferta_TBP01\analisis_riesgos_P1_oferta_TBP01_20261108_151743_reclasificado.json"
    P2 = "datos\Resultados\P2_oferta_PH400\analisis_riesgos_P2_oferta_PH400_20261108_172507_reclasificado.json"
}
$script:log = Join-Path $script:raiz ("datos\Resultados\relanzar_con_rag_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:conRag = @{}      # oferta -> JSON con RAG generado en esta corrida (solo si salio bien)
$script:sinRag = @{}      # oferta -> JSON sin RAG elegido por condicion
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
    # Analisis CON RAG; $script:conRag[oferta] se llena solo si termino bien y trajo la ruta JSON.
    param([hashtable]$Oferta)
    if (Test-Path $Oferta.Archivo) {
        Ejecutar-Python @("-m", "scripts.run_oferta", $Oferta.Archivo, "--oferta", $Oferta.Nombre)
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:conRag[$Oferta.Nombre] = $script:jsonActual }
        else { Escribir-Log ("FALLO: el analisis de {0} termino con codigo {1}; se sigue con lo que falta." -f $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("FALLO: no existe {0}; se sigue con lo que falta." -f $Oferta.Archivo) }
}

function Evaluar-Individual {
    param([string]$Nombre)
    if ($script:conRag.ContainsKey($Nombre)) {
        Ejecutar-Python @("-m", "evaluacion.evaluar", "--resultado", $script:conRag[$Nombre], "--oferta", $Nombre)
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: la evaluacion de {0} termino con codigo {1}." -f $Nombre, $script:codigo) }
    }
    else { Escribir-Log ("{0}: sin analisis, no se evalua." -f $Nombre) }
}

function Elegir-SinRag {
    # El JSON sin RAG mas reciente de la oferta, elegido por configuracion_analisis.condicion (scripts.elegir_json). El log muestra los candidatos y el elegido.
    param([hashtable]$Oferta)
    Ejecutar-Python @("-m", "scripts.elegir_json", $Oferta.Carpeta, "--condicion", "sin_rag")
    if ($script:codigo -eq 0 -and $script:jsonActual) {
        $script:sinRag[$Oferta.Nombre] = $script:jsonActual
        Escribir-Log ("{0}: sin RAG elegido = {1}" -f $Oferta.Nombre, $script:jsonActual)
    }
    else { Escribir-Log ("FALLO: no hay JSON sin RAG para {0}." -f $Oferta.Nombre) }
}

function Evaluar-Agregado {
    # Agregado de $Nombres con $Con (oferta -> JSON) y --comparar contra $Sin (oferta -> JSON sin RAG). Se omite si falta algun JSON de cualquiera de los dos.
    param([string]$Titulo, [string[]]$Nombres, [hashtable]$Con, [hashtable]$Sin)
    $faltanCon = @($Nombres | Where-Object { -not ($Con.ContainsKey($_) -and (Test-Path $Con[$_])) })
    $faltanSin = @($Nombres | Where-Object { -not ($Sin.ContainsKey($_) -and (Test-Path $Sin[$_])) })
    if ($faltanCon.Count -gt 0) {
        Escribir-Log ("Agregado {0} omitido: faltan los JSON con RAG de {1}." -f $Titulo, ($faltanCon -join ", "))
    }
    elseif ($faltanSin.Count -gt 0) {
        Escribir-Log ("Agregado {0} omitido: faltan los JSON sin RAG de {1}." -f $Titulo, ($faltanSin -join ", "))
    }
    else {
        $argumentos = @("-m", "evaluacion.evaluar", "--agregado")
        foreach ($n in $Nombres) { $argumentos += ("{0}={1}" -f $n, $Con[$n]) }
        $argumentos += "--comparar"
        foreach ($n in $Nombres) { $argumentos += ("{0}={1}" -f $n, $Sin[$n]) }
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
Escribir-Log ("Relanzamiento CON RAG de P3 y P4. Log: {0}" -f $script:log)

foreach ($o in $script:ofertas) {
    if ($o.Nombre -eq "P3" -or $o.Nombre -eq "P4") {
        Medir-Etapa ("analisis CON RAG {0}" -f $o.Nombre) { Analizar-Oferta $o }
    }
}
foreach ($n in @("P3", "P4")) {
    Medir-Etapa ("evaluacion CON RAG {0}" -f $n) { Evaluar-Individual $n }
}
foreach ($o in $script:ofertas) {
    Medir-Etapa ("eleccion SIN RAG {0}" -f $o.Nombre) { Elegir-SinRag $o }
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
