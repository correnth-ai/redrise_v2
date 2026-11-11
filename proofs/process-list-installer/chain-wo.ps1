# PROCESS-LIST-INSTALLER-20261110 on the lab (synthetic team): gate -> installer checks (P10, isolated) -> baseline by the
# previous lab install (beta.30) -> quiet update of a copy of beta.30 (the updater's path) -> lab install beta.31 ->
# practical proof (accept_wo: lab app, Kanban between clients, installer wizard) -> rollback check on a copy
# (beta.31 -> beta.30). Started through an Explorer shortcut. Native steps write to stderr: each step checks its own
# result. The installed RedRise of the person and its team are never touched.
param([ValidateSet('gate', 'proof')] [string] $From = 'gate', [string] $Only = '')
$ErrorActionPreference = 'Continue'
$V = '0.1.0-beta.31'
$repo = 'D:\Correnth\.claude\worktrees\elastic-cartwright-5e8477\.app-wo'
$lab = 'C:\Users\raulv\RedRise-v2-dev\lab-test'
$log = Join-Path $lab 'wo-chain.log'
$env:TMP = 'C:\Users\raulv\RedRise-v2-dev\scratch\stab-tmp'; $env:TEMP = $env:TMP
function Log([string] $m) { "$(Get-Date -Format 'HH:mm:ss') $m" | Out-File -Append -Encoding utf8 $log }
function LabRunning {
  $f = Join-Path $lab 'pid.txt'
  if (-not (Test-Path $f)) { return $false }
  $p = Get-Process -Id ([int](Get-Content $f -Raw)) -ErrorAction SilentlyContinue
  return [bool]($p -and $p.ProcessName -eq 'RedRise')
}
function CopyProofs($tools) {
  if (Test-Path $tools) { Remove-Item -Recurse -Force $tools }
  foreach ($d in 'nova-rotina', 'boas-vindas', 'stabilization', 'schedules', 'team-accounts', 'process-list-installer') { Copy-Item -Recurse (Join-Path $repo "proofs\$d") (Join-Path $tools $d) }
}
"" | Out-File -Encoding utf8 $log
try {
  if (LabRunning) { throw 'the lab instance is open: close it first' }
  $prev = Join-Path $lab 'install-beta30'
  $baseline = Join-Path $lab 'wo-baseline.json'
  $tools = Join-Path $lab 'tools\proof-wo'
  $inst = Join-Path $lab 'install-beta31'
  $setup = "C:\Users\raulv\RedRise-v2-dev\release\$V\RedRise-Setup-$V.exe"
  CopyProofs $tools
  if ($From -eq 'gate') {
    Log "gate: verify-candidate $V"
    & (Join-Path $repo 'packaging\release\verify-candidate.ps1') -Version $V *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'wo-gate.log')
    $vj = Get-Content "C:\Users\raulv\RedRise-v2-dev\release\$V\verification.json" -Raw | ConvertFrom-Json
    Log "gate passed=$($vj.passed)"
    if (-not $vj.passed) { throw 'gate failed' }

    Log 'installer checks (P10, isolated): corrupted, install, reinstall, rollback, uninstall'
    $p10 = Join-Path $lab 'wo-p10'
    if (Test-Path $p10) { Remove-Item -Recurse -Force $p10 }
    & (Join-Path $repo 'proofs\installer\p10-installer-checks.ps1') -Setup $setup -OutDir $p10 *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'wo-p10.log')
    $sum = ((Get-Content (Join-Path $p10 'summary.json') -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ')
    Log ("p10: " + $sum.Substring(0, [Math]::Min(400, $sum.Length)))

    Log 'baseline by the previous lab install (beta.30) on the lab data'
    & (Join-Path $prev 'runtime\python\python.exe') -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --baseline-with $prev `
        --data (Join-Path $lab 'data') --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out $baseline *>&1 |
      Out-File -Encoding utf8 (Join-Path $lab 'wo-baseline.log')
    if (-not (Test-Path $baseline)) { throw 'baseline not written' }
    Log 'baseline written'

    Log 'quiet update of a copy of beta.30 (the in-app update path: --quiet, no wizard, no role question)'
    $uc = Join-Path $lab 'update-copy\Programs\@redrise'
    if (Test-Path (Split-Path (Split-Path $uc))) { Remove-Item -Recurse -Force (Split-Path (Split-Path $uc)) }
    New-Item -ItemType Directory -Force (Split-Path $uc) | Out-Null
    & robocopy $prev $uc /E /NFL /NDL /NJH /NJS /NP | Out-Null
    $p = Start-Process -FilePath $setup -ArgumentList @('--quiet', '--install-root', $uc) -Wait -PassThru -NoNewWindow `
         -RedirectStandardOutput (Join-Path $lab 'install-log\update-copy.json')
    $man = Get-Content (Join-Path $uc 'manifest.json') -Raw | ConvertFrom-Json
    Log "update copy exit=$($p.ExitCode) version=$($man.app_version) previous_kept=$(Test-Path ($uc + '.previous'))"
    if ($p.ExitCode -ne 0 -or $man.app_version -ne $V) { throw 'quiet update of the copy failed' }

    if (Test-Path $inst) { throw "exists: $inst" }
    $p = Start-Process -FilePath $setup -ArgumentList @('--quiet', '--install-root', $inst) -Wait -PassThru -NoNewWindow `
         -RedirectStandardOutput (Join-Path $lab 'install-log\install-beta31.json')
    Log "install exit=$($p.ExitCode)"
    if ($p.ExitCode -ne 0 -or -not (Test-Path (Join-Path $inst 'RedRise.exe'))) { throw 'install failed' }
  } else { Log 'from the proof: gate, checks, baseline and install of an earlier run; proof scripts copied again' }

  $py = Join-Path $inst 'runtime\python\python.exe'
  Log "proof: accept_wo $Only"
  $a = @('-B', '-X', 'utf8', (Join-Path $tools 'process-list-installer\accept_wo.py'), '--lab', $lab, '--shots', (Join-Path $lab 'shots-wo'), '--baseline', $baseline, '--setup', $setup)
  if ($Only) { $a += @('--only', $Only) }
  & $py @a *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'wo-proof.log')
  Log ("proof: " + ((Get-Content (Join-Path $lab 'wo-proof.log') -Tail 1)))

  Start-Sleep -Seconds 5
  if ($Only) { Log 'done (partial run: no rollback copy)'; return }
  if (LabRunning) { throw 'the lab instance is still open: rollback copy skipped' }
  $copy = Join-Path $lab 'rollback-copy\data'
  if (Test-Path (Split-Path $copy)) { Remove-Item -Recurse -Force (Split-Path $copy) }
  New-Item -ItemType Directory -Force $copy | Out-Null
  & robocopy (Join-Path $lab 'data') $copy /E /NFL /NDL /NJH /NJS /NP /XD logs | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $copy 'host\pgdata\postmaster.pid')
  Log 'rollback check on the copy (beta.31 -> beta.30, the real install version)'
  & $py -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --new $inst --old $prev `
      --data $copy --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out (Join-Path $lab 'wo-rollback.json') *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'wo-rollback.log')
  Log ("rollback: " + ((Get-Content (Join-Path $lab 'wo-rollback.log') -Tail 1)))
  Log 'done'
} catch {
  Log "stopped: $($_.Exception.Message)"
}
