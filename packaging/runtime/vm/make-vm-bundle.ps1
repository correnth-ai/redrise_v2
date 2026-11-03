<#
.SYNOPSIS
  Builds the folder to copy into the clean VM for P02 acceptance:
    <out>\@redrise\...                      layout from build-layout.ps1 (Engine + private CPython + Runner)
    <out>\proofs\operator\operator.ps1      lab synthetic operator
    <out>\proofs\excel-engine\p01-excel.ps1 P01 scenario (verification runs on the host)
    <out>\run-p02-on-clean-vm.ps1           entry point inside the VM
    <out>\bundle-manifest.json              sha256 of every bundle file
#>
param(
  [Parameter(Mandatory)] [string] $Layout,
  [Parameter(Mandatory)] [string] $Out
)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\..\..')
if (Test-Path -LiteralPath $Out) { throw "output exists: $Out" }
New-Item -ItemType Directory -Force -Path (Join-Path $Out 'proofs\operator'), (Join-Path $Out 'proofs\excel-engine') | Out-Null
Copy-Item -LiteralPath $Layout -Destination (Join-Path $Out '@redrise') -Recurse
Copy-Item -LiteralPath (Join-Path $repo 'proofs\operator\operator.ps1') -Destination (Join-Path $Out 'proofs\operator')
Copy-Item -LiteralPath (Join-Path $repo 'proofs\excel-engine\p01-excel.ps1') -Destination (Join-Path $Out 'proofs\excel-engine')
Copy-Item -LiteralPath (Join-Path $repo 'packaging\runtime\vm\run-p02-on-clean-vm.ps1') -Destination $Out
$files = Get-ChildItem -LiteralPath $Out -Recurse -File | Sort-Object FullName | ForEach-Object {
  [ordered]@{ path = $_.FullName.Substring($Out.Length + 1).Replace('\', '/'); sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower() }
}
[ordered]@{ built_at = (Get-Date).ToUniversalTime().ToString('o'); files = $files } | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $Out 'bundle-manifest.json')
[ordered]@{ out = $Out; files = @($files).Count } | ConvertTo-Json
