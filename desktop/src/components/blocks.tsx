// blocks.so (MIT) blocks adapted to RedRise: stats-02 (summary), stats-13
// (storage), grid-list-02 (process grid), onboarding-05 (activity),
// onboarding-06 (timeline), onboarding-07 (execution log). They only read
// the shared execution state; none of them triggers or verifies anything.
import { useState } from "react";
import { CheckCircle2, Loader2, CircleAlert, CircleDashed, ChevronRight, Hourglass } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { DiagnosticBox, ErrorView } from "@/components/diagnostic";
import { JOB_STATE, TONE_CLASS, executionLabel, executionTone, finishedState, title, tone } from "@/data/status";
import type { Execution, ExecutionStep } from "@/data/types";
import { tv } from "@/lib/locale";
import { bytes, cn, when } from "@/lib/utils";

export function StateBadge({ state, label }: { state: string | null; label?: string }) {
  return <Badge variant="outline" className={cn("font-medium", TONE_CLASS[tone(state)])}>{label ?? JOB_STATE[state ?? ""] ?? "Não executada"}</Badge>;
}

export function ExecutionBadge({ e }: { e: Execution }) {
  return <Badge variant="outline" className={cn("font-medium", TONE_CLASS[executionTone(e)])}>{executionLabel(e)}</Badge>;
}

// ---------------------------------------------------------------- reports of an execution
/** Each report this execution saved, with Veja aqui!: the folder in the Explorer, on the computer that has it. */
export function ExecutionReports({ e, open }: { e: Execution; open: (name: string) => Promise<void> }) {
  const [error, setError] = useState<unknown>(null);
  const steps = (e.context as any)?.steps ?? {};
  const files: string[] = Object.values<any>(steps).map((s) => s?.report?.file).filter((f) => typeof f === "string");
  const messages: any[] = Object.values<any>(steps).map((s) => s?.message).filter((m) => m?.status === "prepared");
  if (!files.length && !messages.length) return null;
  return (
    <div className="space-y-1">
      {messages.map((m, i) => (
        <p key={i}><b>Mensagem preparada</b> para <span className="break-all">{m.to}</span>{m.channel ? ` em ${tv(m.channel)}` : ""}. Nada foi enviado: revise e envie.</p>
      ))}
      {files.map((f) => (
        <p key={f}>Relatório salvo: <span className="break-all font-medium">{f}</span>{" "}
          <button type="button" className="font-medium underline" onClick={() => { setError(null); open(f).catch(setError); }}>Veja aqui!</button></p>
      ))}
      <ErrorView error={error} />
    </div>
  );
}

// ---------------------------------------------------------------- stats-02
export interface Stat { metric: string; value: string | number | null; hint?: string; onOpen?: () => void; action?: string }
export function Stats02({ stats }: { stats: Stat[] }) {
  return (
    <div className={cn("grid grid-cols-1 divide-y divide-border overflow-hidden rounded-lg border bg-border md:divide-x md:divide-y-0",
      stats.length === 4 ? "md:grid-cols-4" : "md:grid-cols-3")}>
      {stats.map((s) => (
        <Card key={s.metric} className="gap-0 rounded-none border-0 py-0 shadow-none">
          <CardContent className="flex h-full flex-col p-4">
            <CardTitle className="text-sm font-normal text-muted-foreground">{s.metric}</CardTitle>
            <button type="button" disabled={!s.onOpen} onClick={s.onOpen}
              className="mt-1 w-fit text-left text-2xl font-semibold tabular-nums text-primary outline-none enabled:hover:underline focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
              aria-label={s.onOpen ? `${s.metric}: ${s.value ?? "—"}. ${s.action ?? "Abrir"}` : undefined}>
              {s.value ?? "—"}
            </button>
            {s.hint && <p className="mt-1 text-xs text-muted-foreground">{s.hint}</p>}
            {s.onOpen && (
              <button type="button" onClick={s.onOpen} className="mt-auto inline-flex w-fit items-center gap-1 pt-2 text-xs font-medium text-foreground hover:underline">
                {s.action ?? "Abrir"} <ChevronRight className="size-3" />
              </button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- stats-13
/** Bytes only (database, local data, logs); record counts are shown apart. No quota is invented:
 * `capacity` is passed only by the demonstration build. */
export function Stats13({ segments, capacity, counts }: {
  segments: { label: string; value: number | null; color: string }[]; capacity?: number | null;
  counts: { label: string; value: number }[];
}) {
  const known = segments.filter((s) => s.value !== null) as { label: string; value: number; color: string }[];
  const used = known.reduce((n, s) => n + s.value, 0);
  const total = capacity ?? used;
  return (
    <Card className="py-4 shadow-none">
      <CardContent className="px-4">
        <p className="mb-3 text-sm text-muted-foreground">
          Espaço usado pelo RedRise{" "}
          <span className="font-semibold tabular-nums text-foreground">{bytes(used)}</span>
          {capacity ? <> de {bytes(capacity)} <Badge variant="outline" className="ml-1">capacidade fictícia</Badge></> : <> · sem limite definido</>}
        </p>
        <div className="mb-3 flex h-2.5 w-full overflow-hidden rounded-full bg-muted">
          {total > 0 && known.map((s) => (
            <div key={s.label} role="progressbar" aria-label={s.label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={s.value}
              className={cn("h-full", s.color)} style={{ width: `${(s.value / total) * 100}%` }} />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
          {segments.map((s) => (
            <span key={s.label} className="flex items-center gap-2">
              <span aria-hidden className={cn("size-3 shrink-0 rounded", s.color)} />{s.label}
              <span className="tabular-nums">{s.value === null ? "indisponível" : bytes(s.value)}</span>
            </span>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
          {counts.map((c) => <span key={c.label}>{c.label}: <b className="tabular-nums text-foreground">{c.value}</b></span>)}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------- grid-list-02
export function ProcessGrid({ items }: { items: { id: number; name: string; detail: string; state: React.ReactNode; onOpen: () => void }[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">Nenhum processo cadastrado.</p>;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((p) => (
        <Card key={p.id} className="relative py-0 shadow-2xs transition-[border-color,box-shadow] focus-within:ring-2 focus-within:ring-ring hover:border-muted-foreground hover:shadow-sm">
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold">{p.name.charAt(0).toUpperCase()}</div>
            <div className="min-w-0 flex-1">
              <button type="button" onClick={p.onOpen} className="block w-full min-w-0 text-left outline-none">
                <span aria-hidden className="absolute inset-0" />
                <p className="truncate text-sm font-medium">{p.name}</p>
                <p className="truncate text-sm text-muted-foreground">{p.detail}</p>
              </button>
            </div>
            <div className="relative">{p.state}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- onboarding-05
export interface Activity { id: string; text: string; who: string; at: string; state: string | null; onOpen?: () => void }
export function ActivityFeed({ items }: { items: Activity[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">Sem atividade registrada.</p>;
  return (
    <ul className="space-y-5 pb-2">
      {items.map((a, i) => (
        <li key={a.id} className="relative flex gap-x-3">
          <div className={cn("absolute left-0 top-0 flex w-6 justify-center", i === items.length - 1 ? "h-6" : "-bottom-5")}>
            <span aria-hidden className="w-px bg-border" />
          </div>
          <div className="relative flex size-6 flex-none items-center justify-center bg-card">
            <div className={cn("size-3 rounded-full border ring-4 ring-card", a.state === "verified" ? "border-ok bg-ok" :
              tone(a.state) === "bad" ? "border-destructive bg-destructive" : tone(a.state) === "warn" ? "border-warn bg-warn" : "border-border bg-muted")} />
          </div>
          <p className="mt-0.5 text-sm">
            <span className="font-medium">{a.who}</span>{" "}
            {a.onOpen ? <button type="button" className="text-muted-foreground hover:underline" onClick={a.onOpen}>{a.text}</button>
              : <span className="text-muted-foreground">{a.text}</span>}
            <span className="text-muted-foreground/70"> ∙ {when(a.at)}</span>
          </p>
        </li>
      ))}
    </ul>
  );
}

/** Feed derived from the same executions shown elsewhere (one entry per persisted step change). */
export function activityOf(executions: Execution[], open: (e: Execution) => void, limit = 8): Activity[] {
  const out: Activity[] = [];
  for (const e of executions) {
    for (const s of e.steps) {
      if (!s.job_id && !s.review) continue;
      const at = s.finished_at ?? s.started_at ?? e.created_at;
      out.push({ id: `${e.id}-${s.position}`, who: s.name, state: s.state,
        text: `${JOB_STATE[s.state ?? ""] ?? "registrada"} em “${title(e)}”`, at, onOpen: () => open(e) });
    }
  }
  return out.sort((a, b) => b.at.localeCompare(a.at)).slice(0, limit);
}

// ---------------------------------------------------------------- onboarding-06
function StepIcon({ s }: { s: ExecutionStep }) {
  if (s.state === "verified") return <CheckCircle2 aria-hidden className="size-5 text-ok" />;
  if (s.state === "running" || s.state === "claimed") return <Loader2 aria-hidden className="size-4 animate-spin text-info" />;
  if (s.state === "awaiting_review") return <Hourglass aria-hidden className="size-4 text-info" />;
  if (finishedState(s.state)) return <CircleAlert aria-hidden className={cn("size-5", tone(s.state) === "warn" ? "text-warn" : "text-destructive")} />;
  return <CircleDashed aria-hidden className="size-4 text-muted-foreground" />;
}

export function Timeline({ e }: { e: Execution }) {
  return (
    <ul className="space-y-5">
      {e.steps.map((s, i) => (
        <li key={s.position} className="relative flex gap-x-3">
          <div className={cn("absolute left-0 top-0 flex w-6 justify-center", i === e.steps.length - 1 ? "h-6" : "-bottom-5")}>
            <span aria-hidden className="w-px bg-border" />
          </div>
          <div className="relative flex size-6 flex-none items-center justify-center bg-card"><StepIcon s={s} /></div>
          <div>
            <p className="mt-0.5 text-sm font-medium">{s.position}. {s.name}{" "}
              <span className="font-normal text-muted-foreground/70">∙ {s.finished_at ? when(s.finished_at) : s.started_at ? "em andamento" : e.state === "finished" ? "não executada" : "a seguir"}</span>
            </p>
            <p className="text-sm text-muted-foreground">
              {s.state ? JOB_STATE[s.state] : e.state === "finished" ? "Não executada" : "Aguardando a anterior"}
              {s.error_code ? ` · ${s.error_code}` : ""}{i === e.steps.length - 1 ? " · fim da sequência"
                : e.state === "finished" && s.state !== null && e.steps[i + 1]?.state === null ? " · execução encerrada aqui"
                : s.continue_next ? " · continua para a próxima" : " · encerra aqui"}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------- onboarding-07
function duration(a: string | null, b: string | null): string {
  if (!a || !b) return "—";
  const s = Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}min ${s % 60}s`;
}

export function ExecutionLog({ e }: { e: Execution }) {
  const pct = (s: ExecutionStep) => (s.state === "verified" ? 100 : finishedState(s.state) ? 100 : s.state === "running" || s.state === "claimed" ? 50 : 0);
  return (
    <div>
      <div className="flex items-center gap-2">
        {e.steps.map((s) => (
          <div key={s.position} className="w-full min-w-0">
            <Progress value={pct(s)} className={cn("h-1.5", finishedState(s.state) && s.state !== "verified" && "[&>div]:bg-warn")} />
            <div className="mt-2 flex items-center gap-1 truncate"><StepIcon s={s} />
              <p className="truncate text-xs text-muted-foreground">{s.name}</p></div>
          </div>
        ))}
      </div>
      <Accordion type="single" collapsible defaultValue="logs" className="mt-4">
        <AccordionItem value="logs" className="border-b-0">
          <AccordionTrigger className="text-sm font-medium">Registro da execução ({e.steps.length})</AccordionTrigger>
          <AccordionContent>
            <ul className="space-y-4 pb-2">
              {e.steps.map((s) => (
                <li key={s.position} className="text-sm">
                  <p className="font-medium">{s.position}. {s.name} <StateBadge state={s.state} /></p>
                  <p className="text-muted-foreground">
                    {s.review ? (s.review.status === "approved" ? `Aprovado por ${s.review.decided_by_name} em ${when(s.review.decided_at)}` : `Com ${s.review.assignee_name} desde ${when(s.review.requested_at)}`)
                      : s.started_at ? `Início ${when(s.started_at)} · duração ${duration(s.started_at, s.finished_at)}` : "Não iniciada"}
                    {s.error_code ? ` · código ${s.error_code}` : ""}
                  </p>
                  {s.diagnostic && <DiagnosticBox d={s.diagnostic} />}
                </li>
              ))}
            </ul>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
