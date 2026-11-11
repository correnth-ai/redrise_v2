// RedRise desktop shell: boot (team bootstrap / remembered session / access / shell), sidebar-03
// navigation, integrated window chrome, the shared execution dialog and the
// update offer ("Pode atualizar" / "Ainda não").
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/app-sidebar";
import { ErrorView } from "@/components/diagnostic";
import { NotificationsBell } from "@/components/notifications-bell";
import { PageHeader } from "@/components/page-header";
import { TopBar } from "@/components/window-chrome";
import { AccessPage, WelcomePage, type SetupRole } from "@/features/auth";
import { AccountWizard } from "@/features/account-wizard";
import { AppPage, StationsPage, TeamPage } from "@/features/configuracoes";
import { EmpresaPage } from "@/features/empresa";
import { ActivityPage, HistoryPage, KanbanPage } from "@/features/fluxos";
import { LegacyRunPage, RecordingPage, TemplatesPage } from "@/features/legacy";
import { ProcessesPage, RoutinesPage } from "@/features/processos";
import { RoutineWizard } from "@/features/routine-wizard";
import { RunDialog } from "@/features/run-dialog";
import { realSource, isDemoBuild, type DataSource } from "@/data/source";
import type { Me } from "@/data/types";
import { AppError, api, call, session } from "@/lib/api";
import { canonical, HOME, PAGE_TITLE, type Route } from "@/routes";
import { StoreProvider, type RunTarget } from "@/state";

type Phase = { kind: "loading" } | { kind: "welcome"; role: SetupRole } | { kind: "access" } | { kind: "shell"; me: Me; version: string }
  | { kind: "server-error"; error: unknown } | { kind: "demo-access" };

export function App() {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [src, setSrc] = useState<DataSource>(realSource);
  const [flash, setFlash] = useState<string | null>(null);
  const [route, setRoute] = useState<Route>(HOME);

  const boot = useCallback(async () => {
    if (import.meta.env.MODE === "demo") { // statically false in the shipped build: fixtures are not bundled
      const { demoSource } = await import("@/data/demo");
      setSrc(demoSource);
      setPhase({ kind: "shell", me: await demoSource.me(), version: "demonstração" });
      return;
    }
    try {
      const info = await call("app_info");
      // The role chosen in the installer (server|station) picks the first-open flow, without asking again.
      if (!info.connection) return setPhase({ kind: "welcome", role: info.setup_intent === "server" || info.setup_intent === "station" ? info.setup_intent : null });
      if (!session.token) return setPhase({ kind: "access" });
      try { setPhase({ kind: "shell", me: await api("GET", "/api/v1/me"), version: info.desktop }); }
      catch (e) {
        if (e instanceof AppError && e.diagnostic.error_code === "AUTH-REQUIRED") { session.set(null); return void boot(); }
        setPhase({ kind: "server-error", error: e });
      }
    } catch (e) { setPhase({ kind: "server-error", error: e }); }
  }, []);
  useEffect(() => { void boot(); }, [boot]);

  const signedIn = (out: { token: string }) => {
    session.set(out.token);
    setRoute(HOME);
    setFlash(null);
    void boot();
  };
  const signOut = async () => {
    if (src.mode === "real") { try { await api("POST", "/api/v1/logout"); } catch { /* session ends locally anyway */ } }
    session.set(null);
    void boot();
  };

  const body = (() => {
    switch (phase.kind) {
      case "loading": return <p className="p-6 text-sm text-muted-foreground">Carregando…</p>;
      case "welcome": return <WelcomePage role={phase.role} onDone={boot} onCreated={(code) => {
        setFlash(`Equipe criada. Para conectar outras estações, use o código exibido em Configuração › Aplicativo: ${code}`);
        setRoute({ menu: "configuracao", page: "aplicativo" }); void boot();
      }} />;
      case "access": return <AccessPage onSignedIn={signedIn} />;
      case "demo-access": return <AccessPage onSignedIn={() => undefined} />;
      case "server-error": return <div className="p-6"><h2 className="mb-2 font-semibold">Servidor da equipe</h2><ErrorView error={phase.error} />
        <Button variant="outline" onClick={boot}>Tentar novamente</Button></div>;
      case "shell": return null;
    }
  })();

  if (phase.kind !== "shell") {
    const scenic = phase.kind === "access" || phase.kind === "demo-access";
    return (
      <TooltipProvider>
        <div className="relative flex h-full flex-col">
          {scenic && <img src="assets/login-register-background.png" alt="" className="pointer-events-none absolute inset-0 size-full object-cover" />}
          <TopBar overlay={scenic}>{isDemoBuild && <DemoBadge />}{isDemoBuild && phase.kind === "demo-access" &&
            <Button size="sm" variant="secondary" onClick={boot}>Voltar ao painel</Button>}</TopBar>
          <main className="relative min-h-0 flex-1 overflow-auto">{body}</main>
        </div>
      </TooltipProvider>
    );
  }
  return (
    <TooltipProvider>
      <Shell me={phase.me} version={phase.version} src={src} route={route} setRoute={setRoute} flash={flash} clearFlash={() => setFlash(null)}
        onLogout={signOut} onSessionEnded={() => { session.set(null); void boot(); }}
        onIdentityDemo={() => setPhase({ kind: "demo-access" })} />
    </TooltipProvider>
  );
}

function DemoBadge() {
  return <Badge className="bg-warn-soft text-warn border-transparent" title="Dados e textos fictícios; nada é salvo ou executado">Demonstração</Badge>;
}

function Shell({ me, version, src, route, setRoute, flash, clearFlash, onLogout, onSessionEnded, onIdentityDemo }: {
  me: Me; version: string; src: DataSource; route: Route; setRoute: (r: Route) => void; flash: string | null; clearFlash: () => void;
  onLogout: () => void; onSessionEnded: () => void; onIdentityDemo: () => void;
}) {
  const [target, setTarget] = useState<RunTarget | undefined>(undefined);
  const update = useUpdate(src.mode === "real");
  const go = (r: Route) => { clearFlash(); setRoute(canonical(r)); };
  const key = `${route.menu}/${route.page}`;
  return (
    <StoreProvider src={src} me={me} go={go} run={(t) => setTarget(t)} signOut={onLogout} onSessionEnded={onSessionEnded}>
      <SidebarProvider className="h-full min-h-0">
        <AppSidebar route={route} go={go} me={me} version={version} update={update.release?.version ?? null}
          onLogout={onLogout} onUpdate={update.show} />
        <SidebarInset className="min-h-0 overflow-hidden">
          <TopBar afterTheme={<NotificationsBell />}>
            <SidebarTrigger aria-label="Recolher ou expandir o menu" />
            <Separator orientation="vertical" className="mx-1 h-4" />
            <span className="truncate text-sm text-muted-foreground">{PAGE_TITLE[key] ?? PAGE_TITLE["empresa/painel"]}</span>
            {src.mode === "demo" && <DemoBadge />}
            {src.mode === "demo" && <Button size="sm" variant="ghost" onClick={onIdentityDemo}>Ver acesso e cadastro</Button>}
          </TopBar>
          <main className="min-h-0 flex-1 overflow-auto p-4 md:p-6">
            {flash && <div role="status" className="mb-4 rounded-md border-l-4 border-ok bg-ok-soft px-4 py-3 text-sm">{flash}</div>}
            <PageHeader route={route} go={go} />
            <Page route={route} />
          </main>
        </SidebarInset>
      </SidebarProvider>
      <RunDialog open={target !== undefined} target={target ?? null} onClose={() => setTarget(undefined)} />
      {update.toast}
    </StoreProvider>
  );
}

function Page({ route }: { route: Route }) {
  const k = `${route.menu}/${route.page}`;
  switch (k) {
    case "rotina/lista": return <RoutinesPage />;
    case "rotina/atividade": return <ActivityPage />;
    case "rotina/nova": return <RoutineWizard key="new" />;
    case "rotina/editar": return <RoutineWizard key={`e${route.id}`} id={route.id} />;
    case "rotina/modelos": return <TemplatesPage />;
    case "rotina/gravacao": return <RecordingPage />;
    case "rotina/executar-legada": return <LegacyRunPage id={route.id} />;
    case "processo/acao": return <ProcessesPage key={`${route.id ?? ""}-${route.nonce ?? ""}`} focus={route.id} />;
    case "processo/historico": return <HistoryPage key={`${route.id ?? ""}-${route.days ?? ""}`} focus={route.id} days={route.days} />;
    case "processo/kanban": return <KanbanPage key={String(route.process ?? "")} process={route.process} />;
    case "configuracao/equipe": return <TeamPage />;
    case "configuracao/nova-conta": return <AccountWizard />;
    case "configuracao/estacao": return <StationsPage />;
    case "configuracao/aplicativo": return <AppPage />;
    default: return <EmpresaPage />;
  }
}

// ---------------------------------------------------------------- update (P11), preserved
function useUpdate(enabled: boolean) {
  const [release, setRelease] = useState<any>(null);
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!enabled) return;
    const check = () => call("update_check").then((r) => { if (r.available) { setRelease(r.release); setVisible(true); } })
      .catch(() => undefined); // only a verified offer is shown; failed checks are logged in logs/update.log
    void check();
    const t = window.setInterval(check, 6 * 3600 * 1000);
    return () => window.clearInterval(t);
  }, [enabled]);
  const toast = release && visible ? (
    <div role="status" className="fixed bottom-4 right-4 z-50 w-[22rem] rounded-xl border border-l-4 border-l-primary bg-card p-4 text-sm shadow-lg">
      <b>Nova versão {release.version} disponível</b>
      {release.notes && <p className="my-1">{release.notes}</p>}
      <p className="my-1 text-muted-foreground">A atualização só começa sem execuções em andamento (no servidor: em nenhuma estação). Documentos de outros aplicativos não são fechados.</p>
      <div className="mt-2 flex gap-2">
        <Button size="sm" disabled={busy} onClick={async () => {
          setBusy(true); setError(null);
          try { await call("update_apply", { token: session.token }); } catch (e) { setError(e); } finally { setBusy(false); }
        }}>{busy ? "Baixando e conferindo…" : "Pode atualizar"}</Button>
        <Button size="sm" variant="ghost" onClick={() => setVisible(false)}>Ainda não</Button>
      </div>
      <ErrorView error={error} />
    </div>
  ) : null;
  return { release, toast, show: () => setVisible(true) };
}
