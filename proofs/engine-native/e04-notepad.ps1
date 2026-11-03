<#
.SYNOPSIS
  E02/E03/E04 native proof on Notepad: the Engine records a synthetic
  operator through the real UI, compiles, replays to a distinct output and
  an independent reader checks both files. Runs entirely under -LabRoot (C:).
#>
param(
  [Parameter(Mandatory)] [string] $Engine,
  [string] $LabRoot = (Join-Path $env:USERPROFILE 'RedRise-v2-dev\proofs\e04-notepad')
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$operator = Join-Path $here '..\operator\operator.ps1'
$run = Join-Path $LabRoot ("run-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path (Join-Path $run 'saida') | Out-Null
$text = 'Teste RedRise E04 ' + [char]0x00E7 + ' 123'
$recOut = Join-Path $run 'saida\gravado.txt'
$repOut = Join-Path $run 'saida\replay.txt'
$result = [ordered]@{ run_dir = $run; text = $text }

function Stop-Launched([string]$pidFile) {
  if (Test-Path $pidFile) {
    # Graceful close only (WM_CLOSE); never kill the user's application state.
    $id = [int](Get-Content $pidFile)
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($p) { [void]$p.CloseMainWindow(); $p.WaitForExit(5000) | Out-Null }
  }
}

# --- 1. record the demonstration
$scenario = @(
  @{ launch = 'notepad.exe' }, @{ wait_window = 15000 },
  @{ keys = '^n' }, @{ sleep = 800 },
  @{ text = $text },
  @{ keys = '^s' }, @{ wait_class = '#32770'; timeout_ms = 10000 }, @{ sleep = 600 },
  @{ keys = '%d' }, @{ sleep = 500 }, @{ text = (Split-Path $recOut) }, @{ keys = '{ENTER}' }, @{ sleep = 1200 }, @{ keys = '%n' }, @{ sleep = 400 }, @{ keys = '^a' }, @{ text = (Split-Path $recOut -Leaf) }, @{ keys = '{ENTER}' }, @{ sleep = 1500 }
)
$scenarioFile = Join-Path $run 'record-scenario.json'
$scenario | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $scenarioFile
$stop = Join-Path $run 'stop.flag'
$rec = Join-Path $run 'recording'
$recProc = Start-Process -FilePath $Engine -ArgumentList @('record','--target','notepad.exe','--out',"`"$rec`"",'--accept-injected','--stop-file',"`"$stop`"",'--max-seconds','120') `
  -RedirectStandardOutput (Join-Path $run 'record.json') -RedirectStandardError (Join-Path $run 'record.err') -PassThru -WindowStyle Hidden
$null = $recProc.Handle  # keep the handle so ExitCode is available
Start-Sleep -Milliseconds 1500
$pidRec = Join-Path $run 'notepad-record.pid'
try {
  & $operator -Scenario $scenarioFile -PidFile $pidRec > (Join-Path $run 'operator-record.json')
  $result.operator_record = 'completed'
  Set-Content -LiteralPath $stop -Value 'stop'
} catch {
  $result.operator_record = "failed: $_"
  Set-Content -LiteralPath $stop -Value 'cancel'
}
$t = Get-Date
$recProc.WaitForExit(15000) | Out-Null
$result.record_exit = $recProc.ExitCode
$result.record_stop_to_exit_ms = [int]((Get-Date) - $t).TotalMilliseconds
Stop-Launched $pidRec
# Protect the recorded evidence before replay: hash it and make it read-only,
# so a misdirected save during replay fails instead of altering it.
if (Test-Path -LiteralPath $recOut) {
  $result.recorded_sha256_before_replay = (Get-FileHash -Algorithm SHA256 -LiteralPath $recOut).Hash.ToLower()
  Set-ItemProperty -LiteralPath $recOut -Name IsReadOnly -Value $true
}

# --- 2. compile with the output path as an explicit parameter
$procFile = Join-Path $run 'procedure.json'
& $Engine compile --recording $rec --out $procFile --param "output_dir=text:$(Split-Path $recOut)" --param "output_name=text:$(Split-Path $recOut -Leaf)" --declare output_path=output_path > (Join-Path $run 'compile.json')
$result.compile_exit = $LASTEXITCODE

# --- 3. replay to a distinct output (harness only opens Notepad)
$pidRep = Join-Path $run 'notepad-replay.pid'
$open = @(@{ launch = 'notepad.exe' }, @{ wait_window = 15000 })
$openFile = Join-Path $run 'replay-open.json'
$open | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $openFile
& $operator -Scenario $openFile -PidFile $pidRep > $null
& $Engine run --procedure $procFile --report (Join-Path $run 'run.json') --bind "output_path=$repOut" --bind "output_dir=$(Split-Path $repOut)" --bind "output_name=$(Split-Path $repOut -Leaf)" > $null
$result.run_exit = $LASTEXITCODE
Start-Sleep -Milliseconds 1000
Stop-Launched $pidRep

# --- 4. independent read (does not use the Engine)
foreach ($k in @('recorded', 'replayed')) {
  $f = if ($k -eq 'recorded') { $recOut } else { $repOut }
  $exists = Test-Path -LiteralPath $f
  $content = if ($exists) { [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8).TrimEnd("`r", "`n") } else { $null }
  $result[$k] = [ordered]@{
    path = $f; exists = $exists; content = $content; matches = ($content -ceq $text)
    sha256 = if ($exists) { (Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash.ToLower() } else { $null }
  }
}
$result.verified = $result.recorded.matches -and $result.replayed.matches -and $result.record_exit -eq 0 -and $result.compile_exit -eq 0 -and $result.run_exit -eq 0
$result | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $run 'verify.json')
