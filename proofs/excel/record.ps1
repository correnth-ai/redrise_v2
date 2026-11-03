# Starts the P01 desktop recording (POC §5.2).
# Source stays in this repository (D:); tests, runtime and data live on C: under
# %USERPROFILE%\RedRise-v2-dev (decision P01-D5). AppData is avoided because the
# Claude desktop app virtualizes it for the processes it launches.
# Recording stops by itself once saida\resultado_teste.xlsx exists and is stable
# (wait_for_output.py via --until-cmd); `capture stop` or Ctrl-C stops it too.
param(
    [string]$Name = 'excel_preenchimento_01'
)
$ErrorActionPreference = 'Stop'

$Dev = Join-Path $env:USERPROFILE 'RedRise-v2-dev'
$Base = Join-Path $Dev 'proofs\excel'
$Flow = Join-Path $Base '.venv\Scripts\openadapt-flow.exe'
$Py = Join-Path $Dev 'runtime\python-3.12.10\tools\python.exe'
$Rec = Join-Path $Base "gravacoes\$Name"
$Output = Join-Path $Base 'saida\resultado_teste.xlsx'
$Probe = Join-Path $PSScriptRoot 'wait_for_output.py'

if (Test-Path -LiteralPath $Rec) { throw "Recording dir already exists, not overwriting: $Rec" }
if (Test-Path -LiteralPath $Output) { throw "Output already exists; move it before recording: $Output" }

# Capture finds the pinned FFmpeg only under this data dir; no user-site packages.
$env:OPENADAPT_CAPTURE_DATA_DIR = Join-Path $Dev 'runtime\openadapt-capture'
$env:PYTHONNOUSERSITE = '1'

# shlex splits --until-cmd, so pass forward-slash paths.
$Until = '"{0}" -I "{1}" "{2}"' -f ($Py -replace '\\', '/'), ($Probe -replace '\\', '/'), ($Output -replace '\\', '/')

Set-Location $Base
& $Flow record --backend windows --out $Rec `
    --task 'Preencher B2 e B3 no Excel e salvar uma copia XLSX' `
    --until-cmd $Until
exit $LASTEXITCODE
