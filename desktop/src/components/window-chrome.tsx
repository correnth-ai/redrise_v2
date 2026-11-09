// Integrated window chrome (M04/M08): the native white title bar is off
// (tauri.conf decorations=false). The top strip is the drag region; on the top right
// three small colored circles, left to right green = maximize/restore, yellow =
// minimize, red = close (TEAM-ACCOUNTS-20261108 item 11: look only, the native calls
// are the same). Names and tooltips do not depend on color; hover or focus shows a
// discreet symbol. The moon turns the dark theme on, the sun turns the light theme on.
import { useEffect, useState } from "react";
import { Maximize2, Minimize2, Minus, Moon, Sun, X } from "lucide-react";
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
  return (
    <div className="flex items-center gap-0.5" role="group" aria-label="Controles da janela">
      <Light color="bg-[#28C840]" label={max ? "Restaurar" : "Maximizar"} onClick={() => win()?.toggleMaximize()}>
        {max ? <Minimize2 /> : <Maximize2 />}
      </Light>
      <Light color="bg-[#FEBC2E]" label="Minimizar" onClick={() => win()?.minimize()}><Minus /></Light>
      <Light color="bg-[#FF5F57]" label="Fechar" onClick={() => win()?.close()}><X /></Light>
    </div>
  );
}

/** One control: a 14 px circle in a fixed color inside a 24 px clickable area; the symbol appears on hover or focus. */
function Light({ color, label, onClick, children }: { color: string; label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick}
      className="group/light inline-flex size-6 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <span aria-hidden className={cn("inline-flex size-3.5 items-center justify-center rounded-full shadow-[inset_0_0_0_0.5px_rgb(0_0_0/0.25)]", color,
        "text-black/60 [&>svg]:size-2.5 [&>svg]:stroke-[3] [&>svg]:opacity-0 group-hover/light:[&>svg]:opacity-100 group-focus-visible/light:[&>svg]:opacity-100")}>
        {children}
      </span>
    </button>
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
