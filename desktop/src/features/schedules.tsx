// Scheduled processes (work order SCHEDULE-PROCESS-20261107). Administrators create, edit, pause, resume and
// delete; operators see the list. The next occurrence always comes from the Core, never from this screen's clock.
import { useEffect, useState } from "react";
import { Pause, Play, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorView } from "@/components/diagnostic";
import { IconAction } from "@/components/icon-action";
import type { Process, Schedule } from "@/data/types";
import { useAction } from "@/hooks/use-action";
import { useStore } from "@/state";

export const WEEKDAYS: [number, string][] = [[1, "Seg"], [2, "Ter"], [3, "Qua"], [4, "Qui"], [5, "Sex"], [6, "Sáb"], [7, "Dom"]];

/** Why an occurrence did not start, or why a schedule is paused (codes from the Core). */
export const SCHEDULE_REASON: Record<string, string> = {
  not_started: "Não iniciado por desconexão.",
  station_unavailable: "Estação indisponível no horário",
  previous_still_running: "Execução anterior ainda em andamento",
  process_unavailable: "Processo arquivado ou sem etapa 1",
  station_incompatible: "Estação incompatível com o processo",
  owner_not_allowed: "Quem agendou não é mais administrador ativo",
  core_stopped: "Servidor desligado no horário",
  paused_by_user: "Pausado",
  process_deleted: "Processo excluído",
};

const RUN_STATE: Record<string, string> = { started: "Iniciada", skipped: "Pulada", missed: "Perdida", expired: "Não iniciada" };

export const days = (w: number[]) => (w.length === 7 ? "Todos os dias" : WEEKDAYS.filter(([d]) => w.includes(d)).map(([, l]) => l).join(", "));
const hhmm = (h: number, m: number) => `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
const slot = (s: string | null) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)} ${s.slice(11, 16)}` : "—");
const localZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

/** Schedule dialog for one process: days, time and station; shows the next occurrence the Core computes. */
export function ScheduleDialog({ process, onClose }: { process: Process | null; onClose: () => void }) {
  const { src, stations } = useStore();
  const [weekdays, setWeekdays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [time, setTime] = useState("08:00");
  const [station, setStation] = useState<string>("");
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const save = useAction(setError);
  const active = (stations ?? []).filter((s) => !s.revoked);
  const [h, m] = time.split(":").map(Number);
  const input = process && station && weekdays.length && Number.isInteger(h) && Number.isInteger(m)
    ? { process_id: process.id, station_id: Number(station), weekdays, hour: h, minute: m, timezone: localZone() } : null;
  const key = JSON.stringify(input);
  useEffect(() => {
    if (process && !station && active.length) setStation(String(active[0].id));
  }, [process, station, active.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setNext(null);
    if (!input) return;
    let on = true;
    src.previewSchedule(input).then((p) => { if (on) { setNext(p.next_slot_local); setError(null); } }, (e) => { if (on) setError(e); });
    return () => { on = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = (d: number) => setWeekdays((w) => (w.includes(d) ? w.filter((x) => x !== d) : [...w, d].sort()));
  return (
    <Dialog open={process !== null} onOpenChange={(o) => { if (!o) { setError(null); onClose(); } }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Agendar {process?.name}</DialogTitle>
          <DialogDescription>O processo executa sozinho nos dias e no horário escolhidos, na estação escolhida. O computador servidor precisa estar ligado e com o RedRise aberto.</DialogDescription></DialogHeader>
        <fieldset className="space-y-2"><legend className="text-sm font-medium">Dias da semana</legend>
          <div className="flex flex-wrap gap-3">
            {WEEKDAYS.map(([d, l]) => (
              <label key={d} className="flex items-center gap-1.5 text-sm"><Checkbox checked={weekdays.includes(d)} onCheckedChange={() => toggle(d)} aria-label={l} />{l}</label>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1"><Label htmlFor="sch-time">Horário</Label>
            <Input id="sch-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} /></div>
          <div className="space-y-1"><Label htmlFor="sch-station">Estação</Label>
            <Select value={station} onValueChange={setStation}>
              <SelectTrigger id="sch-station"><SelectValue placeholder="Escolha a estação" /></SelectTrigger>
              <SelectContent>{active.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>)}</SelectContent>
            </Select></div>
        </div>
        <p className="text-sm" aria-live="polite">{!weekdays.length ? "Escolha ao menos um dia." : next ? `Próxima execução: ${slot(next)}` : "Calculando a próxima execução…"}</p>
        <ErrorView error={error} />
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button disabled={!input || !next || save.busy} onClick={() => save.run(async () => { await src.createSchedule(input!); onClose(); })}>
            {save.busy ? "Salvando…" : "Agendar"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** List of the team's schedules, read again on every change the Core announces. */
export function SchedulesSection() {
  const { src, me, changeTick } = useStore();
  const [rows, setRows] = useState<Schedule[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const act = useAction(setActionError);
  const [n, setN] = useState(0);
  const [doing, setDoing] = useState<string | null>(null); // "<id>:<action>" of the icon that is waiting for the Core
  const [remove, setRemove] = useState<Schedule | null>(null);
  useEffect(() => {
    let on = true;
    src.schedules().then((r) => { if (on) { setRows(r); setError(null); } }, (e) => { if (on) setError(e); });
    return () => { on = false; };
  }, [src, changeTick, n]);
  const admin = me.role === "admin";
  // The row changes only after the Core confirms; a failure keeps it and shows the diagnostic.
  const run = (key: string, fn: () => Promise<unknown>) => act.run(async () => {
    setDoing(key);
    try { setActionError(null); await fn(); setN((x) => x + 1); } finally { setDoing(null); }
  });
  return (
    <section aria-label="Agendamentos" className="space-y-2">
      <h3 className="text-sm font-semibold">Agendamentos</h3>
      <ErrorView error={error} />
      <ErrorView error={actionError} />
      {rows === null ? (error ? null : <p className="text-sm text-muted-foreground">Carregando agendamentos…</p>) : !rows.length
        ? <p className="text-sm text-muted-foreground">Nenhum processo agendado.{admin ? " Use “Agendar” na linha do processo." : ""}</p>
        : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Processo</TableHead><TableHead>Quando</TableHead><TableHead>Estação</TableHead><TableHead>Próxima</TableHead><TableHead>Última</TableHead>
                {admin && <TableHead className="text-right">Ações</TableHead>}
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.process_name}</TableCell>
                    <TableCell>{days(s.weekdays)} às {hhmm(s.hour, s.minute)}</TableCell>
                    <TableCell>{s.station_name}</TableCell>
                    <TableCell>{s.enabled ? slot(s.next_slot_local) : <span className="text-muted-foreground">{SCHEDULE_REASON[s.paused_reason ?? ""] ?? "Pausado"}</span>}</TableCell>
                    <TableCell>{s.last_state ? `${RUN_STATE[s.last_state] ?? s.last_state} (${slot(s.last_slot_local)})${s.last_reason ? ` · ${SCHEDULE_REASON[s.last_reason] ?? s.last_reason}` : ""}` : "—"}</TableCell>
                    {admin && <TableCell className="text-right whitespace-nowrap"><span className="inline-flex items-center justify-end gap-0.5">
                      <IconAction label={`${s.enabled ? "Pausar" : "Retomar"} agendamento de ${s.process_name}`} busy={doing === `${s.id}:toggle`} disabled={act.busy}
                        onClick={() => run(`${s.id}:toggle`, () => src.updateSchedule(s.id, { enabled: !s.enabled }))}>{s.enabled ? <Pause /> : <Play />}</IconAction>
                      <IconAction label={`Excluir agendamento de ${s.process_name}`} destructive disabled={act.busy}
                        onClick={() => { setActionError(null); setRemove(s); }}><Trash2 /></IconAction>
                    </span></TableCell>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      <RemoveSchedule schedule={remove} onClose={() => setRemove(null)} onConfirm={async (id) => { await src.deleteSchedule(id); setN((x) => x + 1); }} />
    </section>
  );
}

/** Deleting a schedule is a decision: the icon opens this confirmation, with words. Cancel changes nothing; it closes only
 *  after the Core confirms, a failure stays in it. Executions it already started stay in the history. */
function RemoveSchedule({ schedule, onClose, onConfirm }: { schedule: Schedule | null; onClose: () => void; onConfirm: (id: number) => Promise<void> }) {
  const [error, setError] = useState<unknown>(null);
  const action = useAction(setError);
  const cancel = () => { if (!action.busy) { setError(null); onClose(); } };
  return (
    <Dialog open={schedule !== null} onOpenChange={(o) => { if (!o) cancel(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Excluir agendamento</DialogTitle>
          <DialogDescription>{schedule ? `O agendamento de ${schedule.process_name} (${days(schedule.weekdays)} às ${hhmm(schedule.hour, schedule.minute)}, ${schedule.station_name}) deixa de executar. As execuções que ele já iniciou continuam no histórico.` : ""}</DialogDescription></DialogHeader>
        <ErrorView error={error} />
        <DialogFooter>
          <Button variant="ghost" disabled={action.busy} onClick={cancel}>Cancelar</Button>
          <Button variant="destructive" disabled={action.busy} onClick={() => action.run(async () => { setError(null); await onConfirm(schedule!.id); onClose(); })}>
            {action.busy ? "Excluindo…" : "Excluir agendamento"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Bell text for a schedule notification. */
export function scheduleNote(state: string | null, reason: string | null): string {
  if (state === "expired") return SCHEDULE_REASON.not_started.replace(/\.$/, "");
  if (state === "missed") return "Agendamento perdido: servidor desligado no horário";
  return `Agendamento ${reason === "owner_not_allowed" || reason === "process_unavailable" ? "pausado" : "pulado"}: ${(SCHEDULE_REASON[reason ?? ""] ?? reason ?? "").toLowerCase()}`;
}
