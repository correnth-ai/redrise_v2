// Fluxos: follow executions and history. Every view (stats, grid, Kanban,
// timeline, log, feed, table) derives from the same execution records; the
// Kanban is read-only (no drag-and-drop, no manual verification).
import { useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorView } from "@/components/diagnostic";
import { ActivityFeed, activityOf, ExecutionBadge, ExecutionLog, StateBadge, Timeline } from "@/components/blocks";
import { JobsSection } from "@/features/legacy";
import { COLUMN_LABEL, column, END_REASON, needsAttention, title, type Column } from "@/data/status";
import type { Execution } from "@/data/types";
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

export function KanbanPage({ process }: { process?: number }) {
  const { executions, processes, go } = useStore();
  const [proc, setProc] = useState(process ? String(process) : "all");
  const cols: Column[] = ["waiting", "running", "verified", "attention", "not_run"];
  // Latest execution per process: its steps are the cards (executed and not executed).
  const shown = useMemo(() => {
    const latest = new Map<string, Execution>();
    for (const e of executions ?? []) {
      const k = e.process_id ? `p${e.process_id}` : `r${e.id}`;
      if (!latest.has(k)) latest.set(k, e);
    }
    return [...latest.values()].filter((e) => proc === "all" || String(e.process_id) === proc);
  }, [executions, proc]);
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-2">
        <div className="space-y-1"><Label htmlFor="k-proc" className="text-xs">Processo</Label>
          <Select value={proc} onValueChange={setProc}>
            <SelectTrigger id="k-proc" size="sm" className="w-64"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todos os processos</SelectItem>{(processes ?? []).map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}</SelectContent>
          </Select></div>
        <p className="pb-1 text-xs text-muted-foreground">Mostra a execução mais recente de cada processo. Somente leitura.</p>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {cols.map((c) => {
          const cards = shown.flatMap((e) => e.steps.filter((s) => column(e, s) === c).map((s) => ({ e, s })));
          return (
            <section key={c} aria-label={COLUMN_LABEL[c]} className="w-60 shrink-0 rounded-lg border bg-muted/40 p-2">
              <h3 className="mb-2 flex items-center justify-between px-1 text-sm font-medium">{COLUMN_LABEL[c]}<span className="text-xs tabular-nums text-muted-foreground">{cards.length}</span></h3>
              <ul className="space-y-2">
                {cards.map(({ e, s }) => (
                  <li key={`${e.id}-${s.position}`}>
                    <button type="button" onClick={() => go({ menu: "processo", page: "historico", id: e.id })}
                      className="w-full rounded-md border bg-card p-2 text-left text-sm shadow-2xs outline-none hover:border-muted-foreground focus-visible:ring-2 focus-visible:ring-ring">
                      <p className="font-medium">{s.position}. {s.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{title(e)}</p>
                      {s.state && c === "attention" && <div className="mt-1"><StateBadge state={s.state} /></div>}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}

export function HistoryPage({ focus }: { focus?: string }) {
  const { executions, processes } = useStore();
  const [proc, setProc] = useState("all");
  const [status, setStatus] = useState(focus === "attention" ? "attention" : "all");
  const [open, setOpen] = useState<string | null>(focus && focus !== "attention" ? focus : null);
  const sel = executions?.find((e) => e.id === open) ?? null;
  if (!executions) return <p className="text-sm text-muted-foreground">Carregando execuções…</p>;
  const shown = executions.filter((e) => (proc === "all" || String(e.process_id) === proc) &&
    (status === "all" || (status === "running" ? e.state === "running" : status === "attention" ? needsAttention(e) : e.outcome === "verified")));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2" role="group" aria-label="Filtros">
        <div className="space-y-1"><Label htmlFor="h-proc" className="text-xs">Processo</Label>
          <Select value={proc} onValueChange={setProc}><SelectTrigger id="h-proc" size="sm" className="w-56"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todos</SelectItem>{(processes ?? []).map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1"><Label htmlFor="h-status" className="text-xs">Situação</Label>
          <Select value={status} onValueChange={setStatus}><SelectTrigger id="h-status" size="sm" className="w-56"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todas</SelectItem><SelectItem value="running">Em andamento</SelectItem>
              <SelectItem value="attention">Precisam de atenção</SelectItem><SelectItem value="verified">Verificadas</SelectItem></SelectContent></Select></div>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader><TableRow><TableHead>Quando</TableHead><TableHead>Processo ou rotina</TableHead><TableHead>Estação</TableHead>
            <TableHead>Situação</TableHead><TableHead>Término</TableHead><TableHead>Por</TableHead></TableRow></TableHeader>
          <TableBody>
            {!shown.length && <TableRow><TableCell colSpan={6} className="text-muted-foreground">Nenhuma execução.</TableCell></TableRow>}
            {shown.map((e) => (
              <TableRow key={e.id} className="cursor-pointer" onClick={() => setOpen(e.id)} tabIndex={0} onKeyDown={(k) => { if (k.key === "Enter" || k.key === " ") { k.preventDefault(); setOpen(e.id); } }}>
                <TableCell>{when(e.created_at)}</TableCell><TableCell className="font-medium">{title(e)}</TableCell>
                <TableCell>{e.station_name}</TableCell><TableCell><ExecutionBadge e={e} /></TableCell>
                <TableCell className="text-muted-foreground">{e.end_reason ? END_REASON[e.end_reason] ?? e.end_reason : "—"}</TableCell><TableCell>{e.requested_by}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
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
