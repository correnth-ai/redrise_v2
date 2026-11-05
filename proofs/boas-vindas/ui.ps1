# Lab UI driver for the installed RedRise window only (UI Automation by element name; window-only screenshots).
# Usage: ui.ps1 -Do dump|shot|invoke|set|focus|keys [-Name n] [-Value v] [-Index i] [-Out file]
param([string]$Do = 'dump', [string]$Name, [string]$Value, [int]$Index = 0, [string]$Out, [string]$Type)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms, System.Drawing
Add-Type -Namespace Lab -Name W -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern bool GetWindowRect(System.IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(System.IntPtr c);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, System.UIntPtr e);
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h, System.IntPtr p);
[DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
[DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
[DllImport("user32.dll")] public static extern bool IsIconic(System.IntPtr h);
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern System.IntPtr FindWindow(string c, string t);
[DllImport("user32.dll")] public static extern bool PrintWindow(System.IntPtr h, System.IntPtr hdc, uint f);
public struct RECT { public int Left, Top, Right, Bottom; }
'@
[void][Lab.W]::SetProcessDpiAwarenessContext([IntPtr](-4))
if ($env:RR_UI_PID) {
  # The isolated test instance: only the window of that process, never the installed app.
  Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class LabPick {
  delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(CB c, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  public static IntPtr Find(uint pid) { IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); var c = new StringBuilder(64); GetClassName(h, c, 64);
      if (p == pid && c.ToString() == "Tauri Window") { found = h; return false; } return true; }, IntPtr.Zero);
    return found; }
}
'@
  $h = [LabPick]::Find([uint32]$env:RR_UI_PID)
} else { $h = [Lab.W]::FindWindow('Tauri Window', 'RedRise') }  # MainWindowHandle can be a helper window
if ($h -eq [IntPtr]::Zero) { 'NO_WINDOW'; exit 2 }
function Front {
  if ([Lab.W]::IsIconic($h)) { [void][Lab.W]::ShowWindow($h, 9); Start-Sleep -Milliseconds 400 }
  # Foreground lock: attach to the foreground thread so the request is honoured, as the Engine does.
  $ft = [Lab.W]::GetWindowThreadProcessId([Lab.W]::GetForegroundWindow(), [IntPtr]::Zero); $me = [Lab.W]::GetCurrentThreadId()
  $att = $ft -ne 0 -and $ft -ne $me -and [Lab.W]::AttachThreadInput($me, $ft, $true)
  [void][Lab.W]::SetForegroundWindow($h)
  if ($att) { [void][Lab.W]::AttachThreadInput($me, $ft, $false) }
  Start-Sleep -Milliseconds 250
  if ([Lab.W]::GetForegroundWindow() -ne $h) { 'NOT_FOREGROUND: no input sent'; exit 3 }
}
$root = [System.Windows.Automation.AutomationElement]::FromHandle($h)
$all = [System.Windows.Automation.TreeScope]::Descendants
function Find([string]$n) {
  $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $n)
  $els = @($root.FindAll($all, $c))
  if ($Type) { $els = @($els | Where-Object { $_.Current.ControlType.ProgrammaticName -like "*$Type" }) }
  if ($els.Count -le $Index) { throw "not found: '$n' [$Type] #$Index (count $($els.Count))" }
  $els[$Index]
}
switch ($Do) {
  'dump' {
    $els = $root.FindAll($all, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($e in $els) {
      $ct = $e.Current.ControlType.ProgrammaticName -replace 'ControlType\.', ''
      $n = $e.Current.Name
      if ($ct -in 'Button','Edit','ComboBox','CheckBox','RadioButton','MenuItem','Hyperlink','ListItem','TabItem','Text','Heading','DataItem','Custom' -and $n) {
        $v = ''
        try { $v = $e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value } catch {}
        "{0}|{1}|{2}" -f $ct, $n.Substring(0, [Math]::Min(90, $n.Length)), $v
      }
    }
  }
  'shot' {
    if ([Lab.W]::IsIconic($h)) { [void][Lab.W]::ShowWindow($h, 9); Start-Sleep -Milliseconds 500 }
    $r = New-Object Lab.W+RECT; [void][Lab.W]::GetWindowRect($h, [ref]$r)
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [void][Lab.W]::PrintWindow($h, $dc, 2); $g.ReleaseHdc($dc)  # window content only, even if covered
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); "saved $Out"
  }
  'invoke' {
    # UI Automation pattern, not input: it does not need the foreground.
    $e = Find $Name
    try { $e.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() }
    catch {
      try { $e.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select() }
      catch { $e.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Toggle() }
    }
    "invoked $Name"
  }
  'set' {
    Front
    $e = Find $Name
    $e.SetFocus(); Start-Sleep -Milliseconds 150
    [System.Windows.Forms.SendKeys]::SendWait('^a'); [System.Windows.Forms.SendKeys]::SendWait('{BACKSPACE}')
    $esc = ($Value.ToCharArray() | ForEach-Object { if ('+^%~(){}[]'.Contains($_)) { "{$_}" } else { "$_" } }) -join ''
    [System.Windows.Forms.SendKeys]::SendWait($esc)
    "set $Name"
  }
  'focus' { Front; (Find $Name).SetFocus(); "focused $Name" }
  'rect' { $r = (Find $Name).Current.BoundingRectangle; "{0} {1} {2} {3}" -f [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height }
  'click' {
    Front
    $r = (Find $Name).Current.BoundingRectangle
    [void][Lab.W]::SetCursorPos([int]($r.X + $r.Width / 2), [int]($r.Y + $r.Height / 2)); Start-Sleep -Milliseconds 100
    [Lab.W]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero); [Lab.W]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
    "clicked $Name"
  }
  'keys' { Front; [System.Windows.Forms.SendKeys]::SendWait($Value); "keys sent" }
}
