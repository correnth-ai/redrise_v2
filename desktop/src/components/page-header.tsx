// Common top of every page of the shell: main title and subtitle of the menu,
// navigation cards to its pages, and the smaller title with the page name.
// Titles use Playfair Display. Cards only navigate; they run nothing.
import { CalendarClock, History, KanbanSquare, ListChecks, ListTree, MonitorCog, Play, Settings2, Users, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { SUB_TITLE, type Menu, type Route } from "@/routes";

interface NavCard { menu: Menu; page: string; title: string; hint: string; icon: LucideIcon }

const MENU: Record<Menu, { title: string; subtitle: string; cards: NavCard[] }> = {
  empresa: { title: "Empresa", subtitle: "Panorama da operação da equipe.", cards: [
    { menu: "processo", page: "acao", title: "Processo", hint: "Sequências de rotinas e execução", icon: ListChecks },
    { menu: "rotina", page: "lista", title: "Rotina", hint: "Etapas cadastradas e vínculos", icon: Workflow },
    { menu: "configuracao", page: "equipe", title: "Configuração", hint: "Equipe, estações e aplicativo", icon: Settings2 },
  ] },
  processo: { title: "Processo", subtitle: "Monte sequências de rotinas, execute e acompanhe o resultado.", cards: [
    { menu: "processo", page: "acao", title: "Ação", hint: "Processos cadastrados e execução", icon: Play },
    { menu: "processo", page: "historico", title: "Histórico", hint: "Execuções e resultados", icon: History },
    { menu: "processo", page: "kanban", title: "Kanban", hint: "Etapas por situação", icon: KanbanSquare },
  ] },
  rotina: { title: "Rotina", subtitle: "Cadastre cada etapa e veja em quais processos ela está.", cards: [
    { menu: "rotina", page: "lista", title: "Lista", hint: "Rotinas cadastradas e vínculos", icon: ListTree },
    { menu: "rotina", page: "atividade", title: "Atividade", hint: "Linha do tempo e registros", icon: CalendarClock },
  ] },
  configuracao: { title: "Configuração", subtitle: "Equipe, estações e dados do aplicativo.", cards: [
    { menu: "configuracao", page: "equipe", title: "Equipe", hint: "Pessoas e perfis de acesso", icon: Users },
    { menu: "configuracao", page: "estacao", title: "Estação", hint: "Computadores que executam", icon: MonitorCog },
    { menu: "configuracao", page: "aplicativo", title: "Aplicativo", hint: "Ambiente, espaço e versão", icon: Settings2 },
  ] },
};

export function NavCards({ route, go }: { route: Route; go: (r: Route) => void }) {
  const { cards, title } = MENU[route.menu];
  return (
    <nav aria-label={`Atalhos de ${title}`} className={cn("grid gap-3", cards.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-3")}>
      {cards.map((c) => {
        const active = c.menu === route.menu && c.page === route.page;
        return (
          <button key={`${c.menu}/${c.page}`} type="button" aria-current={active ? "page" : undefined} onClick={() => go({ menu: c.menu, page: c.page })}
            className={cn("flex items-center gap-3 rounded-lg border bg-card p-3 text-left outline-none transition-colors hover:border-muted-foreground focus-visible:ring-2 focus-visible:ring-ring",
              active && "border-primary hover:border-primary")}>
            <span className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-muted-foreground", active && "border-primary/40 text-primary")}><c.icon aria-hidden className="size-4" /></span>
            <span className="min-w-0"><span className="block text-sm font-medium">{c.title}</span>
              <span className="block truncate text-xs text-muted-foreground">{c.hint}</span></span>
          </button>
        );
      })}
    </nav>
  );
}

export function PageHeader({ route, go }: { route: Route; go: (r: Route) => void }) {
  const m = MENU[route.menu];
  const sub = SUB_TITLE[`${route.menu}/${route.page}`];
  // Pages reached from a screen (wizard, recording) keep the titles but not the shortcuts.
  const onCard = route.menu === "empresa" || m.cards.some((c) => c.page === route.page);
  return (
    <header className="mb-6 space-y-4">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight">{m.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{m.subtitle}</p>
      </div>
      {onCard && <NavCards route={route} go={go} />}
      {sub && <h2 className="font-display text-xl font-semibold">{sub}</h2>}
    </header>
  );
}
