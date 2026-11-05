// Configuração: team and profile, station inventory and remembered stations,
// app/environment. Storage (stats-13) shows measured bytes, separate from counts.
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DiagnosticBox, ErrorView } from "@/components/diagnostic";
import { Stats02, Stats13 } from "@/components/blocks";
import type { Storage } from "@/data/types";
import { api, call } from "@/lib/api";
import { tv } from "@/lib/locale";
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

function ProfileCard() {
  const { me } = useStore();
  const p = useAsync<any>(() => api("GET", "/api/v1/identity/profile"));
  const d = p.data;
  return (
    <Card className="shadow-none"><CardHeader><CardTitle>Meu perfil</CardTitle><CardDescription>O nome é só apresentação: não muda o perfil de acesso.</CardDescription></CardHeader>
      <CardContent className="space-y-1 text-sm"><ErrorView error={p.error} />
        {d && <>
          <p>Nome completo: <b>{d.full_name ?? "—"}</b></p>
          <p>E-mail: {d.email ?? "—"}</p>
          <p>Usuário da equipe: {d.username} · {me.role === "admin" ? "Administrador" : "Operador"}</p>
        </>}
      </CardContent></Card>
  );
}

export function TeamPage() {
  const { src, me } = useStore();
  if (src.mode === "demo") return <p className="text-sm text-muted-foreground">Gestão de equipe indisponível na demonstração.</p>;
  return <div className="space-y-6"><ProfileCard />{me.role === "admin" && <TeamAdmin />}</div>;
}

function TeamAdmin() {
  const { src, changeTick } = useStore();
  const users = useAsync<any[]>(() => (src.mode === "demo" ? Promise.resolve([]) : api("GET", "/api/v1/users")), [changeTick]);
  const [form, setForm] = useState({ username: "", display: "", password: "", role: "operator" });
  const [error, setError] = useState<unknown>(null);
  async function act(fn: () => Promise<unknown>) { setError(null); try { await fn(); users.reload(); } catch (e) { setError(e); } }
  return (
    <div className="space-y-4">
      <ErrorView error={users.error ?? error} />
      <div className="overflow-x-auto rounded-md border"><Table>
        <TableHeader><TableRow><TableHead>Usuário</TableHead><TableHead>Nome</TableHead><TableHead>E-mail</TableHead><TableHead>Perfil</TableHead><TableHead>Ativo</TableHead><TableHead /></TableRow></TableHeader>
        <TableBody>{(users.data ?? []).map((u) => (
          <TableRow key={u.id}><TableCell>{u.username}</TableCell><TableCell>{u.display}</TableCell><TableCell>{u.email ?? "—"}</TableCell>
            <TableCell>{u.role === "admin" ? "Administrador" : "Operador"}</TableCell><TableCell>{u.active ? "sim" : "não"}</TableCell>
            <TableCell className="text-right"><Button size="sm" variant="outline" onClick={() => act(() => api("PATCH", `/api/v1/users/${u.id}`, { active: !u.active }))}>{u.active ? "Desativar" : "Reativar"}</Button></TableCell></TableRow>
        ))}</TableBody></Table></div>
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); void act(() => api("POST", "/api/v1/users", form)); }}>
        <div className="space-y-1"><Label htmlFor="u-user">Usuário</Label><Input id="u-user" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="u-name">Nome</Label><Input id="u-name" value={form.display} onChange={(e) => setForm({ ...form, display: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="u-pw">Senha (mín. 8)</Label><Input id="u-pw" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="u-role">Perfil</Label>
          <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}><SelectTrigger id="u-role" className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="operator">Operador</SelectItem><SelectItem value="admin">Administrador</SelectItem></SelectContent></Select></div>
        <Button type="submit">Adicionar</Button>
      </form>
    </div>
  );
}

export function StationsPage() {
  const { stations, me, reload, src, go } = useStore();
  const [armed, setArmed] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  if (!stations) return <p className="text-sm text-muted-foreground">Carregando estações…</p>;
  return (
    <div className="space-y-6">
      <ErrorView error={error} />
      <Stats02 stats={[
        { metric: "Estações", value: stations.filter((s) => !s.revoked).length },
        { metric: "Estações prontas", value: stations.filter((s) => !s.revoked && s.online && s.session_state === "ready").length },
        { metric: "Navegadores detectados", value: new Set(stations.flatMap((s) => (s.browsers ?? []).map((b) => b.id))).size, hint: "Detectado não significa homologado", action: "Nova rotina Browser", onOpen: () => go({ menu: "rotina", page: "nova" }) },
      ]} />
      <h2 className="font-semibold">Estações conectadas</h2>
      <div className="overflow-x-auto rounded-md border"><Table>
        <TableHeader><TableRow><TableHead>Estação</TableHead><TableHead>Papel</TableHead><TableHead>Sistema</TableHead><TableHead>Estado</TableHead><TableHead>Navegadores detectados</TableHead><TableHead /></TableRow></TableHeader>
        <TableBody>{stations.map((s) => (
          <TableRow key={s.id}>
            <TableCell className="font-medium">{s.name}</TableCell><TableCell>{s.is_host ? "servidor + estação" : "estação"}</TableCell>
            <TableCell>{s.platform ?? "—"}</TableCell>
            <TableCell>{s.revoked ? "revogada" : s.online ? (s.session_state === "ready" ? "pronta" : `aguardando: ${tv(s.session_reason) || s.session_state}`) : "offline"}</TableCell>
            <TableCell className="text-xs">{s.browsers === null ? "não informado (executor anterior)" : s.browsers.length ? s.browsers.map((b) => `${b.name}${b.version ? " " + b.version : ""}${b.homologated ? "" : " · não homologado"}`).join("; ") : "nenhum"}</TableCell>
            <TableCell className="text-right">{!s.revoked && me.role === "admin" && src.mode === "real" && (
              <Button size="sm" variant={armed === s.id ? "destructive" : "outline"} onClick={async () => {
                if (armed !== s.id) { setArmed(s.id); return; }
                try { await api("DELETE", `/api/v1/stations/${s.id}`); setArmed(null); await reload(); } catch (e) { setError(e); }
              }}>{armed === s.id ? "Confirmar: execuções aguardando nela serão recusadas" : "Revogar"}</Button>)}</TableCell>
          </TableRow>
        ))}</TableBody></Table></div>
    </div>
  );
}

export function AppPage() {
  const { src } = useStore();
  const info = useAsync<any>(() => (src.mode === "demo" ? Promise.resolve(null) : call("app_info")));
  const [host, setHost] = useState<any>(null);
  const [burl, setBurl] = useState("https://mail.google.com/");
  const [err, setErr] = useState<unknown>(null);
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
        {!i.agent_running && <Button className="mt-2" onClick={async () => { await call("agent_start"); info.reload(); }}>Iniciar executor</Button>}
      </CardContent></Card>
      {i.host_configured && <Card className="shadow-none"><CardHeader><CardTitle>Servidor da equipe (este computador)</CardTitle></CardHeader><CardContent className="text-sm">
        <p>Código para conectar outras estações:</p><pre className="mt-2 rounded-md bg-muted p-2">{host?.join_code ?? "indisponível"}</pre></CardContent></Card>}
      <Card className="shadow-none"><CardHeader><CardTitle>Navegador do RedRise</CardTitle>
        <CardDescription>Abra o navegador privado usado pelas rotinas gravadas para entrar nas suas contas. Você digita a senha; o RedRise não grava nem digita nada nesta janela.</CardDescription></CardHeader>
        <CardContent className="space-y-2"><div className="flex gap-2"><Input aria-label="Endereço" value={burl} onChange={(e) => setBurl(e.target.value)} />
          <Button onClick={async () => { setErr(null); try { await call("browser_open", { url: burl }); } catch (e) { setErr(e); } }}>Abrir</Button></div><ErrorView error={err} /></CardContent></Card>
      <Card className="shadow-none"><CardHeader><CardTitle>Sobre</CardTitle></CardHeader><CardContent className="space-y-1">
        <p className="mono">Aplicativo {i.desktop} · instalação {i.install_root}</p><p className="mono">Manifesto {i.install_manifest_sha256 ?? "—"}</p><p className="mono">Dados {i.data_root}</p></CardContent></Card>
      <div className="lg:col-span-2"><StorageCard /></div>
    </div>
  );
}
