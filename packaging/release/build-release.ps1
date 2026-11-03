<#
.SYNOPSIS
  Builds one release candidate on C:: full layout (Engine, private runtime,
  Runner, Core, contracts, browser, PostgreSQL, templates, RedRise.exe) and
  the self-contained per-user installer. Prints versions and hashes.
  Prerequisites: Engine, desktop and installer already built (their own scripts).
#>
param(
  [Parameter(Mandatory)] [string] $Version,
  [string] $Lab = (Join-Path $env:USERPROFILE 'RedRise-v2-dev')
)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\..')
$d = Join-Path $Lab 'downloads'
$stage = Join-Path $Lab ("stage\release-$Version\@redrise")
if (Test-Path (Split-Path $stage)) { throw "stage exists: $(Split-Path $stage)" }
New-Item -ItemType Directory -Force (Split-Path $stage) | Out-Null
$layout = & (Join-Path $repo 'packaging\runtime\build-layout.ps1') -Engine (Join-Path $Lab 'target\engine\release\redrise-engine.exe') `
  -PythonNupkg "$d\p02-python\python.3.12.10.nupkg" -Out $stage -PlaywrightSite "$d\p03-playwright\site-packages" `
  -Browsers "$d\p03-playwright\browsers" -CoreSite "$d\p06-core\site-packages" -Postgres "$d\p06-core\pgsql" `
  -Desktop (Join-Path $Lab 'target\desktop\release\redrise-desktop.exe') -AppVersion $Version
$rel = Join-Path $Lab "release\$Version"
New-Item -ItemType Directory -Force $rel | Out-Null
$setup = Join-Path $rel "RedRise-Setup-$Version.exe"
if (Test-Path $setup) { throw "installer exists: $setup" }
$p = Start-Process -FilePath (Join-Path $Lab 'target\installer\release\redrise-setup.exe') -ArgumentList @('pack', '--layout', $stage, '--out', $setup) `
  -Wait -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $rel 'pack.json')
if ($p.ExitCode -ne 0) { throw "pack failed ($($p.ExitCode))" }
[ordered]@{ version = $Version; stage = $stage; layout = ($layout | ConvertFrom-Json); pack = (Get-Content (Join-Path $rel 'pack.json') -Raw | ConvertFrom-Json) } | ConvertTo-Json -Depth 4
