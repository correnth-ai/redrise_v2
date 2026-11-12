// Processos: admin panel (stats-02 + access cards), table-04 grouped by
// process with table-02 row actions and filters, routine library, routine
// detail in a side sheet and process composition in dialog-11.
import { Fragment, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, CalendarClock, ChevronDown, ChevronRight, Eye, History, Link2, ListChecks, Pencil, Play, Plus, Replace, Trash2, Unlink, UserCheck, Workflow } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable, type DataColumn } from "@/components/data-table";
import { ErrorView } from "@/components/diagnostic";
import { IconAction } from "@/components/icon-action";
import { useExecutionSummary } from "@/hooks/use-summary";
import { ScheduleDialog, SchedulesSection } from "@/features/schedules";
import { SearchableSelect } from "@/components/searchable-select";
import { ExecutionBadge, StateBadge } from "@/components/blocks";
import { describeConfig } from "@/features/run-dialog";
import { END_REASON, groupOf, title } from "@/data/status";
import { AssignedToMe } from "@/features/reviews";
import type { Process, Routine } from "@/data/types";
import { useStore } from "@/state";
import { cn, fullWhen, shortWhen, when } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const CATEGORY: Record<string, string> = { windows: "Windows", browser: "Navegador", mac: "Mac", linux: "Linux" };

const FOLLOW_UP: Record<string, string> = { review: "Solicitar revisão", report: "Gerar relatório", notify: "Notificar alguém" };
const originLabel = (kind: string, c: Routine["config"]) => kind === "followup" ? FOLLOW_UP[c?.action ?? ""] ?? "Follow-up" : kind === "notepad_step" ? "Bloco de Notas" : kind === "app_open" ? (c?.target?.kind === "file" ? "Arquivo" : "Aplicativo") : c ? (c.origin === "site" ? "Site" : "HTML local") : "Legada";
const PREPARED = ["browser_open", "app_open"];
/** Kinds a process links (the Core's PROCESS_KINDS): the Boas-vindas steps too, and a follow-up after another step. */
const LINKABLE = [...PREPARED, "notepad_step", "followup"];
/** Kinds that can be a step 1 (a follow-up needs a step before it). */
const STARTS = [...PREPARED, "notepad_step"];
/** Why a process cannot start as composed (the Core refuses it too: PROCESS-START-INVALID), or null. */
export const startProblem = (p: Process): string | null => !p.items.length ? "Sem etapa 1 para executar"
  : p.items[0].kind === "followup" ? "A etapa 1 é um follow-up, que precisa de uma etapa anterior" : null;
const EDITABLE = [...PREPARED, "followup"];

function Loading({ what }: { what: string }) {
  return <p className="text-sm text-muted-foreground">Carregando {what}…</p>;
}

const Action = IconAction;

// ---------------------------------------------------------------- Processo › Ação: paginated processes, routines on demand
/** Situation of the last attempt, for the filter and its column (the same rules as before this table was paginated). */
/** Why the process cannot be deleted now (the Core checks every execution of it: PROCESS-BUSY), or null. */
const busyProblem = (p: Process): string | null => p.last_execution?.state === "running" ? "Em execução: aguarde terminar para excluir"
  : p.last_execution?.state === "waiting_review" ? "Aguardando revisão: conclua a revisão para excluir" : null;
const lastState = (p: Process) => !p.last_execution ? "never" : p.last_execution.state === "running" ? "running"
  : p.last_execution.state === "finished" && p.last_execution.outcome !== "verified" ? "attention" : "other";

/** "Último sucesso": the process's own field from the Core (whole history); never derived from the last attempt. */
function LastSuccess({ p }: { p: Process }) {
  if (p.last_success_at === undefined) return <span className="text-muted-foreground" title="O servidor não informou o último sucesso">—</span>;
  if (p.last_success_at === null) return <span className="text-muted-foreground">Nunca</span>;
  return <time dateTime={p.last_success_at} title={fullWhen(p.last_success_at)} className="tabular-nums">{shortWhen(p.last_success_at)}</time>;
}

export function ProcessTable({ compact = false }: { compact?: boolean }) {
  const { processes, routines, run, me } = useStore();
  // Collapsed on arrival; kept by process id while the data refreshes during this visit (not stored).
  const [open, setOpen] = useState<Set<number>>(new Set());
  const [compose, setCompose] = useState<Process | "new" | null>(null);
  const [detail, setDetail] = useState<Routine | null>(null);
  const [integrate, setIntegrate] = useState<Process | null>(null);
  const [replace, setReplace] = useState<Process | null>(null);
  const [schedule, setSchedule] = useState<Process | null>(null);
  const [remove, setRemove] = useState<Process | null>(null);
  const toggle = (id: number) => setOpen((cur) => { const next = new Set(cur); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const columns: DataColumn<Process>[] = [
    { id: "name", header: "Processo", sortValue: (p) => p.name, searchText: (p) => p.name, cell: (p) => {
      const expanded = open.has(p.id);
      return <span className="flex items-center gap-1.5">
        <Tooltip><TooltipTrigger asChild>
          <Button size="icon" variant="ghost" className="size-7 shrink-0" aria-expanded={expanded} aria-controls={`proc-${p.id}-routines`}
            aria-label={`${expanded ? "Ocultar" : "Mostrar"} as rotinas de ${p.name}`} onClick={() => toggle(p.id)}>
            {expanded ? <ChevronDown /> : <ChevronRight />}
          </Button></TooltipTrigger><TooltipContent>{expanded ? "Ocultar rotinas" : "Mostrar rotinas"}</TooltipContent></Tooltip>
        <span className="font-semibold">{p.name}</span>
        {p.items[0]?.kind === "followup" && <Badge variant="outline" className="border-transparent bg-warn-soft font-medium text-warn">Etapa 1 é um follow-up: não executa</Badge>}
        {p.pending_change && <Badge variant="outline" className="border-transparent bg-info-soft font-medium text-info">Substituição da etapa 1 pendente</Badge>}
      </span>;
    } },
    { id: "routines", header: "Rotinas", className: "text-muted-foreground", sortValue: (p) => p.items.length,
      cell: (p) => p.items.length ? `${p.items.length} ${p.items.length === 1 ? "rotina" : "rotinas"}` : "sem etapa 1" },
    // In a narrow window the last execution goes under its badge, its date kept whole (nothing of it is dropped).
    { id: "state", header: "Execução", searchText: (p) => p.last_execution ? "" : "nunca executado", cell: (p) => <span className="flex flex-col items-start gap-1">
      {p.last_execution ? <ExecutionBadge e={{ state: p.last_execution.state, outcome: p.last_execution.outcome } as any} /> : <Badge variant="outline">Nunca executado</Badge>}
      {p.last_execution && <span className="text-xs text-muted-foreground">última: <span className="whitespace-nowrap">{when(p.last_execution.created_at)}</span>{p.last_execution.end_reason ? ` · ${END_REASON[p.last_execution.end_reason] ?? p.last_execution.end_reason}` : ""}</span>}
    </span> },
    { id: "success", header: "Último sucesso", className: "whitespace-nowrap", sortValue: (p) => p.last_success_at ?? null, cell: (p) => <LastSuccess p={p} /> },
    // The same six actions on every process, Boas-vindas included (PROCESS-ACTIONS-20261111 item 1.1), in this order; an
    // action that cannot work now is unavailable with the reason. Operators only execute; the Core checks access anyway.
    { id: "actions", header: "Ações", fixed: true, className: "text-right whitespace-nowrap", cell: (p) => {
      const replaceWhy = !p.items.length ? "Sem etapa 1 para substituir" : p.pending_change ? "Já há substituição pendente"
        : p.last_execution && p.last_execution.state !== "finished" ? "Em execução: aguarde terminar" : null;
      return <span className="inline-flex items-center justify-end gap-0.5">
        <Action label={startProblem(p) ? `Executar: ${startProblem(p)!.toLowerCase()}` : `Executar ${p.name}`} onClick={() => run({ kind: "process", id: p.id })} disabled={!!startProblem(p)}><Play /></Action>
        {me.role === "admin" && <>
          <Action label={startProblem(p) ? `Agendar: ${startProblem(p)!.toLowerCase()}` : "Agendar"} disabled={!!startProblem(p)} onClick={() => setSchedule(p)}><CalendarClock /></Action>
          <Action label="Integrar rotina avulsa" onClick={() => setIntegrate(p)}><Link2 /></Action>
          <Action label={replaceWhy ?? "Substituir etapa 1"} disabled={!!replaceWhy} onClick={() => setReplace(p)}><Replace /></Action>
          <Action label={busyProblem(p) ?? `Excluir ${p.name}`} destructive disabled={!!busyProblem(p)} onClick={() => setRemove(p)}><Trash2 /></Action>
          <Action label="Editar composição" onClick={() => setCompose(p)}><Pencil /></Action>
        </>}
      </span>;
    } },
  ];
  // The routines of an expanded process, in their order, on the process's own page.
  const routinesOf = (p: Process) => !open.has(p.id) ? null : (
    <ul id={`proc-${p.id}-routines`} aria-label={`Rotinas de ${p.name}`} className="divide-y bg-muted/30">
      {!p.items.length && <li className="px-12 py-2 text-sm text-muted-foreground">Nenhuma rotina: o processo não tem etapa 1.</li>}
      {p.items.map((it) => {
        const rt = routines?.find((r) => r.id === it.routine_id);
        return (
          <li key={`${p.id}-${it.position}`} className="flex flex-wrap items-center gap-x-6 gap-y-1 py-1.5 pl-12 pr-2 text-sm">
            <span className="min-w-48 flex-1">{it.position}. {it.routine_name}</span>
            <span className="w-40 text-muted-foreground">{originLabel(it.kind, it.config)}</span>
            <span className="w-48">{it.position === p.items.length ? "Fim da sequência" : it.continue_next ? "Continua para a próxima" : "Encerra aqui"}</span>
            <span className="w-28 text-muted-foreground">Pelo processo</span>
            <span className="ml-auto">{rt && <Action label="Ver detalhes" onClick={() => setDetail(rt)}><Eye /></Action>}</span>
          </li>
        );
      })}
    </ul>
  );
  return (
    <div className="space-y-3">
      <DataTable label="Processos" storageKey={compact ? "processo-acao-compacta" : "processo-acao"} rows={processes} columns={columns}
        rowKey={(p) => String(p.id)} rowLabel={(p) => p.name} childRows={routinesOf} clearable
        searchPlaceholder="Buscar processo…" empty="Nenhum processo."
        filters={[
          { id: "process", label: "Processo", options: (processes ?? []).map((p) => ({ value: String(p.id), label: p.name, match: (x: Process) => x.id === p.id })) },
          { id: "last", label: "Última execução", options: [
            { value: "running", label: "Em andamento", match: (p) => lastState(p) === "running" },
            { value: "attention", label: "Precisam de atenção", match: (p) => lastState(p) === "attention" },
            { value: "never", label: "Nunca executados", match: (p) => lastState(p) === "never" },
          ] },
        ]}
        toolbar={!compact && me.role === "admin" ? <Button size="sm" onClick={() => setCompose("new")}><Plus /> Novo processo</Button> : undefined} />
      <ProcessComposer value={compose} onClose={() => setCompose(null)} />
      <IntegrateRoutine process={integrate} onClose={() => setIntegrate(null)} />
      <ReplaceStepOne process={replace} onClose={() => setReplace(null)} />
      <ScheduleDialog key={schedule?.id ?? "none"} process={schedule} onClose={() => setSchedule(null)} />
      <DeleteProcess key={remove?.id ?? "none"} process={remove} onClose={() => setRemove(null)} />
      <RoutineSheet routine={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

// ---------------------------------------------------------------- routine library
const routineType = (r: Routine) => r.kind === "followup" ? FOLLOW_UP[r.config?.action ?? ""] ?? "Follow-up" : r.kind === "notepad_step" ? "Bloco de Notas" : r.kind === "app_open" ? (r.config?.target?.kind === "file" ? "Abrir arquivo" : "Abrir aplicativo") : r.config ? (r.config.origin === "site" ? "Navegar em site" : "Abrir HTML local") : r.kind === "template" ? `Modelo ${r.template_id}` : "Gravação";
const routineTarget = (r: Routine) => r.kind === "followup" ? r.assignee_name ?? r.config?.to ?? "Documentos" : r.kind === "app_open" ? r.config?.target?.path ?? r.config?.target?.name ?? "" : r.kind === "browser_open" && r.config ? (r.config.url ?? r.config.path ?? "") : CATEGORY[r.category] ?? r.category;

export function RoutinesPage() {
  const { routines, processes, run, go, me, src, reload } = useStore();
  const [detail, setDetail] = useState<Routine | null>(null);
  const [remove, setRemove] = useState<Routine[] | null>(null);
  // A linked routine, even as the only step, runs through its process.
  const linkOf = (id: number) => (processes ?? []).filter((p) => p.items.some((i) => i.routine_id === id));
  // The ready-made Boas-vindas process keeps its routines (the Core refuses them too).
  const readyMade = (id: number) => linkOf(id).some((p) => !!p.system_key);
  const columns: DataColumn<Routine>[] = [
    { id: "name", header: "Rotina", cell: (r) => <span className="font-medium">{r.name}</span>, sortValue: (r) => r.name, searchText: (r) => r.name },
    { id: "type", header: "Tipo", cell: routineType, sortValue: routineType, searchText: routineType },
    { id: "target", header: "Destino", className: "max-w-48 truncate text-muted-foreground", sortValue: routineTarget, searchText: routineTarget,
      cell: (r) => <span title={routineTarget(r)}>{routineTarget(r)}</span> },
    { id: "version", header: "Versão", cell: (r) => `v${r.version}`, sortValue: (r) => r.version },
    { id: "process", header: "Processo", sortValue: (r) => linkOf(r.id)[0]?.name, searchText: (r) => linkOf(r.id).map((p) => p.name).join(" "),
      cell: (r) => linkOf(r.id).length
        ? <span className="flex flex-wrap gap-1">{linkOf(r.id).map((p) => <Badge key={p.id} variant="secondary"><Link2 aria-hidden /> {p.name}</Badge>)}</span>
        : <Badge variant="outline">Avulsa</Badge> },
    { id: "actions", header: "Ações", fixed: true, className: "text-right", cell: (r) => {
      const linked = linkOf(r.id).length > 0;
      return <>
        <Action label={linked ? "Executa pelo processo" : r.config ? "Executar rotina avulsa" : "Executar"} disabled={linked || (!!r.config && !r.config.isolated)}
          onClick={() => (r.config ? run({ kind: "routine", id: r.id }) : go({ menu: "rotina", page: "executar-legada", id: r.id }))}><Play /></Action>
        <Action label="Ver detalhes" onClick={() => setDetail(r)}><Eye /></Action>
        {me.role === "admin" && EDITABLE.includes(r.kind) && <Action label="Editar" onClick={() => go({ menu: "rotina", page: "editar", id: r.id })}><Pencil /></Action>}
        {me.role === "admin" && <Action label={readyMade(r.id) ? "Rotina do processo pronto: não é excluída" : "Excluir"} disabled={readyMade(r.id)} onClick={() => setRemove([r])}><Trash2 /></Action>}
      </>;
    } },
  ];
  return (
    <div className="space-y-3">
      {me.role === "admin" && <div className="flex flex-wrap justify-end gap-2">
        <Button size="sm" variant="outline" disabled>Testes (em breve)</Button>
        <Button size="sm" variant="outline" disabled>Por gravação (em breve)</Button>
        <Button size="sm" onClick={() => go({ menu: "rotina", page: "nova" })}><Plus /> Nova Rotina</Button>
      </div>}
      <DataTable label="Rotinas" storageKey="rotina-lista" rows={routines} columns={columns} rowKey={(r) => String(r.id)} rowLabel={(r) => r.name}
        searchPlaceholder="Buscar rotina, destino ou processo…" empty="Nenhuma rotina."
        tabs={[{ id: "all", label: "Todas", match: () => true }, { id: "avulsas", label: "Avulsas", icon: Unlink, match: (r) => !linkOf(r.id).length },
          { id: "vinculadas", label: "Vinculadas", icon: Link2, match: (r) => linkOf(r.id).length > 0 }]}
        filters={[{ id: "tipo", label: "Tipo", options: [
          { value: "site", label: "Navegar em site", match: (r) => r.kind === "browser_open" && r.config?.origin === "site" },
          { value: "html", label: "Abrir HTML local", match: (r) => r.kind === "browser_open" && r.config?.origin === "html" },
          { value: "app", label: "Abrir aplicativo ou arquivo", match: (r) => r.kind === "app_open" },
          { value: "followup", label: "Follow-up", match: (r) => r.kind === "followup" },
          { value: "notepad", label: "Bloco de Notas", match: (r) => r.kind === "notepad_step" },
          { value: "legacy", label: "Modelo ou gravação", match: (r) => r.kind === "template" || r.kind === "procedure" },
        ] }]}
        selectable={me.role === "admin"}
        selectionActions={(rows) => {
          const ok = rows.filter((r) => !readyMade(r.id));
          return <Button size="sm" variant="outline" disabled={!ok.length} onClick={() => setRemove(ok)}
            title={ok.length < rows.length ? "Rotinas do processo pronto Boas-vindas não são excluídas" : undefined}><Trash2 /> {ok.length ? `Excluir ${ok.length}` : "Excluir"}</Button>;
        }}
      />
      <RoutineSheet routine={detail} onClose={() => setDetail(null)} />
      <RemoveRoutines rows={remove} linkOf={linkOf} onClose={() => setRemove(null)} remove={src.archiveRoutine} reload={reload} />
    </div>
  );
}

// Deleting archives the routine and takes it out of every process in one Core transaction; the other steps keep
// their order and continuation. Versions, running executions and the history stay. Several are deleted one by one:
// the dialog then says exactly which ones were deleted and which failed, and only those that failed stay selected.
function RemoveRoutines({ rows, linkOf, onClose, remove, reload }: { rows: Routine[] | null; linkOf: (id: number) => Process[]; onClose: () => void;
  remove: (id: number) => Promise<void>; reload: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Routine[]>([]);
  const [failed, setFailed] = useState<{ r: Routine; error: unknown }[]>([]);
  const pending = (rows ?? []).filter((r) => !done.some((d) => d.id === r.id));
  const close = () => { if (busy) return; setDone([]); setFailed([]); onClose(); };
  async function confirm() {
    setBusy(true); setFailed([]);
    const ok: Routine[] = [...done];
    const bad: { r: Routine; error: unknown }[] = [];
    for (const r of pending) {
      try { await remove(r.id); ok.push(r); } catch (e) { bad.push({ r, error: e }); }
    }
    setDone(ok); setFailed(bad); setBusy(false);
    await reload();
    if (!bad.length) { setDone([]); onClose(); }
  }
  const affected = [...new Map(pending.flatMap((r) => linkOf(r.id)).map((p) => [p.id, p])).values()];
  return (
    <Dialog open={rows !== null} onOpenChange={(o) => { if (!o) close(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{rows?.length === 1 ? "Excluir rotina" : `Excluir ${rows?.length ?? 0} rotinas`}</DialogTitle>
          <DialogDescription>Elas deixam de aparecer na Lista. O histórico de execuções é preservado.</DialogDescription>
        </DialogHeader>
        <ul className="list-disc pl-5 text-sm">{pending.map((r) => <li key={r.id}>{r.name}{linkOf(r.id).length ? <span className="text-muted-foreground"> · em {linkOf(r.id).map((p) => p.name).join(", ")}</span> : null}</li>)}</ul>
        {!!affected.length && <p className="text-sm">Será retirada dos processos {affected.map((p) => p.name).join(", ")}. As demais etapas continuam na mesma ordem; um processo sem etapa 1 válida não executa até ser corrigido. Execuções em andamento não mudam.</p>}
        {!!done.length && <p role="status" className="text-sm">Excluídas: {done.map((r) => r.name).join(", ")}.</p>}
        {!!failed.length && <div className="space-y-1"><p className="text-sm font-medium">Não excluídas ({failed.length}): {failed.map((f) => f.r.name).join(", ")}. Elas continuam selecionadas.</p>
          {failed.map((f) => <ErrorView key={f.r.id} error={f.error} />)}</div>}
        <DialogFooter>
          <Button variant="ghost" disabled={busy} onClick={close}>{failed.length ? "Fechar" : "Cancelar"}</Button>
          <Button variant="destructive" disabled={busy || !pending.length} onClick={confirm}>{busy ? "Excluindo…" : failed.length ? "Tentar de novo" : "Excluir"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CountTile({ label, value, icon: Icon, mark, onOpen }: { label: string; value: number | null | undefined; icon?: typeof Play; mark?: string; onOpen?: () => void }) {
  const body = <>
    {Icon && <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-muted-foreground"><Icon aria-hidden className="size-4" /></span>}
    {mark && <span aria-hidden className={cn("size-3 shrink-0 rounded-sm", mark)} />}
    <span><span className="block text-xs text-muted-foreground">{label}</span><span className="block text-xl font-semibold tabular-nums">{value ?? "—"}</span></span>
  </>;
  const box = "flex w-full items-center gap-3 rounded-lg border bg-card p-3 text-left";
  return onOpen
    ? <button type="button" onClick={onOpen} className={cn(box, "outline-none hover:border-muted-foreground focus-visible:ring-2 focus-visible:ring-ring")}>{body}</button>
    : <div className={box}>{body}</div>;
}

export function ProcessesPage({ focus }: { focus?: string }) {
  const { processes, reviews, go, error } = useStore();
  const [tab, setTab] = useState(focus && focus !== "schedules" ? "mine" : "overview");  // "schedules": from a schedule notification
  const { summary, error: summaryError } = useExecutionSummary();
  const days = summary?.days ?? 30;
  const history = (id?: string) => () => go({ menu: "processo", page: "historico", id, days });  // same period as the count
  const pending = reviews?.filter((q) => q.status === "pending").length;
  return (
    <Tabs value={tab} onValueChange={setTab} className="space-y-5">
      <TabsList aria-label="Visão do processo">
        <TabsTrigger value="overview">Visão Geral</TabsTrigger>
        <TabsTrigger value="mine">Marcado para mim{!!pending && <Badge className="ml-1 px-1.5 py-0 text-[11px] tabular-nums">{pending}</Badge>}</TabsTrigger>
      </TabsList>
      <TabsContent value="overview" className="space-y-6">
        <ErrorView error={error} />
        <ErrorView error={summaryError} />
        <div className="grid gap-3 sm:grid-cols-3">
          <CountTile label="Processos cadastrados" value={processes?.length} icon={ListChecks} />
          <CountTile label={"Execuções nos últimos " + days + " dias"} value={summary?.total} icon={History} onOpen={history()} />
          <CountTile label="Marcados para mim" value={pending} icon={UserCheck} onOpen={() => setTab("mine")} />
        </div>
        {/* Counted by the Core for the period, like Empresa; the table below shows only the most recent ones. */}
        <section aria-label={"Execuções iniciadas nos últimos " + days + " dias, por situação"} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <CountTile label="Em andamento" value={summary?.running} mark="bg-warn" onOpen={history("running")} />
          <CountTile label="Aguardando revisão" value={summary?.waiting} mark="bg-info" onOpen={history("waiting")} />
          <CountTile label="Precisam de atenção" value={summary?.attention} mark="bg-destructive" onOpen={history("attention")} />
          <CountTile label="Verificadas" value={summary?.verified} mark="bg-ok" onOpen={history("verified")} />
        </section>
        {/* Executions start from the Play of each process row; the history lives in Processo > Historico. */}
        <ProcessTable />
        <SchedulesSection />
      </TabsContent>
      <TabsContent value="mine"><AssignedToMe focus={focus} /></TabsContent>
    </Tabs>
  );
}

// ---------------------------------------------------------------- side sheet
function RoutineSheet({ routine, onClose }: { routine: Routine | null; onClose: () => void }) {
  const { processes, run, go, me } = useStore();
  const used = routine ? (processes ?? []).filter((p) => p.items.some((i) => i.routine_id === routine.id)) : [];
  return (
    <Sheet open={routine !== null} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent className="w-full sm:max-w-md">
        {routine && <>
          <SheetHeader><SheetTitle>{routine.name}</SheetTitle><SheetDescription>Versão {routine.version} · cadastrada em {when(routine.created_at)}</SheetDescription></SheetHeader>
          <div className="space-y-4 px-4 text-sm">
            <p>{describeConfig(routine.config)}</p>
            {routine.kind === "followup" && routine.assignee_name && <p>Responsável: <b>{routine.assignee_name}</b></p>}
            {routine.config && <p>Execução: <b>{used.length ? "pelo processo" : routine.config.isolated ? "avulsa" : "só em processo (requer contexto)"}</b></p>}
            <div><p className="font-medium">Usada em</p>
              {used.length ? <ul className="list-disc pl-5">{used.map((p) => <li key={p.id}>{p.name}</li>)}</ul> : <p className="text-muted-foreground">Nenhum processo.</p>}
              {used.length > 1 && <p className="mt-1 text-xs text-muted-foreground">Alterações valem para todos esses processos na próxima execução.</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              {routine.config && !used.length && <Button size="sm" disabled={!routine.config.isolated} onClick={() => { onClose(); run({ kind: "routine", id: routine.id }); }}><Play /> Executar</Button>}
              {me.role === "admin" && EDITABLE.includes(routine.kind) && <Button size="sm" variant="outline" onClick={() => { onClose(); go({ menu: "rotina", page: "editar", id: routine.id }); }}><Pencil /> Editar</Button>}
            </div>
          </div>
        </>}
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------- standalone routine -> process
function IntegrateRoutine({ process, onClose }: { process: Process | null; onClose: () => void }) {
  const { routines, processes, src, reload } = useStore();
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // A follow-up needs a step before it, so it is offered only to a process that has one.
  const free = (routines ?? []).filter((r) => (process?.items.length ? LINKABLE : STARTS).includes(r.kind)
    && !(processes ?? []).some((p) => p.items.some((i) => i.routine_id === r.id)));
  const next = (process?.items.length ?? 0) + 1;
  const close = () => { setPick(null); setError(null); onClose(); };
  async function confirm() {
    if (!process || !pick || busy) return;
    setBusy(true); setError(null);
    try { await src.integrateRoutine(process.id, Number(pick)); await reload(); close(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <Dialog open={process !== null} onOpenChange={(o) => { if (!o && !busy) close(); }}>
      <DialogContent className="overflow-visible sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Integrar rotina avulsa</DialogTitle>
          <DialogDescription>Ela passa a ser a etapa {next} de {process?.name} e deixa de executar pela Lista. Execuções em andamento não mudam.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2"><Label htmlFor="int-routine">Rotina avulsa</Label>
          <SearchableSelect id="int-routine" value={pick} onChange={setPick} placeholder="Busque pelo nome da rotina"
            options={free.map((r) => ({ value: String(r.id), label: r.name, hint: routineType(r) }))} empty="Nenhuma rotina avulsa." /></div>
        {next > 1 && <p className="text-xs text-muted-foreground">A etapa {next - 1} passa a continuar para ela.</p>}
        <ErrorView error={error} />
        <DialogFooter>
          <Button variant="ghost" disabled={busy} onClick={close}>Voltar</Button>
          <Button disabled={busy || !pick} onClick={confirm}>{busy ? "Integrando…" : "Integrar"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- replacing step 1, with approval
function ReplaceStepOne({ process, onClose }: { process: Process | null; onClose: () => void }) {
  const { routines, processes, src, reload, go } = useStore();
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const free = (routines ?? []).filter((r) => STARTS.includes(r.kind) && !(processes ?? []).some((p) => p.items.some((i) => i.routine_id === r.id)));
  const close = () => { setPick(null); setError(null); onClose(); };
  async function confirm() {
    if (!process || !pick || busy) return;
    setBusy(true); setError(null);
    try { await src.requestStepChange(process.id, Number(pick)); await reload(); close(); go({ menu: "processo", page: "acao", id: "changes", nonce: Date.now() }); }
    catch (e) { setError(e); await reload(); } finally { setBusy(false); }
  }
  return (
    <Dialog open={process !== null} onOpenChange={(o) => { if (!o && !busy) close(); }}>
      <DialogContent className="overflow-visible sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Substituir etapa 1</DialogTitle>
          <DialogDescription>A etapa 1 de {process?.name} é hoje {process?.items[0]?.routine_name}. A troca só acontece quando um membro elegível aprovar, com o processo fora de execução.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2"><Label htmlFor="rep-routine">Nova etapa 1</Label>
          <SearchableSelect id="rep-routine" value={pick} onChange={setPick} placeholder="Busque uma rotina avulsa"
            options={free.map((r) => ({ value: String(r.id), label: r.name, hint: routineType(r) }))} empty="Nenhuma rotina avulsa." /></div>
        <p className="text-xs text-muted-foreground">Podem aprovar quem criou o processo, os responsáveis por revisões nele e os administradores. Quem pede só aprova se não houver outra pessoa elegível. A rotina atual volta a ser avulsa.</p>
        <ErrorView error={error} />
        <DialogFooter>
          <Button variant="ghost" disabled={busy} onClick={close}>Voltar</Button>
          <Button disabled={busy || !pick} onClick={confirm}>{busy ? "Enviando…" : "Pedir aprovação"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- deleting ONLY the process (PROCESS-ACTIONS-20261111 item 2)
/** The word to type, compared as trim().toLowerCase() (the Core compares it again). */
export const DELETE_WORD = "confirmado";
export const deleteConfirmed = (typed: string) => typed.trim().toLowerCase() === DELETE_WORD;

/** Typing the word only enables Excluir; the request goes by the process id, once, and the lists change only after the Core
 *  confirms. Cancel, X or Escape change nothing; a new opening (another key) starts with an empty field. */
function DeleteProcess({ process, onClose }: { process: Process | null; onClose: () => void }) {
  const { src, reload } = useStore();
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const ok = deleteConfirmed(typed);
  const close = () => { if (!busy) onClose(); };
  async function confirm(ev: React.FormEvent) {
    ev.preventDefault();
    if (!process || !ok || busy) return;
    setBusy(true); setError(null);
    try { await src.archiveProcess(process.id, typed); await reload(); onClose(); }
    catch (e) { setError(e); await reload().catch(() => undefined); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={process !== null} onOpenChange={(o) => { if (!o) close(); }}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={confirm} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Excluir processo</DialogTitle>
            <DialogDescription>Confirma exclusão do processo? As rotinas não serão excluídas.</DialogDescription>
          </DialogHeader>
          <p className="text-sm">Processo: <b className="break-words">{process?.name}</b></p>
          <p className="text-sm text-muted-foreground">Rotinas só deste processo ficam avulsas; as usadas em outros processos continuam neles. Os agendamentos dele deixam de executar e o histórico de execuções é mantido.</p>
          <div className="space-y-2"><Label htmlFor="del-word">Digite Confirmado para excluir</Label>
            <Input id="del-word" value={typed} autoComplete="off" spellCheck={false} disabled={busy} onChange={(e) => setTyped(e.target.value)}
              aria-describedby="del-word-help" /><p id="del-word-help" className="text-xs text-muted-foreground">Maiúsculas e minúsculas tanto faz.</p></div>
          <ErrorView error={error} />
          <DialogFooter>
            <Button type="button" variant="ghost" disabled={busy} onClick={close}>Cancelar</Button>
            <Button type="submit" variant="destructive" disabled={!ok || busy} aria-busy={busy || undefined}>{busy ? "Excluindo…" : "Excluir"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- dialog-11: process composition
function ProcessComposer({ value, onClose }: { value: Process | "new" | null; onClose: () => void }) {
  const { routines, src, reload } = useStore();
  const editing = value && value !== "new" ? value : null;
  const [name, setName] = useState("");
  const [items, setItems] = useState<{ routine_id: number; continue_next: boolean }[]>([]);
  const [add, setAdd] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [seed, setSeed] = useState<unknown>(null);
  if (value !== seed) { // reset when another process is opened
    setSeed(value);
    setName(editing?.name ?? "");
    setItems(editing?.items.map((i) => ({ routine_id: i.routine_id, continue_next: i.continue_next })) ?? []);
    setError(null);
  }
  const available = (routines ?? []).filter((r) => LINKABLE.includes(r.kind));
  const nameOf = (id: number) => routines?.find((r) => r.id === id)?.name ?? `#${id}`;
  const move = (i: number, d: number) => setItems((xs) => { const ys = [...xs]; const [x] = ys.splice(i, 1); ys.splice(i + d, 0, x); return ys; });
  const valid = name.trim().length > 0; // the first routine may come later, from Nova Rotina or an integration
  // Any link can be removed, step 1 included (the process may end empty). Putting another routine ahead of the
  // current step 1 while it stays is a replacement: that one goes through Substituir etapa 1 (approval).
  const firstId = editing?.items[0]?.kind === "followup" ? undefined : editing?.items[0]?.routine_id; // a follow-up first is no start to protect
  const locked = firstId !== undefined && items[0]?.routine_id === firstId;
  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    if (!valid || busy) return;
    setBusy(true); setError(null);
    try { await src.saveProcess(editing?.id ?? null, name.trim(), items); await reload(); onClose(); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  const stepNo = (n: number) => <div className="inline-flex size-6 items-center justify-center rounded-sm bg-muted text-sm">{n}</div>;
  return (
    <Dialog open={value !== null} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="gap-0 overflow-visible p-0 sm:max-w-3xl">
        <DialogHeader className="border-b px-6 py-4"><DialogTitle>{editing ? "Editar processo" : "Novo processo"}</DialogTitle></DialogHeader>
        <form onSubmit={save}>
          <div className="flex flex-col-reverse md:flex-row">
            <div className="flex flex-col justify-between md:w-72 md:border-r">
              <div className="p-6">
                <div className="flex items-center gap-3">
                  <div className="inline-flex shrink-0 items-center justify-center rounded-sm bg-muted p-3"><Workflow className="size-5" /></div>
                  <div><h3 className="text-sm font-medium">Composição</h3><p className="text-sm text-muted-foreground">Rotinas já cadastradas</p></div>
                </div>
                <Separator className="my-4" />
                <p className="text-sm leading-6 text-muted-foreground">A execução sempre começa pela primeira rotina. Só um resultado verificado, com continuação marcada, chama a próxima. O processo pode ser salvo sem rotinas e ganhar a etapa 1 em Nova Rotina.</p>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">Remover uma rotina daqui não a exclui da Lista nem de outros processos. Um processo vazio ou que começa por um follow-up é salvo, mas não executa até ser corrigido.</p>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">A mesma rotina pode estar em vários processos; alterações nela valem na próxima execução. Salvar não executa nada.</p>
                <ErrorView error={error} />
              </div>
              <div className="flex items-center justify-between border-t p-4">
                <DialogClose asChild><Button type="button" variant="ghost">Cancelar</Button></DialogClose>
                <Button size="sm" type="submit" disabled={!valid || busy}>{busy ? "Salvando…" : "Salvar processo"}</Button>
              </div>
            </div>
            <div className="flex-1 space-y-6 p-6">
              <div className="space-y-2">
                <div className="flex items-center gap-3">{stepNo(1)}<Label htmlFor="proc-name">Nome do processo</Label></div>
                <Input id="proc-name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-3">{stepNo(2)}<Label htmlFor="proc-add">Vincular rotina</Label></div>
                <div className="flex gap-2">
                  <Select value={add} onValueChange={setAdd}>
                    <SelectTrigger id="proc-add" className="w-full"><SelectValue placeholder={available.length ? "Selecione uma rotina" : "Cadastre uma rotina primeiro"} /></SelectTrigger>
                    <SelectContent>{available.map((r) => <SelectItem key={r.id} value={String(r.id)}>{r.name}</SelectItem>)}</SelectContent>
                  </Select>
                  <Button type="button" variant="outline" disabled={!add} onClick={() => { setItems((xs) => [...xs, { routine_id: Number(add), continue_next: true }]); setAdd(""); }}><Plus /> Adicionar</Button>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-3">{stepNo(3)}<span className="text-sm font-medium">Ordem e continuação</span></div>
                {!items.length && <p className="text-sm text-muted-foreground">Nenhuma rotina vinculada.</p>}
                <ol className="space-y-2">
                  {items.map((it, i) => (
                    <li key={`${it.routine_id}-${i}`} className="flex items-center gap-2 rounded-md border p-2 text-sm">
                      <span className="w-6 text-center tabular-nums text-muted-foreground">{i + 1}</span>
                      <span className="min-w-0 flex-1 break-words" title={nameOf(it.routine_id)}>{nameOf(it.routine_id)}</span>
                      <label className="flex shrink-0 items-center gap-2 text-xs">
                        <Checkbox checked={it.continue_next}
                          onCheckedChange={(c) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, continue_next: c === true } : x)))} />
                        Continuar para a próxima
                      </label>
                      <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Mover para cima" disabled={i === 0 || (locked && i === 1)} onClick={() => move(i, -1)}><ArrowUp /></Button>
                      <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Mover para baixo" disabled={i === items.length - 1 || (locked && i === 0)} onClick={() => move(i, 1)}><ArrowDown /></Button>
                      <Button type="button" size="icon" variant="ghost" className="size-7" aria-label={`Remover ${nameOf(it.routine_id)} do processo`} title="Remover do processo" onClick={() => setItems((xs) => xs.filter((_, j) => j !== i))}><Trash2 /></Button>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export { StateBadge };
