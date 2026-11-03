<#
.SYNOPSIS
  P01 - RedRise Engine on real Excel (Windows 11 + Excel 365 desktop).

  1. Template created through the Excel UI by the lab operator (setup, not recorded).
  2. Engine records the operator filling B2/B3 through the UI and Save As (copy).
  3. Engine compiles the recording (output path declared as parameter).
  4. Template reopened; Engine replays to a distinct output path.
  5. Independent Python/openpyxl verifier reads the three files after Excel closed.
  Nothing here writes cells directly into an XLSX. Runs under -LabRoot on C:.
#>
param(
  [Parameter(Mandatory)] [string] $Engine,
  # Omit on a clean machine (no Python may be installed there); the run
  # directory is then verified on the host with verify_engine_result.py.
  [string] $VerifierPython,
  [string] $LabRoot = (Join-Path $env:USERPROFILE 'RedRise-v2-dev\proofs\p01-engine'),
  # P02: replay through the packaged Runner (redrise-runner.cmd) as a job.
  [string] $Runner,
  [string] $RunnerDataRoot,
  [switch] $HostilePythonEnv
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$operator = Join-Path $here '..\operator\operator.ps1'
$verifier = Join-Path $here 'verify_engine_result.py'
$excel = 'C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE'
$run = Join-Path $LabRoot ("run-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
foreach ($d in 'entrada', 'saida', 'logs') { New-Item -ItemType Directory -Force -Path (Join-Path $run $d) | Out-Null }
$template = Join-Path $run 'entrada\template_redrise.xlsx'
$recOut = Join-Path $run 'saida\resultado_gravado.xlsx'
$repOut = Join-Path $run 'saida\resultado_replay.xlsx'
$result = [ordered]@{ run_dir = $run; started = (Get-Date).ToString('o') }

function Invoke-Operator([string]$name, [object[]]$actions) {
  $f = Join-Path $run "logs\operator-$name.json"
  $actions | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $f
  & $operator -Scenario $f -PidFile (Join-Path $run "logs\excel-$name.pid") > (Join-Path $run "logs\operator-$name.log.json")
}
function Close-Excel([string]$name) {
  # Graceful WM_CLOSE only; a workbook that is still dirty would prompt and
  # stay open, which is reported instead of killed.
  $pf = Join-Path $run "logs\excel-$name.pid"
  $id = [int](Get-Content $pf)
  $p = Get-Process -Id $id -ErrorAction SilentlyContinue
  if ($p) { [void]$p.CloseMainWindow(); if (-not $p.WaitForExit(15000)) { throw "Excel ($name) did not close gracefully" } }
}

# ---- 1. template through the UI (setup, not recorded)
Invoke-Operator 'template' @(
  @{ launch = $excel }, @{ wait_window = 30000 }, @{ sleep = 4000 },
  @{ keys = '{ESC}' }, @{ wait_class = 'XLMAIN'; timeout_ms = 15000 }, @{ sleep = 2500 },  # start screen -> blank workbook
  @{ keys = '^{HOME}' }, @{ text = 'Campo' }, @{ keys = '{TAB}' }, @{ text = 'Valor' }, @{ keys = '{ENTER}' },
  @{ text = 'Cliente' }, @{ keys = '{ENTER}' }, @{ text = 'Valor do pedido' }, @{ keys = '{ENTER}' },
  @{ keys = '{F12}' }, @{ wait_class = '#32770'; timeout_ms = 15000 }, @{ sleep = 800 },
  @{ keys = '%d' }, @{ sleep = 500 }, @{ text = (Split-Path $template) }, @{ keys = '{ENTER}' }, @{ sleep = 1200 }, @{ keys = '%n' }, @{ sleep = 400 }, @{ keys = '^a' }, @{ text = (Split-Path $template -Leaf) }, @{ keys = '{ENTER}' }, @{ sleep = 2500 }
)
Close-Excel 'template'
$result.template_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $template).Hash.ToLower()
Set-ItemProperty -LiteralPath $template -Name IsReadOnly -Value $true   # T07 protection

# ---- 2. open template (setup), then record the demonstration
Invoke-Operator 'open-record' @(@{ launch = $excel; args = "`"$template`"" }, @{ wait_window = 30000 }, @{ sleep = 3000 })
$stop = Join-Path $run 'logs\stop.flag'
$rec = Join-Path $run 'recording'
$recProc = Start-Process -FilePath $Engine -ArgumentList @('record', '--target', 'excel.exe', '--out', "`"$rec`"", '--accept-injected', '--stop-file', "`"$stop`"", '--max-seconds', '180') `
  -RedirectStandardOutput (Join-Path $run 'logs\record.json') -RedirectStandardError (Join-Path $run 'logs\record.err') -PassThru -WindowStyle Hidden
$null = $recProc.Handle
Start-Sleep -Milliseconds 1500
try {
  Invoke-Operator 'demo' @(
    @{ click_rel = @(600, 450) }, @{ sleep = 600 },
    @{ keys = '^{HOME}' }, @{ keys = '{RIGHT}' }, @{ keys = '{DOWN}' },
    @{ text = 'Cliente Teste 01' }, @{ keys = '{ENTER}' },
    @{ text = '1500' }, @{ keys = '{ENTER}' },
    @{ keys = '{F12}' }, @{ wait_class = '#32770'; timeout_ms = 15000 }, @{ sleep = 800 },
    @{ keys = '%d' }, @{ sleep = 500 }, @{ text = (Split-Path $recOut) }, @{ keys = '{ENTER}' }, @{ sleep = 1200 }, @{ keys = '%n' }, @{ sleep = 400 }, @{ keys = '^a' }, @{ text = (Split-Path $recOut -Leaf) }, @{ keys = '{ENTER}' }, @{ sleep = 3000 }
  )
  $result.demo = 'completed'
  Set-Content -LiteralPath $stop -Value 'stop'
} catch {
  $result.demo = "failed: $_"
  Set-Content -LiteralPath $stop -Value 'cancel'
}
$recProc.WaitForExit(20000) | Out-Null
$result.record_exit = $recProc.ExitCode
Close-Excel 'open-record'
if (Test-Path -LiteralPath $recOut) {
  $result.recorded_sha256_before_replay = (Get-FileHash -Algorithm SHA256 -LiteralPath $recOut).Hash.ToLower()
  Set-ItemProperty -LiteralPath $recOut -Name IsReadOnly -Value $true
}

# ---- 3. compile
$procFile = Join-Path $run 'procedure.json'
& $Engine compile --recording $rec --out $procFile --param "output_dir=text:$(Split-Path $recOut)" --param "output_name=text:$(Split-Path $recOut -Leaf)" --declare output_path=output_path > (Join-Path $run 'logs\compile.json')
$result.compile_exit = $LASTEXITCODE

# ---- 4. reopen template (setup) and replay to a distinct output
if ($result.compile_exit -eq 0) {
  Invoke-Operator 'open-replay' @(@{ launch = $excel; args = "`"$template`"" }, @{ wait_window = 30000 }, @{ sleep = 3000 })
  if ($Runner) {
    $jobId = 'p01-' + (Split-Path $run -Leaf)
    $jobFile = Join-Path $run 'logs\job.json'
    [ordered]@{ job_id = $jobId; procedure = $procFile; bindings = @{ output_path = $repOut; output_dir = (Split-Path $repOut); output_name = (Split-Path $repOut -Leaf) } } | ConvertTo-Json | Set-Content -Encoding utf8 $jobFile
    $runnerArgs = @('run-job', '--job', $jobFile)
    if ($RunnerDataRoot) { $runnerArgs = @('--data-root', $RunnerDataRoot) + $runnerArgs }
    # Hostile Python environment applies to the packaged Runner only: it must
    # ignore it (private runtime). Lab tools below run with the normal env.
    $saved = @{ PYTHONHOME = $env:PYTHONHOME; PYTHONPATH = $env:PYTHONPATH; PATH = $env:PATH }
    if ($HostilePythonEnv) {
      $env:PYTHONHOME = 'C:\does-not-exist\pyhome'; $env:PYTHONPATH = 'C:\does-not-exist\pypath'
      $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
      $result.runner_env = 'hostile: bogus PYTHONHOME/PYTHONPATH, PATH without Python'
    }
    try {
      & $Runner @runnerArgs > (Join-Path $run 'logs\runner-job.json')
      $result.run_exit = $LASTEXITCODE
    } finally {
      $env:PYTHONHOME = $saved.PYTHONHOME; $env:PYTHONPATH = $saved.PYTHONPATH; $env:PATH = $saved.PATH
    }
    $result.replay_via = "runner job $jobId"
    $jobRun = Join-Path $RunnerDataRoot "jobs\$jobId\run.json"
    if (Test-Path -LiteralPath $jobRun) { Copy-Item -LiteralPath $jobRun -Destination (Join-Path $run 'run.json') }
  } else {
    & $Engine run --procedure $procFile --report (Join-Path $run 'run.json') --bind "output_path=$repOut" --bind "output_dir=$(Split-Path $repOut)" --bind "output_name=$(Split-Path $repOut -Leaf)" > $null
    $result.run_exit = $LASTEXITCODE
    $result.replay_via = 'engine cli'
  }
  Start-Sleep -Milliseconds 2000
  Close-Excel 'open-replay'
}

# ---- 5. independent verification after Excel closed (persistence)
$result.template_sha256_after = (Get-FileHash -Algorithm SHA256 -LiteralPath $template).Hash.ToLower()
if (Test-Path -LiteralPath $recOut) { $result.recorded_sha256_after = (Get-FileHash -Algorithm SHA256 -LiteralPath $recOut).Hash.ToLower() }
$env:PYTHONDONTWRITEBYTECODE = '1'
if ($VerifierPython) {
  & $VerifierPython $verifier --run $run --json (Join-Path $run 'verify.json') > $null
  $result.verifier_exit = $LASTEXITCODE
} else {
  $result.verifier_exit = $null
  $result.verification = 'pending_host: copy this run directory to the host and run verify_engine_result.py'
}
$result.template_unchanged = ($result.template_sha256 -eq $result.template_sha256_after)
$result.recorded_unchanged_by_replay = ($result.recorded_sha256_before_replay -eq $result.recorded_sha256_after)
$result.verified = ($result.verifier_exit -eq 0 -and $result.record_exit -eq 0 -and $result.compile_exit -eq 0 -and $result.run_exit -eq 0 -and $result.template_unchanged -and $result.recorded_unchanged_by_replay)
$result.ended = (Get-Date).ToString('o')
$result | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $run 'summary.json')
