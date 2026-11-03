<#
.SYNOPSIS
  P10 localized installer checks in an isolated install root (lab, C:):
    1. corrupted package -> refused, target untouched
    2. quiet install -> files verified, health of the installed layout
    3. second install over it -> previous version kept
    4. rollback -> previous restored
    5. uninstall -> install folder removed, data folder kept
  The product default (%LOCALAPPDATA%\Programs\@redrise) is exercised separately
  by the real install.
#>
param(
  [Parameter(Mandatory)] [string] $Setup,
  [Parameter(Mandatory)] [string] $OutDir
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$root = Join-Path $OutDir 'Programs\@redrise'
function Run([string[]] $a, [string] $name, [string] $exe = $Setup) {
  $p = Start-Process -FilePath $exe -ArgumentList $a -Wait -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $OutDir "$name.json")
  return @{ exit = $p.ExitCode; out = (Get-Content (Join-Path $OutDir "$name.json") -Raw) }
}
$s = [ordered]@{}

# 1. corrupted copy (one byte flipped inside the payload)
$bad = Join-Path $OutDir 'corrupted-setup.exe'
Copy-Item $Setup $bad
$fs = [System.IO.File]::Open($bad, 'Open', 'ReadWrite')
try { $fs.Seek([long]($fs.Length / 2), 'Begin') | Out-Null; $b = $fs.ReadByte(); $fs.Seek(-1, 'Current') | Out-Null; $fs.WriteByte(($b -bxor 0xFF)) } finally { $fs.Dispose() }
$r = Run @('--quiet', '--install-root', $root) 'corrupted' $bad
$s.corrupted = @{ exit = $r.exit; installed = (Test-Path $root); message = ($r.out | ConvertFrom-Json).error }
Remove-Item $bad

# 2. install
$t0 = Get-Date
$r = Run @('--quiet', '--install-root', $root) 'install-1'
$s.install = @{ exit = $r.exit; seconds = [int]((Get-Date) - $t0).TotalSeconds; result = ($r.out | ConvertFrom-Json).result }
$py = Join-Path $root 'runtime\python\python.exe'
$h = & $py -B -X utf8 -m redrise_runner --data-root (Join-Path $OutDir 'data') health
$hj = ($h -join "`n") | ConvertFrom-Json
$s.installed_health = @{ status = $hj.status; integrity = $hj.integrity.ok; files = $hj.integrity.files; uninstall_exe = (Test-Path (Join-Path $root 'uninstall.exe')) }

# 3. second install keeps previous
$r = Run @('--quiet', '--install-root', $root) 'install-2'
$s.reinstall = @{ exit = $r.exit; previous_kept = (Test-Path ($root + '.previous')) }

# 4. rollback
'marker' | Set-Content (Join-Path ($root + '.previous') 'rollback-marker.txt')
# Documented path: the installed uninstall.exe (inside the install folder) hands over to a temp copy.
$r = Run @('--quiet', '--rollback', '--install-root', $root) 'rollback' (Join-Path $root 'uninstall.exe')
for ($i = 0; $i -lt 60 -and -not (Test-Path (Join-Path $root 'rollback-marker.txt')); $i++) { Start-Sleep -Milliseconds 500 }
$s.rollback = @{ exit = $r.exit; via = 'installed uninstall.exe'; restored = (Test-Path (Join-Path $root 'rollback-marker.txt')) }
Remove-Item (Join-Path $root 'rollback-marker.txt')

# 5. uninstall (run the installed uninstall.exe)
New-Item -ItemType Directory -Force (Join-Path $OutDir 'data-kept') | Out-Null
$r = Run @('--uninstall', '--quiet', '--install-root', $root) 'uninstall' (Join-Path $root 'uninstall.exe')
Start-Sleep -Seconds 5
$s.uninstall = @{ exit = $r.exit; root_removed = -not (Test-Path $root); out = ($r.out | ConvertFrom-Json) }
$s | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $OutDir 'summary.json')
$s | ConvertTo-Json -Depth 5
