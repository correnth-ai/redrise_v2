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

/** Kanban column of an execution (PROCESS-ACTIONS-20261111 item 4.3), from its aggregate state and canonical result only:
 *  never a retry, never a promotion. A step not started yet never moves a running execution. */
export type Column = "waiting" | "running" | "done" | "verified";
/** Left to right on the board. */
export const COLUMNS: Column[] = ["waiting", "running", "done", "verified"];
/** Board and summary labels; the canonical results stay `completed_unverified` and `verified` ("Verificada" elsewhere). */
export const COLUMN_LABEL: Record<Column, string> = { waiting: "No aguardo", running: "Em andamento", done: "Concluído", verified: "Conferido" };
/** The step that is now the execution's: the last one that has a state (a later one has not started). */
export const currentStep = (e: Execution): ExecutionStep | null => [...e.steps].reverse().find((s) => s.state !== null) ?? null;
const MOVING: (string | null)[] = ["claimed", "running", "verified"]; // preparing, running, or verified and passing to the next one
export function boardColumn(e: Execution): Column {
  if (e.state === "finished") return e.outcome === "verified" ? "verified" : e.outcome === "completed_unverified" ? "done" : "waiting";
  if (e.state === "waiting_review") return "waiting";
  const s = currentStep(e);
  return s && MOVING.includes(s.state) ? "running" : "waiting"; // queued at the station, or a failure the Core is about to close
}
/** What the summary says the execution is now, with the board's words for the two good endings and the real ones otherwise. */
export function boardStateLabel(e: Execution): string {
  if (e.state === "finished") return e.outcome === "verified" ? "Conferido" : e.outcome === "completed_unverified" ? "Concluído, sem conferência"
    : JOB_STATE[e.outcome ?? ""] ?? "Encerrada";
  if (e.state === "waiting_review") return "Aguardando revisão";
  const s = currentStep(e);
  if (!s || s.state === "queued") return "Na fila da estação";
  return MOVING.includes(s.state) ? (s.state === "claimed" ? "Preparando" : "Em andamento") : JOB_STATE[s.state ?? ""] ?? "Em andamento";
}

export function executionLabel(e: Execution): string {
  if (e.state === "running") return "Em andamento";
  if (e.state === "waiting_review") return "Aguardando revisão";
  return JOB_STATE[e.outcome ?? ""] ?? "Encerrada";
}
export function executionTone(e: Execution): Tone {
  return e.state === "finished" ? tone(e.outcome) : "info";
}

/** Situation groups, the same predicates as the Core summary (service.py _GROUPS). */
export type Group = "running" | "waiting" | "attention" | "verified";
export function groupOf(e: Execution): Group {
  if (e.state === "running") return "running";
  if (e.state === "waiting_review") return "waiting";
  return e.outcome === "verified" ? "verified" : "attention";
}
export const GROUP_LABEL: Record<Group, string> = {
  running: "Em andamento", waiting: "Aguardando revisão", attention: "Precisam de atenção", verified: "Verificadas",
};

export function needsAttention(e: Execution): boolean {
  return groupOf(e) === "attention";
}

/** The process's own name (by id, from the Core); a deleted one says so, so homonyms never look the same. */
export function title(e: Execution): string {
  return e.process_name !== null ? `${e.process_name}${e.process_archived ? " (excluído)" : ""}` : `${e.steps[0]?.name ?? "Rotina"} (avulsa)`;
}

export function finishedState(s: JobState | null): boolean {
  return s !== null && !["queued", "claimed", "running", "awaiting_review"].includes(s);
}
