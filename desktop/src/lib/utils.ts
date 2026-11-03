import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function when(iso?: string | null): string {
  return iso ? new Date(iso).toLocaleString("pt-BR") : "—";
}

export function bytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toLocaleString("pt-BR", { maximumFractionDigits: i ? 1 : 0 })} ${u[i]}`;
}
