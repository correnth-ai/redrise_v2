// Fictional numbers for the Empresa page only (authorized by the work order,
// always shown with the "Dados demonstrativos" badge). Nothing here comes from
// or goes to the Core, and it proves no integration or execution.
export const TIMELINE = {
  total: 312,
  months: ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago"],
  rows: [
    { who: "Financeiro", start: 0.4, end: 3.1, tone: "bg-primary" },
    { who: "Compras", start: 1.6, end: 4.4, tone: "bg-info" },
    { who: "Vendas", start: 2.2, end: 6.2, tone: "bg-warn" },
    { who: "Logística", start: 4.1, end: 7.0, tone: "bg-ok" },
    { who: "Atendimento", start: 5.2, end: 7.8, tone: "bg-primary" },
  ],
};

export const PROJECTS = [
  { name: "Fechamento mensal", done: 84, total: 120, tone: "text-primary bg-primary/10" },
  { name: "Conciliação de pedidos", done: 58, total: 96, tone: "text-info bg-info/10" },
  { name: "Cadastro de fornecedores", done: 31, total: 40, tone: "text-warn bg-warn/10" },
  { name: "Relatórios semanais", done: 120, total: 150, tone: "text-ok bg-ok/10" },
];

export const WEEK = [
  { day: "Seg", value: 42 }, { day: "Ter", value: 58 }, { day: "Qua", value: 51 }, { day: "Qui", value: 73 },
  { day: "Sex", value: 66 }, { day: "Sáb", value: 24 }, { day: "Dom", value: 12 },
];

export const RATE = { value: 92.8, delta: 6.3, spark: [71, 74, 73, 79, 82, 80, 86, 88, 87, 92] };

export const RESOURCES = [
  { name: "Armazenamento", used: 68, detail: "136 GB de 200 GB" },
  { name: "Estações ativas", used: 75, detail: "6 de 8" },
  { name: "Rotinas publicadas", used: 44, detail: "44 de 100" },
];

export const PERFORMANCE: Record<string, { label: string; value: string; delta: string }[]> = {
  "Mês": [{ label: "Horas economizadas", value: "418 h", delta: "+12%" }, { label: "Execuções", value: "2.340", delta: "+8%" }, { label: "Sem intervenção", value: "91%", delta: "+3%" }],
  "Trimestre": [{ label: "Horas economizadas", value: "1.206 h", delta: "+21%" }, { label: "Execuções", value: "6.915", delta: "+17%" }, { label: "Sem intervenção", value: "89%", delta: "+5%" }],
  "Ano": [{ label: "Horas economizadas", value: "4.380 h", delta: "+34%" }, { label: "Execuções", value: "26.104", delta: "+29%" }, { label: "Sem intervenção", value: "87%", delta: "+9%" }],
};

export type ActivityStatus = "Concluída" | "Em andamento" | "Atenção";
export const ACTIVITIES: { activity: string; team: string; owner: string; when: string; status: ActivityStatus }[] = [
  { activity: "Emitir notas do dia", team: "Financeiro", owner: "Ana Prado", when: "02/11 09:12", status: "Concluída" },
  { activity: "Atualizar preços", team: "Vendas", owner: "Bruno Lima", when: "02/11 09:40", status: "Em andamento" },
  { activity: "Baixar pedidos", team: "Compras", owner: "Carla Dias", when: "02/11 10:05", status: "Concluída" },
  { activity: "Conferir entregas", team: "Logística", owner: "Davi Rocha", when: "02/11 10:31", status: "Atenção" },
  { activity: "Responder chamados", team: "Atendimento", owner: "Elisa Melo", when: "02/11 11:02", status: "Em andamento" },
  { activity: "Conciliar extratos", team: "Financeiro", owner: "Ana Prado", when: "01/11 16:20", status: "Concluída" },
  { activity: "Gerar etiquetas", team: "Logística", owner: "Davi Rocha", when: "01/11 15:48", status: "Concluída" },
  { activity: "Revisar cadastro", team: "Compras", owner: "Carla Dias", when: "01/11 14:13", status: "Atenção" },
  { activity: "Enviar propostas", team: "Vendas", owner: "Bruno Lima", when: "01/11 11:37", status: "Concluída" },
  { activity: "Fechar caixa", team: "Financeiro", owner: "Ana Prado", when: "31/10 18:02", status: "Concluída" },
];
