# PROCESS-ACTIONS-20261111 on the lab (synthetic team): gate -> installer checks (P10, isolated) -> baseline by the previous
# lab install (beta.31) -> quiet update of a copy of beta.31 (the updater's path) -> lab install of the candidate -> practical
# proof (accept_actions: lab app, Kanban of a day, deletion, Boas-vindas, installer failures on copies, wizard walkthrough)
# -> rollback check on a copy (candidate -> beta.31). Started through an Explorer shortcut once the computer is idle. Native
# steps write to stderr: each step checks its own result. The installed RedRise of the person and its team are never touched.
param([ValidateSet('gate', 'proof')] [string] $From = 'gate', [string] $Only = '', [string] $V = '0.1.0-beta.32')
$ErrorActionPreference = 'Continue'
$repo = 'D:\Correnth\.claude\worktrees\elastic-cartwright-5e8477\.app-wo'
$lab = 'C:\Users\raulv\RedRise-v2-dev\lab-test'
$log = Join-Path $lab 'actions-chain.log'
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
  foreach ($d in 'nova-rotina', 'boas-vindas', 'stabilization', 'schedules', 'team-accounts', 'process-list-installer', 'process-actions') {
    Copy-Item -Recurse (Join-Path $repo "proofs\$d") (Join-Path $tools $d)
  }
}
"" | Out-File -Encoding utf8 $log
try {
  if (LabRunning) { throw 'the lab instance is open: close it first' }
  $prev = Join-Path $lab 'install-beta31'
  $baseline = Join-Path $lab 'actions-baseline.json'
  $tools = Join-Path $lab 'tools\proof-actions'
  $inst = Join-Path $lab ('install-beta' + $V.Split('.')[-1])
  $setup = "C:\Users\raulv\RedRise-v2-dev\release\$V\RedRise-Setup-$V.exe"
  CopyProofs $tools
  if ($From -eq 'gate') {
    Log "gate: verify-candidate $V"
    & (Join-Path $repo 'packaging\release\verify-candidate.ps1') -Version $V *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'actions-gate.log')
    $vj = Get-Content "C:\Users\raulv\RedRise-v2-dev\release\$V\verification.json" -Raw | ConvertFrom-Json
    Log "gate passed=$($vj.passed)"
    if (-not $vj.passed) { throw 'gate failed' }

    Log 'installer checks (P10, isolated): corrupted, install, reinstall, rollback, uninstall'
    $p10 = Join-Path $lab 'actions-p10'
    if (Test-Path $p10) { Remove-Item -Recurse -Force $p10 }
    & (Join-Path $repo 'proofs\installer\p10-installer-checks.ps1') -Setup $setup -OutDir $p10 *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'actions-p10.log')
    $sum = ((Get-Content (Join-Path $p10 'summary.json') -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ')
    Log ("p10: " + $sum.Substring(0, [Math]::Min(400, $sum.Length)))

    Log 'baseline by the previous lab install (beta.31) on the lab data'
    & (Join-Path $prev 'runtime\python\python.exe') -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --baseline-with $prev `
        --data (Join-Path $lab 'data') --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out $baseline *>&1 |
      Out-File -Encoding utf8 (Join-Path $lab 'actions-baseline.log')
    if (-not (Test-Path $baseline)) { throw 'baseline not written' }
    Log 'baseline written'

    Log 'quiet update of a copy of beta.31 (the in-app update path: --quiet, no wizard, no role question)'
    $uc = Join-Path $lab 'update-copy\Programs\@redrise'
    if (Test-Path (Split-Path (Split-Path $uc))) { Remove-Item -Recurse -Force (Split-Path (Split-Path $uc)) }
    New-Item -ItemType Directory -Force (Split-Path $uc) | Out-Null
    & robocopy $prev $uc /E /NFL /NDL /NJH /NJS /NP | Out-Null
    $p = Start-Process -FilePath $setup -ArgumentList @('--quiet', '--install-root', $uc) -Wait -PassThru -NoNewWindow `
         -RedirectStandardOutput (Join-Path $lab 'install-log\update-copy.json')
    $man = Get-Content (Join-Path $uc 'manifest.json') -Raw | ConvertFrom-Json
    Log "update copy exit=$($p.ExitCode) version=$($man.app_version) previous_kept=$(Test-Path ($uc + '.previous'))"
    if ($p.ExitCode -ne 0 -or $man.app_version -ne $V) { throw 'quiet update of the copy failed' }
    Remove-Item -Recurse -Force (Split-Path (Split-Path $uc))

    if (Test-Path $inst) { throw "exists: $inst" }
    $p = Start-Process -FilePath $setup -ArgumentList @('--quiet', '--install-root', $inst) -Wait -PassThru -NoNewWindow `
         -RedirectStandardOutput (Join-Path $lab "install-log\install-$V.json")
    Log "install exit=$($p.ExitCode)"
    if ($p.ExitCode -ne 0 -or -not (Test-Path (Join-Path $inst 'RedRise.exe'))) { throw 'install failed' }
  } else { Log 'from the proof: gate, checks, baseline and install of an earlier run; proof scripts copied again' }

  $py = Join-Path $inst 'runtime\python\python.exe'
  # The lab window cannot take the foreground from the Claude desktop app's window (the UI driver refuses to type then):
  # that one window is minimized while the person is away, and restored after the proof. No input is sent.
  Add-Type -Namespace CF -Name W -MemberDefinition '[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h, out uint p); [DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c);'
  $fg = [CF.W]::GetForegroundWindow(); $fp = 0; [void][CF.W]::GetWindowThreadProcessId($fg, [ref]$fp)
  $parked = $null
  if ($fg -ne [IntPtr]::Zero -and (Get-Process -Id $fp -ErrorAction SilentlyContinue).ProcessName -eq 'claude') {
    [void][CF.W]::ShowWindow($fg, 6); $parked = $fg; Log 'the Claude window was in front: minimized for the proof (no input)'
  }
  Log "proof: accept_actions $Only"
  $a = @('-B', '-X', 'utf8', (Join-Path $tools 'process-actions\accept_actions.py'), '--lab', $lab, '--shots', (Join-Path $lab 'shots-actions'),
         '--baseline', $baseline, '--setup', $setup, '--previous', $prev)
  if ($Only) { $a += @('--only', $Only) }
  & $py @a *>&1 | Out-File -Encoding utf8 (Join-Path $lab 'actions-proof.log')
  Log ("proof: " + ((Get-Content (Join-Path $lab 'actions-proof.log') -Tail 1)))
  if ($parked) { [void][CF.W]::ShowWindow($parked, 9); Log 'the Claude window was restored' }

  Start-Sleep -Seconds 5
  if ($Only) { Log 'done (partial run: no rollback copy)'; return }
  if (LabRunning) { throw 'the lab instance is still open: rollback copy skipped' }
  $copy = Join-Path $lab 'rollback-copy\data'
  if (Test-Path (Split-Path $copy)) { Remove-Item -Recurse -Force (Split-Path $copy) }
  New-Item -ItemType Directory -Force $copy | Out-Null
  & robocopy (Join-Path $lab 'data') $copy /E /NFL /NDL /NJH /NJS /NP /XD logs | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $copy 'host\pgdata\postmaster.pid')
  Log "rollback check on the copy ($V -> beta.31, the real install version)"
  & $py -B -X utf8 (Join-Path $tools 'stabilization\rollback_check.py') --new $inst --old $prev `
      --data $copy --vault 'rrtest2-host' --account (Join-Path $lab 'test-account.json') --out (Join-Path $lab 'actions-rollback.json') *>&1 |
    Out-File -Encoding utf8 (Join-Path $lab 'actions-rollback.log')
  Log ("rollback: " + ((Get-Content (Join-Path $lab 'actions-rollback.log') -Tail 1)))
  Log 'done'
} catch {
  Log "stopped: $($_.Exception.Message)"
}
