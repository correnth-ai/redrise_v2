# Lab driver for the Windows "Abrir" dialog that the RedRise window owns: folder in the navigation
# field (Alt+D), only the file name in "Nome". Usage: open_dialog.ps1 -AppPid n -Folder dir -File name | -Cancel
param([int]$AppPid, [string]$Folder, [string]$File, [switch]$Cancel, [switch]$Probe)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class LabDialog {
  delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(CB c, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  public static IntPtr Find(uint pid) { IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); var c = new StringBuilder(64); GetClassName(h, c, 64);
      if (p == pid && IsWindowVisible(h) && c.ToString() == "#32770") { found = h; return false; } return true; }, IntPtr.Zero);
    return found; }
}
'@
$h = [IntPtr]::Zero
for ($i = 0; $i -lt 40 -and $h -eq [IntPtr]::Zero; $i++) { $h = [LabDialog]::Find([uint32]$AppPid); if ($h -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 250 } }
if ($h -eq [IntPtr]::Zero) { 'NO_DIALOG'; exit 2 }
if ($Probe) { 'DIALOG'; exit 0 }
$ft = [LabDialog]::GetWindowThreadProcessId([LabDialog]::GetForegroundWindow(), [IntPtr]::Zero); $me = [LabDialog]::GetCurrentThreadId()
$att = $ft -ne 0 -and $ft -ne $me -and [LabDialog]::AttachThreadInput($me, $ft, $true)
[void][LabDialog]::SetForegroundWindow($h)
if ($att) { [void][LabDialog]::AttachThreadInput($me, $ft, $false) }
Start-Sleep -Milliseconds 300
if ([LabDialog]::GetForegroundWindow() -ne $h) { 'NOT_FOREGROUND: no input sent'; exit 3 }
$esc = { param($s) ($s.ToCharArray() | ForEach-Object { if ('+^%~(){}[]'.Contains($_)) { "{$_}" } else { "$_" } }) -join '' }
if ($Cancel) { [System.Windows.Forms.SendKeys]::SendWait('{ESC}'); 'CANCELLED'; exit 0 }
[System.Windows.Forms.SendKeys]::SendWait('%d'); Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait((& $esc $Folder)); [System.Windows.Forms.SendKeys]::SendWait('~'); Start-Sleep -Milliseconds 900
[System.Windows.Forms.SendKeys]::SendWait('%n'); Start-Sleep -Milliseconds 300  # Alt+N: "Nome"
[System.Windows.Forms.SendKeys]::SendWait((& $esc $File)); Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait('~')
'OPENED'
