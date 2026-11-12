// DEMONSTRATION FIXTURES (G52/R13). Loaded only by `vite --mode demo`; every
// screen shows a "Demonstração" badge. Names, numbers and progress are
// fictitious and never written to the Core, the database or any evidence of
// automation. Progress is a declared local simulation, not a verification.
import type { DataSource } from "./source";
import { groupOf, type Group } from "./status";
import type { BrowserConfig, Execution, ExecutionStep, JobState, Process, Routine, Station } from "./types";

const now = () => new Date().toISOString();
const ago = (min: number) => new Date(Date.now() - min * 60000).toISOString();

let routines: Routine[] = [
  r(1, "Abrir portal de pedidos", { origin: "site", browser: "msedge", url: "https://pedidos.exemplo.test/", path: null, isolated: true }),
  r(2, "Abrir manual local", { origin: "html", browser: null, url: null, path: "C:\\Exemplos\\manual.html", isolated: true }),
  r(3, "Abrir painel financeiro", { origin: "site", browser: "chrome", url: "https://financeiro.exemplo.test/painel", path: null, isolated: false }),
  r(4, "Abrir relatório diário", { origin: "site", browser: "chrome", url: "https://relatorios.exemplo.test/diario", path: null, isolated: true }),
];

function r(id: number, name: string, config: BrowserConfig): Routine {
  return { id, name, category: "browser", created_at: ago(3000 - id), version_id: id * 10, version: 1, kind: "browser_open",
    template_id: null, template_version: null, platform: null, inputs: {}, params: null, config };
}

let processes: Process[] = [
  p(1, "Conferir pedidos do dia", [[1, true], [3, true], [4, false]]),
  p(2, "Consultar manual", [[2, false]]),
  p(3, "Fechamento financeiro", [[3, true], [4, true]]),
];

function p(id: number, name: string, items: [number, boolean][]): Process {
  return { id, name, created_at: ago(2000), updated_at: ago(100), last_execution: null,
    items: items.map(([rid, cont], i) => {
      const rt = routines.find((x) => x.id === rid)!;
      return { position: i + 1, routine_id: rid, routine_name: rt.name, continue_next: cont, kind: rt.kind, config: rt.config };
    }) };
}

const stations: Station[] = [
  { id: 1, name: "servidor", is_host: true, platform: "windows-x86_64", categories: ["windows", "browser"], runner_version: "demo",
    session_state: "ready", session_reason: null, last_seen_at: now(), revoked: false, online: true,
    browsers: [
      { id: "msedge", name: "Microsoft Edge", path: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", version: "0.0 (demo)", source: "demo", homologated: false },
      { id: "chrome", name: "Google Chrome", path: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", version: "0.0 (demo)", source: "demo", homologated: false },
    ] },
];

function steps(proc: Process, upto: number, last: JobState): ExecutionStep[] {
  return proc.items.map((it) => ({ position: it.position, routine_id: it.routine_id, routine_version_id: it.routine_id * 10,
    name: it.routine_name, continue_next: it.continue_next, job_id: it.position <= upto ? `demo-${it.position}` : null,
    state: it.position < upto ? "verified" : it.position === upto ? last : null, verified: it.position < upto || (it.position === upto && last === "verified"),
    error_code: it.position === upto && last === "failed" ? "BROWSER-OPEN-UNCONFIRMED" : null,
    started_at: it.position <= upto ? ago(30 - it.position) : null, finished_at: it.position < upto ? ago(29 - it.position) : null }));
}

let executions: Execution[] = [
  ex("e3", processes[2], 1, "failed", "finished", "not_verified", 240),
  ex("e2", processes[1], 1, "verified", "finished", "continuation_off", 90),
  ex("e1", processes[0], 2, "running", "running", null, 2),
];

function ex(id: string, proc: Process, upto: number, last: JobState, state: "running" | "finished", end: string | null, min: number): Execution {
  return { id: `00000000-0000-4000-8000-0000000000${id.slice(1).padStart(2, "0")}`, request_id: id, process_id: proc.id,
    process_name: proc.name, station_id: 1, station_name: "servidor", requested_by: "demo", state,
    outcome: state === "finished" ? last : null, end_reason: end, context: {}, correlation_id: "demo", created_at: ago(min),
    finished_at: state === "finished" ? ago(min - 1) : null, steps: steps(proc, upto, last) };
}

/** Declared simulation: advances the running demo execution one step at a time. */
function simulate(): void {
  for (const e of executions) {
    if (e.state !== "running") continue;
    const cur = e.steps.find((s) => s.state === "running" || s.state === "queued");
    if (!cur) continue;
    if (cur.state === "queued") { cur.state = "running"; cur.started_at = now(); continue; }
    cur.state = "verified"; cur.verified = true; cur.finished_at = now();
    const next = e.steps.find((s) => s.position === cur.position + 1);
    if (cur.continue_next && next) { next.job_id = `demo-${next.position}`; next.state = "queued"; }
    else { e.state = "finished"; e.outcome = "verified"; e.end_reason = next ? "continuation_off" : "sequence_end"; e.finished_at = now(); }
  }
}
setInterval(simulate, 4000);

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

export const demoSource: DataSource = {
  mode: "demo",
  me: async () => ({ id: 1, username: "demo", display: "Pessoa de demonstração", role: "admin" }),
  routines: async () => clone(routines),
  processes: async () => clone(processes.map((x) => ({ ...x, last_execution: (() => {
    const e = executions.find((y) => y.process_id === x.id);
    return e ? { id: e.id, state: e.state, outcome: e.outcome, end_reason: e.end_reason, created_at: e.created_at } : null;
  })(), last_success_at: executions.filter((y) => y.process_id === x.id && y.state === "finished" && y.outcome === "verified" && y.finished_at)
    .map((y) => y.finished_at!).sort().at(-1) ?? null }))),
  executions: async () => clone(executions),
  async kanban(day) { // the demonstration's day is the browser's
    const today = new Date().toLocaleDateString("sv-SE");
    const d = day ?? today;
    const seen = new Set<number>();
    const rows = executions.filter((e) => e.process_id !== null && new Date(e.created_at).toLocaleDateString("sv-SE") === d)
      .filter((e) => !seen.has(e.process_id!) && !!seen.add(e.process_id!));
    return { day: d, today, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, since: d, until: d, executions: clone(rows) };
  },
  async executionSummary() { // same groups as the Core, over the demonstration records
    const since = Date.now() - 30 * 86400000;
    const shown = executions.filter((e) => Date.parse(e.created_at) >= since);
    const n = (g: Group) => shown.filter((e) => groupOf(e) === g).length;
    return { days: 30, since: new Date(since).toISOString(), until: now(), total: shown.length,
      running: n("running"), waiting: n("waiting"), attention: n("attention"), verified: n("verified") };
  },
  executionsSince: async (days) => clone(executions.filter((e) => Date.parse(e.created_at) >= Date.now() - days * 86400000)),
  stations: async () => clone(stations),
  storage: async () => ({ db_bytes: 48_300_000, counts: { routines: routines.length, processes: processes.length,
    executions: executions.length, jobs: executions.reduce((n, e) => n + e.steps.filter((s) => s.job_id).length, 0) },
    local: { data_bytes: 12_600_000, logs_bytes: 2_100_000 } }),
  apps: async () => ({ apps: [{ id: "demo!calc", name: "Calculadora" }, { id: "demo!bloco", name: "Bloco de Notas" }, { id: "browser:msedge", name: "Microsoft Edge", browser_id: "msedge" }] }),
  pickFile: async () => "C:\\Exemplos\\planilha.xlsx",
  async createRoutine(name, _category, version, link) {
    const id = Math.max(0, ...routines.map((x) => x.id)) + 1;
    routines = [...routines, { ...r(id, name, version.config as any), kind: version.kind }];
    if (link) processes = processes.map((x) => (x.id === link.process_id ? p(x.id, x.name, [...x.items.map((i) => [i.routine_id, true] as [number, boolean]), [id, true]]) : x));
    return id;
  },
  async addRoutineVersion(id, name, version) {
    routines = routines.map((x) => (x.id === id ? { ...x, name, config: version.config as any, version: x.version + 1 } : x));
  },
  prepareRoutine: async () => ({ id: "demo-prep", mode: "prepare", state: "verified", events: ["session", "target", "launch"].map((c) => ({ at: now(), state: "check", detail: { id: c, state: "ok" } })) }),
  testRoutine: async () => ({ id: "demo-test", mode: "test", state: "verified" }),
  job: async (id) => ({ id, state: "verified" }),
  cancelJob: async () => undefined,
  members: async () => [{ id: 1, display: "Pessoa de demonstração", username: "demo", active: true }],
  execution: async (id) => clone(executions.find((e) => e.id === id) ?? executions[0]),
  reviews: async () => [],
  approveReview: async () => undefined,
  notifications: async () => ({ unseen: 0, items: [] }),
  markNotificationSeen: async () => undefined,
  openReportFolder: async () => undefined,
  changes: () => new Promise(() => undefined), // the demonstration has its own simulation
  stepChanges: async () => [],
  requestStepChange: async () => undefined,
  approveStepChange: async () => undefined,
  cancelStepChange: async () => undefined,
  async integrateRoutine(processId, routineId) {
    processes = processes.map((x) => (x.id === processId ? p(x.id, x.name, [...x.items.map((i) => [i.routine_id, true] as [number, boolean]), [routineId, true]]) : x));
  },
  async archiveRoutine(id) {
    routines = routines.filter((x) => x.id !== id);
  },
  async archiveProcess(id, confirm) {
    if (confirm.trim().toLowerCase() !== "confirmado") throw new Error("Confirmação incorreta.");
    const target = processes.find((x) => x.id === id);
    processes = processes.filter((x) => x.id !== id);
    return { archived: true, already: !target, process_id: id, name: target?.name ?? "", routines: target?.items.map((i) => i.routine_id) ?? [],
      schedules_disabled: 0, changes_cancelled: 0 };
  },
  async saveProcess(id, name, items) {
    const pid = id ?? Math.max(0, ...processes.map((x) => x.id)) + 1;
    const np = p(pid, name, items.map((i) => [i.routine_id, i.continue_next]));
    processes = id === null ? [...processes, np] : processes.map((x) => (x.id === id ? np : x));
  },
  async startExecution(req) {
    const proc = req.process_id ? processes.find((x) => x.id === req.process_id)! : (() => {
      const rt = routines.find((x) => x.id === req.routine_id)!;
      if (!rt.config?.isolated) throw new Error("Rotina não permite execução isolada.");
      return p(0, rt.name, [[rt.id, false]]);
    })();
    const prior = executions.find((e) => e.request_id === req.request_id);
    if (prior) return clone(prior);
    const e = ex(`e${executions.length + 1}`, proc, 1, "queued", "running", null, 0);
    e.request_id = req.request_id;
    e.process_id = req.process_id ?? null;
    e.process_name = req.process_id ? proc.name : null;
    executions = [e, ...executions];
    return clone(e);
  },
  // Scheduling is shown empty in the demonstration: the next time of a schedule exists only on a real Core.
  async schedules() { return []; },
  async previewSchedule() { throw new Error("Agendamento indisponível na demonstração."); },
  async createSchedule() { throw new Error("Agendamento indisponível na demonstração."); },
  async updateSchedule() { throw new Error("Agendamento indisponível na demonstração."); },
  async deleteSchedule() { throw new Error("Agendamento indisponível na demonstração."); },
};
