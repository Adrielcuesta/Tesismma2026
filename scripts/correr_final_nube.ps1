# scripts\correr_final_nube.ps1
# Corrida final en la NUBE (no usa la GPU; puede correr en paralelo con correr_final_local.ps1):
#   1. scripts.recuperar con perfil local y perfil amplio para P3 y P4.
#   2. scripts.nube para P3 y P4 (una invocacion por oferta, cada una con su tope de PRESUPUESTO_USD) con Qwen/Qwen3-32B:
#        (i)   sin thinking + recuperacion local
#        (ii)  --thinking   + recuperacion local     -> salida ...-thinking-local
#        (iii) --thinking   + recuperacion amplia    -> salida ...-thinking-amplio
#   3. Evaluacion agregada P1-P4 de cada configuracion (P1 y P2: los JSON ya existentes) y agregada solo de P3-P4.
#
# Uso, desde la raiz del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\scripts\correr_final_nube.ps1
#
# Toda la salida va a datos\Resultados\final_nube_<fecha>.txt (Tee-Object) y a la consola (Out-Host).
# Las funciones no devuelven nada: el estado queda en variables $script:. Si una etapa falla, queda en el log y se sigue.
# El script es ASCII a proposito: PowerShell 5.1 lee mal los acentos de un archivo sin BOM.

$ErrorActionPreference = "Continue"
$script:raiz = Split-Path -Parent $PSScriptRoot
Set-Location $script:raiz
$script:python = Join-Path $script:raiz "venv\Scripts\python.exe"
$script:modelo = "Qwen/Qwen3-32B"
$script:ofertasNuevas = @(
    @{ Nombre = "P3"; Archivo = "datos\ProyectoAnalizar\P3_oferta_TV1600.pdf" },
    @{ Nombre = "P4"; Archivo = "datos\ProyectoAnalizar\P4_oferta_TPE800.pdf" }
)
$script:perfiles = @("local", "amplio")
$script:configuraciones = @(
    @{ Id = "i";   Titulo = "(i) 32B sin thinking, recuperacion local";  Thinking = $false; Perfil = "local" },
    @{ Id = "ii";  Titulo = "(ii) 32B thinking, recuperacion local";     Thinking = $true;  Perfil = "local" },
    @{ Id = "iii"; Titulo = "(iii) 32B thinking, recuperacion amplia";   Thinking = $true;  Perfil = "amplio" }
)
# JSON ya existentes de P1 y P2 por configuracion
$d1 = "datos\Resultados\P1_oferta_TBP01\analisis_riesgos_P1_oferta_TBP01_"
$d2 = "datos\Resultados\P2_oferta_PH400\analisis_riesgos_P2_oferta_PH400_"
$script:existentes = @{
    i   = @{ P1 = "${d1}20261108_233006_deepinfra-qwen3-32b.json";          P2 = "${d2}20261108_234255_deepinfra-qwen3-32b.json" }
    ii  = @{ P1 = "${d1}20261109_020326_deepinfra-qwen3-32b.json";          P2 = "${d2}20261109_024612_deepinfra-qwen3-32b.json" }
    iii = @{ P1 = "${d1}20261109_120344_deepinfra-qwen3-32b-thinking.json"; P2 = "${d2}20261109_123806_deepinfra-qwen3-32b-thinking.json" }
}
$script:log = Join-Path $script:raiz ("datos\Resultados\final_nube_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
$script:teeAppend = (Get-Command Tee-Object).Parameters.ContainsKey("Append")
$script:etapas = New-Object System.Collections.Specialized.OrderedDictionary   # etapa -> segundos
$script:recuperaciones = @{}   # "P3|local" -> JSON de recuperacion (solo si salio bien)
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
    param([hashtable]$Oferta, [string]$Perfil)
    if (Test-Path $Oferta.Archivo) {
        Ejecutar-Python @("-m", "scripts.recuperar", $Oferta.Archivo, "--perfil-recuperacion", $Perfil)
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:recuperaciones["$($Oferta.Nombre)|$Perfil"] = $script:jsonActual }
        else { Escribir-Log ("FALLO: la recuperacion {0} de {1} termino con codigo {2}." -f $Perfil, $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("FALLO: no existe {0}." -f $Oferta.Archivo) }
}

function Correr-Nube {
    param([hashtable]$Configuracion, [hashtable]$Oferta)
    $clave = "$($Configuracion.Perfil)"
    $rec = $script:recuperaciones["$($Oferta.Nombre)|$clave"]
    if ($rec) {
        $argumentos = @("-m", "scripts.nube", "--reusar-recuperacion", $rec, "--pdf", $Oferta.Archivo, "--modelo", $script:modelo)
        if ($Configuracion.Thinking) { $argumentos += "--thinking" }
        Ejecutar-Python $argumentos
        if ($script:codigo -eq 0 -and $script:jsonActual) { $script:nubeJson["$($Configuracion.Id)|$($Oferta.Nombre)"] = $script:jsonActual }
        else { Escribir-Log ("FALLO: nube {0} de {1} termino con codigo {2} o sin JSON." -f $Configuracion.Titulo, $Oferta.Nombre, $script:codigo) }
    }
    else { Escribir-Log ("{0} {1}: sin recuperacion {2}, se omite." -f $Configuracion.Titulo, $Oferta.Nombre, $clave) }
}

function Evaluar-Agregado {
    # Agregado de las ofertas en $Rutas (oferta -> JSON). Ejecuta evaluar.py si estan todas y existen.
    param([string]$Titulo, [string[]]$Nombres, [hashtable]$Rutas)
    $faltan = @($Nombres | Where-Object { -not ($Rutas.ContainsKey($_) -and $Rutas[$_] -and (Test-Path $Rutas[$_])) })
    if ($faltan.Count -gt 0) {
        Escribir-Log ("Agregado {0} omitido: faltan los JSON de {1}." -f $Titulo, ($faltan -join ", "))
    }
    else {
        $argumentos = @("-m", "evaluacion.evaluar", "--agregado")
        foreach ($n in $Nombres) { $argumentos += ("{0}={1}" -f $n, $Rutas[$n]) }
        Ejecutar-Python $argumentos
        if ($script:codigo -ne 0) { Escribir-Log ("FALLO: el agregado {0} termino con codigo {1}." -f $Titulo, $script:codigo) }
    }
}

function Evaluar-Configuracion {
    param([hashtable]$Configuracion)
    $rutas = @{ P1 = $script:existentes[$Configuracion.Id].P1; P2 = $script:existentes[$Configuracion.Id].P2 }
    foreach ($o in $script:ofertasNuevas) { $rutas[$o.Nombre] = $script:nubeJson["$($Configuracion.Id)|$($o.Nombre)"] }
    Evaluar-Agregado ("P1-P4 " + $Configuracion.Titulo) @("P1", "P2", "P3", "P4") $rutas
    Evaluar-Agregado ("P3-P4 " + $Configuracion.Titulo) @("P3", "P4") $rutas
}

$relojTotal = [System.Diagnostics.Stopwatch]::StartNew()
Escribir-Log ("Corrida final en la nube ({0}). Log: {1}" -f $script:modelo, $script:log)

foreach ($o in $script:ofertasNuevas) {
    foreach ($perfil in $script:perfiles) {
        Medir-Etapa ("recuperacion {0} {1}" -f $perfil, $o.Nombre) { Recuperar-Oferta $o $perfil }
    }
}
foreach ($c in $script:configuraciones) {
    foreach ($o in $script:ofertasNuevas) {
        Medir-Etapa ("nube {0} {1}" -f $c.Id, $o.Nombre) { Correr-Nube $c $o }
    }
}
foreach ($c in $script:configuraciones) {
    Medir-Etapa ("evaluacion agregada {0}" -f $c.Id) { Evaluar-Configuracion $c }
}

$relojTotal.Stop()
Escribir-Log "=== TIEMPOS POR ETAPA ==="
foreach ($etapa in $script:etapas.Keys) {
    Escribir-Log ("{0,-32} {1,10} s  ({2})" -f $etapa, $script:etapas[$etapa], [timespan]::FromSeconds($script:etapas[$etapa]).ToString("hh\:mm\:ss"))
}
Escribir-Log ("Tiempo total: {0} s  ({1})" -f [math]::Round($relojTotal.Elapsed.TotalSeconds, 1), $relojTotal.Elapsed.ToString("hh\:mm\:ss"))
Escribir-Log "Log completo en: $($script:log)"
