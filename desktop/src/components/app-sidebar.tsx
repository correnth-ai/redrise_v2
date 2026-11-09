// sidebar-03 (shadcn, MIT) adapted: RedRise brand and the singular menus of the
// work order: Empresa, Processo (Ação, Histórico, Kanban), Rotina (Lista,
// Atividade), Configuração (Equipe, Estação, Aplicativo). A main item with sub
// items opens its first one. No demo navigation.
// Hierarchy (TEAM-ACCOUNTS-20261108 item 9, visual only): Empresa on the first level, with a line through
// Processo and Rotina on the second and their pages on the third; Configuração stays on the first level,
// outside that line. Collapsed, every menu keeps its icon and tooltip.
import { Building2, LogOut, Workflow, ListChecks, Settings2, CircleDot } from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarHeader, SidebarMenu, SidebarMenuButton,
  SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem, SidebarRail,
} from "@/components/ui/sidebar";
import type { Me } from "@/data/types";
import { HOME, type Route } from "@/routes";

interface NavItem { menu: Route["menu"]; title: string; icon: typeof Workflow; items: { page: string; title: string }[]; children?: NavItem[] }
const NAV: NavItem[] = [
  { menu: "empresa", title: "Empresa", icon: Building2, items: [], children: [
    { menu: "processo", title: "Processo", icon: ListChecks, items: [{ page: "acao", title: "Ação" }, { page: "historico", title: "Histórico" }, { page: "kanban", title: "Kanban" }] },
    { menu: "rotina", title: "Rotina", icon: Workflow, items: [{ page: "lista", title: "Lista" }, { page: "atividade", title: "Atividade" }] },
  ] },
  { menu: "configuracao", title: "Configuração", icon: Settings2, items: [{ page: "equipe", title: "Equipe" }, { page: "estacao", title: "Estação" }, { page: "aplicativo", title: "Aplicativo" }] },
];

function NavEntry({ n, route, go }: { n: NavItem; route: Route; go: (r: Route) => void }) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton tooltip={n.title}
        isActive={route.menu === n.menu && !n.items.length} className="font-medium"
        onClick={() => go({ menu: n.menu, page: n.items[0]?.page ?? "painel" })}>
        <n.icon />
        <span>{n.title}</span>
      </SidebarMenuButton>
      {!!n.children?.length && (
        // Second level: a line from Empresa through its children, ending before the next main menu.
        <ul data-sidebar="menu-nested" aria-label={`Dentro de ${n.title}`}
          className="mt-1 ml-3.5 flex min-w-0 translate-x-px flex-col gap-1 border-l border-sidebar-border pl-2.5 group-data-[collapsible=icon]:ml-0 group-data-[collapsible=icon]:translate-x-0 group-data-[collapsible=icon]:border-l-0 group-data-[collapsible=icon]:pl-0">
          {n.children.map((c) => <NavEntry key={c.menu} n={c} route={route} go={go} />)}
        </ul>
      )}
      {!!n.items.length && <SidebarMenuSub>
        {n.items.map((it) => (
          <SidebarMenuSubItem key={it.page}>
            <SidebarMenuSubButton isActive={route.menu === n.menu && route.page === it.page}
              onClick={() => go({ menu: n.menu, page: it.page })} className="cursor-pointer">
              <span>{it.title}</span>
            </SidebarMenuSubButton>
          </SidebarMenuSubItem>
        ))}
      </SidebarMenuSub>}
    </SidebarMenuItem>
  );
}

export function AppSidebar({ route, go, me, version, update, onLogout, onUpdate }: {
  route: Route; go: (r: Route) => void; me: Me; version: string; update: string | null;
  onLogout: () => void; onUpdate: () => void;
}) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" onClick={() => go(HOME)}>
              <img src="assets/redrise-icon-64x64.png" alt="" className="size-8 rounded-lg" />
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-semibold">RedRise</span>
                <span className="text-xs text-muted-foreground">versão {version}</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {NAV.map((n) => <NavEntry key={n.menu} n={n} route={route} go={go} />)}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          {update && (
            <SidebarMenuItem>
              <SidebarMenuButton tooltip={`Atualização ${update}`} onClick={onUpdate} className="text-warn">
                <CircleDot />
                <span>Atualização {update}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <div className="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
              {me.display} ({me.role === "admin" ? "administrador" : "operador"})
            </div>
            <SidebarMenuButton tooltip="Sair" onClick={onLogout}>
              <LogOut />
              <span>Sair</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
