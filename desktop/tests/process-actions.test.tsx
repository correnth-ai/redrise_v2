import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { deleteConfirmed, ProcessesPage, ProcessTable } from "@/features/processos";
import { StationsPage } from "@/features/configuracoes";
import { AppError, type Diagnostic } from "@/lib/api";

// PROCESS-ACTIONS-20261111 items 1-3 at component level; the Core's rules are in tests/core/test_process_actions.py.
vi.setConfig({ testTimeout: 30_000 });
const api = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api, call: vi.fn(async () => null) }));
const store: any = {};
vi.mock("@/state", async (orig) => ({ ...(await orig<typeof import("@/state")>()), useStore: () => store }));
vi.mock("@/hooks/use-summary", () => ({ useExecutionSummary: () => ({ summary: null, error: null }) }));

const diag = (code: string, params = {}): Diagnostic => ({ schema: "redrise.diagnostic/1", error_code: code, category: "precondition", what_happened: code, completed: "", pending: "",
  effect_state: "none", next_action: "", retry: "after_fix", details_summary: "", reported_by: "RR-CORE", module_hints: ["RR-CORE"], diagnosis_status: "unconfirmed",
  correlation_id: "c1", boundary: null, version: {}, technical_details: {}, cause: null, params });
const item = (position: number, id: number, name: string, kind = "app_open") => ({ position, routine_id: id, routine_name: name, continue_next: true, kind, config: null });
const proc = (id: number, name: string, over: any = {}) => ({ id, name, created_at: "x", updated_at: "x", items: [item(1, id * 10, `Rotina ${id}`)],
  last_execution: null, pending_change: null, system_key: null, last_success_at: null, ...over });
const WELCOME = proc(1, "Boas-vindas", { system_key: "boas-vindas", items: [item(1, 11, "Abrir e identificar", "notepad_step"), item(2, 12, "Digitar e salvar", "notepad_step"), item(3, 13, "Fechar e verificar", "notepad_step")] });
const page = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const rowOf = (name: string) => screen.getAllByText(name).map((x) => x.closest("tr")).find(Boolean)!;
const actionsOf = (name: string) => within(rowOf(name)).getAllByRole("button").map((b) => b.getAttribute("aria-label")).filter((l) => l && !/rotinas de/.test(l));

beforeEach(() => {
  vi.clearAllMocks();
  for (const k of Object.keys(store)) delete store[k];
  Object.assign(store, { me: { id: 1, role: "admin" }, go: vi.fn(), run: vi.fn(), reload: vi.fn(async () => undefined), changeTick: 0, error: null, reviews: [],
    routines: [{ id: 50, name: "Solta Bloco", kind: "notepad_step", category: "windows", version: 1, config: { step: "open", isolated: false }, created_at: "x" },
      { id: 51, name: "Solta App", kind: "app_open", category: "windows", version: 1, config: { isolated: true }, created_at: "x" }],
    processes: [WELCOME, proc(2, "Fechamento")], executions: [],
    src: { mode: "real", archiveProcess: vi.fn(async (id: number) => ({ archived: true, already: false, process_id: id })), schedules: vi.fn(async () => []),
      integrateRoutine: vi.fn(async () => undefined) } });
});

describe("Processo › Ação: ações por ícone (item 1)", () => {
  it("every process, Boas-vindas included, has the six actions in order; the trash is left of the pencil", () => {
    page(<ProcessTable />);
    const six = (n: string) => ["Executar " + n, "Agendar", "Integrar rotina avulsa", "Substituir etapa 1", "Excluir " + n, "Editar composição"];
    expect(actionsOf("Boas-vindas")).toEqual(six("Boas-vindas"));
    expect(actionsOf("Fechamento")).toEqual(six("Fechamento"));
    for (const b of within(rowOf("Boas-vindas")).getAllByRole("button")) expect((b as HTMLButtonElement).disabled).toBe(false);
  });

  it("an action that cannot work says why; an operator only executes", () => {
    store.processes = [proc(3, "Vazio", { items: [] }), proc(4, "Rodando", { last_execution: { id: "e", state: "running", outcome: null, end_reason: null, created_at: "x" } }),
      proc(5, "Em revisão", { last_execution: { id: "e", state: "waiting_review", outcome: null, end_reason: null, created_at: "x" } }), proc(6, "Pendente", { pending_change: "q1" })];
    const view = page(<ProcessTable />);
    const off = (name: string) => within(rowOf(name)).getAllByRole("button").filter((b) => (b as HTMLButtonElement).disabled).map((b) => b.getAttribute("aria-label"));
    expect(off("Vazio")).toEqual(["Executar: sem etapa 1 para executar", "Agendar: sem etapa 1 para executar", "Sem etapa 1 para substituir"]);
    expect(off("Rodando")).toEqual(["Em execução: aguarde terminar", "Em execução: aguarde terminar para excluir"]);
    expect(off("Em revisão")).toEqual(["Em execução: aguarde terminar", "Aguardando revisão: conclua a revisão para excluir"]);
    expect(off("Pendente")).toEqual(["Já há substituição pendente"]);
    store.me = { id: 9, role: "operator" };
    view.rerender(<TooltipProvider><ProcessTable /></TooltipProvider>);
    expect(actionsOf("Pendente")).toEqual(["Executar Pendente"]);
  });

  it("Play opens the execution dialog of that process; Processo › Ação has no Nova execução and no Execuções recentes", async () => {
    const u = userEvent.setup();
    store.executions = [{ id: "e1", process_id: 2, process_name: "Fechamento", station_name: "st", requested_by: "x", state: "finished", outcome: "verified", steps: [], created_at: "2026-11-12T10:00:00Z" }];
    page(<ProcessesPage />);
    await u.click(within(rowOf("Fechamento")).getByRole("button", { name: "Executar Fechamento" }));
    expect(store.run).toHaveBeenCalledWith({ kind: "process", id: 2 });
    expect(screen.queryByRole("button", { name: /Nova execução/ })).toBeNull();
    expect(screen.queryByText("Execuções recentes")).toBeNull();
    expect(screen.queryByRole("region", { name: "Execuções recentes" })).toBeNull();
    expect(screen.getByRole("region", { name: "Agendamentos" })).toBeTruthy(); // Ação ends with processes and schedules
  });

  it("the integrator offers the Boas-vindas kind of routine too", async () => {
    const u = userEvent.setup();
    page(<ProcessTable />);
    await u.click(within(rowOf("Fechamento")).getByRole("button", { name: "Integrar rotina avulsa" }));
    const dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("combobox"));
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(expect.arrayContaining([expect.stringContaining("Solta Bloco"), expect.stringContaining("Solta App")]));
  });
});

describe("Processo › Ação: excluir só o processo (item 2)", () => {
  it("the word is compared trimmed and without case; anything else is refused", () => {
    for (const w of ["confirmado", "CONFIRMADO", "CoNfIrMaDo", "  Confirmado  "]) expect(deleteConfirmed(w)).toBe(true);
    for (const w of ["", "  ", "confirma", "Confirmado!", "confirmado sim", "Confirmad", "nao confirmado"]) expect(deleteConfirmed(w)).toBe(false);
  });

  it("the trash opens the literal question naming the process; typing only enables Excluir; it deletes by id once", async () => {
    const u = userEvent.setup();
    let finish!: () => void;
    store.src.archiveProcess = vi.fn((id: number) => new Promise((r) => { finish = () => r({ archived: true, already: false, process_id: id }); }));
    page(<ProcessTable />);
    await u.click(within(rowOf("Boas-vindas")).getByRole("button", { name: "Excluir Boas-vindas" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Confirma exclusão do processo? As rotinas não serão excluídas.")).toBeTruthy();
    expect(within(dialog).getByText("Boas-vindas", { selector: "b" })).toBeTruthy();
    const box = within(dialog).getByLabelText("Digite Confirmado para excluir");
    const del = within(dialog).getByRole("button", { name: "Excluir" }) as HTMLButtonElement;
    expect(del.disabled).toBe(true);
    for (const wrong of ["confirma", "Confirmado!", "x"]) {
      await u.clear(box); await u.type(box, wrong);
      expect(del.disabled).toBe(true);
      await u.keyboard("{Enter}"); // Enter on an invalid field submits nothing
    }
    expect(store.src.archiveProcess).not.toHaveBeenCalled();
    await u.clear(box); await u.type(box, "  CoNfIrMaDo ");
    expect(del.disabled).toBe(false);
    expect(store.src.archiveProcess).not.toHaveBeenCalled(); // typing alone deletes nothing
    await u.keyboard("{Enter}");
    expect(store.src.archiveProcess).toHaveBeenCalledWith(1, "  CoNfIrMaDo ");
    const busy = within(dialog).getByRole("button", { name: "Excluindo…" }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    await u.click(busy); await u.keyboard("{Enter}");
    expect(store.src.archiveProcess).toHaveBeenCalledTimes(1); // no double submission
    finish();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(store.reload).toHaveBeenCalled();
  });

  it("Cancel, X and Escape change nothing; opening again (or another process) starts empty", async () => {
    const u = userEvent.setup();
    page(<ProcessTable />);
    for (const how of ["cancel", "x", "escape"]) {
      await u.click(within(rowOf("Fechamento")).getByRole("button", { name: "Excluir Fechamento" }));
      const dialog = await screen.findByRole("dialog");
      const box = within(dialog).getByLabelText("Digite Confirmado para excluir") as HTMLInputElement;
      expect(box.value).toBe("");
      await u.type(box, "confirmado");
      if (how === "cancel") await u.click(within(dialog).getByRole("button", { name: "Cancelar" }));
      else if (how === "x") await u.click(dialog.querySelector<HTMLElement>("[data-slot=dialog-close]")!);
      else await u.keyboard("{Escape}");
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    }
    await u.click(within(rowOf("Boas-vindas")).getByRole("button", { name: "Excluir Boas-vindas" }));
    expect((within(await screen.findByRole("dialog")).getByLabelText("Digite Confirmado para excluir") as HTMLInputElement).value).toBe("");
    expect(store.src.archiveProcess).not.toHaveBeenCalled();
  });

  it("a refusal keeps the process and shows the reason in the dialog", async () => {
    const u = userEvent.setup();
    store.src.archiveProcess = vi.fn(async () => { throw new AppError(diag("PROCESS-BUSY", { process: "Fechamento" })); });
    page(<ProcessTable />);
    await u.click(within(rowOf("Fechamento")).getByRole("button", { name: "Excluir Fechamento" }));
    const dialog = await screen.findByRole("dialog");
    await u.type(within(dialog).getByLabelText("Digite Confirmado para excluir"), "Confirmado");
    await u.click(within(dialog).getByRole("button", { name: "Excluir" }));
    expect((await within(dialog).findAllByText(/em andamento ou aguardando revisão/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(rowOf("Fechamento")).toBeTruthy();
  });
});

describe("Configuração › Estação: revogar por ícone com confirmação", () => {
  it("the icon asks first with words; Cancelar sends nothing; Revogar sends once", async () => {
    const u = userEvent.setup();
    const st = (id: number, over = {}) => ({ id, name: `est-${id}`, is_host: false, platform: "windows-x86_64", online: true, session_state: "ready", session_reason: null, revoked: false, current: false, browsers: [], ...over });
    store.src = { mode: "real", stations: vi.fn(async () => [st(1, { current: true }), st(2)]) };
    api.mockImplementation(async () => ({ ok: true }));
    page(<StationsPage />);
    const row = (await screen.findByText("est-2")).closest("tr")!;
    expect((within((await screen.findByText("est-1")).closest("tr")!).getByRole("button", { name: "Revogar" }) as HTMLButtonElement).disabled).toBe(true);
    await u.click(within(row).getByRole("button", { name: "Revogar" }));
    let dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/execuções aguardando nela serão recusadas/)).toBeTruthy();
    await u.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(api.mock.calls.filter(([m]) => m === "DELETE")).toHaveLength(0);
    await u.click(within(row).getByRole("button", { name: "Revogar" }));
    dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("button", { name: "Revogar" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("DELETE", "/api/v1/stations/2"));
    expect(api.mock.calls.filter(([m]) => m === "DELETE")).toHaveLength(1);
  });
});
