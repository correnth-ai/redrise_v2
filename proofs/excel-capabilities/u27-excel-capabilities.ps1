<#
.SYNOPSIS
  U27 localized native checks of the Excel capabilities through the packaged
  Runner (no recording/replay campaign):
    1. excel-discover            -> found + validated descriptor (native)
    2. excel-start --descriptor  -> new Excel process, blank workbook ready (native, short)
    3. excel-start with an invalid descriptor fixture -> CONTRACT-EXCEL-DESCRIPTOR, nothing launched
    4. excel-new                 -> discover -> start composition (native)
  Each Excel opened here is our own /x process with an unmodified blank
  workbook; it is closed with WM_CLOSE afterwards (never killed, no save).
#>
param(
  [Parameter(Mandatory)] [string] $Install,
  [Parameter(Mandatory)] [string] $OutDir
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$data = Join-Path $OutDir 'data'
$py = Join-Path $Install 'runtime\python\python.exe'

Add-Type -Namespace RR -Name W -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool PostMessageW(System.IntPtr h, uint m, System.IntPtr w, System.IntPtr l);
'@

function Runner([string[]] $ArgList, [string] $Name) {
  $o = & $py -B -X utf8 -m redrise_runner --data-root $data @ArgList
  $code = $LASTEXITCODE
  $text = ($o -join "`n")
  [System.IO.File]::WriteAllText((Join-Path $OutDir "$Name.json"), $text, [System.Text.UTF8Encoding]::new($false))
  return @{ code = $code; json = ($text | ConvertFrom-Json) }
}

function Close-Excel([int] $ProcId) {
  $p = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
  if ($p -and $p.MainWindowHandle -ne 0) { [void][RR.W]::PostMessageW($p.MainWindowHandle, 0x10, [IntPtr]::Zero, [IntPtr]::Zero) }
  for ($i = 0; $i -lt 40; $i++) { if (-not (Get-Process -Id $ProcId -ErrorAction SilentlyContinue)) { return 'closed' }; Start-Sleep -Milliseconds 250 }
  return 'still_running'
}

$summary = [ordered]@{}
$r1 = Runner @('excel-discover') 'discover'
$summary.discover = @{ exit = $r1.code; status = $r1.json.status; method = $r1.json.descriptor.method; version = $r1.json.descriptor.version }
$desc = Join-Path $OutDir 'descriptor.json'
($r1.json.descriptor | ConvertTo-Json) | Set-Content -Encoding utf8 $desc

$before = @(Get-Process EXCEL -ErrorAction SilentlyContinue).Count
$r2 = Runner @('excel-start', '--descriptor', $desc) 'start'
$summary.start = @{ exit = $r2.code; status = $r2.json.status; dismissed = $r2.json.start_screen_dismissed; pid = $r2.json.pid; excel_before = $before }
if ($r2.json.pid) { $summary.start.close = Close-Excel $r2.json.pid }

$bad = Join-Path $OutDir 'descriptor-invalid.json'
'{"schema":"redrise.excel-descriptor/0","executable":"cmd.exe","version":"x","method":"guess"}' | Set-Content -Encoding utf8 $bad
$before = @(Get-Process EXCEL -ErrorAction SilentlyContinue).Count
$r3 = Runner @('excel-start', '--descriptor', $bad) 'start-invalid'
$summary.invalid = @{ exit = $r3.code; error_code = $r3.json.diagnostic.error_code; launched = (@(Get-Process EXCEL -ErrorAction SilentlyContinue).Count -ne $before); footer = ($r3.json.message -split "`n")[-1] }

$r4 = Runner @('excel-new') 'new'
$summary.new = @{ exit = $r4.code; status = $r4.json.status; stage = $r4.json.stage; pid = $r4.json.pid }
if ($r4.json.pid) { $summary.new.close = Close-Excel $r4.json.pid }

$summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $OutDir 'summary.json')
$summary | ConvertTo-Json -Depth 4
