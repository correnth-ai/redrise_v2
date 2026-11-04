// sidebar-03 (shadcn, MIT) adapted: RedRise brand and the singular menus of the
// work order: Empresa, Processo (Ação, Histórico, Kanban), Rotina (Lista,
// Atividade), Configuração (Equipe, Estação, Aplicativo). A main item with sub
// items opens its first one. No demo navigation.
import { Building2, LogOut, Workflow, ListChecks, Settings2, CircleDot } from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarHeader, SidebarMenu, SidebarMenuButton,
  SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem, SidebarRail,
} from "@/components/ui/sidebar";
import type { Me } from "@/data/types";
import { HOME, type Route } from "@/routes";

const NAV: { menu: Route["menu"]; title: string; icon: typeof Workflow; items: { page: string; title: string }[] }[] = [
  { menu: "empresa", title: "Empresa", icon: Building2, items: [] },
  { menu: "processo", title: "Processo", icon: ListChecks, items: [{ page: "acao", title: "Ação" }, { page: "historico", title: "Histórico" }, { page: "kanban", title: "Kanban" }] },
  { menu: "rotina", title: "Rotina", icon: Workflow, items: [{ page: "lista", title: "Lista" }, { page: "atividade", title: "Atividade" }] },
  { menu: "configuracao", title: "Configuração", icon: Settings2, items: [{ page: "equipe", title: "Equipe" }, { page: "estacao", title: "Estação" }, { page: "aplicativo", title: "Aplicativo" }] },
];

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
            {NAV.map((n) => (
              <SidebarMenuItem key={n.menu}>
                <SidebarMenuButton tooltip={n.title}
                  isActive={route.menu === n.menu && !n.items.length} className="font-medium"
                  onClick={() => go({ menu: n.menu, page: n.items[0]?.page ?? "painel" })}>
                  <n.icon />
                  <span>{n.title}</span>
                </SidebarMenuButton>
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
            ))}
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
