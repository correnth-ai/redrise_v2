import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ProcessTable } from "@/features/processos";
import { boardExecutions, KanbanPage } from "@/features/fluxos";
import { TeamPage } from "@/features/configuracoes";
import { COLUMN_LABEL, COLUMNS } from "@/data/status";
import { AppError, type Diagnostic } from "@/lib/api";
import { shortWhen } from "@/lib/utils";

// PROCESS-LIST-INSTALLER-20261110 items 1, 3 and 4 at component level. The Core's own rules (last success, latest
// execution per process, self-deactivation) are in tests/core/test_process_list.py; the installed app is proved apart.
vi.setConfig({ testTimeout: 30_000 }); // jsdom renders 100-process tables slowly when the suite runs in parallel
const api = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api, call: vi.fn(async () => null) }));
const store: any = {};
vi.mock("@/state", async (orig) => ({ ...(await orig<typeof import("@/state")>()), useStore: () => store }));

const diag = (code: string): Diagnostic => ({ schema: "redrise.diagnostic/1", error_code: code, category: "communication", what_happened: code, completed: "", pending: "",
  effect_state: "none", next_action: "", retry: "after_fix", details_summary: "", reported_by: "RR-UI", module_hints: ["RR-UI"], diagnosis_status: "unconfirmed",
  correlation_id: "c1", boundary: null, version: {}, technical_details: {}, cause: null, params: {} });
const item = (position: number, id: number, name: string) => ({ position, routine_id: id, routine_name: name, continue_next: true, kind: "app_open", config: null });
const proc = (id: number, over: any = {}) => ({ id, name: `Processo ${String(id).padStart(3, "0")}`, created_at: "x", updated_at: "x",
  items: [item(1, id * 10, `Rotina ${id}.1`), item(2, id * 10 + 1, `Rotina ${id}.2`)], last_execution: null, pending_change: null, system_key: null, last_success_at: null, ...over });
const many = (n: number) => Array.from({ length: n }, (_, i) => proc(i + 1));
const page = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

beforeEach(() => {
  vi.clearAllMocks();
  for (const k of Object.keys(store)) delete store[k];
  Object.assign(store, { me: { id: 1, role: "admin" }, go: vi.fn(), run: vi.fn(), reload: vi.fn(async () => undefined), changeTick: 0, routines: [], error: null,
    processes: [], executions: [], src: { mode: "real" } });
});

const names = () => screen.queryAllByText(/^Processo \d{3}$/).map((x) => x.textContent);
const status = () => screen.getByText(/^(Mostrando|Nenhuma linha)/).textContent;
async function allPages(u: ReturnType<typeof userEvent.setup>) {
  const seen: string[] = [];
  for (;;) {
    seen.push(...(names() as string[]));
    const next = screen.getByRole("button", { name: "Próxima página" }) as HTMLButtonElement;
    if (next.disabled) return seen;
    await u.click(next);
  }
}

describe("Processo › Ação: processos paginados (item 1)", () => {
  it.each([0, 1, 10, 11, 25, 51, 100])("%i processos: total e páginas corretos, sem perder nem repetir", async (n) => {
    const u = userEvent.setup();
    store.processes = many(n);
    page(<ProcessTable />);
    expect(status()).toBe(n ? `Mostrando 1 a ${Math.min(10, n)} de ${n} ${n === 1 ? "linha" : "linhas"}` : "Nenhuma linha");
    expect(screen.getByText(`Página 1 de ${Math.max(1, Math.ceil(n / 10))}`)).toBeTruthy();
    const seen = await allPages(u);
    expect(seen).toEqual(many(n).map((p) => p.name)); // every process once, in the stable order
  }, 30_000);

  it("25 and 50 per page; changing the size goes back to a page that exists", async () => {
    const u = userEvent.setup();
    store.processes = many(51);
    page(<ProcessTable />);
    await u.click(screen.getByRole("button", { name: "Última página" }));
    expect(screen.getByText("Página 6 de 6")).toBeTruthy();
    await u.click(screen.getByRole("combobox", { name: "Linhas por página" }));
    await u.click(await screen.findByRole("option", { name: "50" }));
    expect(screen.getByText("Página 1 de 2")).toBeTruthy();
    expect(names()).toHaveLength(50);
  });

  it("search and filters work on the whole collection, then paginate; Limpar filtros restores it", async () => {
    const u = userEvent.setup();
    store.processes = many(30).map((p) => p.id === 27 ? { ...p, last_execution: { id: "e", state: "running", outcome: null, end_reason: null, created_at: "2026-11-10T10:00:00Z" } } : p);
    page(<ProcessTable />);
    expect(names()).not.toContain("Processo 027");
    await u.type(screen.getByRole("searchbox", { name: "Buscar em Processos" }), "027");
    expect(names()).toEqual(["Processo 027"]);
    await u.click(screen.getByRole("button", { name: /Limpar filtros/ }));
    expect(status()).toBe("Mostrando 1 a 10 de 30 linhas");
    await u.click(screen.getByRole("button", { name: /Filtrar/ }));
    await u.click(await screen.findByRole("menuitemradio", { name: "Em andamento" }));
    await u.keyboard("{Escape}");
    expect(names()).toEqual(["Processo 027"]);
    await u.click(screen.getByRole("button", { name: /Limpar filtros/ }));
    expect(status()).toBe("Mostrando 1 a 10 de 30 linhas");
  });

  it("collapsed on arrival; only the chevron toggles, by mouse and keyboard; actions never toggle; kept across a refresh", async () => {
    const u = userEvent.setup();
    store.processes = many(3);
    const view = page(<ProcessTable />);
    expect(screen.queryByText("1. Rotina 1.1")).toBeNull();
    const toggle = screen.getByRole("button", { name: "Mostrar as rotinas de Processo 001" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    await u.click(toggle);
    expect(screen.getByRole("button", { name: "Ocultar as rotinas de Processo 001" }).getAttribute("aria-expanded")).toBe("true");
    const list = screen.getByRole("list", { name: "Rotinas de Processo 001" });
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent?.split("App")[0]))
      .toEqual(["1. Rotina 1.1", "2. Rotina 1.2"].map((x) => expect.stringContaining(x)) as any);
    await u.click(within(screen.getByText("Processo 002").closest("tr")!).getByRole("button", { name: "Executar processo" }));
    expect(store.run).toHaveBeenCalledWith({ kind: "process", id: 2 });
    expect(screen.queryByRole("list", { name: "Rotinas de Processo 002" })).toBeNull(); // the action did not expand
    screen.getByRole("button", { name: "Mostrar as rotinas de Processo 002" }).focus();
    await u.keyboard("{Enter}");
    expect(screen.getByRole("list", { name: "Rotinas de Processo 002" })).toBeTruthy();
    // A refresh of the same visit (new objects, same ids, a process removed) keeps what was open; the count is processes.
    store.processes = many(3).filter((p) => p.id !== 3).map((p) => ({ ...p }));
    view.rerender(<TooltipProvider><ProcessTable /></TooltipProvider>);
    expect(screen.getByRole("list", { name: "Rotinas de Processo 001" })).toBeTruthy();
    expect(screen.getByRole("list", { name: "Rotinas de Processo 002" })).toBeTruthy();
    expect(status()).toBe("Mostrando 1 a 2 de 2 linhas");
    expect(api).not.toHaveBeenCalled(); // expanding reads and changes nothing
  });

  it("Último sucesso: the Core's date, Nunca, and — when the server does not say; sortable with a stable tie", async () => {
    const u = userEvent.setup();
    const old = "2026-09-01T12:34:00Z";
    store.processes = [
      proc(1, { last_success_at: old, last_execution: { id: "e1", state: "finished", outcome: "failed", end_reason: "not_verified", created_at: "2026-11-10T10:00:00Z" } }),
      proc(2, { last_success_at: null }),
      proc(3, { last_success_at: undefined }),
      proc(4, { last_success_at: old }),
    ];
    page(<ProcessTable />);
    const cell = (id: number) => within(screen.getByText(`Processo 00${id}`).closest("tr")!).getAllByRole("cell")[3];
    expect(cell(1).textContent).toBe(shortWhen(old)); // a later failure keeps the success
    expect(cell(1).textContent).toMatch(/^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/);
    expect(cell(1).querySelector("time")!.getAttribute("title")).toMatch(/\(.+\)$/);
    expect(cell(2).textContent).toBe("Nunca");
    expect(cell(3).textContent).toBe("—");
    await u.click(screen.getByRole("button", { name: "Opções da coluna Último sucesso" }));
    await u.click(await screen.findByRole("menuitem", { name: /Ordem decrescente/ }));
    expect(names()).toEqual(["Processo 001", "Processo 004", "Processo 002", "Processo 003"]); // tie by id, empty last
  });
});

describe("Configuração › Equipe: a própria conta (item 3)", () => {
  const user = (id: number, over = {}) => ({ id, username: `u${id}`, display: `Pessoa ${id}`, full_name: `Pessoa ${id}`, email: `p${id}@x.com.br`, role: "admin", active: true, ...over });
  beforeEach(() => {
    api.mockImplementation(async (method: string, path: string) => {
      if (path === "/api/v1/identity/profile") return { full_name: "x", email: null, username: "x" };
      if (method === "GET" && path === "/api/v1/users") return [user(1), user(2), user(3, { role: "operator", active: false })];
      return { ok: true };
    });
  });
  const row = async (n: number) => (await screen.findAllByText(`Pessoa ${n}`)).at(-1)!.closest("tr")!;

  it("the signed-in account's Desativar stays visible, disabled, with the reason, and sends nothing", async () => {
    const u = userEvent.setup();
    page(<TeamPage />);
    const mine = await row(1);
    const btn = within(mine).getByRole("button", { name: "Desativar" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(document.getElementById(btn.getAttribute("aria-describedby")!)!.textContent).toBe("Você não pode desativar sua própria conta");
    await u.click(btn);
    btn.focus(); await u.keyboard("{Enter} ");
    btn.click(); // a programmatic event too
    expect(api.mock.calls.filter(([m]) => m === "PATCH")).toHaveLength(0);
    expect(screen.queryByText(/Código:/)).toBeNull(); // no red panel for a predictable refusal
    await u.click(within(await row(2)).getByRole("button", { name: "Desativar" })); // another administrator stays manageable
    expect(api).toHaveBeenCalledWith("PATCH", "/api/v1/users/2", { active: false });
  });

  it("follows the session's id, not a name: another signed-in person protects their own row", async () => {
    store.me = { id: 2, role: "admin" };
    page(<TeamPage />);
    expect((within(await row(2)).getByRole("button", { name: "Desativar" }) as HTMLButtonElement).disabled).toBe(true);
    expect((within(await row(1)).getByRole("button", { name: "Desativar" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

// ---------------------------------------------------------------- Kanban
const step = (position: number, name: string, state: string | null, over = {}) => ({ position, routine_id: position, routine_version_id: position, name, continue_next: true,
  job_id: state ? `j${position}` : null, state, verified: state === "verified", error_code: null, started_at: state ? "2026-11-10T10:00:00Z" : null, finished_at: null, ...over });
const exe = (id: string, process_id: number | null, created: string, steps: any[], over = {}) => ({ id, request_id: id, process_id, process_name: process_id ? `Processo ${process_id}` : null,
  station_id: 1, station_name: "servidor-teste", requested_by: "pessoa.a", state: "running", outcome: null, end_reason: null, context: {}, correlation_id: "c",
  created_at: created, finished_at: null, steps, ...over });

describe("Processo › Kanban (item 4)", () => {
  let latest: any[];
  beforeEach(() => {
    latest = [];
    store.processes = [{ id: 1, name: "Processo 1" }, { id: 2, name: "Processo 2" }];
    store.src = { mode: "real", latestExecutions: vi.fn(async () => latest), execution: vi.fn() };
  });

  it("columns left to right, Conferida for verified, sharing the width with a horizontal scroll when narrow", async () => {
    page(<KanbanPage />);
    const sections = await screen.findAllByRole("region");
    const board = sections.find((s) => s.getAttribute("aria-label") === "Quadro de etapas")!;
    expect(COLUMNS.map((c) => COLUMN_LABEL[c])).toEqual(["Aguardando", "Em andamento", "Atenção", "Não executada", "Conferida"]);
    expect(within(board).getAllByRole("heading").map((h) => h.textContent?.replace(/\d+$/, ""))).toEqual(["Aguardando", "Em andamento", "Atenção", "Não executada", "Conferida"]);
    expect(board.className).toContain("overflow-x-auto");
    expect(board.firstElementChild!.className).toContain("grid-cols-[repeat(5,minmax(11rem,1fr))]");
    expect(board.innerHTML).not.toContain("w-60");
  });

  it("a process whose latest execution is beyond the general list still has its cards (read for the board)", async () => {
    latest = [exe("old-1", 2, "2026-01-01T00:00:00Z", [step(1, "Velha", "verified")], { state: "finished", outcome: "verified" })];
    store.executions = [exe("new-1", 1, "2026-11-10T10:00:00Z", [step(1, "Nova", "running")])];
    page(<KanbanPage />);
    expect(await screen.findByText("1. Velha")).toBeTruthy();
    expect(screen.getByText("1. Nova")).toBeTruthy();
    expect(store.src.latestExecutions).toHaveBeenCalled();
  });

  it("boardExecutions: one per process, the newest wins; standalone routines kept; stable order", () => {
    const a = exe("a", 1, "2026-11-10T10:00:00Z", []), b = exe("b", 1, "2026-11-10T11:00:00Z", []), r = exe("r", null, "2026-11-10T09:00:00Z", []);
    expect(boardExecutions([a], [b, r]).map((e) => e.id)).toEqual(["b", "r"]);
    expect(boardExecutions([b], [a]).map((e) => e.id)).toEqual(["b"]); // an older answer never replaces a newer card
  });

  it("clicking a card opens its summary without navigating; Escape and X keep the board; Saber mais opens Histórico", async () => {
    const u = userEvent.setup();
    store.executions = [exe("e1", 1, "2026-11-10T10:00:00Z", [step(1, "Abrir", "failed", { error_code: "TARGET-NOT-FOUND", finished_at: "2026-11-10T10:01:00Z" }), step(2, "Salvar", null)],
      { state: "finished", outcome: "failed", end_reason: "not_verified", finished_at: "2026-11-10T10:01:00Z" })];
    page(<KanbanPage />);
    const card = await screen.findByRole("button", { name: /1\. Abrir/ });
    await u.click(card);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("servidor-teste")).toBeTruthy();
    expect(within(dialog).getByText("pessoa.a")).toBeTruthy();
    expect(within(dialog).getByText("1 de 2")).toBeTruthy();
    expect(store.go).not.toHaveBeenCalled();
    await u.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /1\. Abrir/ })); // focus back on the card
    screen.getByRole("button", { name: /2\. Salvar/ }).focus();
    await u.keyboard("{Enter}");
    const d2 = await screen.findByRole("dialog");
    expect(within(d2).getByText("Interrompida: resultado não verificado")).toBeTruthy(); // why it did not run
    await u.click(d2.querySelector<HTMLElement>("[data-slot=dialog-close]")!); // the X
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(store.go).not.toHaveBeenCalled();
    await u.click(screen.getByRole("button", { name: /1\. Abrir/ }));
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Saber mais" }));
    expect(store.go).toHaveBeenCalledWith({ menu: "processo", page: "historico", id: "e1" });
  });

  it("an open summary follows its own execution: a newer one replacing the cards does not swap it", async () => {
    const u = userEvent.setup();
    const first = exe("e1", 1, "2026-11-10T10:00:00Z", [step(1, "Abrir", "running")]);
    store.executions = [first];
    store.src.execution = vi.fn(async () => ({ ...first, steps: [step(1, "Abrir", "verified")], state: "finished", outcome: "verified" }));
    const view = page(<KanbanPage />);
    await u.click(await screen.findByRole("button", { name: /1\. Abrir/ }));
    expect(within(await screen.findByRole("dialog")).getByText("(Em andamento)")).toBeTruthy();
    store.executions = [exe("e2", 1, "2026-11-10T11:00:00Z", [step(1, "Abrir", "queued")]), first].slice(0, 1); // e1 left the store
    view.rerender(<TooltipProvider><KanbanPage /></TooltipProvider>);
    await waitFor(() => expect(store.src.execution).toHaveBeenCalledWith("e1"));
    const dialog = screen.getByRole("dialog");
    expect(await within(dialog).findByText("(Conferida)")).toBeTruthy(); // the same execution, read by its id
    expect(within(dialog).queryByText("(Aguardando)")).toBeNull();
  });

  it("a failed read keeps the cards and says they may be out of date", async () => {
    store.executions = [exe("e1", 1, "2026-11-10T10:00:00Z", [step(1, "Abrir", "running")])];
    store.src.latestExecutions = vi.fn(async () => { throw new AppError(diag("CORE-UNREACHABLE")); });
    page(<KanbanPage />);
    expect(await screen.findByText(/podem estar desatualizados/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /1\. Abrir/ })).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Em andamento" })).getByText("1")).toBeTruthy(); // counters not zeroed
  });

  it("each store read reads the board again (change feed or periodic): no F5", async () => {
    store.executions = [];
    const view = page(<KanbanPage />);
    await waitFor(() => expect(store.src.latestExecutions).toHaveBeenCalledTimes(1));
    latest = [exe("e9", 2, "2026-11-10T12:00:00Z", [step(1, "Chegou", "queued")])];
    store.executions = [];
    await act(async () => view.rerender(<TooltipProvider><KanbanPage /></TooltipProvider>));
    expect(await screen.findByText("1. Chegou")).toBeTruthy();
  });
});
