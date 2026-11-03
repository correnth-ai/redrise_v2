<#
.SYNOPSIS
  Lab-only synthetic operator. Plays the human demonstrating a task through
  the real UI while the RedRise Engine records. Independent of Engine code:
  uses System.Windows.Forms.SendKeys and user32 mouse calls.

  It never writes files itself; every file effect comes from the target
  application's own UI (e.g. Save As). Not shipped with the product.

.PARAMETER Scenario
  JSON array of actions:
    {"launch": "<exe>", "args": "<args>"}      start target, remember pid
    {"wait_window": <timeout_ms>}              until launched pid has a main window; activate it
    {"wait_class": "<class>", "timeout_ms": n} until foreground window class matches
    {"keys": "<SendKeys syntax>"}              e.g. "{F12}", "^s", "{ENTER}"
    {"text": "<literal>"}                      literal text (escaped for SendKeys)
    {"click_rel": [x, y]}                      left click relative to foreground window rect
    {"sleep": <ms>}
.PARAMETER PidFile
  Where the launched process id is written (for bounded cleanup by the caller).
#>
param(
  [Parameter(Mandatory)] [string] $Scenario,
  [Parameter(Mandatory)] [string] $PidFile
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -Namespace Lab -Name U32 -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern bool GetWindowRect(System.IntPtr h, out RECT r);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(System.IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, System.UIntPtr e);
[DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(System.IntPtr c);
public struct RECT { public int Left, Top, Right, Bottom; }
'@
[void][Lab.U32]::SetProcessDpiAwarenessContext([IntPtr](-4))  # per-monitor v2

function Get-FgClass {
  $sb = New-Object System.Text.StringBuilder 256
  [void][Lab.U32]::GetClassName([Lab.U32]::GetForegroundWindow(), $sb, 256)
  $sb.ToString()
}
function Escape-SendKeys([string]$s) {
  ($s.ToCharArray() | ForEach-Object { if ('+^%~(){}[]'.Contains($_)) { "{$_}" } else { "$_" } }) -join ''
}

$actions = Get-Content -Raw -LiteralPath $Scenario | ConvertFrom-Json
$launched = $null
$log = @()
foreach ($a in $actions) {
  $t0 = Get-Date
  if ($null -ne $a.launch) {
    $p = if ($a.args) { Start-Process -FilePath $a.launch -ArgumentList $a.args -PassThru } else { Start-Process -FilePath $a.launch -PassThru }
    $launched = $p
    $launchedName = [System.IO.Path]::GetFileNameWithoutExtension($a.launch)
    Set-Content -LiteralPath $PidFile -Value $p.Id
  } elseif ($null -ne $a.wait_window) {
    $deadline = (Get-Date).AddMilliseconds([int]$a.wait_window)
    $h = [IntPtr]::Zero
    $name = $launchedName
    do {
      Start-Sleep -Milliseconds 200
      # Launchers of single-instance apps (Excel, Windows 11 Notepad) may exit
      # and hand off to another pid; take the newest window of that image.
      $cand = Get-Process -Name $name -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -and $_.MainWindowHandle -ne [IntPtr]::Zero } |
        Sort-Object StartTime -Descending | Select-Object -First 1
      if ($cand) { $h = $cand.MainWindowHandle; Set-Content -LiteralPath $PidFile -Value $cand.Id }
    } while ($h -eq [IntPtr]::Zero -and (Get-Date) -lt $deadline)
    if ($h -eq [IntPtr]::Zero) { throw "window did not appear" }
    [void][Lab.U32]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 500
  } elseif ($null -ne $a.wait_class) {
    $deadline = (Get-Date).AddMilliseconds([int]$a.timeout_ms)
    while ((Get-FgClass) -ne $a.wait_class) {
      if ((Get-Date) -gt $deadline) { throw "foreground class '$($a.wait_class)' not reached (is '$(Get-FgClass)')" }
      Start-Sleep -Milliseconds 100
    }
  } elseif ($null -ne $a.keys) {
    [System.Windows.Forms.SendKeys]::SendWait($a.keys)
  } elseif ($null -ne $a.text) {
    foreach ($ch in $a.text.ToCharArray()) {
      [System.Windows.Forms.SendKeys]::SendWait((Escape-SendKeys "$ch"))
      Start-Sleep -Milliseconds 30
    }
  } elseif ($null -ne $a.click_rel) {
    $r = New-Object Lab.U32+RECT
    [void][Lab.U32]::GetWindowRect([Lab.U32]::GetForegroundWindow(), [ref]$r)
    [void][Lab.U32]::SetCursorPos($r.Left + [int]$a.click_rel[0], $r.Top + [int]$a.click_rel[1])
    Start-Sleep -Milliseconds 80
    [Lab.U32]::mouse_event(0x2, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 40
    [Lab.U32]::mouse_event(0x4, 0, 0, 0, [UIntPtr]::Zero)
  } elseif ($null -ne $a.sleep) {
    Start-Sleep -Milliseconds ([int]$a.sleep)
  } else { throw "unknown action $($a | ConvertTo-Json -Compress)" }
  $log += [pscustomobject]@{ action = ($a | ConvertTo-Json -Compress); ms = [int]((Get-Date) - $t0).TotalMilliseconds; fg_class = (Get-FgClass) }
  Start-Sleep -Milliseconds 150
}
$log | ConvertTo-Json -Depth 3
