// Empresa: first page after signing in. Composition inspired by the reference
// dashboard (timeline + list, two chart cards, resources and performance, then
// a filterable table), rebuilt with the project's components. Every number is a
// fixture of this page and the badge stays visible; no billing of any kind.
import { useMemo, useState } from "react";
import { ArrowUp, BarChart3, Boxes, ClipboardList, FileText, Truck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ACTIVITIES, PERFORMANCE, PROJECTS, RATE, RESOURCES, TIMELINE, WEEK, type ActivityStatus } from "@/data/empresa-demo";
import { cn } from "@/lib/utils";

const PROJECT_ICONS = [FileText, ClipboardList, Boxes, Truck];
const PAGE_SIZE = 5;

export function EmpresaPage() {
  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-10 flex justify-end">
        <Badge className="border-transparent bg-warn-soft text-warn" title="Números fictícios desta página. Não vêm de execuções reais.">Dados demonstrativos</Badge>
      </div>
      <Card className="gap-0 py-0 shadow-none">
        <div className="grid lg:grid-cols-3">
          <div className="p-6 lg:col-span-2 lg:border-r"><TimelineChart /></div>
          <div className="border-t p-6 lg:border-t-0"><ProjectList /></div>
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <WeekCard />
        <RateCard />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <ResourcesCard />
        <PerformanceCard />
      </div>
      <ActivityTable />
    </div>
  );
}

function TimelineChart() {
  const span = TIMELINE.months.length;
  return (
    <>
      <h2 className="font-semibold">Linha do tempo</h2>
      <p className="mb-5 text-sm text-muted-foreground">{TIMELINE.total} atividades concluídas</p>
      <div className="overflow-x-auto">
        <div className="min-w-[32rem]" role="img" aria-label={`Linha do tempo demonstrativa com ${TIMELINE.rows.length} áreas`}>
          {TIMELINE.rows.map((r) => (
            <div key={r.who} className="grid h-11 grid-cols-[6.5rem_1fr] items-center gap-2">
              <span className="truncate text-xs text-muted-foreground">{r.who}</span>
              <div className="relative h-full border-l border-dashed">
                <div className={cn("absolute top-1/2 h-5 -translate-y-1/2 rounded-full", r.tone)}
                  style={{ left: `${(r.start / span) * 100}%`, width: `${((r.end - r.start) / span) * 100}%` }} />
              </div>
            </div>
          ))}
          <div className="grid grid-cols-[6.5rem_1fr] gap-2 pt-2">
            <span />
            <div className="grid text-xs text-muted-foreground" style={{ gridTemplateColumns: `repeat(${span}, 1fr)` }}>
              {TIMELINE.months.map((m) => <span key={m}>{m}</span>)}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function ProjectList() {
  return (
    <>
      <h2 className="font-semibold">Frentes de trabalho</h2>
      <p className="mb-5 text-sm text-muted-foreground">{PROJECTS.length} em andamento</p>
      <ul className="space-y-4">
        {PROJECTS.map((p, i) => {
          const Icon = PROJECT_ICONS[i % PROJECT_ICONS.length];
          return (
            <li key={p.name} className="flex items-center gap-3">
              <span className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-lg", p.tone)}><Icon className="size-4" /></span>
              <span className="min-w-0"><span className="block text-sm font-medium">{p.name}</span>
                <span className="block text-xs text-muted-foreground">{p.done} de {p.total} atividades</span></span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function WeekCard() {
  const max = Math.max(...WEEK.map((d) => d.value));
  return (
    <Card className="shadow-none">
      <CardHeader><CardTitle>Visão semanal</CardTitle><CardDescription>Atividades por dia</CardDescription></CardHeader>
      <CardContent>
        <div className="flex h-44 items-end gap-3" role="img" aria-label={`Atividades por dia: ${WEEK.map((d) => `${d.day} ${d.value}`).join(", ")}`}>
          {WEEK.map((d) => (
            <div key={d.day} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
              <span className="text-xs tabular-nums text-muted-foreground">{d.value}</span>
              <div className="w-full rounded-t-md bg-primary" style={{ height: `${(d.value / max) * 78}%` }} />
              <span className="text-xs text-muted-foreground">{d.day}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RateCard() {
  const lo = Math.min(...RATE.spark), hi = Math.max(...RATE.spark);
  const points = RATE.spark.map((v, i) => `${(i / (RATE.spark.length - 1)) * 300},${70 - ((v - lo) / (hi - lo || 1)) * 60}`).join(" ");
  return (
    <Card className="shadow-none">
      <CardHeader><CardTitle>Taxa de conclusão</CardTitle><CardDescription>Comparada ao mês anterior</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <p className="flex items-baseline gap-2"><span className="text-4xl font-semibold tabular-nums">{RATE.value.toLocaleString("pt-BR")}%</span>
          <span className="inline-flex items-center text-sm text-ok"><ArrowUp className="size-3.5" />{RATE.delta.toLocaleString("pt-BR")}%</span></p>
        <svg viewBox="0 0 300 80" className="h-24 w-full" role="img" aria-label="Minigráfico demonstrativo em alta" preserveAspectRatio="none">
          <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.5" className="text-primary" vectorEffect="non-scaling-stroke" />
        </svg>
      </CardContent>
    </Card>
  );
}

function ResourcesCard() {
  return (
    <Card className="shadow-none">
      <CardHeader><CardTitle>Recursos</CardTitle><CardDescription>Uso de armazenamento e estações</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {RESOURCES.map((r) => (
          <div key={r.name} className="space-y-1">
            <p className="flex justify-between gap-2 text-sm"><span>{r.name}</span><span className="text-muted-foreground">{r.detail}</span></p>
            <Progress value={r.used} aria-label={r.name} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function PerformanceCard() {
  const tabs = Object.keys(PERFORMANCE);
  const [tab, setTab] = useState(tabs[0]);
  return (
    <Card className="shadow-none lg:col-span-2">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <div><CardTitle className="mb-1.5"><span className="inline-flex items-center gap-2"><BarChart3 className="size-4" />Desempenho da empresa</span></CardTitle><CardDescription>Resultado no período</CardDescription></div>
        <div role="tablist" aria-label="Período" className="flex gap-1 rounded-lg bg-muted p-1">
          {tabs.map((t) => (
            <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={cn("rounded-md px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring", tab === t ? "bg-card font-medium shadow-xs" : "text-muted-foreground")}>{t}</button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        {PERFORMANCE[tab].map((m) => (
          <div key={m.label} className="rounded-lg border p-4">
            <p className="text-sm text-muted-foreground">{m.label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{m.value}</p>
            <p className="text-xs text-ok">{m.delta}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

const STATUS_CLASS: Record<ActivityStatus, string> = {
  "Concluída": "bg-ok-soft text-ok", "Em andamento": "bg-info-soft text-info", "Atenção": "bg-warn-soft text-warn",
};

function ActivityTable() {
  const [team, setTeam] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(0);
  const teams = useMemo(() => [...new Set(ACTIVITIES.map((a) => a.team))], []);
  const shown = ACTIVITIES.filter((a) => (team === "all" || a.team === team) && (status === "all" || a.status === status));
  const pages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  return (
    <Card className="shadow-none">
      <CardHeader><CardTitle>Atividades da equipe</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-2" role="group" aria-label="Filtros">
          <div className="space-y-1"><Label htmlFor="e-team" className="text-xs">Área</Label>
            <Select value={team} onValueChange={(v) => { setTeam(v); setPage(0); }}><SelectTrigger id="e-team" size="sm" className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">Todas</SelectItem>{teams.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1"><Label htmlFor="e-status" className="text-xs">Situação</Label>
            <Select value={status} onValueChange={(v) => { setStatus(v); setPage(0); }}><SelectTrigger id="e-status" size="sm" className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">Todas</SelectItem>{Object.keys(STATUS_CLASS).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
        </div>
        <div className="overflow-x-auto rounded-md border"><Table>
          <TableHeader><TableRow><TableHead>Atividade</TableHead><TableHead>Área</TableHead><TableHead>Responsável</TableHead><TableHead>Quando</TableHead><TableHead>Situação</TableHead></TableRow></TableHeader>
          <TableBody>
            {!shown.length && <TableRow><TableCell colSpan={5} className="text-muted-foreground">Nenhuma atividade corresponde aos filtros.</TableCell></TableRow>}
            {shown.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE).map((a) => (
              <TableRow key={`${a.activity}-${a.when}`}><TableCell className="font-medium">{a.activity}</TableCell><TableCell>{a.team}</TableCell><TableCell>{a.owner}</TableCell>
                <TableCell>{a.when}</TableCell><TableCell><Badge variant="outline" className={cn("border-transparent", STATUS_CLASS[a.status])}>{a.status}</Badge></TableCell></TableRow>
            ))}
          </TableBody></Table></div>
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">Página {current + 1} de {pages}</span>
          <Button size="sm" variant="outline" disabled={current === 0} onClick={() => setPage(current - 1)}>Anterior</Button>
          <Button size="sm" variant="outline" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Próxima</Button>
        </div>
      </CardContent>
    </Card>
  );
}
