// Thin typed wrappers over the Tauri commands and the diagnostic contract.
import { label, userText } from "./locale";
declare global {
  interface TauriWindow { minimize(): Promise<void>; toggleMaximize(): Promise<void>; close(): Promise<void>;
    isMaximized(): Promise<boolean>; onResized(cb: () => void): Promise<() => void> }
  interface Window { __TAURI__?: { core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
    window: { getCurrentWindow(): TauriWindow } } }
}

export interface Diagnostic {
  schema: string; error_code: string; category: string; what_happened: string; completed: string; pending: string;
  effect_state: string; next_action: string; retry: string; details_summary: string; reported_by: string;
  module_hints: string[]; diagnosis_status: string; correlation_id: string; boundary: unknown;
  version: Record<string, string>; technical_details: Record<string, unknown>; cause: Diagnostic | null;
  params?: Record<string, string>;
}

export class AppError extends Error {
  constructor(public diagnostic: Diagnostic) { super(diagnostic.error_code); }
}

function uiDiagnostic(reason: string): Diagnostic {
  // The UI itself could not interpret an answer: contract boundary UI <- desktop core.
  return {
    schema: "redrise.diagnostic/1", error_code: "CONTRACT-PAYLOAD", category: "contract",
    what_happened: "An internal RedRise answer came in an incompatible format.",
    completed: "The answer was received and rejected by validation.", pending: "The next step was not run.",
    effect_state: "unknown", next_action: "Refresh the screen and check the state before repeating. If it persists, copy the diagnostic.",
    retry: "check_first", details_summary: reason, reported_by: "RR-UI", module_hints: ["RR-UI", "RR-CONTRACT"],
    params: { contract: "desktop IPC", reason },
    diagnosis_status: "unconfirmed", correlation_id: Math.random().toString(16).slice(2, 18), boundary: null,
    version: {}, technical_details: {}, cause: null,
  };
}

export async function call<T = any>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  try {
    if (!window.__TAURI__) throw new AppError(uiDiagnostic("desktop IPC unavailable (not running inside the RedRise app)"));
    return await window.__TAURI__.core.invoke<T>(cmd, args);
  } catch (e: any) {
    if (e && typeof e === "object" && e.diagnostic && typeof e.diagnostic.error_code === "string") throw new AppError(e.diagnostic);
    if (e && typeof e === "object" && e.compile) throw new AppError({ ...uiDiagnostic(JSON.stringify(e.compile).slice(0, 300)),
      error_code: "ENGINE-IR-COMPILE", what_happened: "The recording could not be turned into a routine.",
      module_hints: ["RR-ENGINE-IR"], category: "unknown", effect_state: "none", retry: "after_fix",
      next_action: "Check the given parameters (the text must have been typed during the recording) and try again.",
      params: { reason: JSON.stringify(e.compile).slice(0, 300) } });
    throw new AppError(uiDiagnostic(String(e).slice(0, 300)));
  }
}

let token: string | null = sessionStorage.getItem("rr.token");
export const session = {
  get token() { return token; },
  set(t: string | null) { token = t; t ? sessionStorage.setItem("rr.token", t) : sessionStorage.removeItem("rr.token"); },
};

export function api<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  return call<T>("api", { method, path, body: body ?? null, token: session.token });
}

export const FOOTER = (d: Diagnostic) => label("footer", "Code: {code} | Modules: {modules}")
  .replace("{code}", d.error_code).replace("{modules}", (d.module_hints.length ? d.module_hints : ["RR-DIAG"]).join(", "));

export const effectText = (d: Diagnostic): string =>
  d.effect_state === "unknown" ? " " + label("effect_unknown", "An effect with unknown result exists.")
  : d.effect_state === "partial" ? " " + label("effect_partial", "Part of the operation was already done.") : "";

/** User (pt-BR) text of a diagnostic for copying; the footer is always the last line. */
export function diagnosticText(d: Diagnostic, technical = true): string {
  const lines = [
    `${label("what", "What happened")}: ${userText(d, "what")}`,
    `${label("result", "Result")}: ${userText(d, "completed")} ${userText(d, "pending")}${effectText(d)}`,
    `${label("next", "Next action")}: ${userText(d, "next")}`,
    `${label("details", "Diagnostic details")}: ${userText(d, "details")} ${label("reference", "Reference")}: ${d.correlation_id}.`,
  ];
  if (technical) {
    const chain: string[] = [];
    for (let c = d.cause; c; c = c.cause) chain.push(c.error_code);
    lines.push(JSON.stringify({ reported_by: d.reported_by, category: d.category, effect_state: d.effect_state,
      diagnosis_status: d.diagnosis_status, boundary: d.boundary, version: d.version, technical_details: d.technical_details,
      cause: chain }, null, 2));
  }
  lines.push(FOOTER(d)); // always the last line
  return lines.join("\n");
}
