# scripts\correr_reeval_nube.ps1
# Reevaluacion en la NUBE con la recuperacion ELEGIDA (perfil "elegido" de config.PERFILES_RECUPERACION; no usa la GPU):
#   1. scripts.recuperar con el perfil elegido para P1, P2, P3 y P4 (una sola vez). Los JSON de recuperacion quedan registrados en
#      datos\Resultados\recuperacion_elegido.json (oferta -> ruta), que lee tambien correr_reeval_local.ps1: todos los LLM verifican EXACTAMENTE los mismos pares.
#   2. scripts.nube para las 4 ofertas (una invocacion por oferta, cada una con su tope de PRESUPUESTO_USD). Antes de cada modelo se imprime la cantidad de
#      pares y el costo estimado (scripts.nube --estimar, sin API):
#        (i)   Qwen/Qwen3-32B sin razonamiento -> salida ...-deepinfra-qwen3-32b-elegido
#        (ii)  openai/gpt-oss-120b, esfuerzo bajo ("Reasoning: low" en el mensaje de sistema) -> salida ...-deepinfra-gpt-oss-120b-elegido
#        (iii) Qwen/Qwen3-32B --thinking       -> salida ...-deepinfra-qwen3-32b-thinking-elegido
#      Antes de (iii) el script se detiene: muestra el costo estimado de esa corrida y el gasto real acumulado de (i) y (ii) (costo_usd de sus JSON) y pide
#      confirmacion (S/N). Con -SinRazonamiento se saltea (iii) sin preguntar.
# Prompts, LLM y motor de reglas sin cambios: la unica diferencia con v1 es la recuperacion. La evaluacion la hace evaluacion.tabla_comparativa (config_reeval.json).
#
# Requisito: haber cargado el perfil "elegido" (config.PERFILES_RECUPERACION["elegido"]) y puesto config.PERFIL_ELEGIDO_CARGADO = True; si no, scripts.recuperar se niega.
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\correr_reeval_nube.ps1 [-ReusarRecuperacion] [-SoloRecuperar]
#   -ReusarRecuperacion: no vuelve a recuperar; usa los JSON ya registrados en recuperacion_elegido.json.
#   -SoloRecuperar:      recupera y registra, sin llamar a la nube.
#   -SinRazonamiento:    saltea directamente la corrida (iii), Qwen3-32B con razonamiento.
#
# Toda la salida va a datos\Resultados\reeval_nube_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.
param([switch]$ReusarRecuperacion, [switch]$SoloRecuperar, [switch]$SinRazonamiento)

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:perfil = "elegido"
$script:manifiesto = Join-Path $script:raiz "datos\Resultados\recuperacion_elegido.json"
$script:ofertas = @(
    @{ Nombre = "P1"; Archivo = "datos\ProyectoAnalizar\P1_oferta_TBP01.pdf" },
    @{ Nombre = "P2"; Archivo = "datos\ProyectoAnalizar\P2_oferta_PH400.pdf" },
    @{ Nombre = "P3"; Archivo = "datos\ProyectoAnalizar\P3_oferta_TV1600.pdf" },
    @{ Nombre = "P4"; Archivo = "datos\ProyectoAnalizar\P4_oferta_TPE800.pdf" }
)
$script:configuraciones = @(
    @{ Id = "i";   Modelo = "Qwen/Qwen3-32B";       Titulo = "(i) 32B sin razonamiento, recuperacion elegida"; Thinking = $false; Confirmar = $false },
    @{ Id = "ii";  Modelo = "openai/gpt-oss-120b";  Titulo = "(ii) gpt-oss-120b esfuerzo bajo, recuperacion elegida"; Thinking = $false; Confirmar = $false },
    @{ Id = "iii"; Modelo = "Qwen/Qwen3-32B";       Titulo = "(iii) 32B con razonamiento, recuperacion elegida"; Thinking = $true; Confirmar = $true }
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
        $argumentos = @("-m", "scripts.nube", "--reusar-recuperacion", $rec, "--pdf", $Oferta.Archivo, "--modelo", $Configuracion.Modelo)
        if ($Configuracion.Thinking) { $argumentos += "--thinking" }
        Ejecutar-Python $argumentos
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:nubeJson["$($Configuracion.Id)|$($Oferta.Nombre)"] = $script:jsonActual }
        else { Escribir-Log ("FALLO: nube {0} de {1} termino con codigo {2} o sin JSON." -f $Configuracion.Titulo, $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("{0} {1}: sin recuperacion, se omite." -f $Configuracion.Titulo, $Oferta.Nombre) }
}

function Estimar-Configuracion {
    # Imprime la cantidad de pares y el costo estimado de la configuracion (scripts.nube --estimar: no llama a la API). No devuelve nada.
    param([hashtable]$Configuracion)
    $jsons = @()
    foreach ($o in $script:ofertas) { if ($script:recuperaciones.ContainsKey($o.Nombre)) { $jsons += $script:recuperaciones[$o.Nombre] } }
    if ($jsons.Count -eq 0) { Escribir-Log ("{0}: sin recuperaciones, no se puede estimar." -f $Configuracion.Titulo); return }
    $argumentos = @("-m", "scripts.nube", "--estimar", "--reusar-recuperacion") + $jsons + @("--modelo", $Configuracion.Modelo)
    if ($Configuracion.Thinking) { $argumentos += "--thinking" }
    Escribir-Log ("ESTIMACION {0}" -f $Configuracion.Titulo)
    Ejecutar-Python $argumentos
}

function Gasto-Acumulado {
    # Gasto real (costo_usd de los JSON de analisis) de las corridas de nube ya hechas en esta ejecucion. Devuelve un hashtable: Usd, Archivos, Sin.
    $total = 0.0; $n = 0; $sin = 0
    foreach ($clave in @($script:nubeJson.Keys)) {
        $ruta = $script:nubeJson[$clave]
        $costo = $null
        if ($ruta -and (Test-Path $ruta)) {
            try { $costo = (Get-Content -Raw -Encoding UTF8 -Path $ruta | ConvertFrom-Json).configuracion_analisis.costo_computacional.costo_usd } catch { $costo = $null }
        }
        if ($null -ne $costo) { $total += [double]$costo; $n++ } else { $sin++ }
    }
    return @{ Usd = $total; Archivos = $n; Sin = $sin }
}

function Confirmar-Razonamiento {
    # Antes de la corrida con razonamiento: costo estimado y gasto real acumulado; pide S/N. Devuelve $true si se confirma.
    param([hashtable]$Configuracion)
    Estimar-Configuracion $Configuracion
    $g = Gasto-Acumulado
    Escribir-Log ("GASTO REAL acumulado de las corridas anteriores de esta ejecucion: {0:N4} USD ({1} JSON leidos, {2} sin JSON o sin costo)." -f $g.Usd, $g.Archivos, $g.Sin)
    $respuesta = Read-Host ("Correr {0}? (S/N)" -f $Configuracion.Titulo)
    Escribir-Log ("Respuesta: {0}" -f $respuesta)
    return ($respuesta -match '^\s*[sSyY]')
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Reevaluacion en la nube con la recuperacion {0}. Log: {1}" -f $script:perfil, $script:log)

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
        if ($c.Confirmar) {
            if ($SinRazonamiento) { Escribir-Log ("{0}: se saltea (-SinRazonamiento)." -f $c.Titulo); continue }
            if (-not (Confirmar-Razonamiento $c)) { Escribir-Log ("{0}: no confirmada, se saltea." -f $c.Titulo); continue }
        }
        else { Medir-Etapa ("estimacion {0}" -f $c.Id) { Estimar-Configuracion $c } }
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
Escribir-Log "Para evaluacion\config_reeval.json (auto por sufijo): deepinfra-qwen3-32b-elegido, deepinfra-gpt-oss-120b-elegido y deepinfra-qwen3-32b-thinking-elegido."
Escribir-Log "Log completo en: $($script:log)"
