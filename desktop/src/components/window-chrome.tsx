// Integrated window chrome (M04/M08): the native white title bar is off
// (tauri.conf decorations=false). The top strip is the drag region; round
// controls on the top right in the order minimize, maximize/restore, close;
// the moon turns the dark theme on, the sun turns the light theme on.
import { useEffect, useState } from "react";
import { Copy, Minus, Moon, Square, Sun, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";
const KEY = "rr.theme";

function readTheme(): Theme {
  try { const v = localStorage.getItem(KEY); if (v === "dark" || v === "light") return v; } catch { /* storage unavailable */ }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyStoredTheme(): void {
  document.documentElement.classList.toggle("dark", readTheme() === "dark");
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try { localStorage.setItem(KEY, theme); } catch { /* preference stays for this session only */ }
  }, [theme]);
  const dark = theme === "dark";
  return (
    <button type="button" onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "Ativar modo claro" : "Ativar modo escuro"} title={dark ? "Modo claro" : "Modo escuro"}
      className={cn("inline-flex size-8 items-center justify-center rounded-full text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring outline-none", className)}>
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

const win = () => window.__TAURI__?.window.getCurrentWindow();

export function WindowControls() {
  const [max, setMax] = useState(false);
  useEffect(() => {
    const w = win();
    if (!w) return;
    let off: (() => void) | undefined;
    w.isMaximized().then(setMax).catch(() => undefined);
    w.onResized(() => { w.isMaximized().then(setMax).catch(() => undefined); }).then((u) => { off = u; }).catch(() => undefined);
    return () => off?.();
  }, []);
  if (!win()) return null; // demo build in a plain browser: no window to control
  const btn = "inline-flex size-7 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-xs outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring";
  return (
    <div className="flex items-center gap-2" role="group" aria-label="Controles da janela">
      <button type="button" className={cn(btn, "hover:bg-accent")} aria-label="Minimizar" title="Minimizar" onClick={() => win()?.minimize()}>
        <Minus className="size-3.5" />
      </button>
      <button type="button" className={cn(btn, "hover:bg-accent")} aria-label={max ? "Restaurar" : "Maximizar"} title={max ? "Restaurar" : "Maximizar"}
        onClick={() => win()?.toggleMaximize()}>
        {max ? <Copy className="size-3" /> : <Square className="size-3" />}
      </button>
      <button type="button" className={cn(btn, "hover:border-destructive hover:bg-destructive hover:text-white")} aria-label="Fechar" title="Fechar"
        onClick={() => win()?.close()}>
        <X className="size-3.5" />
      </button>
    </div>
  );
}

/** Top strip: drag region (double click maximizes, native behavior), title slot, theme and window controls. */
export function TopBar({ children, overlay, afterTheme }: { children?: React.ReactNode; overlay?: boolean; afterTheme?: React.ReactNode }) {
  return (
    <header data-tauri-drag-region className={cn("flex h-12 shrink-0 select-none items-center gap-2 px-3", overlay ? "absolute inset-x-0 top-0 z-10" : "border-b bg-background")}>
      <div data-tauri-drag-region className="flex min-w-0 flex-1 items-center gap-2">{children}</div>
      <ThemeToggle className={overlay ? "border border-border bg-card shadow-xs" : undefined} />
      {afterTheme}
      <WindowControls />
    </header>
  );
}
