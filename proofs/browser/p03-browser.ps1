<#
.SYNOPSIS
  P03 - Engine-owned browser record/compile/replay with the packaged
  Playwright/Chromium, against a loopback synthetic form whose server-side
  store is the system of record. Includes a fault-injection pass where the
  page says "Salvo com sucesso" without persisting (must be refuted).
#>
param(
  [Parameter(Mandatory)] [string] $Install,        # staged @redrise layout with browser
  [Parameter(Mandatory)] [string] $LabPython,      # lab python for the synthetic server and verifier (not the product)
  [string] $LabRoot = (Join-Path $env:USERPROFILE 'RedRise-v2-dev\proofs\p03-browser'),
  [int] $Port = 47321
)
# Continue: native tools write progress to stderr, which Windows PowerShell 5.1
# would otherwise turn into terminating errors. Exit codes are checked explicitly.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$operator = Join-Path $here '..\operator\operator.ps1'
$engine = Join-Path $Install 'engine\redrise-engine.exe'
$run = Join-Path $LabRoot ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path (Join-Path $run 'logs') | Out-Null
$url = "http://127.0.0.1:$Port/"
$result = [ordered]@{ run_dir = $run; url = $url }

function Start-Server([string]$store, [switch]$Fake) {
  $a = @('-B', (Join-Path $here 'synthetic_server.py'), '--store', $store, '--port', $Port)
  if ($Fake) { $a += '--fake-success' }
  $p = Start-Process -FilePath $LabPython -ArgumentList $a -PassThru -WindowStyle Hidden -RedirectStandardOutput "$store.server.out"
  Start-Sleep -Milliseconds 1200
  return $p
}
function Chrome-Paths {
  @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | ForEach-Object ExecutablePath | Sort-Object -Unique)
}
$globalCache = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ms-playwright'
$result.global_cache_mtime_before = if (Test-Path $globalCache) { (Get-Item $globalCache).LastWriteTimeUtc.ToString('o') } else { $null }

# ---- 1. record through the real browser UI
$store = Join-Path $run 'store.jsonl'
$srv = Start-Server $store
$rec = Join-Path $run 'recording'; $stop = Join-Path $run 'logs\stop.flag'
$rp = Start-Process -FilePath $engine -ArgumentList @('record', '--category', 'browser', '--url', $url, '--out', "`"$rec`"", '--stop-file', "`"$stop`"", '--max-seconds', '180') `
  -RedirectStandardOutput (Join-Path $run 'logs\record.json') -RedirectStandardError (Join-Path $run 'logs\record.err') -PassThru -WindowStyle Hidden
$null = $rp.Handle
# Wait for the Engine's readiness line (start page loaded, recorder installed).
$errFile = Join-Path $run 'logs\record.err'; $deadline = (Get-Date).AddSeconds(90)
while (-not ((Test-Path $errFile) -and (Select-String -LiteralPath $errFile -Pattern 'browser recording via' -Quiet))) {
  if ((Get-Date) -gt $deadline -or $rp.HasExited) { break }
  Start-Sleep -Milliseconds 200
}
$result.recorder_ready = [bool](Select-String -LiteralPath $errFile -Pattern 'browser recording via' -Quiet)
$scen = Join-Path $run 'logs\operator-demo.json'
@(
  @{ wait_class = 'Chrome_WidgetWin_1'; timeout_ms = 60000 }, @{ sleep = 800 },
  @{ click_rel = @(700, 500) }, @{ sleep = 500 },  # focus the page (blank area), not the address bar
  @{ keys = '{TAB}' }, @{ text = 'Cliente Teste 01' },
  @{ keys = '{TAB}' }, @{ text = '1500' },
  @{ keys = '{TAB}' }, @{ keys = ' ' }, @{ sleep = 2500 }
) | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $scen
try {
  & $operator -Scenario $scen -PidFile (Join-Path $run 'logs\x.pid') > (Join-Path $run 'logs\operator-demo.log.json')
  $result.demo = 'completed'
  $result.chrome_during_record = Chrome-Paths
  Set-Content -LiteralPath $stop -Value 'stop'
} catch { $result.demo = "failed: $_"; Set-Content -LiteralPath $stop -Value 'cancel' }
$rp.WaitForExit(60000) | Out-Null
$result.record_exit = $rp.ExitCode
$result.store_records_after_record = @(Get-Content $store -ErrorAction SilentlyContinue).Count

# ---- 2. compile
$proc = Join-Path $run 'procedure.json'
& $engine compile --recording $rec --out $proc > (Join-Path $run 'logs\compile.json')
$result.compile_exit = $LASTEXITCODE

# ---- 3. replay (Engine drives the packaged browser)
& $engine run --procedure $proc --report (Join-Path $run 'run.json') 2> (Join-Path $run 'logs\run.err') > $null
$result.run_exit = $LASTEXITCODE
$result.replay_browser = (Get-Content (Join-Path $run 'logs\run.err') -ErrorAction SilentlyContinue) -join ' '
Stop-Process -Id $srv.Id
& $LabPython -B (Join-Path $here 'verify_browser_result.py') --store $store --expect-records 2 > (Join-Path $run 'verify.json')
$result.verifier_exit = $LASTEXITCODE

# ---- 4. fault injection: page shows success but nothing is persisted
$fstore = Join-Path $run 'store-fake.jsonl'
$fsrv = Start-Server $fstore -Fake
& $engine run --procedure $proc --report (Join-Path $run 'run-fake.json') 2> $null > $null
$result.fake_run_exit = $LASTEXITCODE
Stop-Process -Id $fsrv.Id
& $LabPython -B (Join-Path $here 'verify_browser_result.py') --store $fstore --expect-records 1 > (Join-Path $run 'verify-fake.json')
$result.fake_verifier_exit = $LASTEXITCODE   # must be 1 (refuted)

$result.global_cache_mtime_after = if (Test-Path $globalCache) { (Get-Item $globalCache).LastWriteTimeUtc.ToString('o') } else { $null }
$pkgBrowsers = (Resolve-Path (Join-Path $Install 'browsers')).Path
# The user's own Chrome may run too; what matters is that the recorder's
# Chromium came from the package and nothing ran from the global cache.
$result.chrome_from_package = (@($result.chrome_during_record) | Where-Object { $_ -and $_.StartsWith($pkgBrowsers, 'OrdinalIgnoreCase') }).Count -ge 1
$result.chrome_from_global_cache = (@($result.chrome_during_record) | Where-Object { $_ -and $_.StartsWith($globalCache, 'OrdinalIgnoreCase') }).Count -ge 1
$result.chrome_from_package_only = $result.chrome_from_package -and -not $result.chrome_from_global_cache
$result.verified = ($result.record_exit -eq 0 -and $result.compile_exit -eq 0 -and $result.run_exit -eq 0 -and $result.verifier_exit -eq 0 -and
  $result.fake_run_exit -eq 0 -and $result.fake_verifier_exit -eq 1 -and $result.chrome_from_package_only -and
  $result.global_cache_mtime_before -eq $result.global_cache_mtime_after)
$result | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $run 'summary.json')
