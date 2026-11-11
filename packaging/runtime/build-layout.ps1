<#
.SYNOPSIS
  Assembles the app-managed binary layout (P02): Engine + private CPython +
  Runner, with a hash manifest and licence inventory. Output is a directory
  that the P10 installer will place at %LOCALAPPDATA%\Programs\@redrise.

  Layout:
    <out>\engine\redrise-engine.exe
    <out>\runtime\python\...            CPython 3.12.10 x64 (nuget.org "python"), pruned
    <out>\runtime\python\python312._pth fixed sys.path; isolated mode (PYTHON* env ignored)
    <out>\runner\redrise_runner\...     stdlib-only Runner
    <out>\contracts\...                 error catalog, module registry, schemas, redrise_contracts
    <out>\redrise-runner.cmd            launcher (dev form; final launcher decided in P08/P10)
    <out>\licenses\...                  PSF licence, Rust crate inventory
    <out>\manifest.json                 every file with sha256

  Mutable data is never written here (-B: no .pyc; data goes to %LOCALAPPDATA%\RedRise).
#>
param(
  [Parameter(Mandatory)] [string] $Engine,
  [Parameter(Mandatory)] [string] $PythonNupkg,
  [Parameter(Mandatory)] [string] $Out,
  # P03 (optional): pinned Playwright install target and browsers directory
  # prepared at build time (`playwright install --no-shell chromium`).
  [string] $PlaywrightSite,
  [string] $Browsers,
  # P06/P08/P10 (optional): Core third-party site (psycopg, cryptography), PostgreSQL
  # binaries folder (EDB pgsql), desktop exe (becomes RedRise.exe) and app version.
  [string] $CoreSite,
  [string] $Postgres,
  [string] $Desktop,
  # Identity (optional): public project URL and publishable key, kept outside the repository.
  [string] $IdentityConfig,
  [string] $AppVersion = '0.0.0-dev',
  [string] $ExpectedNupkgSha512 = 'u9pNz2iKlCEbYtUJaKkbOPMF0LjR7NkCafdKhvigpPzrt8oWKgdTpHaR6z3wyWQAm9PYGUxv0Zr66NX9AeHMDw=='
)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\..')
if (Test-Path -LiteralPath $Out) { throw "output exists: $Out (layouts are built into a new directory)" }

# ---- verify the CPython package against the NuGet catalog hash
$sha = [System.Security.Cryptography.SHA512]::Create()
$fs = [System.IO.File]::OpenRead($PythonNupkg)
try { $nupkgSha512 = [Convert]::ToBase64String($sha.ComputeHash($fs)) } finally { $fs.Dispose() }
if ($nupkgSha512 -ne $ExpectedNupkgSha512) { throw "python nupkg SHA512 mismatch: $nupkgSha512" }

$tmp = Join-Path ([System.IO.Path]::GetDirectoryName($Out)) ("_extract-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Copy-Item -LiteralPath $PythonNupkg -Destination (Join-Path $tmp 'p.zip')
Expand-Archive -LiteralPath (Join-Path $tmp 'p.zip') -DestinationPath (Join-Path $tmp 'x')
$tools = Join-Path $tmp 'x\tools'

$py = Join-Path $Out 'runtime\python'
New-Item -ItemType Directory -Force -Path $py, (Join-Path $Out 'engine'), (Join-Path $Out 'runner'), (Join-Path $Out 'licenses') | Out-Null
foreach ($item in 'python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'DLLs', 'Lib') {
  Copy-Item -LiteralPath (Join-Path $tools $item) -Destination $py -Recurse
}
# Prune: package manager, test suites, IDE/Tk, dev headers (not used by the Runner).
foreach ($rel in 'Lib\site-packages', 'Lib\test', 'Lib\idlelib', 'Lib\ensurepip', 'Lib\tkinter', 'Lib\turtledemo', 'Lib\turtle.py', 'Lib\venv', 'DLLs\_tkinter.pyd', 'DLLs\tcl86t.dll', 'DLLs\tk86t.dll') {
  $p = Join-Path $py $rel
  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
}
Get-ChildItem -LiteralPath $py -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Path (Join-Path $py 'Lib\site-packages') | Out-Null
# ._pth: exact sys.path; its presence also puts CPython in isolated mode.
$pth = "Lib`r`nDLLs`r`n..\..\runner`r`n..\..\contracts\python`r`n"
if ($PlaywrightSite) {
  # Third-party packages for the browser adapter only (no pip in the runtime).
  foreach ($d in Get-ChildItem -LiteralPath $PlaywrightSite) {
    if ($d.Name -in 'bin', 'include') { continue }
    Copy-Item -LiteralPath $d.FullName -Destination (Join-Path $py 'Lib\site-packages') -Recurse
  }
  Get-ChildItem -LiteralPath (Join-Path $py 'Lib\site-packages') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  New-Item -ItemType Directory -Force -Path (Join-Path $Out 'browser') | Out-Null
  Copy-Item -LiteralPath (Join-Path $repo 'browser\redrise_browser') -Destination (Join-Path $Out 'browser') -Recurse
  Get-ChildItem -LiteralPath (Join-Path $Out 'browser') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  Copy-Item -LiteralPath $Browsers -Destination (Join-Path $Out 'browsers') -Recurse
  foreach ($di in Get-ChildItem -LiteralPath $PlaywrightSite -Directory -Filter '*.dist-info') {
    foreach ($lf in Get-ChildItem -LiteralPath $di.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICEN[CS]E|NOTICE|COPYING)' }) {
      Copy-Item -LiteralPath $lf.FullName -Destination (Join-Path $Out ("licenses\" + $di.Name.Split('-')[0] + "-" + $lf.Name))
    }
  }
  Copy-Item -LiteralPath (Join-Path $PlaywrightSite 'playwright\driver\LICENSE') -Destination (Join-Path $Out 'licenses\playwright-driver-node-LICENSE.txt')
  $pth += "Lib\site-packages`r`n..\..\browser`r`n"
}
if ($CoreSite) {
  # Core packages (no pip in the runtime); same site folder as the browser packages.
  foreach ($d in Get-ChildItem -LiteralPath $CoreSite) {
    if ($d.Name -in 'bin', 'include') { continue }
    Copy-Item -LiteralPath $d.FullName -Destination (Join-Path $py 'Lib\site-packages') -Recurse -Force
  }
  Get-ChildItem -LiteralPath (Join-Path $py 'Lib\site-packages') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  foreach ($di in Get-ChildItem -LiteralPath $CoreSite -Directory -Filter '*.dist-info') {
    foreach ($lf in Get-ChildItem -LiteralPath $di.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICEN[CS]E|NOTICE|COPYING)' }) {
      Copy-Item -LiteralPath $lf.FullName -Destination (Join-Path $Out ("licenses\" + $di.Name.Split('-')[0] + "-" + $lf.Name)) -Force
    }
  }
  if ($pth -notmatch 'site-packages') { $pth += "Lib\site-packages`r`n" }
  $pth += "..\..\core`r`n"
  New-Item -ItemType Directory -Force -Path (Join-Path $Out 'core') | Out-Null
  Copy-Item -LiteralPath (Join-Path $repo 'core\redrise_core') -Destination (Join-Path $Out 'core') -Recurse
  Get-ChildItem -LiteralPath (Join-Path $Out 'core') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
}
if ($Postgres) {
  # Server binaries only: bin, share, DLLs of lib (no pgAdmin, docs, headers, StackBuilder).
  $pgOut = Join-Path $Out 'postgres'
  New-Item -ItemType Directory -Force -Path (Join-Path $pgOut 'lib') | Out-Null
  Copy-Item -LiteralPath (Join-Path $Postgres 'bin') -Destination $pgOut -Recurse
  Copy-Item -LiteralPath (Join-Path $Postgres 'share') -Destination $pgOut -Recurse
  Get-ChildItem -LiteralPath (Join-Path $Postgres 'lib') -Filter '*.dll' | Copy-Item -Destination (Join-Path $pgOut 'lib')
  $legal = Join-Path $Postgres 'doc\postgresql\html\legalnotice.html'
  if (Test-Path -LiteralPath $legal) { Copy-Item -LiteralPath $legal -Destination (Join-Path $Out 'licenses\PostgreSQL-legalnotice.html') }
}
if ($Desktop) { Copy-Item -LiteralPath $Desktop -Destination (Join-Path $Out 'RedRise.exe') }
[System.IO.File]::WriteAllText((Join-Path $py 'python312._pth'), $pth, [System.Text.Encoding]::ASCII)
Copy-Item -LiteralPath (Join-Path $tools 'LICENSE.txt') -Destination (Join-Path $Out 'licenses\PSF-CPython-3.12.10.txt')
Remove-Item -LiteralPath $tmp -Recurse -Force

# ---- Engine and Runner
Copy-Item -LiteralPath $Engine -Destination (Join-Path $Out 'engine\redrise-engine.exe')
Copy-Item -LiteralPath (Join-Path $repo 'runner\redrise_runner') -Destination (Join-Path $Out 'runner') -Recurse
Get-ChildItem -LiteralPath (Join-Path $Out 'runner') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repo 'templates') -Destination (Join-Path $Out 'templates') -Recurse
Copy-Item -LiteralPath (Join-Path $repo 'desktop\licenses\playfair-display-OFL.txt') -Destination (Join-Path $Out 'licenses\playfair-display-OFL.txt')  # the font bundled in the UI
# The authorized mark, byte for byte, for what the Runner generates (report PDF).
New-Item -ItemType Directory -Force -Path (Join-Path $Out 'assets') | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'assets\brand\redrise\redrise-icon-128x128.png') -Destination (Join-Path $Out 'assets\redrise-icon-128x128.png')
# Shared contracts: error catalog, module registry, schemas, redrise_contracts (stdlib only)
New-Item -ItemType Directory -Force -Path (Join-Path $Out 'contracts') | Out-Null
foreach ($c in 'errors.json', 'modules.json', 'schemas', 'python') { Copy-Item -LiteralPath (Join-Path $repo "contracts\$c") -Destination (Join-Path $Out 'contracts') -Recurse }
Get-ChildItem -LiteralPath (Join-Path $Out 'contracts') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
[System.IO.File]::WriteAllText((Join-Path $Out 'redrise-runner.cmd'), "@`"%~dp0runtime\python\python.exe`" -B -X utf8 -m redrise_runner %*`r`n", [System.Text.Encoding]::ASCII)

# ---- Rust crate inventory of the shipped Engine (normal deps, licences)
Push-Location (Join-Path $repo 'engine')
try {
  $crates = & cargo tree -p redrise-engine -e normal --prefix none --format '{p}|{l}' --locked --target x86_64-pc-windows-msvc |
    ForEach-Object { ($_ -replace ' \(\*\)', '') -replace ' \([A-Za-z]:\\[^)]*\)', '' } | Sort-Object -Unique |
    ForEach-Object { $n, $l = $_ -split '\|', 2; [ordered]@{ crate = $n.Trim(); license = $l.Trim() } }
  # Superset: includes build-time proc-macro crates (serde_derive, syn, quote,
  # proc-macro2, unicode-ident) that are not linked into the binary.
} finally { Pop-Location }
$crates | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 (Join-Path $Out 'licenses\engine-crates.json')

# ---- The installer stub (the setup's wizard; uninstall.exe in this folder is the same stub): its crates and the MIT
# notice of InstallRS (PROCESS-LIST-INSTALLER-20261110), copied from the exact crate cargo resolved for the lockfile.
Push-Location (Join-Path $repo 'installer')
try {
  $icrates = & cargo tree -p redrise-setup -e normal --prefix none --format '{p}|{l}' --locked --target x86_64-pc-windows-msvc |
    ForEach-Object { ($_ -replace ' \(\*\)', '') -replace ' \([A-Za-z]:\\[^)]*\)', '' } | Sort-Object -Unique |
    ForEach-Object { $n, $l = $_ -split '\|', 2; [ordered]@{ crate = $n.Trim(); license = $l.Trim() } }
  $irs = (& cargo metadata --format-version 1 --locked --filter-platform x86_64-pc-windows-msvc | ConvertFrom-Json).packages |
    Where-Object { $_.name -eq 'installrs' } | Select-Object -First 1
} finally { Pop-Location }
$icrates | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 (Join-Path $Out 'licenses\installer-crates.json')
if (-not $irs) { throw 'installrs not found in the installer lockfile' }
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $irs.manifest_path) 'LICENSE.txt') -Destination (Join-Path $Out "licenses\installrs-$($irs.version)-LICENSE.txt")

if ($IdentityConfig -and (Test-Path -LiteralPath $IdentityConfig)) { Copy-Item -LiteralPath $IdentityConfig -Destination (Join-Path $Out 'identity.json') }

# ---- manifest (written last)
$files = Get-ChildItem -LiteralPath $Out -Recurse -File | Sort-Object FullName | ForEach-Object {
  [ordered]@{ path = $_.FullName.Substring($Out.Length + 1).Replace('\', '/'); size = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower() }
}
$manifest = [ordered]@{
  product = 'product:redrise-v2'
  layout_version = 1
  app_version = $AppVersion
  desktop = if ($Desktop) { [ordered]@{ path = 'RedRise.exe'; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Out 'RedRise.exe')).Hash.ToLower() } } else { $null }
  core = if ($CoreSite) { [ordered]@{ path = 'core/redrise_core'; packages = @(Get-ChildItem -LiteralPath $CoreSite -Directory -Filter '*.dist-info' | ForEach-Object { $_.Name -replace '\.dist-info$', '' }) } } else { $null }
  postgres = if ($Postgres) { [ordered]@{ version = '17.6-1'; source = 'https://get.enterprisedb.com/postgresql/postgresql-17.6-1-windows-x64-binaries.zip'; zip_sha256 = 'd378882abd001a186735acd6f6ba716bca6ccd192e800412d4fd15ed25376b3e'; path = 'postgres'; bound_to = '127.0.0.1 (app-managed by the host Core)' } } else { $null }
  built_at = (Get-Date).ToUniversalTime().ToString('o')
  install_scope = 'per-user'
  default_install_root = '%LOCALAPPDATA%\Programs\@redrise'
  data_root = '%LOCALAPPDATA%\RedRise'
  engine = [ordered]@{ path = 'engine/redrise-engine.exe'; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Out 'engine\redrise-engine.exe')).Hash.ToLower() }
  python = [ordered]@{ version = '3.12.10'; arch = 'x64'; source = 'https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg'; nupkg_sha512 = $nupkgSha512; license = 'licenses/PSF-CPython-3.12.10.txt'; third_party_packages = @(if ($PlaywrightSite) { Get-ChildItem -LiteralPath $PlaywrightSite -Directory -Filter '*.dist-info' | ForEach-Object { $_.Name -replace '\.dist-info$', '' } }) }
  runner = [ordered]@{ path = 'runner/redrise_runner'; launcher = 'redrise-runner.cmd'; dependencies = 'python stdlib only' }
  browser = if ($PlaywrightSite) { [ordered]@{
      adapter = 'browser/redrise_browser'
      packages = @(Get-ChildItem -LiteralPath $PlaywrightSite -Directory -Filter '*.dist-info' | ForEach-Object { $_.Name -replace '\.dist-info$', '' })
      browsers = @(Get-ChildItem -LiteralPath $Browsers -Directory | ForEach-Object Name)
      browsers_path = 'browsers (forced by the adapter; global ms-playwright cache never used)'
    } } else { $null }
  file_count = @($files).Count
  files = $files
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $Out 'manifest.json')
[ordered]@{ out = $Out; files = @($files).Count; bytes = [long]($files | ForEach-Object { $_.size } | Measure-Object -Sum).Sum; engine_sha256 = $manifest.engine.sha256 } | ConvertTo-Json
