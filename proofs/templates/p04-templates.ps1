<#
.SYNOPSIS
  P04 dev-machine proof of the installed templates through the packaged Runner.
  - Boas-vindas into a lab Desktop stand-in (the real Desktop is only resolved, read-only),
    then a collision rerun (must refuse).
  - Excel with defaults and with other inputs (T10/T11 candidate), input workbook
    created earlier through the Excel UI (P01).
  - Outlook: detection/preconditions only (check-template; nothing launched).
  - Gmail: RedRise browser profile without login -> must report login_required.
  Closes only windows of processes that started during this proof (WM_CLOSE).
#>
param(
  [Parameter(Mandatory)] [string] $Install,
  [Parameter(Mandatory)] [string] $InputWorkbook,
  [string] $LabRoot = (Join-Path $env:USERPROFILE 'RedRise-v2-dev\proofs\p04-templates')
)
$ErrorActionPreference = 'Continue'
$runner = Join-Path $Install 'redrise-runner.cmd'
$run = Join-Path $LabRoot ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$data = Join-Path $run 'data'; $desk = Join-Path $run 'Desktop'; $xl = Join-Path $run 'excel'
New-Item -ItemType Directory -Force -Path $data, $desk, $xl | Out-Null
$result = [ordered]@{ run_dir = $run }

function Invoke-Runner([string]$name, [string[]]$a) {
  $f = Join-Path $run "$name.json"
  & $runner --data-root $data @a > $f
  $code = $LASTEXITCODE
  $j = Get-Content -Raw -LiteralPath $f | ConvertFrom-Json
  [ordered]@{ exit = $code; state = $j.state; code = $j.code; verified = $j.verified; file = "$name.json" }
}
function Close-New([string]$image, [int[]]$before) {
  Get-Process -Name $image -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id -and $_.MainWindowHandle -ne 0 } |
    ForEach-Object { [void]$_.CloseMainWindow(); $_.WaitForExit(15000) | Out-Null }
}
function Pids([string]$image) { @(Get-Process -Name $image -ErrorAction SilentlyContinue | ForEach-Object Id) }

# ---- Boas-vindas
$result.real_desktop_check = Invoke-Runner 'boas-vindas-check-real-desktop' @('check-template', '--template', 'boas-vindas')
$before = Pids 'notepad'
$result.boas_vindas = Invoke-Runner 'boas-vindas' @('run-template', '--template', 'boas-vindas', '--desktop-dir', $desk)
Start-Sleep 2; Close-New 'notepad' $before
$result.boas_vindas_collision = Invoke-Runner 'boas-vindas-collision' @('run-template', '--template', 'boas-vindas', '--desktop-dir', $desk)
$result.boas_vindas_file_sha256 = (Get-FileHash -Algorithm SHA256 (Join-Path $desk 'Boas_Vindas.txt') -ErrorAction SilentlyContinue).Hash

# ---- Excel (defaults, then other inputs)
$in = Join-Path $xl 'template_redrise.xlsx'
Copy-Item -LiteralPath $InputWorkbook -Destination $in; Set-ItemProperty -LiteralPath $in -Name IsReadOnly -Value $true
$before = Pids 'EXCEL'
$result.excel_defaults = Invoke-Runner 'excel-defaults' @('run-template', '--template', 'excel-pedido', '--input', "input_path=$in", '--input', "output_path=$xl\pedido-01.xlsx")
Start-Sleep 2; Close-New 'EXCEL' $before; Start-Sleep 2
$before = Pids 'EXCEL'
$result.excel_inputs = Invoke-Runner 'excel-inputs' @('run-template', '--template', 'excel-pedido', '--input', "input_path=$in", '--input', "output_path=$xl\pedido-02.xlsx", '--input', 'cliente=Cliente Teste 02', '--input', 'valor=2750')
Start-Sleep 2; Close-New 'EXCEL' $before
$result.excel_missing_input = Invoke-Runner 'excel-missing-input' @('run-template', '--template', 'excel-pedido', '--input', "input_path=$xl\nao-existe.xlsx", '--input', "output_path=$xl\x.xlsx")

# ---- Outlook (no launch) and Gmail
$result.outlook_check = Invoke-Runner 'outlook-check' @('check-template', '--template', 'outlook-abrir')
$result.gmail = Invoke-Runner 'gmail' @('run-template', '--template', 'gmail-acessar')
$result.candidate_browser = Invoke-Runner 'browser-candidate' @('run-template', '--template', 'browser-formulario')

$result.expected = [ordered]@{
  real_desktop_check = 'ready'; boas_vindas = 'verified'; boas_vindas_collision = 'refused/output_exists'
  excel_defaults = 'verified'; excel_inputs = 'verified'; excel_missing_input = 'precondition_missing/input_missing'
  outlook_check = 'ready'; gmail = 'login_required'; candidate_browser = 'refused/template_candidate_not_shipped'
}
$result.all_as_expected = (
  $result.real_desktop_check.state -eq 'ready' -and $result.boas_vindas.state -eq 'verified' -and
  $result.boas_vindas_collision.code -eq 'output_exists' -and $result.excel_defaults.state -eq 'verified' -and
  $result.excel_inputs.state -eq 'verified' -and $result.excel_missing_input.code -eq 'input_missing' -and
  $result.outlook_check.state -eq 'ready' -and $result.gmail.state -eq 'login_required' -and
  $result.candidate_browser.code -eq 'template_candidate_not_shipped')
$result | ConvertTo-Json -Depth 5 | Tee-Object -FilePath (Join-Path $run 'summary.json')
