import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { WindowControls } from "@/components/window-chrome";
import { JobsSection } from "@/features/legacy";
import { ProcessTable, RoutinesPage } from "@/features/processos";
import { AppError, type Diagnostic } from "@/lib/api";

// TEAM-ACCOUNTS-20261108 items 3, 5, 6, 9 and 11 (component level; the Core rules are in tests/core/test_team_accounts.py).
const api = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api }));
const store: any = {};
vi.mock("@/state", async (orig) => ({ ...(await orig<typeof import("@/state")>()), useStore: () => store }));

const diag = (code: string): Diagnostic => ({ schema: "redrise.diagnostic/1", error_code: code, category: "precondition", what_happened: code, completed: "", pending: "",
  effect_state: "none", next_action: "", retry: "after_fix", details_summary: "", reported_by: "RR-CORE", module_hints: ["RR-CORE"], diagnosis_status: "unconfirmed",
  correlation_id: "c1", boundary: null, version: {}, technical_details: {}, cause: null, params: {} });
const routine = (id: number, name: string, kind = "app_open") => ({ id, name, category: "windows", created_at: "2026-11-08T10:00:00Z", version_id: id, version: 1, kind,
  template_id: null, template_version: null, platform: null, inputs: {}, params: null, config: { target: { kind: "app", name: "Calc" }, isolated: true, origin: "site" } });
const item = (position: number, r: { id: number; name: string; kind: string }, continue_next = true) => ({ position, routine_id: r.id, routine_name: r.name, continue_next, kind: r.kind, config: null });
const R = { a: routine(1, "Abrir A"), b: routine(2, "Abrir B"), c: routine(3, "Avulsa C"), w: routine(4, "Boas-vindas 1", "notepad_step"), f: routine(5, "Revisar", "followup") };
const proc = (id: number, name: string, items: any[], over = {}) => ({ id, name, created_at: "x", updated_at: "x", items, last_execution: null, pending_change: null, system_key: null, ...over });

beforeEach(() => {
  vi.clearAllMocks();
  Object.assign(store, {
    me: { id: 1, role: "admin" }, go: vi.fn(), run: vi.fn(), reload: vi.fn(async () => undefined), changeTick: 0,
    routines: Object.values(R),
    processes: [proc(10, "Fechamento", [item(1, R.a), item(2, R.b)]), proc(11, "Conferência", [item(1, R.b)]),
      proc(12, "Boas-vindas", [item(1, R.w)], { system_key: "boas-vindas" }), proc(13, "Só revisão", [item(1, R.f)])],
    src: { mode: "real", archiveRoutine: vi.fn(async () => undefined), saveProcess: vi.fn(async () => undefined) },
  });
});
const page = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("Rotina › Lista: excluir (item 6)", () => {
  it("a linked routine can be deleted; the dialog names the processes it leaves", async () => {
    const u = userEvent.setup();
    page(<RoutinesPage />);
    const row = screen.getByText("Abrir B").closest("tr")!;
    await u.click(within(row).getByRole("button", { name: "Excluir" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Será retirada dos processos Fechamento, Conferência/)).toBeTruthy();
    await u.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(store.src.archiveRoutine).not.toHaveBeenCalled();
    await u.click(within(row).getByRole("button", { name: "Excluir" }));
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(store.src.archiveRoutine).toHaveBeenCalledWith(2));
    expect(store.reload).toHaveBeenCalled();
  });

  it("the ready-made process keeps its routines", () => {
    page(<RoutinesPage />);
    const row = screen.getByText("Boas-vindas 1").closest("tr")!;
    expect((within(row).getByRole("button", { name: /processo pronto/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("several: never 'Excluir 0' with an eligible one, and a partial failure says exactly what happened", async () => {
    const u = userEvent.setup();
    store.src.archiveRoutine.mockImplementation(async (id: number) => { if (id === 2) throw new AppError(diag("CONFLICT")); });
    page(<RoutinesPage />);
    for (const n of ["Abrir A", "Abrir B", "Avulsa C"]) await u.click(within(screen.getByText(n).closest("tr")!).getByRole("checkbox"));
    await u.click(screen.getByRole("button", { name: "Excluir 3" }));
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Excluir" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Excluídas: Abrir A, Avulsa C.")).toBeTruthy();
    expect(within(dialog).getByText(/Não excluídas \(1\): Abrir B/)).toBeTruthy();
    expect(within(dialog).getByText(/Código: CONFLICT/)).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Tentar de novo" })).toBeTruthy();
    expect(store.src.archiveRoutine).toHaveBeenCalledTimes(3);
  });
});

describe("Processo › Ação: remover vínculos (item 5)", () => {
  it("removes the first and only routine and saves; a composition that cannot start does not offer Executar", async () => {
    const u = userEvent.setup();
    store.processes = [proc(11, "Conferência", [item(1, R.b)]), proc(13, "Só revisão", [item(1, R.f)]), proc(14, "Vazio", [])];
    page(<ProcessTable />);
    for (const [name, why] of [["Só revisão", /follow-up/], ["Vazio", /Sem etapa 1/]] as const) {
      const head = screen.getByText(name).closest("tr")!;
      expect((within(head).getByRole("button", { name: why }) as HTMLButtonElement).disabled).toBe(true);
    }
    await u.click(within(screen.getByText("Conferência").closest("tr")!).getByRole("button", { name: "Editar composição" }));
    const dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("button", { name: "Remover Abrir B do processo" }));
    expect(within(dialog).getByText("Nenhuma rotina vinculada.")).toBeTruthy();
    await u.click(within(dialog).getByRole("button", { name: "Salvar processo" }));
    await waitFor(() => expect(store.src.saveProcess).toHaveBeenCalledWith(11, "Conferência", []));
  });
});

describe("Rotina › Atividade: detalhes das execuções técnicas (item 3)", () => {
  it("only the eye shows and hides the details of its own row, and nothing is run", async () => {
    const u = userEvent.setup();
    const job = (id: string, name: string) => ({ id, created_at: "2026-11-08T10:00:00Z", routine_name: name, version: 1, station_name: "st1", state: "verified", requested_by: "admin", waiting_reason: null });
    api.mockImplementation(async (method: string, path: string) => {
      if (path === "/api/v1/jobs") return [job("j-1", "Abrir A"), job("j-2", "Abrir B")];
      const id = path.split("/").pop();
      return { ...job(id!, id === "j-1" ? "Abrir A" : "Abrir B"), events: [], verified: true, station_name: `estação de ${id}` };
    });
    page(<JobsSection />);
    const row = (await screen.findByText("Abrir A v1")).closest("tr")!;
    await u.click(within(row).getAllByRole("cell")[1]); // the rest of the row does nothing
    expect(screen.queryByText(/Estação estação de j-1/)).toBeNull();
    const eye = within(row).getByRole("button", { name: "Mostrar detalhes" });
    expect(eye.getAttribute("aria-expanded")).toBe("false");
    await u.click(eye);
    expect(await screen.findByText(/Estação estação de j-1/)).toBeTruthy();
    expect(within(row).getByRole("button", { name: "Ocultar detalhes" }).getAttribute("aria-expanded")).toBe("true");
    const rowB = screen.getAllByText("Abrir B v1")[0].closest("tr")!;
    within(rowB).getByRole("button", { name: "Mostrar detalhes" }).focus();
    await u.keyboard("{Enter}");
    expect(await screen.findByText(/Estação estação de j-2/)).toBeTruthy();
    expect(screen.queryByText(/Estação estação de j-1/)).toBeNull();
    await u.click(within(rowB).getByRole("button", { name: "Ocultar detalhes" }));
    expect(screen.queryByText(/Estação estação de j-2/)).toBeNull();
    expect(api.mock.calls.every(([method]) => method === "GET")).toBe(true);
  });
});

describe("Controles da janela (item 11)", () => {
  it("green maximizes, yellow minimizes, red closes, in that order", async () => {
    const w = { minimize: vi.fn(async () => undefined), toggleMaximize: vi.fn(async () => undefined), close: vi.fn(async () => undefined),
      isMaximized: vi.fn(async () => false), onResized: vi.fn(async () => () => undefined) };
    (window as any).__TAURI__ = { window: { getCurrentWindow: () => w }, core: { invoke: vi.fn() } };
    try {
      render(<WindowControls />);
      const buttons = within(screen.getByRole("group", { name: "Controles da janela" })).getAllByRole("button");
      expect(buttons.map((b) => b.getAttribute("aria-label"))).toEqual(["Maximizar", "Minimizar", "Fechar"]);
      expect(buttons.map((b) => b.getAttribute("title"))).toEqual(["Maximizar", "Minimizar", "Fechar"]);
      expect(buttons.map((b) => b.querySelector("span")!.className.match(/bg-\[#\w+\]/)![0])).toEqual(["bg-[#28C840]", "bg-[#FEBC2E]", "bg-[#FF5F57]"]);
      for (const b of buttons) await userEvent.click(b);
      expect([w.toggleMaximize.mock.calls.length, w.minimize.mock.calls.length, w.close.mock.calls.length]).toEqual([1, 1, 1]);
    } finally { delete (window as any).__TAURI__; }
  });
});

describe("Sidebar (item 9)", () => {
  it("Processo and Rotina sit under Empresa; Configuração stays apart; every route still opens", async () => {
    const go = vi.fn();
    window.matchMedia ??= ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })) as any;
    render(<TooltipProvider><SidebarProvider><AppSidebar route={{ menu: "empresa", page: "painel" }} go={go} me={{ id: 1, username: "a", display: "A", role: "admin" }}
      version="x" update={null} onLogout={() => undefined} onUpdate={() => undefined} /></SidebarProvider></TooltipProvider>);
    const nested = screen.getByRole("list", { name: "Dentro de Empresa" });
    expect(within(nested).getByRole("button", { name: "Processo" })).toBeTruthy();
    expect(within(nested).getByRole("button", { name: "Rotina" })).toBeTruthy();
    expect(within(nested).getByText("Kanban")).toBeTruthy();
    expect(within(nested).queryByText("Configuração")).toBeNull();
    expect(within(nested).queryByText("Equipe")).toBeNull();
    await userEvent.click(within(nested).getByText("Atividade"));
    expect(go).toHaveBeenLastCalledWith({ menu: "rotina", page: "atividade" });
    await userEvent.click(screen.getByRole("button", { name: "Configuração" }));
    expect(go).toHaveBeenLastCalledWith({ menu: "configuracao", page: "equipe" });
    await userEvent.click(screen.getByRole("button", { name: "Empresa" }));
    expect(go).toHaveBeenLastCalledWith({ menu: "empresa", page: "painel" });
  });
});
