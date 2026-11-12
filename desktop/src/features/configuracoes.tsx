// Configuração: team and profile, station inventory and remembered stations,
// app/environment. Storage (stats-13) shows measured bytes, separate from counts.
import { useEffect, useState } from "react";
import { Ban, Plus, Trash2, UserCheck, UserX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DiagnosticBox, ErrorView } from "@/components/diagnostic";
import { IconAction } from "@/components/icon-action";
import { Stats02, Stats13 } from "@/components/blocks";
import type { Station, Storage } from "@/data/types";
import { api, call } from "@/lib/api";
import { tv } from "@/lib/locale";
import { useAction } from "@/hooks/use-action";
import { useStore } from "@/state";

function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): { data: T | null; error: unknown; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let alive = true;
    fn().then((d) => { if (alive) { setData(d); setError(null); } }).catch((e) => { if (alive) setError(e); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { data, error, reload: () => setN((x) => x + 1) };
}

export function StorageCard() {
  const { src } = useStore();
  const { data, error } = useAsync<Storage>(() => src.storage(), [src]);
  if (error) return <ErrorView error={error} />;
  if (!data) return <p className="text-sm text-muted-foreground">Medindo espaço…</p>;
  return <Stats13 capacity={src.mode === "demo" ? 200_000_000 : null}
    segments={[
      { label: "Banco PostgreSQL", value: data.db_bytes, color: "bg-primary" },
      { label: "Dados desta estação", value: data.local?.data_bytes ?? null, color: "bg-info" },
      { label: "Logs", value: data.local?.logs_bytes ?? null, color: "bg-warn" },
    ]}
    counts={[{ label: "Rotinas", value: data.counts.routines }, { label: "Processos", value: data.counts.processes },
      { label: "Execuções", value: data.counts.executions }, { label: "Execuções técnicas (jobs)", value: data.counts.jobs }]} />;
}

// ---------------------------------------------------------------- Equipe
function ProfileCard() {
  const { me, go } = useStore();
  const p = useAsync<any>(() => api("GET", "/api/v1/identity/profile"));
  const d = p.data;
  return (
    <Card className="shadow-none"><CardHeader><CardTitle>Meu perfil</CardTitle><CardDescription>O nome é só apresentação: não muda o perfil de acesso.</CardDescription></CardHeader>
      <CardContent className="flex flex-wrap items-end justify-between gap-4 text-sm">
        <div className="min-w-0 space-y-1"><ErrorView error={p.error} />
          {d && <>
            <p>Nome completo: <b>{d.full_name ?? "—"}</b></p>
            <p>E-mail: {d.email ?? "—"}</p>
            <p>Usuário da equipe: {d.username} · {me.role === "admin" ? "Administrador" : "Operador"}</p>
          </>}
        </div>
        {/* Accounts are created only here, by an administrator (the Core checks it too). */}
        {me.role === "admin" && <Button size="sm" className="ml-auto" onClick={() => go({ menu: "configuracao", page: "nova-conta" })}><Plus /> Nova Conta</Button>}
      </CardContent></Card>
  );
}

export function TeamPage() {
  const { src, me } = useStore();
  if (src.mode === "demo") return <p className="text-sm text-muted-foreground">Gestão de equipe indisponível na demonstração.</p>;
  return <div className="space-y-6"><ProfileCard />{me.role === "admin" && <TeamAdmin />}</div>;
}

interface Account { id: number; username: string; display: string; full_name: string | null; email: string | null; role: string; active: boolean }

function TeamAdmin() {
  const { changeTick, me } = useStore();
  const users = useAsync<Account[]>(() => api("GET", "/api/v1/users"), [changeTick]);
  const [error, setError] = useState<unknown>(null);
  const [remove, setRemove] = useState<Account | null>(null);
  const [doing, setDoing] = useState<number | null>(null);
  const action = useAction(setError);
  // The row changes only after the Core confirms; a failure keeps it and shows the diagnostic.
  const act = (fn: () => Promise<unknown>) => action.run(async () => { setError(null); await fn(); users.reload(); });
  return (
    <div className="space-y-4">
      <ErrorView error={users.error ?? error} />
      <div className="overflow-x-auto rounded-md border"><Table>
        <TableHeader><TableRow><TableHead>Nome</TableHead><TableHead>E-mail</TableHead><TableHead>Usuário</TableHead><TableHead>Perfil</TableHead><TableHead>Estado</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader>
        <TableBody>{(users.data ?? []).map((u) => (
          <TableRow key={u.id}><TableCell className="font-medium">{u.full_name ?? u.display}</TableCell><TableCell>{u.email ?? "—"}</TableCell><TableCell>{u.username}</TableCell>
            <TableCell>{u.role === "admin" ? "Administrador" : "Operador"}</TableCell><TableCell>{u.active ? "Ativa" : "Inativa"}</TableCell>
            <TableCell className="text-right"><span className="inline-flex items-center justify-end gap-1">
              {/* The signed-in account (by the session's id, never by a name) cannot deactivate itself: the button stays
                  visible but unavailable, with the reason, and sends nothing (the Core refuses it too: ACCOUNT-SELF-DEACTIVATE). */}
              {u.id === me.id && u.active
                ? <span className="inline-flex items-center gap-2"><span id={`acc-${u.id}-why`} className="text-xs text-muted-foreground">Você não pode desativar sua própria conta</span>
                    <IconAction label="Desativar" disabled describedBy={`acc-${u.id}-why`} onClick={() => undefined}><UserX /></IconAction></span>
                : <IconAction label={u.active ? "Desativar" : "Reativar"} busy={action.busy && doing === u.id} disabled={action.busy}
                    onClick={() => { setDoing(u.id); void act(() => api("PATCH", `/api/v1/users/${u.id}`, { active: !u.active })); }}>{u.active ? <UserX /> : <UserCheck />}</IconAction>}
              {!u.active && <IconAction label="Excluir conta" disabled={action.busy} onClick={() => { setError(null); setRemove(u); }}><Trash2 /></IconAction>}
            </span></TableCell></TableRow>
        ))}</TableBody></Table></div>
      <ConfirmDelete open={remove !== null} title="Excluir conta" confirm="Excluir conta"
        description={remove ? `A conta ${remove.full_name ?? remove.display} (${remove.email ?? remove.username}) é apagada e não pode ser reativada: o e-mail e a senha são removidos e o e-mail fica livre para uma conta nova. O nome continua só no histórico.` : ""}
        onCancel={() => setRemove(null)} onConfirm={async () => { await api("DELETE", `/api/v1/users/${remove!.id}`); setRemove(null); users.reload(); }} />
    </div>
  );
}

/** Simple confirmation: Cancel changes nothing; the dialog closes only after the Core confirms, a failure stays in it. */
function ConfirmDelete({ open, title, description, confirm, busyLabel = "Excluindo…", onCancel, onConfirm }: { open: boolean; title: string; description: string;
  confirm: string; busyLabel?: string; onCancel: () => void; onConfirm: () => Promise<void> }) {
  const [error, setError] = useState<unknown>(null);
  const action = useAction(setError);
  const cancel = () => { if (!action.busy) { setError(null); onCancel(); } };
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) cancel(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader>
        <ErrorView error={error} />
        <DialogFooter>
          <Button variant="ghost" disabled={action.busy} onClick={cancel}>Cancelar</Button>
          <Button variant="destructive" disabled={action.busy} onClick={() => action.run(async () => { setError(null); await onConfirm(); })}>{action.busy ? busyLabel : confirm}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Estação
/** The screen reads the stations again this often while visible: "offline" comes from the absence of a heartbeat,
 * which announces nothing, so Online -> Offline shows at most ONLINE_S (Core) + this after the last signal. */
export const STATIONS_POLL_MS = 10_000;

function useStations(): { stations: Station[] | null; error: unknown; reload: () => Promise<void> } {
  const { src, changeTick } = useStore();
  const [stations, setStations] = useState<Station[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let alive = true;
    let t = 0;
    const load = async () => {
      window.clearTimeout(t);
      if (document.visibilityState === "visible") {
        try { const s = await src.stations(); if (alive) { setStations(s); setError(null); } } catch (e) { if (alive) setError(e); }
      }
      if (alive) t = window.setTimeout(load, STATIONS_POLL_MS);
    };
    void load();
    document.addEventListener("visibilitychange", load);
    return () => { alive = false; window.clearTimeout(t); document.removeEventListener("visibilitychange", load); };
  }, [src, changeTick, n]);
  return { stations, error, reload: async () => setN((x) => x + 1) };
}

const readiness = (s: Station) => s.revoked ? "revogada" : !s.online ? "aguardando conexão" : s.session_state === "ready" ? "pronta" : `aguardando: ${tv(s.session_reason) || s.session_state}`;

export function StationsPage() {
  const { me, reload: reloadStore, src, go } = useStore();
  const { stations, error: readError, reload } = useStations();
  const [armed, setArmed] = useState<number | null>(null);
  const [remove, setRemove] = useState<Station | null>(null);
  const [error, setError] = useState<unknown>(null);
  const revoke = useAction(setError);
  if (!stations) return readError ? <ErrorView error={readError} /> : <p className="text-sm text-muted-foreground">Carregando estações…</p>;
  const unknown = !!readError; // the last read failed: what is shown may be old, so connectivity is not claimed
  const manage = me.role === "admin" && src.mode === "real";
  const after = async () => { await reload(); await reloadStore(); };
  return (
    <div className="space-y-6">
      <ErrorView error={readError} />
      <ErrorView error={error} />
      <Stats02 stats={[
        { metric: "Estações", value: stations.filter((s) => !s.revoked).length },
        { metric: "Estações prontas", value: unknown ? "—" : stations.filter((s) => !s.revoked && s.online && s.session_state === "ready").length },
        { metric: "Navegadores detectados", value: new Set(stations.flatMap((s) => (s.browsers ?? []).map((b) => b.id))).size, hint: "Detectado não significa homologado", action: "Nova rotina Browser", onOpen: () => go({ menu: "rotina", page: "nova" }) },
      ]} />
      <h2 className="font-semibold">Estações conectadas</h2>
      <p className="text-xs text-muted-foreground">Status é a conexão com o servidor (sinal nos últimos 45 s, atualizado a cada 10 s nesta tela). Estado é a autorização e a prontidão para executar: online não quer dizer pronta.</p>
      <div className="overflow-x-auto rounded-md border"><Table>
        <TableHeader><TableRow><TableHead>Estação</TableHead><TableHead>Papel</TableHead><TableHead>Sistema</TableHead><TableHead>Status</TableHead><TableHead>Estado</TableHead><TableHead>Navegadores detectados</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader>
        <TableBody>{stations.map((s) => (
          <TableRow key={s.id}>
            <TableCell className="font-medium">{s.name}{s.current && <Badge variant="outline" className="ml-2">Esta estação</Badge>}</TableCell>
            <TableCell>{s.is_host ? "servidor + estação" : "estação"}</TableCell>
            <TableCell>{s.platform ?? "—"}</TableCell>
            <TableCell>{unknown ? <Badge variant="outline">Desconhecido</Badge> : s.online
              ? <Badge variant="outline" className="border-transparent bg-ok-soft text-ok">Online</Badge> : <Badge variant="outline">Offline</Badge>}</TableCell>
            <TableCell>{readiness(s)}</TableCell>
            <TableCell className="text-xs">{s.browsers === null ? "não informado (executor anterior)" : s.browsers.length ? s.browsers.map((b) => `${b.name}${b.version ? " " + b.version : ""}${b.homologated ? "" : " · não homologado"}`).join("; ") : "nenhum"}</TableCell>
            <TableCell className="text-right">{manage && (s.current
              ? <span className="inline-flex items-center gap-2"><span id={`st-${s.id}-why`} className="text-xs text-muted-foreground">Em uso por esta sessão</span>
                  <IconAction label={s.revoked ? "Excluir estação" : "Revogar"} disabled describedBy={`st-${s.id}-why`} onClick={() => undefined}>{s.revoked ? <Trash2 /> : <Ban />}</IconAction></span>
              : !s.revoked
                ? <IconAction label="Revogar" destructive disabled={revoke.busy} onClick={() => { setError(null); setArmed(s.id); }}><Ban /></IconAction>
                : <IconAction label="Excluir estação" disabled={revoke.busy} onClick={() => { setError(null); setRemove(s); }}><Trash2 /></IconAction>)}</TableCell>
          </TableRow>
        ))}</TableBody></Table></div>
      <ConfirmDelete open={armed !== null} title="Revogar estação" confirm="Revogar" busyLabel="Revogando…"
        description={(() => { const st = stations.find((x) => x.id === armed); return st ? `A estação ${st.name} deixa de executar: execuções aguardando nela serão recusadas. Ela continua no inventário como revogada.` : ""; })()}
        onCancel={() => setArmed(null)} onConfirm={async () => { await api("DELETE", `/api/v1/stations/${armed}`); setArmed(null); await after(); }} />
      <ConfirmDelete open={remove !== null} title="Excluir estação" confirm="Excluir estação"
        description={remove ? `A estação ${remove.name} sai do inventário. As execuções e os agendamentos que a usaram continuam no histórico; agendamentos nela não executam.` : ""}
        onCancel={() => setRemove(null)} onConfirm={async () => { await api("POST", `/api/v1/stations/${remove!.id}/remove`); setRemove(null); await after(); }} />
    </div>
  );
}

// ---------------------------------------------------------------- Aplicativo
function About({ i }: { i: any }) {
  return (
    <div className="space-y-1 border-t pt-3">
      <p className="text-sm font-medium">Sobre</p>
      <p className="mono break-all">Aplicativo {i.desktop} · instalação {i.install_root}</p>
      <p className="mono break-all">Manifesto {i.install_manifest_sha256 ?? "—"}</p>
      <p className="mono break-all">Dados {i.data_root}</p>
    </div>
  );
}

export function AppPage() {
  const { src } = useStore();
  const info = useAsync<any>(() => (src.mode === "demo" ? Promise.resolve(null) : call("app_info")));
  const [host, setHost] = useState<any>(null);
  const [agentErr, setAgentErr] = useState<unknown>(null);
  const agent = useAction(setAgentErr);
  useEffect(() => { if (info.data?.host_configured) call("host_start").then(setHost).catch(() => setHost(null)); }, [info.data?.host_configured]);
  if (src.mode === "demo") return <p className="text-sm text-muted-foreground">Dados do aplicativo indisponíveis na demonstração.</p>;
  const i = info.data;
  if (!i) return <ErrorView error={info.error} />;
  const st = i.agent_status ?? {};
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="shadow-none"><CardHeader><CardTitle>Esta estação</CardTitle></CardHeader><CardContent className="space-y-1 text-sm">
        <p>Estação: {i.connection?.station_name ?? "—"} · executor {i.agent_running ? "ativo" : "parado"}</p>
        <p>Sessão do Windows: {st.session_state === "ready" ? "disponível" : (tv(st.session_reason) || st.session_state || "—")}</p>
        <p>Servidor da equipe: {st.core_reachable ? "conectado" : "sem conexão"}</p>
        {st.last_error && <DiagnosticBox d={st.last_error} />}
        {!i.agent_running && <Button className="mt-2" disabled={agent.busy} onClick={() => agent.run(async () => { setAgentErr(null); await call("agent_start"); info.reload(); })}>{agent.busy ? "Iniciando…" : "Iniciar executor"}</Button>}
        {!i.agent_running && <ErrorView error={agentErr} />}
      </CardContent></Card>
      {i.host_configured
        ? <Card className="shadow-none"><CardHeader><CardTitle>Servidor da equipe (este computador)</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
            <div><p>Código para conectar outras estações:</p><pre className="mt-2 rounded-md bg-muted p-2">{host?.join_code ?? "indisponível"}</pre></div>
            <About i={i} /></CardContent></Card>
        // A station-only install is not the server: the same data under its own title.
        : <Card className="shadow-none"><CardHeader><CardTitle>Sobre este aplicativo</CardTitle></CardHeader><CardContent className="space-y-1 text-sm">
            <p className="mono break-all">Aplicativo {i.desktop} · instalação {i.install_root}</p>
            <p className="mono break-all">Manifesto {i.install_manifest_sha256 ?? "—"}</p>
            <p className="mono break-all">Dados {i.data_root}</p></CardContent></Card>}
      <div className="lg:col-span-2"><StorageCard /></div>
    </div>
  );
}
