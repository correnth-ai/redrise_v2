<#
.SYNOPSIS
  P02 acceptance on a CLEAN, DISPOSABLE Windows 11 x64 machine (run inside the VM).

  Prerequisites (the VM owner's job, see CLEAN-MACHINE-P02.md):
    - fresh Windows 11 x64, interactive unlocked session, no Python/Node/Rust;
    - Microsoft Excel (Microsoft 365) desktop installed and activated (target app);
    - this bundle copied to the VM; network disconnected for the offline passes.

  What it does:
    1. Records environment facts (OS, toolchains absent, Python registry keys, network).
    2. Installs the layout per-user into the REAL %LOCALAPPDATA%\Programs\@redrise
       (refuses if it already exists) - the VM is disposable.
    3. Runner health (private runtime, Engine, hooks, manifest integrity).
    4. P01 Excel scenario through the installed Engine + Runner job, twice:
       a) as is;  b) with an "incompatible global Python" simulated by a fake
       python.exe first on PATH plus bogus PYTHONHOME/PYTHONPATH.
    5. Leaves run directories under .\results for host-side verification
       (verify_engine_result.py). No Python is installed on the VM.
#>
param([string] $Bundle = (Split-Path -Parent $MyInvocation.MyCommand.Path))
$ErrorActionPreference = 'Stop'
$results = Join-Path $Bundle ('results-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $results | Out-Null
$facts = [ordered]@{}

# ---- 1. environment facts
$os = Get-CimInstance Win32_OperatingSystem
$facts.os = "$($os.Caption) $($os.Version) $($os.OSArchitecture)"
$facts.machine = $env:COMPUTERNAME
foreach ($t in 'python', 'python3', 'py', 'node', 'npm', 'rustc', 'cargo', 'pip') {
  $c = Get-Command $t -ErrorAction SilentlyContinue
  $facts["cmd_$t"] = if ($c) { $c.Source } else { $null }
}
$facts.python_registry = @(foreach ($k in 'HKCU:\Software\Python', 'HKLM:\Software\Python', 'HKLM:\Software\WOW6432Node\Python') { if (Test-Path $k) { (Get-ChildItem $k -Recurse | ForEach-Object Name) } })
$facts.network_up = @(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up' | ForEach-Object Name)
$facts.excel = (Get-Item 'C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE' -ErrorAction SilentlyContinue).VersionInfo.ProductVersion
$facts.local_app_data = [Environment]::GetFolderPath('LocalApplicationData')

# ---- 2. per-user install into the real LocalAppData
$install = Join-Path $facts.local_app_data 'Programs\@redrise'
if (Test-Path -LiteralPath $install) { throw "already installed at $install (use a fresh VM)" }
New-Item -ItemType Directory -Force -Path (Split-Path $install) | Out-Null
Copy-Item -LiteralPath (Join-Path $Bundle '@redrise') -Destination $install -Recurse
$facts.install_root = $install
$runner = Join-Path $install 'redrise-runner.cmd'

# ---- 3. health
& $runner health > (Join-Path $results 'health.json')
$facts.health_exit = $LASTEXITCODE

# ---- 4. P01 scenario, plain and with an incompatible "global Python"
$p01 = Join-Path $Bundle 'proofs\excel-engine\p01-excel.ps1'
$engine = Join-Path $install 'engine\redrise-engine.exe'
$data = Join-Path $facts.local_app_data 'RedRise'
$plain = & $p01 -Engine $engine -LabRoot (Join-Path $results 'p01-plain') -Runner $runner -RunnerDataRoot $data | ConvertFrom-Json
$facts.p01_plain = $plain

$fake = Join-Path $results 'fake-global-python'
New-Item -ItemType Directory -Force -Path $fake | Out-Null
Set-Content -Encoding ascii (Join-Path $fake 'python.cmd') '@echo incompatible global python & exit /b 99'
Copy-Item -LiteralPath (Join-Path $fake 'python.cmd') -Destination (Join-Path $fake 'python3.cmd')
$savedPath = $env:PATH
try {
  $env:PATH = "$fake;$env:PATH"; $env:PYTHONHOME = 'C:\Python27-incompatible'; $env:PYTHONPATH = 'C:\Python27-incompatible\Lib'
  & $runner health > (Join-Path $results 'health-incompatible-python.json')
  $facts.health_incompatible_python_exit = $LASTEXITCODE
  $hostile = & $p01 -Engine $engine -LabRoot (Join-Path $results 'p01-incompatible-python') -Runner $runner -RunnerDataRoot $data | ConvertFrom-Json
  $facts.p01_incompatible_python = $hostile
} finally {
  $env:PATH = $savedPath; Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue; Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
}

$facts | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $results 'vm-facts.json')
"Done. Copy '$results' back to the host and run verify_engine_result.py on each p01-*\run-* directory."
