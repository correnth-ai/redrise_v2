// Processos: admin panel (stats-02 + access cards), table-04 grouped by
// process with table-02 row actions and filters, routine library, routine
// detail in a side sheet and process composition in dialog-11.
import { Fragment, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Eye, Pencil, Play, Plus, Trash2, Workflow } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ErrorView } from "@/components/diagnostic";
import { ExecutionBadge, StateBadge, Stats02 } from "@/components/blocks";
import { describeConfig } from "@/features/run-dialog";
import { END_REASON, needsAttention } from "@/data/status";
import type { Process, Routine } from "@/data/types";
import { useStore } from "@/state";
import { when } from "@/lib/utils";

const CATEGORY: Record<string, string> = { windows: "Windows", browser: "Navegador", mac: "Mac", linux: "Linux" };

const originLabel = (kind: string, c: Routine["config"]) => kind === "notepad_step" ? "Bloco de Notas" : c ? (c.origin === "site" ? "Site" : "HTML local") : "Legada";

function Loading({ what }: { what: string }) {
  return <p className="text-sm text-muted-foreground">Carregando {what}…</p>;
}

function Action({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={disabled ? 0 : -1}>
          <Button size="icon" variant="ghost" className="size-8" aria-label={label} onClick={onClick} disabled={disabled}>{children}</Button>
        </span>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

// ---------------------------------------------------------------- table-04 + table-02
export function ProcessTable({ compact = false }: { compact?: boolean }) {
  const { processes, routines, run, me } = useStore();
  const [filterProc, setFilterProc] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [compose, setCompose] = useState<Process | "new" | null>(null);
  const [detail, setDetail] = useState<Routine | null>(null);
  if (!processes) return <Loading what="processos" />;
  const shown = processes.filter((p) => (filterProc === "all" || String(p.id) === filterProc) && (filterStatus === "all" ||
    (filterStatus === "running" ? p.last_execution?.state === "running" : filterStatus === "attention" ?
      p.last_execution?.state === "finished" && p.last_execution.outcome !== "verified" : filterStatus === "never" ? !p.last_execution : true)));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2" role="group" aria-label="Filtros">
        <div className="space-y-1"><Label htmlFor="f-proc" className="text-xs">Processo</Label>
          <Select value={filterProc} onValueChange={setFilterProc}>
            <SelectTrigger id="f-proc" size="sm" className="w-52"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todos</SelectItem>{processes.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}</SelectContent>
          </Select></div>
        <div className="space-y-1"><Label htmlFor="f-status" className="text-xs">Última execução</Label>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger id="f-status" size="sm" className="w-52"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem><SelectItem value="running">Em andamento</SelectItem>
              <SelectItem value="attention">Precisam de atenção</SelectItem><SelectItem value="never">Nunca executados</SelectItem>
            </SelectContent>
          </Select></div>
        {(filterProc !== "all" || filterStatus !== "all") && <Button size="sm" variant="ghost" onClick={() => { setFilterProc("all"); setFilterStatus("all"); }}>Limpar filtros</Button>}
        {!compact && me.role === "admin" && <Button size="sm" className="ml-auto" onClick={() => setCompose("new")}><Plus /> Novo processo</Button>}
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Rotina</TableHead><TableHead>Origem</TableHead><TableHead>Continuação</TableHead><TableHead>Execução</TableHead><TableHead className="text-right">Ações</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {!shown.length && <TableRow><TableCell colSpan={5} className="text-muted-foreground">Nenhum processo corresponde aos filtros.</TableCell></TableRow>}
            {shown.map((p) => (
              <Fragment key={p.id}>
                <TableRow className="bg-muted/50 hover:bg-muted/50">
                  <TableCell colSpan={3} className="font-semibold">
                    {p.name} <span className="ml-2 font-normal text-muted-foreground">{p.items.length} rotina(s)</span>
                    {p.last_execution && <span className="ml-3 font-normal text-xs text-muted-foreground">última: {when(p.last_execution.created_at)}{p.last_execution.end_reason ? ` · ${END_REASON[p.last_execution.end_reason] ?? p.last_execution.end_reason}` : ""}</span>}
                  </TableCell>
                  <TableCell>{p.last_execution ? <ExecutionBadge e={{ state: p.last_execution.state, outcome: p.last_execution.outcome } as any} /> : <Badge variant="outline">Nunca executado</Badge>}</TableCell>
                  <TableCell className="text-right">
                    <Action label="Executar processo" onClick={() => run({ kind: "process", id: p.id })} disabled={!p.items.length}><Play /></Action>
                    {me.role === "admin" && !p.system_key && <Action label="Editar composição" onClick={() => setCompose(p)}><Pencil /></Action>}
                  </TableCell>
                </TableRow>
                {p.items.map((it) => {
                  const rt = routines?.find((r) => r.id === it.routine_id);
                  return (
                    <TableRow key={`${p.id}-${it.position}`}>
                      <TableCell className="pl-8">{it.position}. {it.routine_name}</TableCell>
                      <TableCell className="text-muted-foreground">{originLabel(it.kind, it.config)}</TableCell>
                      <TableCell>{it.position === p.items.length ? "Fim da sequência" : it.continue_next ? "Continua para a próxima" : "Encerra aqui"}</TableCell>
                      <TableCell>Pelo processo</TableCell>
                      <TableCell className="text-right">
                        {rt && <Action label="Ver detalhes" onClick={() => setDetail(rt)}><Eye /></Action>}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </Fragment>
            ))}
          </TableBody>
        </Table>
      </div>
      <ProcessComposer value={compose} onClose={() => setCompose(null)} />
      <RoutineSheet routine={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

// ---------------------------------------------------------------- routine library
export function RoutinesPage() {
  const { routines, processes, run, go, me } = useStore();
  const [detail, setDetail] = useState<Routine | null>(null);
  const [q, setQ] = useState("");
  // A linked routine, even as the only step, runs through its process.
  const linkOf = (id: number) => (processes ?? []).filter((p) => p.items.some((i) => i.routine_id === id));
  const [origin, setOrigin] = useState("all");
  if (!routines) return <Loading what="rotinas" />;
  const shown = routines.filter((r) => r.name.toLowerCase().includes(q.toLowerCase()) &&
    (origin === "all" || (origin === "legacy" ? r.kind !== "browser_open" : r.config?.origin === origin)));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1"><Label htmlFor="q-rt" className="text-xs">Buscar</Label><Input id="q-rt" className="h-8 w-56" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="space-y-1"><Label htmlFor="f-origin" className="text-xs">Tipo</Label>
          <Select value={origin} onValueChange={setOrigin}>
            <SelectTrigger id="f-origin" size="sm" className="w-48"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todas</SelectItem><SelectItem value="site">Navegar em site</SelectItem>
              <SelectItem value="html">Abrir HTML local</SelectItem><SelectItem value="legacy">Modelo ou gravação</SelectItem></SelectContent>
          </Select></div>
        {me.role === "admin" && <div className="ml-auto flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => go({ menu: "rotina", page: "modelos" })}>A partir de modelo</Button>
          <Button size="sm" variant="outline" onClick={() => go({ menu: "rotina", page: "gravacao" })}>Por gravação (avançado)</Button>
          <Button size="sm" onClick={() => go({ menu: "rotina", page: "nova" })}><Plus /> Nova rotina Browser</Button>
        </div>}
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader><TableRow><TableHead>Rotina</TableHead><TableHead>Tipo</TableHead><TableHead>Destino</TableHead><TableHead>Versão</TableHead><TableHead>Processo</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader>
          <TableBody>
            {!shown.length && <TableRow><TableCell colSpan={6} className="text-muted-foreground">Nenhuma rotina.</TableCell></TableRow>}
            {shown.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell>{r.kind === "notepad_step" ? "Bloco de Notas" : r.config ? (r.config.origin === "site" ? "Navegar em site" : "Abrir HTML local") : r.kind === "template" ? `Modelo ${r.template_id}` : "Gravação"}</TableCell>
                <TableCell className="max-w-64 truncate text-muted-foreground" title={r.kind === "browser_open" && r.config ? (r.config.url ?? r.config.path ?? "") : undefined}>{r.kind === "browser_open" && r.config ? (r.config.url ?? r.config.path) : CATEGORY[r.category] ?? r.category}</TableCell>
                <TableCell>v{r.version}</TableCell>
                <TableCell>{linkOf(r.id).length ? linkOf(r.id).map((p) => p.name).join(", ") : "Avulsa"}</TableCell>
                <TableCell className="text-right">
                  <Action label={linkOf(r.id).length ? "Executa pelo processo" : r.config ? "Executar rotina avulsa" : "Executar"} disabled={!!linkOf(r.id).length || (!!r.config && !r.config.isolated)}
                    onClick={() => (r.config ? run({ kind: "routine", id: r.id }) : go({ menu: "rotina", page: "executar-legada", id: r.id }))}><Play /></Action>
                  <Action label="Ver detalhes" onClick={() => setDetail(r)}><Eye /></Action>
                  {me.role === "admin" && r.kind === "browser_open" && <Action label="Editar" onClick={() => go({ menu: "rotina", page: "editar", id: r.id })}><Pencil /></Action>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <RoutineSheet routine={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

export function ProcessesPage() {
  const { processes, executions, go, run, error } = useStore();
  return (
    <div className="space-y-6">
      <ErrorView error={error} />
      <Stats02 stats={[
        { metric: "Processos cadastrados", value: processes?.length ?? null },
        { metric: "Execuções em andamento", value: executions?.filter((e) => e.state === "running").length ?? null, action: "Acompanhar", onOpen: () => go({ menu: "processo", page: "historico" }) },
        { metric: "Precisam de atenção", value: executions?.filter(needsAttention).length ?? null, hint: "Falha, incerta ou não verificada", action: "Ver ocorrências", onOpen: () => go({ menu: "processo", page: "historico", id: "attention" }) },
      ]} />
      <div className="flex justify-end"><Button onClick={() => run(null)}><Play /> Nova execução</Button></div>
      <ProcessTable />
    </div>
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
            {routine.config && <p>Execução: <b>{used.length ? "pelo processo" : routine.config.isolated ? "avulsa" : "só em processo (requer contexto)"}</b></p>}
            <div><p className="font-medium">Usada em</p>
              {used.length ? <ul className="list-disc pl-5">{used.map((p) => <li key={p.id}>{p.name}</li>)}</ul> : <p className="text-muted-foreground">Nenhum processo.</p>}
              {used.length > 1 && <p className="mt-1 text-xs text-muted-foreground">Alterações valem para todos esses processos na próxima execução.</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              {routine.config && !used.length && <Button size="sm" disabled={!routine.config.isolated} onClick={() => { onClose(); run({ kind: "routine", id: routine.id }); }}><Play /> Executar</Button>}
              {me.role === "admin" && routine.kind === "browser_open" && <Button size="sm" variant="outline" onClick={() => { onClose(); go({ menu: "rotina", page: "editar", id: routine.id }); }}><Pencil /> Editar</Button>}
            </div>
          </div>
        </>}
      </SheetContent>
    </Sheet>
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
  const available = (routines ?? []).filter((r) => r.kind === "browser_open");
  const nameOf = (id: number) => routines?.find((r) => r.id === id)?.name ?? `#${id}`;
  const move = (i: number, d: number) => setItems((xs) => { const ys = [...xs]; const [x] = ys.splice(i, 1); ys.splice(i + d, 0, x); return ys; });
  const valid = name.trim().length > 0 && items.length > 0;
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
                <p className="text-sm leading-6 text-muted-foreground">A execução sempre começa pela primeira rotina. Só um resultado verificado, com continuação marcada, chama a próxima.</p>
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
                    <SelectTrigger id="proc-add" className="w-full"><SelectValue placeholder={available.length ? "Selecione uma rotina" : "Cadastre uma rotina Browser primeiro"} /></SelectTrigger>
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
                      <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Mover para cima" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp /></Button>
                      <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Mover para baixo" disabled={i === items.length - 1} onClick={() => move(i, 1)}><ArrowDown /></Button>
                      <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Remover do processo" onClick={() => setItems((xs) => xs.filter((_, j) => j !== i))}><Trash2 /></Button>
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
