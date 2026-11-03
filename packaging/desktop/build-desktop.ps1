<#
.SYNOPSIS
  Builds the desktop app (Tauri 2 + TypeScript Vanilla) on C: from the D:
  sources: copies desktop\ to a build folder, generates icons from the
  authorized logos, npm install (lockfile kept with the sources), tsc, and
  `tauri build` (no bundler: the RedRise installer packages the exe, P10).
  Output: <BuildRoot>\target\release\redrise-desktop.exe
#>
param(
  [string] $BuildRoot = (Join-Path $env:USERPROFILE 'RedRise-v2-dev\build\desktop'),
  [string] $TargetDir = (Join-Path $env:USERPROFILE 'RedRise-v2-dev\target\desktop'),
  [string] $ChannelUrl = 'http://127.0.0.1:47880/releases'
)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\..')
$src = Join-Path $repo 'desktop'
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
& robocopy $src $BuildRoot /MIR /XD node_modules dist gen target /XF package-lock.json /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
if (Test-Path (Join-Path $src 'package-lock.json')) { Copy-Item (Join-Path $src 'package-lock.json') $BuildRoot -Force }
$brand = Join-Path $repo 'assets\brand\redrise'
& node (Join-Path $repo 'packaging\desktop\make-ico.mjs') $brand (Join-Path $BuildRoot 'src-tauri\icons')
Push-Location $BuildRoot
try {
  $ErrorActionPreference = 'Continue'
  if (Test-Path 'package-lock.json') { & npm ci --no-audit --no-fund } else { & npm install --no-audit --no-fund }
  if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
  Copy-Item 'package-lock.json' (Join-Path $src 'package-lock.json') -Force   # lockfile is source
  $env:REDRISE_BRAND_DIR = $brand
  & npm run build:ui
  if ($LASTEXITCODE -ne 0) { throw "ui build failed" }
  $env:CARGO_TARGET_DIR = $TargetDir
  # Default update channel compiled into this build (closed beta: local isolated site, P12).
  $env:REDRISE_CHANNEL_URL = $ChannelUrl
  & npx tauri build --no-bundle
  if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }
  if (Test-Path 'src-tauri\Cargo.lock') { Copy-Item 'src-tauri\Cargo.lock' (Join-Path $src 'src-tauri\Cargo.lock') -Force }
} finally { Pop-Location }
$exe = Join-Path $TargetDir 'release\redrise-desktop.exe'
[ordered]@{ exe = $exe; sha256 = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower(); bytes = (Get-Item $exe).Length } | ConvertTo-Json
