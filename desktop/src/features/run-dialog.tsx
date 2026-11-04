// Shared execution use case (M06/G47): Processos and Fluxos open this same
// dialog. Registered values are shown, never asked again (G26). One request
// id per dialog: a repeated click or a retry after a lost answer reaches the
// same execution on the Core (idempotent), never a second one.
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorView } from "@/components/diagnostic";
import { useStore, type RunTarget } from "@/state";
import type { BrowserConfig } from "@/data/types";

export function describeConfig(c: BrowserConfig | null, browserName?: (id: string) => string): string {
  if (!c) return "Rotina legada (modelo/gravação)";
  if ("step" in c) return "Bloco de Notas, pela interface";
  return c.origin === "site" ? `Site ${c.url} · ${browserName ? browserName(c.browser ?? "") : c.browser}` : `HTML local ${c.path}`;
}

export function RunDialog({ open, target, onClose }: { open: boolean; target: RunTarget; onClose: () => void }) {
  const { src, processes, routines, stations, go, reload } = useStore();
  const [pick, setPick] = useState<string>("");
  const [station, setStation] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());

  useEffect(() => { setPick(target ? `${target.kind}:${target.id}` : ""); setError(null); setRequestId(crypto.randomUUID()); }, [target, open]);

  const eligible = useMemo(() => [
    ...(processes ?? []).filter((p) => p.items.length).map((p) => ({ key: `process:${p.id}`, label: `Processo · ${p.name}` })),
    ...(routines ?? []).filter((r) => r.kind === "browser_open" && r.config?.isolated && !(processes ?? []).some((p) => p.items.some((i) => i.routine_id === r.id))).map((r) => ({ key: `routine:${r.id}`, label: `Rotina avulsa · ${r.name}` })),
  ], [processes, routines]);
  const [kind, idStr] = pick.split(":");
  const id = Number(idStr);
  const proc = kind === "process" ? processes?.find((p) => p.id === id) : undefined;
  const routine = kind === "routine" ? routines?.find((r) => r.id === id) : undefined;
  const categories = proc?.items.some((i) => i.kind === "notepad_step") ? ["windows"] : ["browser"];
  const compatible = (stations ?? []).filter((s) => !s.revoked && categories.every((c) => s.categories.includes(c)));
  useEffect(() => { if (!station && compatible.length) setStation(String(compatible[0].id)); }, [compatible, station]);
  const browserName = (bid: string) => compatible.flatMap((s) => s.browsers ?? []).find((b) => b.id === bid)?.name ?? bid;
  const blocked = routine && !routine.config?.isolated;

  async function confirm() {
    if (busy || !station || (!proc && !routine)) return;
    setBusy(true); setError(null);
    try {
      const e = await src.startExecution({ request_id: requestId, station_id: Number(station),
        ...(proc ? { process_id: proc.id } : { routine_id: routine!.id }) });
      await reload(); // idle polling is slow: show the new execution at once
      onClose();
      go({ menu: "processo", page: "historico", id: e.id });
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  const items = proc ? proc.items : routine ? [{ position: 1, routine_name: routine.name, config: routine.config, continue_next: false }] : [];
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Executar</DialogTitle>
          <DialogDescription>Confira o alvo e os valores cadastrados. Nada é executado até você confirmar.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="rr-run-target">Processo ou rotina</Label>
            <Select value={pick} onValueChange={(v) => { setPick(v); setRequestId(crypto.randomUUID()); }}>
              <SelectTrigger id="rr-run-target" className="w-full"><SelectValue placeholder="Selecione o que executar" /></SelectTrigger>
              <SelectContent>{eligible.map((o) => <SelectItem key={o.key} value={o.key}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          {items.length > 0 && (
            <ol className="space-y-1 rounded-md border p-3 text-sm">
              {items.map((it) => (
                <li key={it.position}><b>{it.position}. {it.routine_name}</b>
                  <span className="text-muted-foreground"> — {describeConfig(it.config, browserName)}{proc ? (it.continue_next ? " · continua" : " · encerra aqui") : ""}</span></li>
              ))}
            </ol>
          )}
          {blocked && <p className="text-sm text-destructive">Esta rotina não pode ser executada isoladamente.</p>}
          <div className="space-y-2">
            <Label htmlFor="rr-run-station">Estação</Label>
            {compatible.length ? (
              <Select value={station} onValueChange={(v) => { setStation(v); setRequestId(crypto.randomUUID()); }}>
                <SelectTrigger id="rr-run-station" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{compatible.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>{s.name}{s.online ? "" : " (offline)"}{s.session_state && s.session_state !== "ready" ? " — sessão indisponível" : ""}</SelectItem>
                ))}</SelectContent>
              </Select>
            ) : <p className="text-sm text-muted-foreground">Nenhuma estação compatível.</p>}
          </div>
          <ErrorView error={error} />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Voltar</Button>
          <Button onClick={confirm} disabled={busy || !station || (!proc && !routine) || !!blocked}>{busy ? "Enviando…" : "Confirmar execução"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
