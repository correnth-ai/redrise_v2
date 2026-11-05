// Existing capabilities preserved in the new UI (no new Excel options):
// routine from installed template, routine by recording (advanced), the
// run form of template/recorded routines (POST /jobs, idempotent request id)
// and the technical job history with detail and Cancel.
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DiagnosticBox, ErrorView } from "@/components/diagnostic";
import { StateBadge } from "@/components/blocks";
import { JOB_STATE } from "@/data/status";
import { api, AppError, call, type Diagnostic } from "@/lib/api";
import { tv } from "@/lib/locale";
import { useStore } from "@/state";
import { ACTIVE_POLL_MS, IDLE_POLL_MS } from "@/state";
import { when } from "@/lib/utils";

const CATEGORY: Record<string, string> = { browser: "Browser", windows: "Windows", mac: "Mac", linux: "Linux" };
const INPUT_LABEL: Record<string, string> = {
  output_path: "Arquivo de saída (caminho completo)", input_path: "Planilha de entrada (caminho completo)", cliente: "Cliente", valor: "Valor do pedido",
};
const inputLabel = (n: string) => INPUT_LABEL[n] ?? n;

function DemoUnavailable() {
  return <p className="text-sm text-muted-foreground">Indisponível na demonstração: depende do executor local e do servidor da equipe.</p>;
}

export function TemplatesPage() {
  const { src, go, reload } = useStore();
  const [templates, setT] = useState<any[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { if (src.mode === "real") api("GET", "/api/v1/templates").then(setT).catch(setError); }, [src]);
  if (src.mode === "demo") return <DemoUnavailable />;
  return (
    <div className="space-y-3"><ErrorView error={error} />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{(templates ?? []).map((t) => (
        <Card key={t.id} className="shadow-none"><CardHeader><CardTitle>{t.title}</CardTitle><CardDescription>{t.purpose}</CardDescription></CardHeader>
          <CardContent className="space-y-2"><p className="text-xs text-muted-foreground">{CATEGORY[t.category]} · versão {t.version}</p>
            <Label htmlFor={`tn-${t.id}`}>Nome da rotina</Label>
            <Input id={`tn-${t.id}`} maxLength={120} value={names[t.id] ?? t.title} onChange={(e) => setNames({ ...names, [t.id]: e.target.value })} />
            <Button onClick={async () => {
              const name = (names[t.id] ?? t.title).trim();
              if (!name) return;
              try { await api("POST", "/api/v1/routines", { name, category: t.category, version: { kind: "template", template_id: t.id } }); await reload(); go({ menu: "rotina", page: "lista" }); }
              catch (e) { setError(e); }
            }}>Usar este modelo</Button></CardContent></Card>
      ))}</div></div>
  );
}

/** Engine recording outcome -> diagnostic (texts mirror contracts/errors.json RECORDING-*). */
function recordingDiagnostic(state: string, reason?: string): Diagnostic {
  const empty = state === "empty";
  return {
    schema: "redrise.diagnostic/1", error_code: empty ? "RECORDING-EMPTY" : "RECORDING-INCOMPLETE",
    category: empty ? "precondition" : "unknown",
    what_happened: empty ? "The recording ended without any action recorded in the chosen application." : "The recording did not finish correctly and cannot become a routine.",
    completed: "The recording was closed; nothing was saved as a routine.", pending: "No routine was created.", effect_state: "none", retry: "after_fix",
    next_action: empty ? "Record again using the keyboard and mouse in the chosen application." : "Record again. If it persists, copy the diagnostic and send it to support.",
    details_summary: empty ? (reason ?? "") : `Recording state: ${state}${reason ? " (" + reason + ")" : ""}`,
    params: { reason: empty ? (reason ?? "") : `${state}${reason ? " (" + reason + ")" : ""}` },
    reported_by: "RR-UI", module_hints: ["RR-ENGINE-CAP"], diagnosis_status: "unconfirmed", boundary: null,
    correlation_id: Math.random().toString(16).slice(2, 18), version: {}, technical_details: { status: state, reason: reason ?? null }, cause: null,
  };
}

export function RecordingPage() {
  const { src, reload, go } = useStore();
  const [cat, setCat] = useState("windows");
  const [target, setTarget] = useState("excel.exe");
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("");
  const [recording, setRecording] = useState<string | null>(null);
  const [active, setActive] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [params, setParams] = useState([{ n: "", r: "text", l: "" }]);
  const [declare, setDeclare] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<unknown>(null);
  if (src.mode === "demo") return <DemoUnavailable />;
  const guard = async (fn: () => Promise<void>) => { setError(null); try { await fn(); } catch (e) { setError(e); } };
  return (
    <div className="max-w-3xl space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1"><Label>Categoria</Label><Select value={cat} onValueChange={setCat}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="windows">Windows</SelectItem><SelectItem value="browser">Browser</SelectItem></SelectContent></Select></div>
        <div className="space-y-1"><Label>Aplicativo (Windows)</Label><Select value={target} onValueChange={setTarget}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="excel.exe">Excel</SelectItem><SelectItem value="notepad.exe">Bloco de Notas</SelectItem></SelectContent></Select></div>
        <div className="space-y-1"><Label htmlFor="rec-url">Endereço (Browser)</Label><Input id="rec-url" placeholder="https://… ou file:///…" value={url} onChange={(e) => setUrl(e.target.value)} /></div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => guard(async () => {
          const out = await call("runner_local", { args: ["excel-new"] });
          if (out.result.status === "ready") setStatus("Nova planilha do Excel aberta e pronta.");
          else if (out.result.diagnostic) throw new AppError(out.result.diagnostic);
        })}>Abrir nova planilha no Excel</Button>
        <Button disabled={active} onClick={() => guard(async () => {
          const out = await call("record_start", { category: cat, target, url: url || null });
          setRecording(out.recording); setActive(true);
          setStatus(`Gravando… Faça as ações no ${cat === "browser" ? "navegador do RedRise" : target === "excel.exe" ? "Excel" : "Bloco de Notas"} e clique em Parar.` +
            (out.injected_input_accepted ? " (modo laboratório: entrada sintética aceita)" : ""));
        })}>Iniciar gravação</Button>
        <Button disabled={!active} onClick={() => guard(async () => {
          const out = await call("record_stop", { cancel: false });
          setActive(false);
          const r = out.result;
          if (r.status !== "complete") { setStatus(""); throw new AppError(recordingDiagnostic(r.status, r.reason)); }
          setStatus(`Gravação concluída: ${r.manifest?.event_count ?? "?"} eventos.`);
          setDone(out.recording ?? recording);
        })}>Parar</Button>
      </div>
      {status && <p className="text-sm text-muted-foreground">{status}</p>}
      <ErrorView error={error} />
      {done && <Card className="shadow-none"><CardHeader><CardTitle>Parâmetros</CardTitle>
        <CardDescription>Opcional: transforme textos digitados durante a gravação em entradas da rotina. Para “Salvar como”, grave a pasta no campo de navegação e o nome no campo Nome do arquivo e declare-os como parâmetros.</CardDescription></CardHeader>
        <CardContent className="space-y-2">
          {params.map((p, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-3">
              <Input aria-label="Nome do parâmetro" placeholder="nome (ex.: cliente)" value={p.n} onChange={(e) => setParams(params.map((x, j) => (j === i ? { ...x, n: e.target.value } : x)))} />
              <Select value={p.r} onValueChange={(v) => setParams(params.map((x, j) => (j === i ? { ...x, r: v } : x)))}><SelectTrigger className="w-full" aria-label="Papel"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="text">Texto</SelectItem><SelectItem value="output_path">Caminho de saída</SelectItem></SelectContent></Select>
              <Input aria-label="Texto digitado" placeholder="texto exatamente como foi digitado" value={p.l} onChange={(e) => setParams(params.map((x, j) => (j === i ? { ...x, l: e.target.value } : x)))} />
            </div>
          ))}
          <Button size="sm" variant="ghost" onClick={() => setParams([...params, { n: "", r: "text", l: "" }])}>+ parâmetro</Button>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={declare} onCheckedChange={(c) => setDeclare(c === true)} />Declarar caminho completo de saída (output_path) para checar colisão</label>
          <div className="space-y-1"><Label htmlFor="rec-name">Nome</Label><Input id="rec-name" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <Button onClick={() => guard(async () => {
            const p = params.filter((x) => x.n && x.l).map((x) => `${x.n}=${x.r}:${x.l}`);
            const compiled = await call("record_compile", { recording: done, params: p, declares: declare ? ["output_path=output_path"] : [] });
            await api("POST", "/api/v1/routines", { name: name || "Rotina gravada", category: cat,
              version: { kind: "procedure", procedure: compiled.procedure, note: `gravação ${compiled.compile.events_sha256 ?? ""}` } });
            await reload(); go({ menu: "rotina", page: "lista" });
          })}>Compilar e salvar rotina</Button>
        </CardContent></Card>}
    </div>
  );
}

export function LegacyRunPage({ id }: { id?: number }) {
  const { routines, stations, src, go } = useStore();
  const r = routines?.find((x) => x.id === id);
  const [templates, setT] = useState<any[]>([]);
  const [station, setStation] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const req = useRef({ id: crypto.randomUUID(), last: "" });
  useEffect(() => { if (src.mode === "real") api("GET", "/api/v1/templates").then(setT).catch(setError); }, [src]);
  if (src.mode === "demo") return <DemoUnavailable />;
  if (!r) return <p className="text-sm text-muted-foreground">Carregando rotina…</p>;
  const t = templates.find((x) => x.id === r.template_id);
  const compatible = (stations ?? []).filter((s) => !s.revoked && s.categories.includes(r.category));
  const fields: { name: string; placeholder: string; required: boolean }[] = [];
  if (t) for (const [name, spec] of Object.entries<any>(t.inputs)) {
    const def = typeof spec.default === "string" ? spec.default.replace("{desktop}", "Área de Trabalho") : "";
    fields.push({ name, placeholder: def ? `padrão: ${def}` : "", required: !!spec.required && !spec.default });
  }
  for (const p of r.kind === "procedure" ? r.params ?? [] : []) {
    if (p.name === "output_dir" || p.name === "output_name") continue; // derived from output_path
    fields.push({ name: p.name, placeholder: p.role === "output_path" ? "caminho completo do arquivo" : "", required: true });
  }
  const st = station || (compatible[0] ? String(compatible[0].id) : "");
  return (
    <form className="max-w-xl space-y-3" onSubmit={async (ev) => {
      ev.preventDefault();
      if (busy || !st) return;
      const inputs = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== ""));
      const key = JSON.stringify([st, inputs]);
      if (req.current.last && key !== req.current.last) req.current.id = crypto.randomUUID(); // a different request
      req.current.last = key;
      setBusy(true); setError(null);
      try { await api("POST", "/api/v1/jobs", { request_id: req.current.id, version_id: r.version_id, station_id: Number(st), inputs }); go({ menu: "processo", page: "historico" }); }
      catch (e) { setError(e); } finally { setBusy(false); }
    }}>
      <h2 className="text-base font-semibold">Executar — {r.name} (v{r.version})</h2>
      {compatible.length ? <div className="space-y-1"><Label>Estação</Label><Select value={st} onValueChange={setStation}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>{compatible.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.name}{s.online ? "" : " (offline)"}{s.session_state && s.session_state !== "ready" ? " — sessão indisponível" : ""}</SelectItem>)}</SelectContent></Select></div>
        : <p className="text-sm">Nenhuma estação compatível com esta categoria.</p>}
      {fields.map((f) => <div key={f.name} className="space-y-1"><Label htmlFor={`in-${f.name}`}>{inputLabel(f.name)}</Label>
        <Input id={`in-${f.name}`} placeholder={f.placeholder} required={f.required} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} /></div>)}
      <ErrorView error={error} />
      <Button type="submit" disabled={!compatible.length || busy}>{busy ? "Enviando…" : "Executar"}</Button>
    </form>
  );
}

export function JobsSection() {
  const { src, changeTick } = useStore();
  const [jobs, setJobs] = useState<any[] | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (src.mode !== "real") return;
    let alive = true;
    let t = 0;
    // Fast only while something runs; nothing while the window is hidden (F4).
    const load = async () => {
      window.clearTimeout(t);
      let busy = false;
      if (document.visibilityState === "visible") {
        try { const j = await api<any[]>("GET", "/api/v1/jobs"); if (alive) setJobs(j); busy = j.some((x) => ["queued", "claimed", "running"].includes(x.state)); }
        catch (e) { if (alive) setError(e); }
      }
      if (alive) t = window.setTimeout(load, busy ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };
    void load();
    document.addEventListener("visibilitychange", load);
    return () => { alive = false; window.clearTimeout(t); document.removeEventListener("visibilitychange", load); };
  }, [src, changeTick]);
  if (src.mode !== "real") return null;
  const openJob = async (id: string) => { setError(null); try { setDetail(await api("GET", `/api/v1/jobs/${id}`)); } catch (e) { setError(e); } };
  return (
    <Card className="shadow-none"><CardHeader><CardTitle>Execuções técnicas</CardTitle>
      <CardDescription>Cada rotina executada gera um registro técnico, inclusive as de modelo e gravação.</CardDescription></CardHeader>
      <CardContent className="space-y-3"><ErrorView error={error} />
        <div className="max-h-80 overflow-auto rounded-md border"><Table>
          <TableHeader><TableRow><TableHead>Quando</TableHead><TableHead>Rotina</TableHead><TableHead>Estação</TableHead><TableHead>Estado</TableHead><TableHead>Por</TableHead></TableRow></TableHeader>
          <TableBody>{(jobs ?? []).map((j) => (
            <TableRow key={j.id} className="cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" tabIndex={0} onClick={() => openJob(j.id)}
              onKeyDown={(k) => { if (k.key === "Enter" || k.key === " ") { k.preventDefault(); void openJob(j.id); } }}><TableCell>{when(j.created_at)}</TableCell><TableCell>{j.routine_name} v{j.version}</TableCell>
              <TableCell>{j.station_name}</TableCell><TableCell><StateBadge state={j.state} />{j.waiting_reason && <small className="ml-1 text-muted-foreground">{tv(j.waiting_reason)}</small>}</TableCell><TableCell>{j.requested_by}</TableCell></TableRow>
          ))}</TableBody></Table></div>
        {detail && <div className="rounded-md border p-3 text-sm">
          <p className="font-medium">{detail.routine_name} v{detail.version} <StateBadge state={detail.state} /></p>
          <p className="text-muted-foreground">Estação {detail.station_name} · pedida por {detail.requested_by} · {when(detail.created_at)}</p>
          <p>{detail.verified ? "Resultado conferido por verificador independente." : detail.state === "completed_unverified" ? "Passos enviados; resultado não verificado." : ""}</p>
          {detail.diagnostic && <DiagnosticBox d={detail.diagnostic} />}
          <details><summary className="cursor-pointer">Linha do tempo</summary><ul className="list-disc pl-5">{detail.events.map((e: any, i: number) =>
            <li key={i}>{when(e.at)} — {JOB_STATE[e.state] ?? e.state}{e.detail?.error_code ? " · " + e.detail.error_code : ""}</li>)}</ul></details>
          {detail.result && <details><summary className="cursor-pointer">Resultado técnico</summary><pre>{JSON.stringify(detail.result, null, 2)}</pre></details>}
          {["queued", "claimed", "running"].includes(detail.state) && <Button size="sm" variant="outline" className="mt-2" onClick={async () => {
            try { await api("POST", `/api/v1/jobs/${detail.id}/cancel`); await openJob(detail.id); } catch (e) { setError(e); }
          }}>Cancelar</Button>}
        </div>}
      </CardContent></Card>
  );
}
