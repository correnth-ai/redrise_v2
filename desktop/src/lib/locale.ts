// UI locale mask: the backend speaks English ASCII (codes, messages, params);
// the person reads pt-BR. Texts come from locale/pt-BR.json by error_code and
// params; a value without translation is shown as the backend sent it.
// The mask is bundled at build time: the window CSP (connect-src ipc only)
// blocks fetching it at run time, which left the installed beta.13 in English.
import type { Diagnostic } from "./api";
import ptBR from "../../locale/pt-BR.json";

interface Locale {
  labels: Record<string, string>;
  errors: Record<string, Record<string, string>>;
  values: Record<string, string>;
  patterns: { en: string; pt: string }[];
  report: Record<string, string>;
  notify: Record<string, string>;
}

const L: Locale = { labels: {}, errors: {}, values: {}, patterns: [], report: {}, notify: {}, ...(ptBR as Partial<Locale>) };

/** The fixed words of the report PDF; stored with the routine, since the Runner speaks English. */
export const reportLabels = (): Record<string, string> => L.report;
export const notifyLabels = (): Record<string, string> => L.notify;

/** Kept for the entry point; the mask is already loaded. */
export async function loadLocale(): Promise<void> {}

export const label = (key: string, fallback: string): string => L.labels[key] ?? fallback;

const escape = (s: string) => s.replace(/[.*+?^$()|[\]\\]/g, "\\$&");

/** Backend value -> pt-BR (exact entry, then patterns with {slots}). */
export function tv(v: string | null | undefined): string {
  if (v === null || v === undefined) return "";
  if (v in L.values) return L.values[v];
  for (const p of L.patterns) {
    const names: string[] = [];
    const re = new RegExp("^" + escape(p.en).replace(/\\?\{(\w+)\\?\}/g, (_, n) => { names.push(n); return "(.+?)"; }) + "$");
    const m = re.exec(v);
    if (m) return p.pt.replace(/\{(\w+)\}/g, (s, n) => (names.includes(n) ? tv(m[names.indexOf(n) + 1]) : s));
  }
  return v;
}

const BACKEND: Record<string, keyof Diagnostic> = {
  what: "what_happened", completed: "completed", pending: "pending", next: "next_action", details: "details_summary",
};

/** One user topic of a diagnostic in pt-BR. Older diagnostics without params
 * (or a template needing a missing param) keep the stored text. */
export function userText(d: Diagnostic, topic: "what" | "completed" | "pending" | "next" | "details"): string {
  const stored = String(d[BACKEND[topic]] ?? "");
  const t = L.errors[d.error_code]?.[topic];
  if (!t) return tv(stored);
  const params = d.params ?? {};
  const needed = [...t.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
  if (needed.some((n) => !(n in params))) return needed.length ? tv(stored) : t;
  return t.replace(/\{(\w+)\}/g, (_, n) => tv(params[n]));
}
