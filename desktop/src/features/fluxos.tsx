// Fluxos: follow executions and history. Every view (stats, grid, Kanban,
// timeline, log, feed, table) derives from the same execution records; the
// Kanban is read-only (no drag-and-drop, no manual verification).
import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, CircleAlert, Hourglass, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataTable, type DataColumn } from "@/components/data-table";
import { ErrorView } from "@/components/diagnostic";
import { ActivityFeed, activityOf, ExecutionBadge, ExecutionLog, ExecutionReports, StateBadge, Timeline } from "@/components/blocks";
import { JobsSection } from "@/features/legacy";
import { boardColumn, boardStateLabel, COLUMN_LABEL, COLUMNS, currentStep, END_REASON, executionLabel, groupOf, title } from "@/data/status";
import type { Execution, KanbanDay, Process } from "@/data/types";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { userText } from "@/lib/locale";
import { useStore } from "@/state";
import { when } from "@/lib/utils";

export function ActivityPage() {
  const { executions, go, error } = useStore();
  const open = (e: Execution) => go({ menu: "processo", page: "historico", id: e.id });
  const latest = executions?.[0];
  return (
    <div className="space-y-6">
      <ErrorView error={error} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="shadow-none">
          <CardHeader><CardTitle>Linha do tempo</CardTitle><CardDescription>{latest ? `${title(latest)} · ${when(latest.created_at)}` : "Sem execuções"}</CardDescription></CardHeader>
          <CardContent>{latest ? <Timeline e={latest} /> : <p className="text-sm text-muted-foreground">Nenhuma execução ainda.</p>}</CardContent>
        </Card>
        <Card className="shadow-none">
          <CardHeader><CardTitle>Atividade recente</CardTitle></CardHeader>
          <CardContent><ActivityFeed items={activityOf(executions ?? [], open)} /></CardContent>
        </Card>
      </div>
      <JobsSection />
    </div>
  );
}

/** Processes to filter by, BY ID: the registered ones and those of the given executions (a deleted one says so); equal
 *  names get their number, so homonyms are never merged (PROCESS-ACTIONS-20261111 item 2). */
export function processChoices(processes: Process[] | null, rows: Execution[] | null): { id: number; label: string }[] {
  const m = new Map<number, string>();
  for (const p of processes ?? []) m.set(p.id, p.name);
  for (const e of rows ?? []) if (e.process_id !== null && !m.has(e.process_id)) m.set(e.process_id, title(e));
  const names = [...m.values()];
  return [...m.entries()].map(([id, name]) => ({ id, label: names.filter((n) => n === name).length > 1 ? `${name} · nº ${id}` : name }));
}

/** dd/mm/aaaa of a calendar day "YYYY-MM-DD" (no time zone involved: it is the team's day as the Core gave it). */
export const dayLabel = (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}`;

/** Kanban of one day (PROCESS-ACTIONS-20261111 item 4.3): one card per process, its latest execution STARTED that day in the
 *  team zone, read from the Core for that day (never the general list). Hoje follows the team's day; a chosen day stays.
 *  Read again with every store read (change feed or periodic) and every minute; an answer for another day never shows. */
export function KanbanPage({ process }: { process?: number }) {
  const { executions, processes, go, src, error } = useStore();
  const [proc, setProc] = useState(process ? String(process) : "all");
  const [pick, setPick] = useState<string | null>(null); // null: Hoje (never kept from an earlier visit)
  const [board, setBoard] = useState<KanbanDay | null>(null);
  const [boardError, setBoardError] = useState<unknown>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [minute, setMinute] = useState(0);
  const reads = useRef(0);
  useEffect(() => {
    if (pick !== null) return;
    const t = window.setInterval(() => setMinute((m) => m + 1), 60_000); // the day may turn while nothing changes
    return () => window.clearInterval(t);
  }, [pick]);
  useEffect(() => {
    const mine = ++reads.current;
    src.kanban(pick).then((r) => {
      if (mine !== reads.current || (pick !== null && r.day !== pick)) return; // an older or other-day answer is dropped
      setBoard(r); setBoardError(null);
    }, (e) => { if (mine === reads.current) setBoardError(e); });
  }, [src, executions, pick, minute]);
  const choose = (d: string | null) => {
    if (d === pick) return;
    reads.current++; // any answer still on its way belongs to the previous day
    setBoard(null); setBoardError(null); setOpen(null); setPick(d);
  };
  const shown = useMemo(() => (board?.executions ?? []).filter((e) => proc === "all" || String(e.process_id) === proc), [board, proc]);
  const options = useMemo(() => processChoices(processes, board?.executions ?? null), [processes, board]);
  const day = pick ?? board?.day ?? null;
  const stale = !!(error || boardError);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1"><Label htmlFor="k-day" className="text-xs">Dia</Label>
          <div className="flex items-center gap-2">
            <Input id="k-day" type="date" required value={day ?? ""} className="h-8 w-40" aria-describedby="k-day-help"
              onChange={(ev) => { if (ev.target.value) choose(ev.target.value); }} />
            <Button size="sm" variant={pick === null ? "secondary" : "outline"} aria-pressed={pick === null} onClick={() => choose(null)}>Hoje</Button>
          </div></div>
        <div className="space-y-1"><Label htmlFor="k-proc" className="text-xs">Processo</Label>
          <Select value={proc} onValueChange={setProc}>
            <SelectTrigger id="k-proc" size="sm" className="w-64"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todos os processos</SelectItem>{options.map((o) => <SelectItem key={o.id} value={String(o.id)}>{o.label}</SelectItem>)}</SelectContent>
          </Select></div>
        <p id="k-day-help" className="pb-1 text-xs text-muted-foreground">
          {day ? `Execuções iniciadas em ${dayLabel(day)}${board && day === board.today ? " (hoje)" : ""}` : "Execuções iniciadas hoje"}
          {board ? `, no fuso da equipe (${board.timezone})` : ""}. A mais recente de cada processo; atualiza sozinho. Somente leitura.</p>
      </div>
      {stale && <div role="status" className="space-y-2 rounded-md border border-warn/40 bg-warn-soft px-3 py-2 text-sm text-warn">
        <p>Os dados podem estar desatualizados: não foi possível ler o servidor agora. O quadro mostra a última leitura e tenta de novo sozinho.</p>
        <ErrorView error={boardError ?? error} />
      </div>}
      {board && !shown.length && <p role="status" className="text-sm text-muted-foreground">Nenhuma execução iniciada em {dayLabel(board.day)}{proc !== "all" ? " para este processo" : ""}.</p>}
      {!board && !boardError && <p className="text-sm text-muted-foreground">Carregando o quadro…</p>}
      {/* Four columns share the width; under ~12rem each, the board scrolls sideways instead of cutting cards. */}
      <div role="region" aria-label="Quadro de processos" tabIndex={0} className="overflow-x-auto rounded-md pb-2 outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <div className="grid grid-cols-[repeat(4,minmax(12rem,1fr))] gap-3">
          {COLUMNS.map((c) => {
            const cards = shown.filter((e) => boardColumn(e) === c);
            return (
              <section key={c} aria-label={COLUMN_LABEL[c]} className="min-w-0 rounded-lg border bg-muted/40 p-2">
                <h3 className="mb-2 flex items-center justify-between gap-2 px-1 text-sm font-medium">{COLUMN_LABEL[c]}<span className="text-xs tabular-nums text-muted-foreground">{cards.length}</span></h3>
                <ul className="space-y-2">
                  {cards.map((e) => (
                    <li key={e.id}>
                      <button type="button" data-card={e.id} onClick={() => setOpen(e.id)}
                        className="w-full rounded-md border bg-card p-2 text-left text-sm shadow-2xs outline-none hover:border-muted-foreground focus-visible:ring-2 focus-visible:ring-ring">
                        <p className="break-words font-medium">{title(e)}</p>
                        <p className="break-words text-xs text-muted-foreground">{e.station_name}</p>
                        <p className="break-words text-xs text-muted-foreground">{e.requested_by}</p>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      </div>
      <ExecutionSummary target={open} board={shown} onClose={() => setOpen(null)}
        onMore={(id) => { setOpen(null); go({ menu: "processo", page: "historico", id }); }} />
    </div>
  );
}

/** Summary of one card over the board: the same execution while open (by its id), followed with the current data. A newer
 *  execution of the process replacing the card never swaps it: off the board it is read by its id. Reading only. */
function ExecutionSummary({ target, board, onClose, onMore }: { target: string | null; board: Execution[];
  onClose: () => void; onMore: (id: string) => void }) {
  const { src, executions } = useStore();
  const [fetched, setFetched] = useState<Execution | null>(null);
  const [gone, setGone] = useState<unknown>(null);
  const last = useRef(target); // the card to focus again once closed (the target is cleared before that)
  if (target) last.current = target;
  const onBoard = target ? board.find((e) => e.id === target) ?? null : null;
  useEffect(() => {
    setFetched(null); setGone(null);
  }, [target]);
  useEffect(() => {
    if (!target || onBoard) return;
    let on = true; // off the board: read it by its id with each store read
    src.execution(target).then((e) => { if (on) { setFetched(e); setGone(null); } }, (err) => { if (on) setGone(err); });
    return () => { on = false; };
  }, [target, onBoard, src, executions]);
  const e = onBoard ?? (fetched?.id === target ? fetched : null);
  const s = e ? currentStep(e) : null;
  const notRun = e && e.state === "finished" ? e.steps.filter((x) => x.state === null) : [];
  const reason = !e ? null : e.state === "waiting_review" || s?.state === "awaiting_review"
    ? (s?.review ? `Aguardando revisão de ${s.review.assignee_name}` : "Aguardando revisão")
    : s?.diagnostic ? userText(s.diagnostic, "what") : s?.error_code ? s.error_code
    : e.state === "finished" && e.end_reason && e.outcome !== "verified" ? END_REASON[e.end_reason] ?? e.end_reason : null;
  return (
    <Dialog open={target !== null} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent onCloseAutoFocus={(ev) => {
        const card = last.current && document.querySelector<HTMLElement>(`[data-card="${last.current}"]`);
        if (card) { ev.preventDefault(); card.focus(); } // back to the card, while it is still on the board
      }}>
        <DialogHeader>
          <DialogTitle>{e ? title(e) : "Execução"}</DialogTitle>
          <DialogDescription>{e ? `Execução mais recente do processo no dia, iniciada em ${when(e.created_at)}` : "Resumo da execução"}</DialogDescription>
        </DialogHeader>
        {!e ? (gone ? <div className="space-y-2 text-sm"><p>Esta execução não está mais disponível.</p><ErrorView error={gone} /></div>
          : <p className="text-sm text-muted-foreground">Carregando…</p>) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-muted-foreground">Situação</dt><dd>{boardStateLabel(e)} <span className="text-xs text-muted-foreground">({COLUMN_LABEL[boardColumn(e)]})</span></dd>
            {s && <><dt className="text-muted-foreground">Etapa</dt><dd>{s.position} de {e.steps.length}: {s.name}</dd></>}
            <dt className="text-muted-foreground">Estação</dt><dd>{e.station_name}</dd>
            <dt className="text-muted-foreground">Pedida por</dt><dd>{e.requested_by}</dd>
            <dt className="text-muted-foreground">Início</dt><dd>{when(e.created_at)}</dd>
            {e.finished_at && <><dt className="text-muted-foreground">Fim</dt><dd>{when(e.finished_at)}</dd></>}
            {reason && <><dt className="text-muted-foreground">Motivo</dt><dd>{reason}</dd></>}
            {!!notRun.length && <><dt className="text-muted-foreground">Não executadas</dt><dd>{notRun.map((x) => x.name).join(", ")}</dd></>}
          </dl>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fechar</Button>
          <Button disabled={!e} onClick={() => e && onMore(e.id)}>Saber mais</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export const HISTORY_COLUMNS: DataColumn<Execution>[] = [
  { id: "when", header: "Quando", cell: (e) => when(e.created_at), sortValue: (e) => e.created_at },
  { id: "what", header: "Processo ou rotina", cell: (e) => <span className="font-medium">{title(e)}{e.schedule_id ? <Badge variant="outline" className="ml-2 font-normal">Agendada</Badge> : null}</span>,
    sortValue: title, searchText: (e) => `${title(e)}${e.schedule_id ? " agendada" : ""}` },
  { id: "station", header: "Estação", cell: (e) => e.station_name, sortValue: (e) => e.station_name, searchText: (e) => e.station_name },
  { id: "state", header: "Situação", cell: (e) => <ExecutionBadge e={e} />, sortValue: executionLabel, searchText: executionLabel },
  { id: "end", header: "Término", className: "text-muted-foreground", cell: (e) => (e.end_reason ? END_REASON[e.end_reason] ?? e.end_reason : "—"), sortValue: (e) => e.end_reason },
  { id: "by", header: "Por", cell: (e) => e.requested_by, sortValue: (e) => e.requested_by, searchText: (e) => e.requested_by },
];

const HISTORY_TABS = ["running", "waiting", "attention", "verified"];

/** Rows the Core returns for a period at most (service.py list_executions). */
export const PERIOD_LIMIT = 500;

export function HistoryPage({ focus, days }: { focus?: string; days?: number }) {
  const { executions, processes, src, go } = useStore();
  const [open, setOpen] = useState<string | null>(focus && !HISTORY_TABS.includes(focus) ? focus : null);
  // With a period (opened from an Empresa indicator): the same rows the Core counted, read again with the store.
  const [period, setPeriod] = useState<Execution[] | null>(null);
  const [periodError, setPeriodError] = useState<unknown>(null);
  useEffect(() => {
    if (!days) return;
    let on = true;
    // A failed re-read keeps the rows already shown, under the error; with nothing shown yet there is no table.
    src.executionsSince(days).then((r) => { if (on) { setPeriod(r); setPeriodError(null); } }, (e) => { if (on) setPeriodError(e); });
    return () => { on = false; };
  }, [src, days, executions]); // every store read (change feed or periodic) gives a new list: one read here per store read
  const rows = days ? period : executions;
  // "Saber mais" in the Kanban opens this exact execution, even when it is older than the recent list: read it by its id.
  const [byId, setById] = useState<Execution | null>(null);
  const listed = rows?.find((e) => e.id === open) ?? executions?.find((e) => e.id === open) ?? null;
  useEffect(() => {
    if (!open || listed || !/^[0-9a-f-]{36}$/.test(open)) return; // only an execution id ("all" and tab names are not)
    let on = true;
    src.execution(open).then((e) => { if (on) setById(e); }, () => { if (on) setById(null); });
    return () => { on = false; };
  }, [open, listed, src, executions]);
  const sel = listed ?? (byId?.id === open ? byId : null);
  return (
    <div className="space-y-3">
      {days && <div role="status" className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm">
        <span>Iniciadas nos últimos {days} dias{period ? `: ${period.length} ${period.length === 1 ? "execução" : "execuções"}` : ""}
          {period && period.length >= PERIOD_LIMIT ? ` (as ${PERIOD_LIMIT} mais recentes; o total está em Empresa)` : ""}.</span>
        <Button size="sm" variant="ghost" onClick={() => go({ menu: "processo", page: "historico" })}>Ver todas as recentes</Button>
      </div>}
      <ErrorView error={periodError} />
      {days && period === null && periodError ? null : <DataTable label="Execuções" storageKey="processo-historico" rows={rows} columns={HISTORY_COLUMNS} rowKey={(e) => e.id} rowLabel={title}
        empty="Nenhuma execução." searchPlaceholder="Buscar processo, estação ou pessoa…" onRowOpen={(e) => setOpen(e.id)} initialTab={HISTORY_TABS.includes(focus ?? "") ? focus : "all"}
        tabs={[{ id: "all", label: "Todas", match: () => true }, { id: "running", label: "Em andamento", icon: Loader2, match: (e) => groupOf(e) === "running" },
          { id: "waiting", label: "Aguardando revisão", icon: Hourglass, match: (e) => groupOf(e) === "waiting" },
          { id: "attention", label: "Precisam de atenção", icon: CircleAlert, match: (e) => groupOf(e) === "attention" },
          { id: "verified", label: "Verificadas", icon: CheckCircle2, match: (e) => groupOf(e) === "verified" }]}
        filters={[{ id: "process", label: "Processo", options: processChoices(processes, rows).map((o) => ({ value: String(o.id), label: o.label, match: (e: Execution) => e.process_id === o.id })) }]} />}
      <Sheet open={sel !== null} onOpenChange={(o) => { if (!o) setOpen(null); }}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          {sel && <>
            <SheetHeader><SheetTitle>{title(sel)}</SheetTitle>
              <SheetDescription>Estação {sel.station_name} · pedida por {sel.requested_by} · {when(sel.created_at)}</SheetDescription></SheetHeader>
            <div className="space-y-5 px-4 pb-6 text-sm">
              <p className="flex flex-wrap items-center gap-2"><ExecutionBadge e={sel} />{sel.end_reason && <span className="text-muted-foreground">{END_REASON[sel.end_reason] ?? sel.end_reason}</span>}</p>
              {sel.state === "finished" && sel.steps.some((s) => s.state === null) && (
                <p className="text-muted-foreground">Não executadas: {sel.steps.filter((s) => s.state === null).map((s) => s.name).join(", ")}.</p>
              )}
              <ExecutionReports e={sel} open={src.openReportFolder} />
              {typeof (sel.context as any)?.last?.output_path === "string" && <p>Arquivo salvo: <span className="break-all font-medium">{(sel.context as any).last.output_path}</span></p>}
              <ExecutionLog e={sel} />
              <div><p className="mb-2 font-medium">Linha do tempo</p><Timeline e={sel} /></div>
              {Object.keys(sel.context ?? {}).length > 0 && <details><summary className="cursor-pointer font-medium">Contexto desta execução</summary>
                <pre className="mt-2">{JSON.stringify(sel.context, null, 2)}</pre></details>}
              <p className="font-mono text-xs text-muted-foreground">Referência {sel.correlation_id}</p>
            </div>
          </>}
        </SheetContent>
      </Sheet>
    </div>
  );
}
