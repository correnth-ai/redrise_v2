import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function when(iso?: string | null): string {
  return iso ? new Date(iso).toLocaleString("pt-BR") : "—";
}

/** Local date and time as dd/MM/aaaa HH:mm (e.g. "Último sucesso"); "—" without a value. */
export function shortWhen(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(d.getDate())}/${two(d.getMonth() + 1)}/${d.getFullYear()} ${two(d.getHours())}:${two(d.getMinutes())}`;
}

/** The full instant with its time zone, for a tooltip. */
export function fullWhen(iso: string): string {
  const d = new Date(iso);
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return `${d.toLocaleString("pt-BR")} (${zone})`;
}

export function bytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toLocaleString("pt-BR", { maximumFractionDigits: i ? 1 : 0 })} ${u[i]}`;
}
