<#
.SYNOPSIS
  Builds the RedRise installer stub (installer\, InstallRS wizard) on C: from the D: sources: copies the crate to a
  build folder, `cargo build --release` into <Lab>\target\installer (the path build-release.ps1 packs with), and copies
  Cargo.lock back to the sources (the lockfile is source). Prints the stub's SHA-256.
  -Locked refuses a lockfile change (a release build after the dependencies were reviewed).
#>
param(
  [string] $Lab = (Join-Path $env:USERPROFILE 'RedRise-v2-dev'),
  [switch] $Locked
)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\..')
$src = Join-Path $repo 'installer'
$build = Join-Path $Lab 'build\installer'
& robocopy $src $build /MIR /XD target /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
Push-Location $build
try {
  $env:CARGO_TARGET_DIR = Join-Path $Lab 'target\installer'
  $ErrorActionPreference = 'Continue'
  $cargoArgs = @('build', '--release')
  if ($Locked) { $cargoArgs += '--locked' }
  & cargo @cargoArgs
  if ($LASTEXITCODE -ne 0) { throw "cargo build failed ($LASTEXITCODE)" }
  $ErrorActionPreference = 'Stop'
  Copy-Item 'Cargo.lock' (Join-Path $src 'Cargo.lock') -Force
} finally { Pop-Location; Remove-Item Env:CARGO_TARGET_DIR -ErrorAction SilentlyContinue }
$exe = Join-Path $Lab 'target\installer\release\redrise-setup.exe'
[ordered]@{ exe = $exe; sha256 = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower(); bytes = (Get-Item $exe).Length } | ConvertTo-Json
