<#
.SYNOPSIS
  P02 localized checks (roadmap rev 4) on a built layout, current environment:
    1. health under a hostile Python environment (PYTHONPATH/PYTHONHOME/PYTHONSTARTUP set to junk)
    2. tamper: an unlisted file makes health unhealthy; removing it restores health
    3. private resolution: Runner, Core and their packages import from the layout only
#>
param(
  [Parameter(Mandatory)] [string] $Install,
  [Parameter(Mandatory)] [string] $OutDir
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$py = Join-Path $Install 'runtime\python\python.exe'
$data = Join-Path $OutDir 'data'
function Save($name, $lines) { [System.IO.File]::WriteAllText((Join-Path $OutDir $name), ($lines -join "`n"), [System.Text.UTF8Encoding]::new($false)) }

$env:PYTHONPATH = 'C:\nonexistent\evil'; $env:PYTHONHOME = 'C:\nonexistent\home'; $env:PYTHONSTARTUP = 'C:\nonexistent\x.py'
$h = & $py -B -X utf8 -m redrise_runner --data-root $data health; $hc = $LASTEXITCODE
Save 'health-hostile.json' $h

$extra = Join-Path $Install 'runner\redrise_runner\injected.py'
'x = 1' | Set-Content $extra
$t = & $py -B -X utf8 -m redrise_runner --data-root $data health; $tc = $LASTEXITCODE
Remove-Item $extra
Save 'health-tampered.json' $t
$r = & $py -B -X utf8 -m redrise_runner --data-root $data health; $rc = $LASTEXITCODE

$imp = & $py -B -X utf8 -c "import sys, psycopg, cryptography, redrise_core, redrise_runner, redrise_contracts, playwright; print({'psycopg': psycopg.__file__, 'cryptography': cryptography.__file__, 'core': redrise_core.__file__, 'runner': redrise_runner.__file__, 'contracts': redrise_contracts.__file__, 'playwright': playwright.__file__, 'sys_path': sys.path, 'pq_impl': psycopg.pq.__impl__, 'libpq': psycopg.pq.version()})"
Remove-Item Env:PYTHONPATH, Env:PYTHONHOME, Env:PYTHONSTARTUP
Save 'imports.txt' $imp

$hj = ($h -join "`n") | ConvertFrom-Json
$tj = ($t -join "`n") | ConvertFrom-Json
$summary = [ordered]@{
  health_hostile = @{ exit = $hc; status = $hj.status; runtime_ok = $hj.runtime.ok; integrity_ok = $hj.integrity.ok; env_python_vars_present = $hj.runtime.env_python_vars_present; engine = $hj.engine.path }
  tampered = @{ exit = $tc; status = $tj.status; unexpected = $tj.integrity.unexpected }
  restored = @{ exit = $rc }
  imports_from_layout = -not (($imp -join '') -match 'Users\\\\raulv\\\\RedRise-v2-dev\\\\(runtime|downloads)')
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $OutDir 'summary.json')
$summary | ConvertTo-Json -Depth 4
