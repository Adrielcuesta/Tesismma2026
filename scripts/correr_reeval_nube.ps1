# scripts\correr_reeval_nube.ps1
# Reevaluacion en la NUBE con la recuperacion ELEGIDA (perfil "elegido" de config.PERFILES_RECUPERACION; no usa la GPU):
#   1. scripts.recuperar con el perfil elegido para P1, P2, P3 y P4 (una sola vez). Los JSON de recuperacion quedan registrados en
#      datos\Resultados\recuperacion_elegido.json (oferta -> ruta), que lee tambien correr_reeval_local.ps1: todos los LLM verifican EXACTAMENTE los mismos pares.
#   2. scripts.nube con Qwen/Qwen3-32B para las 4 ofertas (una invocacion por oferta, cada una con su tope de PRESUPUESTO_USD):
#        (i)  sin razonamiento -> salida ...-deepinfra-qwen3-32b-elegido
#        (ii) --thinking       -> salida ...-deepinfra-qwen3-32b-thinking-elegido
# Prompts, LLM y motor de reglas sin cambios: la unica diferencia con v1 es la recuperacion. La evaluacion la hace evaluacion.tabla_comparativa (config_reeval.json).
#
# Requisito: haber cargado el perfil "elegido" (config.PERFILES_RECUPERACION["elegido"]) y puesto config.PERFIL_ELEGIDO_CARGADO = True; si no, scripts.recuperar se niega.
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\correr_reeval_nube.ps1 [-ReusarRecuperacion] [-SoloRecuperar]
#   -ReusarRecuperacion: no vuelve a recuperar; usa los JSON ya registrados en recuperacion_elegido.json.
#   -SoloRecuperar:      recupera y registra, sin llamar a la nube.
#
# Toda la salida va a datos\Resultados\reeval_nube_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.
param([switch]$ReusarRecuperacion, [switch]$SoloRecuperar)

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:modelo = "Qwen/Qwen3-32B"
$script:perfil = "elegido"
$script:manifiesto = Join-Path $script:raiz "datos\Resultados\recuperacion_elegido.json"
$script:ofertas = @(
    @{ Nombre = "P1"; Archivo = "datos\ProyectoAnalizar\P1_oferta_TBP01.pdf" },
    @{ Nombre = "P2"; Archivo = "datos\ProyectoAnalizar\P2_oferta_PH400.pdf" },
    @{ Nombre = "P3"; Archivo = "datos\ProyectoAnalizar\P3_oferta_TV1600.pdf" },
    @{ Nombre = "P4"; Archivo = "datos\ProyectoAnalizar\P4_oferta_TPE800.pdf" }
)
$script:configuraciones = @(
    @{ Id = "i";  Titulo = "(i) 32B sin razonamiento, recuperacion elegida"; Thinking = $false },
    @{ Id = "ii"; Titulo = "(ii) 32B con razonamiento, recuperacion elegida"; Thinking = $true }
)
$script:log = Join-Path $script:raiz ("datos\Resultados\reeval_nube_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:recuperaciones = @{}   # "P3" -> JSON de recuperacion (solo si salio bien)
$script:nubeJson = @{}         # "i|P3" -> JSON del analisis en la nube
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

function Recuperar-Oferta {
    param([hashtable]$Oferta)
    if (Test-Path $Oferta.Archivo) {
        Ejecutar-Python @("-m", "scripts.recuperar", $Oferta.Archivo, "--perfil-recuperacion", $script:perfil)
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:recuperaciones[$Oferta.Nombre] = $script:jsonActual }
        else { Escribir-Log ("FALLO: la recuperacion {0} de {1} termino con codigo {2}." -f $script:perfil, $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("FALLO: no existe {0}." -f $Oferta.Archivo) }
}

function Guardar-Manifiesto {
    # oferta -> JSON de recuperacion, para correr_reeval_local.ps1 (y para el que quiera reusar la misma recuperacion).
    $datos = [ordered]@{ perfil = $script:perfil; fecha = (Get-Date -Format "yyyy-MM-dd HH:mm") }
    foreach ($o in $script:ofertas) { if ($script:recuperaciones.ContainsKey($o.Nombre)) { $datos[$o.Nombre] = $script:recuperaciones[$o.Nombre] } }
    $datos | ConvertTo-Json | Set-Content -Path $script:manifiesto -Encoding UTF8
    Escribir-Log ("Recuperaciones registradas en {0}" -f $script:manifiesto)
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
    else { Escribir-Log ("FALLO: no existe {0}; corre sin -ReusarRecuperacion." -f $script:manifiesto) }
}

function Correr-Nube {
    param([hashtable]$Configuracion, [hashtable]$Oferta)
    $rec = $script:recuperaciones[$Oferta.Nombre]
    if ($rec) {
        $argumentos = @("-m", "scripts.nube", "--reusar-recuperacion", $rec, "--pdf", $Oferta.Archivo, "--modelo", $script:modelo)
        if ($Configuracion.Thinking) { $argumentos += "--thinking" }
        Ejecutar-Python $argumentos
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:nubeJson["$($Configuracion.Id)|$($Oferta.Nombre)"] = $script:jsonActual }
        else { Escribir-Log ("FALLO: nube {0} de {1} termino con codigo {2} o sin JSON." -f $Configuracion.Titulo, $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("{0} {1}: sin recuperacion, se omite." -f $Configuracion.Titulo, $Oferta.Nombre) }
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Reevaluacion en la nube ({0}) con la recuperacion {1}. Log: {2}" -f $script:modelo, $script:perfil, $script:log)

if ($ReusarRecuperacion) {
    Medir-Etapa "leer recuperaciones registradas" { Leer-Manifiesto }
}
else {
    foreach ($o in $script:ofertas) {
        Medir-Etapa ("recuperacion {0} {1}" -f $script:perfil, $o.Nombre) { Recuperar-Oferta $o }
    }
    Guardar-Manifiesto
}
if (-not $SoloRecuperar) {
    foreach ($c in $script:configuraciones) {
        foreach ($o in $script:ofertas) {
            Medir-Etapa ("nube {0} {1}" -f $c.Id, $o.Nombre) { Correr-Nube $c $o }
        }
    }
}

$relojTotal.Stop()
Escribir-Log "=== TIEMPOS POR ETAPA ==="
foreach ($etapa in $script:etapas.Keys) {
    Escribir-Log ("{0,-32} {1,10} s  ({2})" -f $etapa, $script:etapas[$etapa], [timespan]::FromSeconds($script:etapas[$etapa]).ToString("hh\:mm\:ss"))
}
Escribir-Log ("Tiempo total: {0} s  ({1})" -f [math]::Round($relojTotal.Elapsed.TotalSeconds, 1), $relojTotal.Elapsed.ToString("hh\:mm\:ss"))
Escribir-Log "Para evaluacion\config_reeval.json (auto por sufijo): deepinfra-qwen3-32b-elegido y deepinfra-qwen3-32b-thinking-elegido."
Escribir-Log "Log completo en: $($script:log)"
