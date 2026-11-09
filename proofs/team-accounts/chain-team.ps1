# TEAM-ACCOUNTS-20261108 on the lab (synthetic team): gate -> baseline by the previous lab install (beta.28)
# -> lab install beta.29 -> practical proof against the baseline -> rollback check on a copy (beta.29 -> beta.28).
# Started through an Explorer shortcut. Every step stops the chain on failure. The installed RedRise of the user
# and its team are never touched: the lab instance is identified and closed by its own process id.
$ErrorActionPreference = 'Stop'
$V = '0.1.0-beta.29'
$repo = 'D:\Correnth\.claude\worktrees\elastic-cartwright-5e8477\products\redrise-v2\repos\app'
$lab = 'C:\Users\raulv\RedRise-v2-dev\lab-test'
$log = Join-Path $lab 'team-chain.log'
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
  Log "gate: verify-candidate $V"
  & (Join-Path $repo 'packaging\release\verify-candidate.ps1') -Version $V *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'team-gate.log')
  $vj = Get-Content "C:\Users\raulv\RedRise-v2-dev\release\$V\verification.json" -Raw | ConvertFrom-Json
  Log "gate passed=$($vj.passed)"
  if (-not $vj.passed) { throw 'gate failed' }

  $tools = Join-Path $lab 'tools\proof-team'
  if (Test-Path $tools) { Remove-Item -Recurse -Force $tools }
  foreach ($d in 'nova-rotina', 'boas-vindas', 'stabilization', 'schedules', 'team-accounts') { Copy-Item -Recurse (Join-Path $repo "proofs\$d") (Join-Path $tools $d) }
  $prev = Join-Path $lab 'install-beta28'
  $baseline = Join-Path $lab 'team-baseline.json'
  Log 'baseline by the previous lab install (beta.28) on the lab data'
  & (Join-Path $prev 'runtime\python\python.exe') -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --baseline-with $prev `
      --data (Join-Path $lab 'data') --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out $baseline *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'team-baseline.log')
  if (-not (Test-Path $baseline)) { throw 'baseline not written' }
  Log 'baseline written'

  $inst = Join-Path $lab 'install-beta29'
  if (Test-Path $inst) { throw "exists: $inst" }
  $setup = "C:\Users\raulv\RedRise-v2-dev\release\$V\RedRise-Setup-$V.exe"
  $p = Start-Process -FilePath $setup -ArgumentList @('--quiet', '--install-root', $inst) -Wait -PassThru -NoNewWindow `
       -RedirectStandardOutput (Join-Path $lab 'install-log\install-beta29.json')
  Log "install exit=$($p.ExitCode)"
  if ($p.ExitCode -ne 0 -or -not (Test-Path (Join-Path $inst 'RedRise.exe'))) { throw 'install failed' }

  $py = Join-Path $inst 'runtime\python\python.exe'
  Log 'proof: accept_team'
  & $py -B -X utf8 (Join-Path $tools 'team-accounts\accept_team.py') --lab $lab --shots (Join-Path $lab 'shots-team') --baseline $baseline *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'team-proof.log')
  Log ("proof: " + ((Get-Content (Join-Path $lab 'team-proof.log') -Tail 1)))

  Start-Sleep -Seconds 5
  if (LabRunning) { throw 'the lab instance is still open: rollback copy skipped' }
  $copy = Join-Path $lab 'rollback-copy\data'
  if (Test-Path (Split-Path $copy)) { Remove-Item -Recurse -Force (Split-Path $copy) }
  New-Item -ItemType Directory -Force $copy | Out-Null
  & robocopy (Join-Path $lab 'data') $copy /E /NFL /NDL /NJH /NJS /NP /XD logs | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $copy 'host\pgdata\postmaster.pid')
  Log 'rollback check on the copy (beta.29 -> beta.28, the real install version)'
  & $py -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --new $inst --old $prev `
      --data $copy --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out (Join-Path $lab 'team-rollback.json') *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'team-rollback.log')
  Log ("rollback: " + ((Get-Content (Join-Path $lab 'team-rollback.log') -Tail 1)))
  Log 'done'
} catch {
  Log "stopped: $($_.Exception.Message)"
}
