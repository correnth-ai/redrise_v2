<#
  Lab debug: runs the browser adapter's record mode directly (no Engine) with
  the synthetic server and the operator, then prints the adapter's events.
  Every process it starts is stopped at the end (only those, by PID).
#>
param([Parameter(Mandatory)] [string] $Install, [Parameter(Mandatory)] [string] $LabPython, [string] $Work)
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $Work | Out-Null
$srv = Start-Process -FilePath $LabPython -ArgumentList @('-B', (Join-Path $here 'synthetic_server.py'), '--store', "$Work\store.jsonl", '--port', '47321') -PassThru -WindowStyle Hidden
Start-Sleep 1
$psi = New-Object System.Diagnostics.ProcessStartInfo "$Install\runtime\python\python.exe", "-B -X utf8 -m redrise_browser --browsers `"$Install\browsers`" record --url http://127.0.0.1:47321/ --profile `"$Work\profile`""
$psi.UseShellExecute = $false; $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
$ad = [System.Diagnostics.Process]::Start($psi)
$outTask = $ad.StandardOutput.ReadToEndAsync(); $errTask = $ad.StandardError.ReadToEndAsync()
Start-Sleep 8
'[{"click_rel":[700,500]},{"sleep":500},{"keys":"{TAB}"},{"text":"Cliente Teste 01"},{"keys":"{TAB}"},{"text":"1500"},{"keys":"{TAB}"},{"keys":" "},{"sleep":2500}]' | Set-Content -Encoding utf8 "$Work\keys.json"
& (Join-Path $here '..\operator\operator.ps1') -Scenario "$Work\keys.json" -PidFile "$Work\x.pid" | Out-Null
$ad.StandardInput.WriteLine('ping'); Start-Sleep 1; $ad.StandardInput.WriteLine('stop')
$exited = $ad.WaitForExit(20000)
if (-not $exited) { Stop-Process -Id $ad.Id -Force }
Stop-Process -Id $srv.Id -ErrorAction SilentlyContinue
"exited=$exited"
"--- stdout"; if ($outTask.Wait(5000)) { $outTask.Result }
"--- stderr (tail)"; if ($errTask.Wait(5000)) { ($errTask.Result -split "`n" | Select-Object -Last 6) -join "`n" }
"--- store"; Get-Content "$Work\store.jsonl" -ErrorAction SilentlyContinue
