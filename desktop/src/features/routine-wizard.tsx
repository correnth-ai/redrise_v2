// Nova Rotina: three steps on a page (work order UI-ENGINE-BOAS-VINDAS-20261103).
// 1 Vínculo: start a process, follow up, or standalone. 2 Destino: an application the
// station can start, a site in a detected browser, or a file from "Outro…"; a follow-up
// chooses its action instead. 3 Preparação: saves, then the station resolves destination
// and dependencies and reports each operation. Preparing never opens the destination;
// only "Quer testar?" does, and follow-ups do not offer it.
import { useEffect, useMemo, useRef, useState } from "react";
import { Check, CheckCircle2, CircleAlert, CircleDashed, Loader2, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DiagnosticBox, ErrorView } from "@/components/diagnostic";
import { SearchableSelect } from "@/components/searchable-select";
import type { AppTarget, Job, Member, RoutineLink, RoutineVersionInput, StationApp } from "@/data/types";
import { useAction } from "@/hooks/use-action";
import { useStore } from "@/state";
import { notifyLabels, reportLabels, tv } from "@/lib/locale";
import { cn } from "@/lib/utils";

export const validUrl = (u: string) => /^https?:\/\/[^\s/$.?#][^\s]*$/i.test(u.trim());
const isHtml = (p: string) => /\.html?$/i.test(p);
const OTHER = "__other";
const JOB_DONE = ["completed_unverified", "verified", "failed", "uncertain", "refused", "cancelled", "error"];
const POLL_MS = 800;

type Mode = "start" | "followup" | "standalone";
type Dest = { kind: "app"; app_id: string; name: string } | { kind: "browser"; browser_id: string; name: string } | { kind: "file"; path: string; name: string };

const fileName = (p: string) => p.split(/[\\/]/).pop() ?? p;

/** What the Core stores for this destination. */
export function versionOf(dest: Dest, url: string): { category: "windows" | "browser"; version: RoutineVersionInput } {
  if (dest.kind === "browser") {
    return { category: "browser", version: { kind: "browser_open", config: { origin: "site", browser: dest.browser_id, url: url.trim(), path: null, isolated: true } } };
  }
  if (dest.kind === "file" && isHtml(dest.path)) {
    return { category: "browser", version: { kind: "browser_open", config: { origin: "html", browser: null, url: null, path: dest.path, isolated: true } } };
  }
  const target: AppTarget = dest.kind === "app" ? { kind: "app", app_id: dest.app_id, name: dest.name } : { kind: "file", path: dest.path, name: dest.name };
  return { category: "windows", version: { kind: "app_open", config: { target, isolated: true } } };
}

const HOW: Record<string, string> = { start_menu: "Pelo menu Iniciar", program: "Como programa", association: "Pelo programa associado ao arquivo" };
const CHECKS: { id: string; label: string }[] = [
  { id: "session", label: "Sessão do Windows disponível" },
  { id: "target", label: "Destino encontrado na estação" },
  { id: "launch", label: "Pode ser aberto nesta estação" },
];

function usePoll(job: Job | null, get: (id: string) => Promise<Job>, set: (j: Job) => void) {
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    if (!job || JOB_DONE.includes(job.state)) return;
    const t = window.setTimeout(async () => {
      try { const j = await get(job.id); if (alive.current) set(j); } catch { if (alive.current) set({ ...job }); } // transient: the next tick asks again
    }, POLL_MS);
    return () => window.clearTimeout(t);
  }, [job]); // eslint-disable-line react-hooks/exhaustive-deps
}

function StepMark({ state }: { state: "wait" | "running" | "ok" | "failed" }) {
  if (state === "ok") return <CheckCircle2 aria-hidden className="size-5 shrink-0 text-ok" />;
  if (state === "failed") return <CircleAlert aria-hidden className="size-5 shrink-0 text-destructive" />;
  if (state === "running") return <Loader2 aria-hidden className="size-5 shrink-0 animate-spin text-info" />;
  return <CircleDashed aria-hidden className="size-5 shrink-0 text-muted-foreground" />;
}
const STATE_LABEL = { wait: "aguardando", running: "em andamento", ok: "concluído", failed: "falhou" };

function Operation({ label, state, detail }: { label: string; state: "wait" | "running" | "ok" | "failed"; detail?: string | null }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      <StepMark state={state} />
      <span><span className={cn(state === "wait" && "text-muted-foreground")}>{label}</span>
        <span className="sr-only"> ({STATE_LABEL[state]})</span>
        {detail && <span className="block text-xs text-muted-foreground break-all">{detail}</span>}</span>
    </li>
  );
}

/** Last reported state of each operation, plus the job's own outcome for what never reported. */
function checkState(job: Job | null, id: string): { state: "wait" | "running" | "ok" | "failed"; detail?: string | null } {
  const events = (job?.events ?? []).filter((e) => e.state === "check" && e.detail?.id === id);
  const last = events[events.length - 1]?.detail;
  if (last) return { state: last.state === "running" ? (job && JOB_DONE.includes(job.state) ? "failed" : "running") : last.state, detail: HOW[last.detail] ?? last.detail };
  return { state: "wait" };
}

export function RoutineWizard({ id }: { id?: number }) {
  const { routines, processes, stations, src, reload, go } = useStore();
  const existing = id ? routines?.find((r) => r.id === id) : undefined;
  const editing = !!id;
  const [step, setStep] = useState(editing ? 2 : 1);
  const [mode, setMode] = useState<Mode>(existing?.kind === "followup" ? "followup" : "standalone");
  const [previous, setPrevious] = useState<string | null>(null); // "process:position"
  const [assignee, setAssignee] = useState<string | null>(null);
  const [action, setAction] = useState<"review" | "report" | "notify">((existing?.config?.action as any) ?? "review");
  const [mailTo, setMailTo] = useState("");
  const [mailDest, setMailDest] = useState<string | null>(null); // a mail application or a browser of the station
  const [webmail, setWebmail] = useState("gmail");
  const [members, setMembers] = useState<Member[] | null>(null);
  const [name, setName] = useState("");
  const [processId, setProcessId] = useState<string | null>(null);
  const [station, setStation] = useState("");
  const [dest, setDest] = useState<Dest | null>(null);
  const [url, setUrl] = useState("");
  const [apps, setApps] = useState<StationApp[] | null | undefined>(undefined);
  const [loadingApps, setLoadingApps] = useState(false);
  const [routineId, setRoutineId] = useState<number | null>(id ?? null);
  const [savedAs, setSavedAs] = useState<string | null>(null); // the version already on the Core, to not create another for nothing
  const [lockedCategory, setLockedCategory] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const cancelling = useAction(setError);
  const [prep, setPrep] = useState<Job | null>(null);
  const [test, setTest] = useState<Job | null>(null);
  const [testError, setTestError] = useState<unknown>(null);
  const [testAsked, setTestAsked] = useState(false); // from the click until the Core answers: one click, one opening
  usePoll(prep, src.job, setPrep);
  usePoll(test, src.job, setTest);

  // Editing starts from what is registered; the routine's category does not change.
  const [seeded, setSeeded] = useState(false);
  if (existing && !seeded) {
    setSeeded(true);
    setName(existing.name);
    setLockedCategory(existing.category);
    const c = existing.config;
    if (existing.kind === "followup") { setMode("followup"); setAction((c?.action as any) ?? "review"); setAssignee(String(c?.assignee_id ?? ""));
      setMailTo(c?.to ?? ""); if (c?.channel) { setMailDest(c.channel.kind === "app" ? `mail:${c.channel.mail_id}` : `browser:${c.channel.browser}`); if (c.channel.kind === "webmail") setWebmail(c.channel.provider); } }
    if (c?.target) setDest(c.target.kind === "app" ? { kind: "app", app_id: c.target.app_id!, name: c.target.name } : { kind: "file", path: c.target.path!, name: c.target.name });
    else if (c?.origin === "site") { setDest({ kind: "browser", browser_id: c.browser ?? "", name: c.browser ?? "" }); setUrl(c.url ?? ""); }
    else if (c?.origin === "html") setDest({ kind: "file", path: c.path ?? "", name: fileName(c.path ?? "") });
  }

  const usable = useMemo(() => (stations ?? []).filter((s) => !s.revoked), [stations]);
  useEffect(() => {
    if (!station && usable.length) setStation(String((usable.find((s) => s.online) ?? usable[0]).id));
  }, [usable, station]);
  const stationNow = usable.find((s) => String(s.id) === station);

  const loadApps = async () => {
    if (!station) return;
    setLoadingApps(true);
    try { setApps((await src.apps(Number(station))).apps); setError(null); } catch (e) { setApps(undefined); setError(e); } finally { setLoadingApps(false); }
  };
  useEffect(() => { if (step === 2 && (mode !== "followup" || action === "notify")) void loadApps(); }, [station, step, action]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (mode === "followup" && action === "review" && !members) src.members().then(setMembers).catch(setError);
  }, [mode, action, members, src]);

  if (id && !existing) return <p className="text-sm text-muted-foreground">{routines ? "Rotina não encontrada." : "Carregando…"}</p>;

  const free = (processes ?? []).filter((p) => !p.items.length && !p.system_key);
  const inProcess = (processes ?? []).filter((p) => p.items.some((i) => i.routine_id === routineId));
  const startsProcess = mode === "start" || (processes ?? []).some((p) => p.items.some((i) => i.routine_id === routineId && i.position === 1));

  const options = (apps ?? []).filter((a) => !a.mail_id && (!lockedCategory || (lockedCategory === "browser") === !!a.browser_id))
    .map((a) => ({ value: a.id, label: a.name, hint: a.browser_id ? "Navegador: informe o endereço do site" : undefined }));
  options.push({ value: OTHER, label: "Outro…", hint: "Escolher um arquivo no Windows", pinned: true } as any);
  const destValue = dest?.kind === "app" ? dest.app_id : dest?.kind === "browser" ? `browser:${dest.browser_id}` : dest?.kind === "file" ? OTHER : null;

  async function pickDest(value: string) {
    setError(null);
    if (value !== OTHER) {
      const a = (apps ?? []).find((x) => x.id === value);
      if (a) setDest(a.browser_id ? { kind: "browser", browser_id: a.browser_id, name: a.name } : { kind: "app", app_id: a.id, name: a.name });
      return;
    }
    try {
      const path = await src.pickFile();
      if (path) setDest({ kind: "file", path, name: fileName(path) });
    } catch (e) { setError(e); }
  }

  const plan = dest ? versionOf(dest, url) : null;
  const wrongCategory = !!plan && !!lockedCategory && plan.category !== lockedCategory;
  const step1 = name.trim().length > 0 && name.length <= 120 && (mode === "standalone" || (mode === "start" && !!processId) || (mode === "followup" && !!previous));
  const mailOptions = (apps ?? []).filter((a) => a.mail_id || a.browser_id).map((a) => ({ value: a.id, label: tv(a.name), hint: a.browser_id ? "Navegador: prepara no webmail" : "Aplicativo de e-mail" }));
  const pickedMail = (apps ?? []).find((a) => a.id === mailDest);
  const validMail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mailTo.trim());
  const notifyReady = validMail && !!mailDest;
  const step2 = mode === "followup" ? (action === "report" || (action === "review" ? !!assignee : notifyReady)) : !!dest && !!station && !wrongCategory && (dest.kind !== "browser" || validUrl(url));
  // Every step of every process, found by process or routine name and shown with its number.
  const stepsToFollow = (processes ?? []).filter((p) => !p.system_key).flatMap((p) => p.items.map((i) => ({
    value: `${p.id}:${i.position}`, label: `${p.name} · Etapa ${i.position}`, hint: i.routine_name })));

  async function saveFollowUp() {
    if (busy || !step2) return;
    setBusy(true); setError(null);
    try {
      const [destKind, destId] = (mailDest ?? "").split(":");
      const channel = destKind === "mail" ? { kind: "app" as const, mail_id: destId, name: pickedMail?.name ?? destId }
        : { kind: "webmail" as const, provider: webmail, browser: destId, name: webmail === "gmail" ? "Gmail" : "Outlook na web" };
      const version: RoutineVersionInput = { kind: "followup", config: action === "report" ? { action, labels: reportLabels() }
        : action === "notify" ? { action, to: mailTo.trim(), channel, labels: notifyLabels() } : { action, assignee_id: Number(assignee) } };
      if (routineId === null) {
        const [process_id, after_position] = (previous ?? "").split(":").map(Number);
        const link: RoutineLink = { process_id, after_position };
        setRoutineId(await src.createRoutine(name.trim(), "windows", version, link));
      } else {
        await src.addRoutineVersion(routineId, name.trim(), version); // pending requests move to the new responsible on the Core
      }
      await reload();
      setStep(3);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  async function saveAndPrepare() {
    if (!plan || busy) return;
    setBusy(true); setError(null); setPrep(null); setTest(null); setTestError(null);
    try {
      let rid = routineId;
      const fingerprint = JSON.stringify([name.trim(), plan.version]);
      if (rid === null) {
        rid = await src.createRoutine(name.trim(), plan.category, plan.version, mode === "start" ? { process_id: Number(processId) } : null);
        setRoutineId(rid);
        setLockedCategory(plan.category); // a saved routine keeps its category
      } else if (fingerprint !== savedAs) {
        await src.addRoutineVersion(rid, name.trim(), plan.version);
      }
      setSavedAs(fingerprint);
      await reload();
      setStep(3);
      setPrep(await src.prepareRoutine(rid, crypto.randomUUID(), Number(station)));
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  async function runTest() {
    if (!prep || routineId === null || testAsked) return;
    setTestAsked(true); setTest(null); setTestError(null);
    try { setTest(await src.testRoutine(routineId, crypto.randomUUID(), prep.id)); } catch (e) { setTestError(e); } finally { setTestAsked(false); }
  }

  const followUp = mode === "followup";
  const prepDone = followUp || (!!prep && JOB_DONE.includes(prep.state)) || (step === 3 && !prep && !busy); // refused before reaching the station
  const prepOk = !followUp && prep?.state === "verified";
  const testing = testAsked || (!!test && !JOB_DONE.includes(test.state));
  const steps = ["Vínculo", "Destino", "Preparação"];
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <ol className="flex items-center gap-2" aria-label="Etapas do cadastro">
        {steps.map((s, i) => (
          <li key={s} className="flex flex-1 items-center gap-2">
            <span aria-current={step === i + 1 ? "step" : undefined} className={cn("inline-flex size-7 shrink-0 items-center justify-center rounded-full border text-sm",
              step > i + 1 ? "border-primary bg-primary text-primary-foreground" : step === i + 1 ? "border-primary text-primary" : "text-muted-foreground")}>
              {step > i + 1 ? <Check className="size-4" /> : i + 1}
            </span>
            <span className={cn("text-sm", step === i + 1 ? "font-medium" : "text-muted-foreground")}>{s}</span>
            {i < steps.length - 1 && <span aria-hidden className="h-px flex-1 bg-border" />}
          </li>
        ))}
      </ol>
      <Card className="shadow-none"><CardContent className="space-y-5 pt-0">
        {step === 1 && <>
          <div className="space-y-2"><Label htmlFor="rt-name">Nome da rotina</Label>
            <Input id="rt-name" value={name} maxLength={120} autoFocus onChange={(e) => setName(e.target.value)} /></div>
          <div className="space-y-2"><Label id="rt-mode-label">O que esta rotina faz no processo</Label>
            <RadioGroup value={mode} onValueChange={(v) => setMode(v as Mode)} className="grid gap-2" aria-labelledby="rt-mode-label">
              {([["start", "Iniciar um processo", "É a etapa 1 de um processo que ainda não tem etapa 1.", false],
                ["followup", "Fazer follow-up", "Continua depois de uma etapa de um processo, com o contexto dela.", false],
                ["standalone", "Rotina avulsa", "Fica salva sem vínculo e executa pela Lista.", false]] as const).map(([v, t, d, off]) => (
                <Label key={v} htmlFor={`m-${v}`} className={cn("flex items-start gap-3 rounded-md border p-3 has-[[data-state=checked]]:border-primary", off ? "cursor-not-allowed opacity-60" : "cursor-pointer")}>
                  <RadioGroupItem id={`m-${v}`} value={v} disabled={off} className="mt-0.5" aria-label={t} aria-describedby={`m-${v}-d`} />
                  <span><span className="block font-medium">{t}</span><span id={`m-${v}-d`} className="block text-xs font-normal text-muted-foreground">{d}</span></span>
                </Label>
              ))}
            </RadioGroup></div>
          {mode === "start" && (
            <div className="space-y-2"><Label htmlFor="rt-process">Processo</Label>
              <SearchableSelect id="rt-process" value={processId} onChange={setProcessId} placeholder="Busque pelo nome do processo"
                options={free.map((p) => ({ value: String(p.id), label: p.name }))} empty="Nenhum processo sem etapa 1." />
              {!free.length && <p className="text-xs text-muted-foreground">Cadastre o processo em <button type="button" className="underline" onClick={() => go({ menu: "processo", page: "acao" })}>Processo › Ação</button> antes de vinculá-lo aqui.</p>}
            </div>
          )}
          {mode === "followup" && (
            <div className="space-y-2"><Label htmlFor="rt-previous">Etapa anterior</Label>
              <SearchableSelect id="rt-previous" value={previous} onChange={setPrevious} placeholder="Busque por processo ou rotina" options={stepsToFollow} empty="Nenhuma etapa encontrada." />
              <p className="text-xs text-muted-foreground">O follow-up entra logo depois dela e recebe o contexto daquela etapa na mesma execução.</p>
            </div>
          )}
        </>}
        {step === 2 && editing && <div className="space-y-2"><Label htmlFor="rt-name">Nome da rotina</Label>
          <Input id="rt-name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></div>}
        {step === 2 && followUp && <>
          <div className="space-y-2"><Label id="rt-action-label">Ação</Label>
            <RadioGroup value={action} onValueChange={(v) => setAction(v as "review" | "report" | "notify")} className="grid gap-2" aria-labelledby="rt-action-label">
              {([["notify", "Notificar alguém", "Prepara um rascunho para a pessoa revisar e enviar. Nada é enviado pelo RedRise.", editing && action !== "notify"],
                ["report", "Gerar relatório", "Salva um PDF com o que foi feito na execução, em Documentos, RedRise, Relatorios.", editing && action !== "report"],
                ["review", "Solicitar revisão", "Pausa a execução até o responsável aprovar.", editing && action !== "review"]] as const).map(([v, t, d, off]) => (
                <Label key={v} htmlFor={`a-${v}`} className={cn("flex items-start gap-3 rounded-md border p-3 has-[[data-state=checked]]:border-primary", off ? "cursor-not-allowed opacity-60" : "cursor-pointer")}>
                  <RadioGroupItem id={`a-${v}`} value={v} disabled={off} className="mt-0.5" aria-label={t} aria-describedby={`a-${v}-d`} />
                  <span><span className="block font-medium">{t}</span><span id={`a-${v}-d`} className="block text-xs font-normal text-muted-foreground">{d}</span></span>
                </Label>
              ))}
            </RadioGroup></div>
          {action === "notify" && <>
            <div className="space-y-2"><Label htmlFor="rt-mail-to">Para</Label>
              <Input id="rt-mail-to" type="email" value={mailTo} placeholder="pessoa@empresa.com" onChange={(e) => setMailTo(e.target.value)} aria-invalid={!!mailTo && !validMail} />
              {mailTo && !validMail && <p className="text-xs text-destructive">Informe um endereço de e-mail completo.</p>}</div>
            {usable.length > 1 && <div className="space-y-2"><Label htmlFor="rt-mail-station">Estação</Label>
              <Select value={station} onValueChange={(v) => { setStation(v); setMailDest(null); }}>
                <SelectTrigger id="rt-mail-station" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{usable.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.name}{s.online ? "" : " (offline)"}</SelectItem>)}</SelectContent>
              </Select></div>}
            <div className="space-y-2"><Label htmlFor="rt-mail-dest">Preparar em</Label>
              <SearchableSelect id="rt-mail-dest" value={mailDest} onChange={setMailDest} placeholder="Aplicativo de e-mail ou navegador" options={mailOptions} empty="Nenhum aplicativo de e-mail ou navegador nesta estação." />
              <p className="text-xs text-muted-foreground">Na execução, o rascunho abre na estação que executa, com um anexo quando o aplicativo permite; caso contrário o texto cita o arquivo.</p></div>
            {pickedMail?.browser_id && <div className="space-y-2"><Label htmlFor="rt-webmail">Webmail</Label>
              <Select value={webmail} onValueChange={setWebmail}>
                <SelectTrigger id="rt-webmail" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="gmail">Gmail</SelectItem><SelectItem value="outlook">Outlook na web</SelectItem></SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">A pessoa precisa estar conectada à própria conta nesse navegador. O RedRise não entra em contas.</p></div>}
          </>}
          {action === "review" && <div className="space-y-2"><Label htmlFor="rt-assignee">Responsável pela revisão</Label>
            <SearchableSelect id="rt-assignee" value={assignee} onChange={setAssignee} placeholder="Busque um membro da equipe" empty="Nenhum membro ativo."
              options={(members ?? []).filter((m) => m.active).map((m) => ({ value: String(m.id), label: m.display, hint: m.username }))} />
            {editing && <p className="text-xs text-muted-foreground">Pedidos ainda pendentes passam para o novo responsável. Pedidos concluídos mantêm autor e horário.</p>}</div>}
        </>}
        {step === 2 && !followUp && <>
          <div className="space-y-2"><Label htmlFor="rt-station">Estação</Label>
            {usable.length ? (
              <Select value={station} onValueChange={(v) => { setStation(v); setDest(null); }}>
                <SelectTrigger id="rt-station" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{usable.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.name}{s.online ? "" : " (offline)"}</SelectItem>)}</SelectContent>
              </Select>
            ) : <p className="text-sm text-muted-foreground">Nenhuma estação conectada à equipe.</p>}
          </div>
          <div className="space-y-2">
            <div className="flex items-end justify-between gap-2"><Label htmlFor="rt-dest">O que abrir</Label>
              <Button type="button" size="sm" variant="ghost" disabled={loadingApps || !station} onClick={loadApps}>
                <RefreshCw className={cn(loadingApps && "animate-spin")} /> Atualizar lista</Button></div>
            <SearchableSelect id="rt-dest" value={destValue} onChange={pickDest} disabled={!station} placeholder="Busque um aplicativo instalado" options={options} />
            {apps === null && <p className="text-xs text-muted-foreground">Esta estação ainda não informou seus aplicativos. Use Outro… ou atualize em instantes.</p>}
            {dest?.kind === "file" && <p className="text-xs text-muted-foreground break-all">Arquivo escolhido: {dest.path}</p>}
            {wrongCategory && <p className="text-xs text-destructive">Esta rotina já foi cadastrada como {lockedCategory === "browser" ? "navegador" : "aplicativo"}. Escolha um destino do mesmo tipo ou crie outra rotina.</p>}
            <p className="text-xs text-muted-foreground">Lista informada pela estação (menu Iniciar e navegadores detectados). Na execução, o destino escolhido é conferido nela; não há troca automática por outro.</p>
          </div>
          {dest?.kind === "browser" && (
            <div className="space-y-2"><Label htmlFor="rt-url">Endereço do site</Label>
              <Input id="rt-url" value={url} placeholder="https://" onChange={(e) => setUrl(e.target.value)} aria-invalid={!!url && !validUrl(url)} />
              {url && !validUrl(url) && <p className="text-xs text-destructive">Informe um endereço completo começando com http:// ou https://.</p>}</div>
          )}
        </>}
        {step === 3 && followUp && (
          <div className="space-y-4">
            <ul className="space-y-3" aria-live="polite">
              <Operation label="Cadastro salvo" state="ok" detail={inProcess.length ? `Vinculada a ${inProcess.map((p) => p.name).join(", ")}` : null} />
              {action === "review" && <Operation label="Responsável ativo na equipe" state="ok" detail={(members ?? []).find((m) => String(m.id) === assignee)?.display} />}
            </ul>
            <div role="status" className="rounded-md border-l-4 border-ok bg-ok-soft px-4 py-3 text-sm">Deu tudo certo! A etapa vale a partir da próxima execução do processo.</div>
          </div>
        )}
        {step === 3 && !followUp && (
          <div className="space-y-4">
            <ul className="space-y-3" aria-live="polite">
              <Operation label="Cadastro salvo" state="ok" detail={inProcess.length ? `Vinculada a ${inProcess.map((p) => p.name).join(", ")}` : "Sem vínculo"} />
              <Operation label="Pedido entregue à estação" state={!prep ? (busy ? "running" : "failed") : prep.state === "queued" ? "running" : JOB_DONE.includes(prep.state) && prep.state !== "verified" && !prep.events?.some((x) => x.state === "check") ? "failed" : "ok"}
                detail={prep?.state === "queued" ? (prep.waiting_reason ?? `Aguardando ${stationNow?.name ?? "a estação"}`) : stationNow?.name} />
              {CHECKS.map((c) => { const s = checkState(prep, c.id); return <Operation key={c.id} label={c.label} state={s.state} detail={s.detail} />; })}
            </ul>
            {prep?.diagnostic && <DiagnosticBox d={prep.diagnostic} />}
            {prepOk && (
              <div role="status" className="rounded-md border-l-4 border-ok bg-ok-soft px-4 py-3 text-sm">
                {startsProcess
                  ? <>Deu tudo certo! <button type="button" disabled={testing} onClick={runTest} className="font-medium underline disabled:no-underline disabled:opacity-60">Quer testar?</button></>
                  : <>Deu tudo certo! A rotina já pode executar pela Lista.</>}
              </div>
            )}
            {test && (
              <ul className="space-y-3" aria-live="polite">
                <Operation label="Abrir o destino" state={test.state === "verified" ? "ok" : JOB_DONE.includes(test.state) ? "failed" : "running"}
                  detail={test.state === "verified" ? "Janela confirmada na estação." : testing ? "Aguardando a janela abrir." : null} />
              </ul>
            )}
            {test?.diagnostic && <DiagnosticBox d={test.diagnostic} />}
            <ErrorView error={testError} />
          </div>
        )}
        <ErrorView error={error} />
        <div className="flex justify-between gap-2 border-t pt-4">
          {step === 3
            ? followUp ? <span /> : <Button variant="ghost" disabled={!prepDone && !!prep} onClick={() => { setStep(2); setPrep(null); setTest(null); }}>Voltar e ajustar</Button>
            : <Button variant="ghost" onClick={() => (step === 1 || editing || routineId !== null ? go({ menu: "rotina", page: "lista" }) : setStep(step - 1))}>{step === 1 || editing || routineId !== null ? "Cancelar" : "Voltar"}</Button>}
          {step === 1 && <Button disabled={!step1} onClick={() => setStep(2)}>Continuar</Button>}
          {step === 2 && <Button disabled={busy || !step2} onClick={followUp ? saveFollowUp : saveAndPrepare}>{busy ? "Salvando…" : followUp ? "Salvar" : editing ? "Salvar e verificar" : "Salvar e preparar"}</Button>}
          {step === 3 && <span className="flex gap-2">
            {prepDone && !prepOk && <Button variant="outline" onClick={saveAndPrepare} disabled={busy}><Play /> Verificar de novo</Button>}
            {prep && !prepDone && prep.state === "queued" && <Button variant="outline" disabled={cancelling.busy} onClick={() => cancelling.run(async () => { await src.cancelJob(prep.id); setPrep(await src.job(prep.id)); })}>Cancelar verificação</Button>}
            <Button disabled={!prepDone || testing} onClick={async () => { await reload(); go({ menu: "rotina", page: "lista" }); }}>Concluir</Button>
          </span>}
        </div>
      </CardContent></Card>
      {editing && existing && <p className="text-xs text-muted-foreground">Salvar cria a versão {existing.version + 1}; execuções já iniciadas mantêm a versão com que começaram.</p>}
    </div>
  );
}
