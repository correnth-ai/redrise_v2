// pt-BR labels and the single state model shared by tables, grid, Kanban,
// log, timeline and activity feed (M10): every view derives from the same
// execution/step records, never from its own copy.
import type { Execution, ExecutionStep, JobState } from "./types";

export const JOB_STATE: Record<string, string> = {
  queued: "Aguardando", claimed: "Preparando", running: "Em andamento", completed_unverified: "Concluída, não verificada",
  verified: "Verificada", failed: "Falhou", uncertain: "Incerta — conferir", refused: "Recusada", cancelled: "Cancelada",
  error: "Erro", awaiting_review: "Aguardando revisão",
};

export const END_REASON: Record<string, string> = {
  sequence_end: "Fim da sequência",
  continuation_off: "Encerrada pela configuração do vínculo",
  not_verified: "Interrompida: resultado não verificado",
  cancelled: "Cancelada",
};

export type Tone = "ok" | "warn" | "bad" | "info" | "muted";
export function tone(state: string | null | undefined): Tone {
  switch (state) {
    case "verified": return "ok";
    case "completed_unverified": case "uncertain": return "warn";
    case "failed": case "error": case "refused": return "bad";
    case "running": case "claimed": case "queued": case "awaiting_review": return "info";
    default: return "muted";
  }
}

export const TONE_CLASS: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  bad: "bg-bad-soft text-destructive border-transparent",
  info: "bg-info-soft text-info border-transparent",
  muted: "bg-muted text-muted-foreground border-transparent",
};

/** Kanban column of a step. "Atenção" keeps failed/uncertain/unverified distinct via their badge. */
export type Column = "waiting" | "running" | "verified" | "attention" | "not_run";
export const COLUMN_LABEL: Record<Column, string> = {
  waiting: "Aguardando", running: "Em andamento", verified: "Verificada", attention: "Atenção", not_run: "Não executada",
};
export function column(e: Execution, s: ExecutionStep): Column {
  if (s.state === null) return e.state === "finished" ? "not_run" : "waiting";
  if (s.state === "queued" || s.state === "awaiting_review") return "waiting";
  if (s.state === "claimed" || s.state === "running") return "running";
  if (s.state === "verified") return "verified";
  return "attention";
}

export function executionLabel(e: Execution): string {
  if (e.state === "running") return "Em andamento";
  if (e.state === "waiting_review") return "Aguardando revisão";
  return JOB_STATE[e.outcome ?? ""] ?? "Encerrada";
}
export function executionTone(e: Execution): Tone {
  return e.state === "finished" ? tone(e.outcome) : "info";
}

export function needsAttention(e: Execution): boolean {
  return e.state === "finished" && e.outcome !== "verified";
}

export function title(e: Execution): string {
  return e.process_name ?? `${e.steps[0]?.name ?? "Rotina"} (avulsa)`;
}

export function finishedState(s: JobState | null): boolean {
  return s !== null && !["queued", "claimed", "running", "awaiting_review"].includes(s);
}
