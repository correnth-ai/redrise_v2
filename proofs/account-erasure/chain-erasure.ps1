# ACCOUNT-ERASURE-20261109 on the lab (synthetic team): gate -> baseline by the previous lab install (beta.29)
# -> lab install beta.30 -> practical proof (accept_erasure, then accept_team account and delete) -> rollback check on
# a copy (beta.30 -> beta.29). Started through an Explorer shortcut. Every step stops the chain on failure. The
# installed RedRise of the user and its team are never touched: the lab instance is identified and closed by its own id.
param([ValidateSet('gate', 'proof')] [string] $From = 'gate')
# Native tools write to stderr; each step checks its own result, so stderr lines must not stop the chain.
$ErrorActionPreference = 'Continue'
$V = '0.1.0-beta.30'
$repo = 'D:\Correnth\.claude\worktrees\elastic-cartwright-5e8477\.app-erase'
$lab = 'C:\Users\raulv\RedRise-v2-dev\lab-test'
$log = Join-Path $lab 'erase-chain.log'
$env:TMP = 'C:\Users\raulv\RedRise-v2-dev\scratch\stab-tmp'; $env:TEMP = $env:TMP
function Log([string] $m) { "$(Get-Date -Format 'HH:mm:ss') $m" | Out-File -Append -Encoding utf8 $log }
function LabRunning {
  $f = Join-Path $lab 'pid.txt'
  if (-not (Test-Path $f)) { return $false }
  $p = Get-Process -Id ([int](Get-Content $f -Raw)) -ErrorAction SilentlyContinue
  return [bool]($p -and $p.ProcessName -eq 'RedRise')
}
"" | Out-File -Encoding utf8 $log
try {
  if (LabRunning) { throw 'the lab instance is open: close it first' }
  $prev = Join-Path $lab 'install-beta29'
  $baseline = Join-Path $lab 'erase-baseline.json'
  $tools = Join-Path $lab 'tools\proof-erase'
  $inst = Join-Path $lab 'install-beta30'
  if ($From -eq 'gate') {
  Log "gate: verify-candidate $V"
  & (Join-Path $repo 'packaging\release\verify-candidate.ps1') -Version $V *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'erase-gate.log')
  $vj = Get-Content "C:\Users\raulv\RedRise-v2-dev\release\$V\verification.json" -Raw | ConvertFrom-Json
  Log "gate passed=$($vj.passed)"
  if (-not $vj.passed) { throw 'gate failed' }

  $tools = Join-Path $lab 'tools\proof-erase'
  if (Test-Path $tools) { Remove-Item -Recurse -Force $tools }
  foreach ($d in 'nova-rotina', 'boas-vindas', 'stabilization', 'schedules', 'team-accounts', 'account-erasure') { Copy-Item -Recurse (Join-Path $repo "proofs\$d") (Join-Path $tools $d) }
  $prev = Join-Path $lab 'install-beta29'
  $baseline = Join-Path $lab 'erase-baseline.json'
  Log 'baseline by the previous lab install (beta.29) on the lab data'
  & (Join-Path $prev 'runtime\python\python.exe') -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --baseline-with $prev `
      --data (Join-Path $lab 'data') --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out $baseline *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'erase-baseline.log')
  if (-not (Test-Path $baseline)) { throw 'baseline not written' }
  Log 'baseline written'

  $inst = Join-Path $lab 'install-beta30'
  if (Test-Path $inst) { throw "exists: $inst" }
  $setup = "C:\Users\raulv\RedRise-v2-dev\release\$V\RedRise-Setup-$V.exe"
  $p = Start-Process -FilePath $setup -ArgumentList @('--quiet', '--install-root', $inst) -Wait -PassThru -NoNewWindow `
       -RedirectStandardOutput (Join-Path $lab 'install-log\install-beta30.json')
  Log "install exit=$($p.ExitCode)"
  if ($p.ExitCode -ne 0 -or -not (Test-Path (Join-Path $inst 'RedRise.exe'))) { throw 'install failed' }
  } else {
    Log 'from the proof: gate, baseline and install of an earlier run; proof scripts copied again'
    if (Test-Path $tools) { Remove-Item -Recurse -Force $tools }
    foreach ($d in 'nova-rotina', 'boas-vindas', 'stabilization', 'schedules', 'team-accounts', 'account-erasure') { Copy-Item -Recurse (Join-Path $repo "proofs\$d") (Join-Path $tools $d) }
  }

  $py = Join-Path $inst 'runtime\python\python.exe'
  $shots = Join-Path $lab 'shots-erase'
  Log 'proof: accept_erasure'
  & $py -B -X utf8 (Join-Path $tools 'account-erasure\accept_erasure.py') --lab $lab --shots $shots --baseline $baseline *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'erase-proof.log')
  Log ("proof: " + ((Get-Content (Join-Path $lab 'erase-proof.log') -Tail 1)))
  Start-Sleep -Seconds 5
  if (LabRunning) { throw 'the lab instance is still open: next steps skipped' }
  Log 'proof: accept_team --only account,delete'
  & $py -B -X utf8 (Join-Path $tools 'team-accounts\accept_team.py') --lab $lab --shots $shots --baseline $baseline --only 'account,delete' *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'erase-proof-team.log')
  Log ("proof team: " + ((Get-Content (Join-Path $lab 'erase-proof-team.log') -Tail 1)))

  Start-Sleep -Seconds 5
  if (LabRunning) { throw 'the lab instance is still open: rollback copy skipped' }
  $copy = Join-Path $lab 'rollback-copy\data'
  if (Test-Path (Split-Path $copy)) { Remove-Item -Recurse -Force (Split-Path $copy) }
  New-Item -ItemType Directory -Force $copy | Out-Null
  & robocopy (Join-Path $lab 'data') $copy /E /NFL /NDL /NJH /NJS /NP /XD logs | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $copy 'host\pgdata\postmaster.pid')
  Log 'rollback check on the copy (beta.30 -> beta.29, the real install version)'
  & $py -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --new $inst --old $prev `
      --data $copy --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out (Join-Path $lab 'erase-rollback.json') *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'erase-rollback.log')
  Log ("rollback: " + ((Get-Content (Join-Path $lab 'erase-rollback.log') -Tail 1)))
  Log 'done'
} catch {
  Log "stopped: $($_.Exception.Message)"
}
