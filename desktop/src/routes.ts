export type Menu = "empresa" | "rotina" | "processo" | "configuracao";
export interface Route { menu: Menu; page: string; id?: any; process?: number; /** Opens the same target again. */ nonce?: number;
  /** Processo › Histórico limited to executions started in the last `days` days (the Empresa summary period). */ days?: number }

export const HOME: Route = { menu: "empresa", page: "painel" };

export const PAGE_TITLE: Record<string, string> = {
  "empresa/painel": "Empresa",
  "rotina/lista": "Rotina › Lista", "rotina/atividade": "Rotina › Atividade", "rotina/nova": "Nova Rotina", "rotina/editar": "Editar rotina",
  "rotina/gravacao": "Nova rotina por gravação", "rotina/modelos": "Nova rotina a partir de modelo", "rotina/executar-legada": "Executar rotina",
  "processo/acao": "Processo › Ação", "processo/historico": "Processo › Histórico", "processo/kanban": "Processo › Kanban",
  "configuracao/equipe": "Configuração › Equipe", "configuracao/nova-conta": "Nova Conta", "configuracao/estacao": "Configuração › Estação", "configuracao/aplicativo": "Configuração › Aplicativo",
};

/** Smaller title with the page name, under the main title of the menu. */
export const SUB_TITLE: Record<string, string> = {
  "rotina/lista": "Lista", "rotina/atividade": "Atividade", "rotina/nova": "Nova Rotina", "rotina/editar": "Editar rotina",
  "rotina/gravacao": "Nova rotina por gravação", "rotina/modelos": "Nova rotina a partir de modelo", "rotina/executar-legada": "Executar rotina",
  "processo/acao": "Ação", "processo/historico": "Histórico", "processo/kanban": "Kanban",
  "configuracao/equipe": "Equipe", "configuracao/nova-conta": "Nova Conta", "configuracao/estacao": "Estação", "configuracao/aplicativo": "Aplicativo",
};

// Internal links of earlier versions keep working; ids of routines, processes and results do not change.
const ALIASES: Record<string, [Menu, string]> = {
  "processos/painel": ["empresa", "painel"], "processos/processos": ["processo", "acao"], "processos/rotinas": ["rotina", "lista"],
  "processos/nova-rotina": ["rotina", "nova"], "processos/editar-rotina": ["rotina", "editar"], "processos/gravacao": ["rotina", "gravacao"],
  "processos/modelos": ["rotina", "modelos"], "processos/executar-legada": ["rotina", "executar-legada"],
  "fluxos/painel": ["processo", "acao"], "fluxos/kanban": ["processo", "kanban"], "fluxos/historico": ["processo", "historico"],
  "configuracoes/painel": ["configuracao", "aplicativo"], "configuracoes/equipe": ["configuracao", "equipe"],
  "configuracoes/estacoes": ["configuracao", "estacao"], "configuracoes/aplicativo": ["configuracao", "aplicativo"],
};

export function canonical(r: { menu: string; page: string; id?: any; process?: number }): Route {
  const a = ALIASES[`${r.menu}/${r.page}`];
  return a ? { ...r, menu: a[0], page: a[1] } : (r as Route);
}
