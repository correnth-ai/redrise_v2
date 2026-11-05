// Fluxos: follow executions and history. Every view (stats, grid, Kanban,
// timeline, log, feed, table) derives from the same execution records; the
// Kanban is read-only (no drag-and-drop, no manual verification).
import { useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Hourglass, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataTable, type DataColumn } from "@/components/data-table";
import { ErrorView } from "@/components/diagnostic";
import { ActivityFeed, activityOf, ExecutionBadge, ExecutionLog, ExecutionReports, StateBadge, Timeline } from "@/components/blocks";
import { JobsSection } from "@/features/legacy";
import { COLUMN_LABEL, column, END_REASON, executionLabel, needsAttention, title, type Column } from "@/data/status";
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

export const HISTORY_COLUMNS: DataColumn<Execution>[] = [
  { id: "when", header: "Quando", cell: (e) => when(e.created_at), sortValue: (e) => e.created_at },
  { id: "what", header: "Processo ou rotina", cell: (e) => <span className="font-medium">{title(e)}</span>, sortValue: title, searchText: title },
  { id: "station", header: "Estação", cell: (e) => e.station_name, sortValue: (e) => e.station_name, searchText: (e) => e.station_name },
  { id: "state", header: "Situação", cell: (e) => <ExecutionBadge e={e} />, sortValue: executionLabel, searchText: executionLabel },
  { id: "end", header: "Término", className: "text-muted-foreground", cell: (e) => (e.end_reason ? END_REASON[e.end_reason] ?? e.end_reason : "—"), sortValue: (e) => e.end_reason },
  { id: "by", header: "Por", cell: (e) => e.requested_by, sortValue: (e) => e.requested_by, searchText: (e) => e.requested_by },
];

const HISTORY_TABS = ["running", "waiting", "attention", "verified"];

export function HistoryPage({ focus }: { focus?: string }) {
  const { executions, processes, src } = useStore();
  const [open, setOpen] = useState<string | null>(focus && !HISTORY_TABS.includes(focus) ? focus : null);
  const sel = executions?.find((e) => e.id === open) ?? null;
  return (
    <div className="space-y-3">
      <DataTable label="Execuções" storageKey="processo-historico" rows={executions} columns={HISTORY_COLUMNS} rowKey={(e) => e.id} rowLabel={title}
        empty="Nenhuma execução." searchPlaceholder="Buscar processo, estação ou pessoa…" onRowOpen={(e) => setOpen(e.id)} initialTab={HISTORY_TABS.includes(focus ?? "") ? focus : "all"}
        tabs={[{ id: "all", label: "Todas", match: () => true }, { id: "running", label: "Em andamento", icon: Loader2, match: (e) => e.state === "running" },
          { id: "waiting", label: "Aguardando revisão", icon: Hourglass, match: (e) => e.state === "waiting_review" },
          { id: "attention", label: "Precisam de atenção", icon: CircleAlert, match: needsAttention }, { id: "verified", label: "Verificadas", icon: CheckCircle2, match: (e) => e.outcome === "verified" }]}
        filters={[{ id: "process", label: "Processo", options: (processes ?? []).map((p) => ({ value: String(p.id), label: p.name, match: (e: Execution) => e.process_id === p.id })) }]} />
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
