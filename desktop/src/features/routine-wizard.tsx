// Browser routine registration as a page with steps (M07/G48):
// 1 Identificação (nome, origem, isolada) → 2 Destino (site: navegador + endereço;
// HTML local: só caminho) → 3 Revisão e cadastro. Saving never executes and
// never links the routine to a process.
import { useMemo, useState } from "react";
import { Check, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorView } from "@/components/diagnostic";
import type { BrowserConfig, Origin } from "@/data/types";
import { useStore } from "@/state";
import { cn } from "@/lib/utils";

export const validUrl = (u: string) => /^https?:\/\/[^\s/$.?#][^\s]*$/i.test(u.trim());
export const validHtmlPath = (p: string) => /^([a-zA-Z]:\\|\\\\[^\\]+\\[^\\]+\\).+\.html?$/i.test(p.trim());

export function RoutineWizard({ id }: { id?: number }) {
  const { routines, stations, src, reload, go } = useStore();
  const existing = id ? routines?.find((r) => r.id === id) : undefined;
  const [step, setStep] = useState(1);
  const [name, setName] = useState(existing?.name ?? "");
  const [origin, setOrigin] = useState<Origin>(existing?.config?.origin ?? "site");
  const [isolated, setIsolated] = useState(existing?.config?.isolated ?? true);
  const [browser, setBrowser] = useState(existing?.config?.browser ?? "");
  const [url, setUrl] = useState(existing?.config?.url ?? "");
  const [path, setPath] = useState(existing?.config?.path ?? "");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Browsers reported by the stations' Runners (registered sources and known paths, no disk scan).
  const browsers = useMemo(() => {
    const m = new Map<string, { id: string; name: string; stations: string[]; homologated: boolean }>();
    for (const s of stations ?? []) for (const b of s.browsers ?? []) {
      const cur = m.get(b.id) ?? { id: b.id, name: b.name, stations: [], homologated: b.homologated };
      cur.stations.push(s.name);
      m.set(b.id, cur);
    }
    return [...m.values()];
  }, [stations]);
  if (id && !existing) return <p className="text-sm text-muted-foreground">{routines ? "Rotina não encontrada." : "Carregando…"}</p>;

  const step1 = name.trim().length > 0 && name.length <= 120;
  const step2 = origin === "site" ? !!browser && validUrl(url) : validHtmlPath(path);
  const config: BrowserConfig = origin === "site"
    ? { origin, browser, url: url.trim(), path: null, isolated }
    : { origin, browser: null, url: null, path: path.trim(), isolated };
  const browserLabel = browsers.find((b) => b.id === browser)?.name ?? browser;

  async function save() {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      if (existing) await src.updateBrowserRoutine(existing.id, name.trim(), config);
      else await src.createBrowserRoutine(name.trim(), config);
      await reload();
      go({ menu: "rotina", page: "lista" });
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  const steps = ["Identificação", "Destino", "Revisão"];
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
          <div className="space-y-2"><Label>Origem</Label>
            <RadioGroup value={origin} onValueChange={(v) => setOrigin(v as Origin)} className="grid gap-2 sm:grid-cols-2">
              {([["site", "Navegar em site", "Abre o endereço numa nova guia do navegador escolhido."],
                ["html", "Abrir HTML local", "Abre o arquivo pelo mecanismo de abertura do Windows."]] as const).map(([v, t, d]) => (
                <Label key={v} htmlFor={`o-${v}`} className="flex cursor-pointer items-start gap-3 rounded-md border p-3 has-[[data-state=checked]]:border-primary">
                  <RadioGroupItem id={`o-${v}`} value={v} className="mt-0.5" />
                  <span><span className="block font-medium">{t}</span><span className="block text-xs font-normal text-muted-foreground">{d}</span></span>
                </Label>
              ))}
            </RadioGroup></div>
          <label className="flex items-start gap-3 text-sm">
            <Checkbox checked={isolated} onCheckedChange={(c) => setIsolated(c === true)} className="mt-0.5" />
            <span>Esta rotina pode ser executada isoladamente
              <span className="block text-xs text-muted-foreground">Desmarcada, ela só executa dentro de um processo (com o contexto da rotina anterior).</span></span>
          </label>
        </>}
        {step === 2 && origin === "site" && <>
          <div className="space-y-2">
            <div className="flex items-end justify-between gap-2"><Label htmlFor="rt-browser">Navegador</Label>
              <Button type="button" size="sm" variant="ghost" disabled={refreshing} onClick={async () => { setRefreshing(true); await reload(); setRefreshing(false); }}>
                <RefreshCw className={cn(refreshing && "animate-spin")} /> Atualizar lista</Button></div>
            <Select value={browser} onValueChange={setBrowser}>
              <SelectTrigger id="rt-browser" className="w-full"><SelectValue placeholder={browsers.length ? "Selecione o navegador" : "Nenhum navegador encontrado nas estações"} /></SelectTrigger>
              <SelectContent>{browsers.map((b) => <SelectItem key={b.id} value={b.id}>{b.name} — {b.stations.join(", ")}{b.homologated ? "" : " (detectado, não homologado)"}</SelectItem>)}</SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">Lista informada pelas estações (registros do Windows e caminhos conhecidos). Na execução, o navegador escolhido é conferido na estação; não há troca automática por outro.</p>
          </div>
          <div className="space-y-2"><Label htmlFor="rt-url">Endereço do site</Label>
            <Input id="rt-url" value={url} placeholder="https://" onChange={(e) => setUrl(e.target.value)} aria-invalid={!!url && !validUrl(url)} />
            {url && !validUrl(url) && <p className="text-xs text-destructive">Informe um endereço completo começando com http:// ou https://.</p>}</div>
        </>}
        {step === 2 && origin === "html" && (
          <div className="space-y-2"><Label htmlFor="rt-path">Caminho completo do arquivo HTML</Label>
            <Input id="rt-path" value={path} placeholder="C:\pasta\arquivo.html" onChange={(e) => setPath(e.target.value)} aria-invalid={!!path && !validHtmlPath(path)} />
            {path && !validHtmlPath(path) && <p className="text-xs text-destructive">Informe o caminho completo, com nome e extensão .html ou .htm.</p>}
            <p className="text-xs text-muted-foreground">Não é preciso escolher navegador: o arquivo abre como o Windows o abriria, e o RedRise identifica o navegador e a guia em que ele abriu.</p></div>
        )}
        {step === 3 && (
          <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
            <dt className="text-muted-foreground">Nome</dt><dd>{name}</dd>
            <dt className="text-muted-foreground">Origem</dt><dd>{origin === "site" ? "Navegar em site" : "Abrir HTML local"}</dd>
            {origin === "site" ? <><dt className="text-muted-foreground">Navegador</dt><dd>{browserLabel}</dd>
              <dt className="text-muted-foreground">Endereço</dt><dd className="break-all">{url}</dd></>
              : <><dt className="text-muted-foreground">Arquivo</dt><dd className="break-all">{path}</dd></>}
            <dt className="text-muted-foreground">Execução isolada</dt><dd>{isolated ? "Permitida" : "Não permitida"}</dd>
          </dl>
        )}
        <ErrorView error={error} />
        <div className="flex justify-between gap-2 border-t pt-4">
          <Button variant="ghost" onClick={() => (step === 1 ? go({ menu: "rotina", page: "lista" }) : setStep(step - 1))}>{step === 1 ? "Cancelar" : "Voltar"}</Button>
          {step < 3 ? <Button disabled={step === 1 ? !step1 : !step2} onClick={() => setStep(step + 1)}>Continuar</Button>
            : <Button disabled={busy || !step1 || !step2} onClick={save}>{busy ? "Salvando…" : existing ? "Salvar alterações" : "Cadastrar rotina"}</Button>}
        </div>
      </CardContent></Card>
      {existing && <p className="text-xs text-muted-foreground">Salvar cria a versão {existing.version + 1}; execuções já iniciadas mantêm a versão com que começaram.</p>}
    </div>
  );
}
