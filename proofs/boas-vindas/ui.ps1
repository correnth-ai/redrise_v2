# Lab UI driver for the installed RedRise window only (UI Automation by element name; window-only screenshots).
# Usage: ui.ps1 -Do dump|shot|invoke|set|focus|keys [-Name n] [-Value v] [-Index i] [-Out file]
param([string]$Do = 'dump', [string]$Name, [string]$Value, [int]$Index = 0, [string]$Out, [string]$Type)
$ErrorActionPreference = 'Stop'
if ($env:RR_UI_UTF8) { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 }  # callers that read UTF-8
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
Add-Type -Namespace Lab -Name N -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr SendMessage(System.IntPtr h, uint m, System.IntPtr w, System.IntPtr l);
[DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")] public static extern System.IntPtr SendMessageS(System.IntPtr h, uint m, System.IntPtr w, string l);
[DllImport("user32.dll")] public static extern bool PostMessage(System.IntPtr h, uint m, System.IntPtr w, System.IntPtr l);
[DllImport("user32.dll")] public static extern System.IntPtr GetParent(System.IntPtr h);
[DllImport("user32.dll")] public static extern int GetDlgCtrlID(System.IntPtr h);
[DllImport("user32.dll")] public static extern void SwitchToThisWindow(System.IntPtr h, bool alt);
[DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")] public static extern System.IntPtr SendMessageB(System.IntPtr h, uint m, System.IntPtr w, System.Text.StringBuilder l);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(System.IntPtr h, System.Text.StringBuilder s, int n);
'@
if ($env:RR_UI_PID) {
  # The isolated test instance: only the window of that process, never the installed app.
  Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class LabPick {
  delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(CB c, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  // cls "*": the visible top-level window of that process titled `title` (the installer wizard, its message boxes).
  public static IntPtr Find(uint pid, string cls, string title) { IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); var c = new StringBuilder(64); GetClassName(h, c, 64);
      var t = new StringBuilder(256); GetWindowText(h, t, 256);
      bool ok = cls == "*" ? IsWindowVisible(h) && (title == "" || t.ToString() == title) : c.ToString() == cls;
      if (p == pid && ok) { found = h; return false; } return true; }, IntPtr.Zero);
    return found; }
}
'@
  # RR_UI_CLASS=* drives a native window of that process (the installer wizard), RR_UI_TITLE picks it by title.
  $cls = if ($env:RR_UI_CLASS) { $env:RR_UI_CLASS } else { 'Tauri Window' }
  $title = if ($env:RR_UI_TITLE) { $env:RR_UI_TITLE } else { '' }
  $h = [LabPick]::Find([uint32]$env:RR_UI_PID, $cls, $title)
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
  if ([Lab.W]::GetForegroundWindow() -ne $h) {
    # No foreground window to attach to (e.g. right after another closed): minimize and restore this one, then ask the
    # shell to switch to it. Still no input is sent; if Windows keeps refusing, nothing is typed (exit 3 below).
    [void][Lab.W]::ShowWindow($h, 6); Start-Sleep -Milliseconds 300; [void][Lab.W]::ShowWindow($h, 9); Start-Sleep -Milliseconds 300
    [Lab.N]::SwitchToThisWindow($h, $true); Start-Sleep -Milliseconds 300
    [void][Lab.W]::SetForegroundWindow($h); Start-Sleep -Milliseconds 250
  }
  if ([Lab.W]::GetForegroundWindow() -ne $h) { 'NOT_FOREGROUND: no input sent'; exit 3 }
}
$root = [System.Windows.Automation.AutomationElement]::FromHandle($h)
$all = [System.Windows.Automation.TreeScope]::Descendants
function Find([string]$n) {
  if ($n.EndsWith('*') -and $n.Length -gt 1) {
    # A name ending in * matches by prefix (long names, e.g. a Kanban card).
    $p = $n.Substring(0, $n.Length - 1)
    $els = @($root.FindAll($all, [System.Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.Name.StartsWith($p) })
  } else {
    $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $n)
    $els = @($root.FindAll($all, $c))
  }
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
    # With Caps Lock on, SendKeys letters come out with the case inverted: send them inverted so the field gets the
    # value as given (the person's keyboard state is never changed).
    $caps = [System.Windows.Forms.Control]::IsKeyLocked([System.Windows.Forms.Keys]::CapsLock)
    $esc = ($Value.ToCharArray() | ForEach-Object {
      $ch = "$_"
      if ($caps -and (($_ -ge [char]'a' -and $_ -le [char]'z') -or ($_ -ge [char]'A' -and $_ -le [char]'Z'))) { $ch = if ([char]::IsUpper($_)) { $ch.ToLower() } else { $ch.ToUpper() } }
      if ('+^%~(){}[]'.Contains($_)) { "{$_}" } else { $ch } }) -join ''
    [System.Windows.Forms.SendKeys]::SendWait($esc)
    "set $Name"
  }
  'focus' { Front; (Find $Name).SetFocus(); "focused $Name" }
  'value' {
    # UI Automation's own SetValue on a field: no foreground and no keystrokes (a window Windows will not bring forward).
    (Find $Name).GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($Value)
    "value $Name"
  }
  'rect' { $r = (Find $Name).Current.BoundingRectangle; "{0} {1} {2} {3}" -f [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height }
  'click' {
    Front
    $e = Find $Name
    # An element below the fold is scrolled into view first; a point outside this window is never clicked
    # (it would land on whatever is there, e.g. the taskbar).
    try { $e.GetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern).ScrollIntoView(); Start-Sleep -Milliseconds 300 } catch {}
    $r = $e.Current.BoundingRectangle
    $w = New-Object Lab.W+RECT; [void][Lab.W]::GetWindowRect($h, [ref]$w)
    $cx = $r.X + $r.Width / 2; $cy = $r.Y + $r.Height / 2
    if ($r.IsEmpty -or $cx -lt $w.Left -or $cx -gt $w.Right -or $cy -lt $w.Top -or $cy -gt $w.Bottom) { 'OUTSIDE_WINDOW: no click sent'; exit 4 }
    [void][Lab.W]::SetCursorPos([int]($r.X + $r.Width / 2), [int]($r.Y + $r.Height / 2)); Start-Sleep -Milliseconds 100
    [Lab.W]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero); [Lab.W]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
    "clicked $Name"
  }
  'keys' { Front; [System.Windows.Forms.SendKeys]::SendWait($Value); "keys sent" }
  # Native controls (the installer wizard: winsafe controls reach UI Automation as plain panes). No input is sent: each
  # action is the control's own message, posted to it or to its parent, so it works without the foreground.
  'ndump' {
    foreach ($e in $root.FindAll($all, [System.Windows.Automation.Condition]::TrueCondition)) {
      $n = $e.Current.Name; $cl = $e.Current.ClassName
      if ($cl -eq 'ComboBox') {
        $ch = [IntPtr]$e.Current.NativeWindowHandle; $i = [Lab.N]::SendMessage($ch, 0x0147, [IntPtr]::Zero, [IntPtr]::Zero)  # CB_GETCURSEL
        $t = New-Object System.Text.StringBuilder 256
        if ($i.ToInt64() -ge 0) { [void][Lab.N]::SendMessageB($ch, 0x0148, $i, $t) }  # CB_GETLBTEXT
        "ComboBox||$t"; continue }
      if ($cl -eq 'Button' -and $n) { $st = [Lab.N]::SendMessage([IntPtr]$e.Current.NativeWindowHandle, 0x00F0, [IntPtr]::Zero, [IntPtr]::Zero); "Button|$n|$st"; continue }
      if ($n) { "{0}|{1}|" -f $cl, ($n -replace "`r?`n", ' ') }
    }
  }
  'nclick' {
    $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $Name)
    $els = @($root.FindAll($all, $c) | Where-Object { $_.Current.ClassName -eq 'Button' })
    if ($els.Count -le $Index) { throw "not found: native button '$Name'" }
    $bh = [IntPtr]$els[$Index].Current.NativeWindowHandle
    $id = [Lab.N]::GetDlgCtrlID($bh)
    [void][Lab.N]::PostMessage([Lab.N]::GetParent($bh), 0x0111, [IntPtr](($id -band 0xFFFF)), $bh)  # WM_COMMAND, BN_CLICKED (0)
    "clicked $Name"
  }
  'ncheck' {
    $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $Name)
    $e = $root.FindFirst($all, $c); if (-not $e) { throw "not found: '$Name'" }
    [void][Lab.N]::SendMessage([IntPtr]$e.Current.NativeWindowHandle, 0x00F1, [IntPtr][int]$Value, [IntPtr]::Zero)  # BM_SETCHECK
    "checked $Name = $Value"
  }
  'nselect' {
    $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, 'ComboBox')
    $e = $root.FindFirst($all, $c); if (-not $e) { throw 'no combo box' }
    $ch = [IntPtr]$e.Current.NativeWindowHandle
    $i = [Lab.N]::SendMessageS($ch, 0x0158, [IntPtr](-1), $Value)  # CB_FINDSTRINGEXACT
    if ($i.ToInt64() -lt 0) { throw "no item '$Value'" }
    [void][Lab.N]::SendMessage($ch, 0x014E, $i, [IntPtr]::Zero)  # CB_SETCURSEL
    "selected $Value"
  }
  'select' {
    # A native combo box (the installer wizard): -Name '*' takes the first one; the item named -Value is selected
    # through UI Automation, not by typing.
    if ($Name -eq '*') {
      $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::ComboBox)
      $e = $root.FindFirst($all, $c); if (-not $e) { throw 'no combo box' }
    } else { $e = Find $Name }
    try { $e.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand(); Start-Sleep -Milliseconds 300 } catch {}
    $ic = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $Value)
    $it = $e.FindFirst($all, $ic); if (-not $it) { throw "no item '$Value'" }
    $it.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    try { $e.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Collapse() } catch {}
    "selected $Value"
  }
}
