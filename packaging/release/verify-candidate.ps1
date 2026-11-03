<#
.SYNOPSIS
  Release gate (lab, C:): verifies one built candidate BEFORE it may be signed
  into the update channel. release_channel.py refuses to sign without a passed
  record for the same installer hash.
    1. isolated quiet install (never touches the real install, shortcut or registry)
    2. health and file integrity of the installed layout
    3. functional smoke from the installed layout: Boas-vindas N times idle and
       N times under full CPU load; each must be verified and close the app it opened
    4. isolated uninstall
  Writes release\<version>\verification.json. Needs the computer free (the
  smoke waits for 30 s without input and stops if someone uses it).
#>
param(
  [Parameter(Mandatory)] [string] $Version,
  [int] $Trials = 3,
  [string] $Lab = (Join-Path $env:USERPROFILE 'RedRise-v2-dev')
)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\..')
$rel = Join-Path $Lab "release\$Version"
$setup = Join-Path $rel "RedRise-Setup-$Version.exe"
if (-not (Test-Path $setup)) { throw "installer not found: $setup" }
$sha = (Get-FileHash -Algorithm SHA256 $setup).Hash.ToLower()
$work = Join-Path $Lab ("verify\$Version-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$root = Join-Path $work 'Programs\@redrise'
New-Item -ItemType Directory -Force $work | Out-Null
$checks = [ordered]@{}

function Run([string] $exe, [string[]] $a, [string] $name) {
  $p = Start-Process -FilePath $exe -ArgumentList $a -Wait -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $work "$name.out")
  return @{ exit = $p.ExitCode; out = (Get-Content (Join-Path $work "$name.out") -Raw -ErrorAction SilentlyContinue) }
}

# 1. isolated install
$r = Run $setup @('--quiet', '--install-root', $root) 'install'
$checks.install = @{ ok = ($r.exit -eq 0 -and (Test-Path (Join-Path $root 'RedRise.exe'))); exit = $r.exit }

# 2. health + integrity
$py = Join-Path $root 'runtime\python\python.exe'
if ($checks.install.ok) {
  $h = (& $py -B -X utf8 -m redrise_runner --data-root (Join-Path $work 'data') health) -join "`n" | ConvertFrom-Json
  $checks.health = @{ ok = ($h.status -eq 'healthy' -and $h.integrity.ok); status = $h.status; integrity = $h.integrity.ok; files = $h.integrity.files }
}

# 3. functional smoke from the installed layout
$smoke = Join-Path $repo 'packaging\release\smoke_templates.py'
foreach ($mode in 'idle', 'load') {
  if (-not ($checks.install.ok -and $checks.health.ok)) { break }
  $a = @('-B', '-X', 'utf8', $smoke, '--install-root', $root, '--out', (Join-Path $work 'smoke'), '--template', 'boas-vindas', '--trials', $Trials)
  if ($mode -eq 'load') { $a += '--load' }
  $out = (& $py @a) -join "`n"
  $res = $out | ConvertFrom-Json
  $checks["boas_vindas_$mode"] = @{ ok = [bool]$res.passed; stopped = $res.stopped; rows = $res.rows }
  if (-not $res.passed) { break }
}

# 4. isolated uninstall
if (Test-Path (Join-Path $root 'uninstall.exe')) {
  $r = Run (Join-Path $root 'uninstall.exe') @('--uninstall', '--quiet', '--install-root', $root) 'uninstall'
  $checks.uninstall = @{ ok = ($r.exit -eq 0); exit = $r.exit }
}

$passed = @('install', 'health', 'boas_vindas_idle', 'boas_vindas_load', 'uninstall') |
  ForEach-Object { $checks.Contains($_) -and $checks[$_].ok } | Where-Object { -not $_ } | Measure-Object | ForEach-Object { $_.Count -eq 0 }
$record = [ordered]@{
  schema = 'redrise.release-verification/1'; version = $Version; installer_sha256 = $sha
  verified_at = (Get-Date).ToString('o'); trials_per_mode = $Trials; work_dir = $work; checks = $checks; passed = $passed
}
$json = $record | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText((Join-Path $rel 'verification.json'), $json, (New-Object System.Text.UTF8Encoding($false)))
$json
if (-not $passed) { exit 1 }
