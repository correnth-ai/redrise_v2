import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EmpresaPage, verifiedShare } from "@/features/empresa";
import { HistoryPage } from "@/features/fluxos";

// Indicators read real sources only (S2): the store lists and the Core summary. No fixture reaches this page.
const summary = { days: 30, since: "2026-10-08T12:00:00Z", until: "2026-11-07T12:00:00Z", total: 150, running: 120, waiting: 3, attention: 7, verified: 20 };
const station = (id: number, over = {}) => ({ id, name: `st${id}`, is_host: id === 1, platform: "windows-x86_64", categories: ["windows"], runner_version: "x",
  session_state: "ready", session_reason: null, last_seen_at: null, revoked: false, online: true, browsers: null, ...over });
const exec = (id: string, state: string, outcome: string | null) => ({ id, request_id: id, process_id: 1, process_name: `Proc ${id}`, station_id: 1, station_name: "st1",
  requested_by: "admin", state, outcome, end_reason: null, context: {}, correlation_id: "c", created_at: "2026-11-07T10:00:00Z", finished_at: null,
  steps: [{ position: 1, routine_id: 1, routine_version_id: 1, name: "Abrir", continue_next: true, job_id: "j", state: outcome ?? "running", verified: outcome === "verified",
    error_code: null, diagnostic: null, started_at: "2026-11-07T10:00:00Z", finished_at: null }] });

const src = {
  executionSummary: vi.fn(async () => summary as any),
  executionsSince: vi.fn(async () => [exec("p1", "finished", "failed"), exec("p2", "finished", "verified"), exec("p3", "running", null)] as any),
  storage: vi.fn(async () => ({ db_bytes: 2_097_152, counts: { routines: 1, processes: 1, executions: 1, jobs: 1 } })),
  openReportFolder: vi.fn(),
};
const store: any = {};
vi.mock("@/state", () => ({ useStore: () => store }));

beforeEach(() => {
  vi.clearAllMocks();
  Object.assign(store, {
    src, go: vi.fn(), error: null, changeTick: 0, me: { id: 1, role: "admin" },
    processes: [{ id: 1, name: "A" }, { id: 2, name: "B" }],
    stations: [station(1), station(2, { online: false }), station(3, { revoked: true })],
    reviews: [{ id: "r1", status: "pending" }, { id: "r2", status: "approved" }],
    executions: [exec("e1", "finished", "verified"), exec("e2", "running", null)],
  });
});

const tile = (name: RegExp) => screen.getByRole("button", { name });

describe("Empresa", () => {
  it("shows counts from the Core summary, not from the capped execution list", async () => {
    render(<EmpresaPage />);
    await waitFor(() => expect(tile(/Execuções nos últimos 30 dias: 150/)).toBeTruthy());
    expect(tile(/Precisam de atenção: 7/)).toBeTruthy();
    expect(tile(/Em andamento: 120/)).toBeTruthy();
    expect(tile(/Processos cadastrados: 2/)).toBeTruthy();
    expect(tile(/Marcados para mim: 1/)).toBeTruthy();
    expect(tile(/Estações disponíveis: 1 de 2/)).toBeTruthy(); // revoked one is not counted; offline one is not available
    expect(screen.getByText("74% das finalizadas no período")).toBeTruthy();
    expect(await screen.findByText("2 MB")).toBeTruthy();
    expect(screen.queryByText(/demonstrativ/i)).toBeNull();
  });

  it("each indicator opens the list it counts, with the same group and period", async () => {
    const user = userEvent.setup();
    render(<EmpresaPage />);
    await user.click(await screen.findByRole("button", { name: /Precisam de atenção: 7/ }));
    expect(store.go).toHaveBeenLastCalledWith({ menu: "processo", page: "historico", id: "attention", days: 30 });
    await user.click(tile(/Execuções nos últimos 30 dias/));
    expect(store.go).toHaveBeenLastCalledWith({ menu: "processo", page: "historico", id: undefined, days: 30 });
    await user.click(tile(/Estações disponíveis/));
    expect(store.go).toHaveBeenLastCalledWith({ menu: "configuracao", page: "estacao" });
    await user.click(tile(/Marcados para mim/));
    expect(store.go).toHaveBeenLastCalledWith(expect.objectContaining({ menu: "processo", page: "acao", id: "mine" }));
  });

  it("a failed summary shows the diagnostic and no number, never zero", async () => {
    src.executionSummary.mockRejectedValueOnce(new Error("servidor indisponível"));
    render(<EmpresaPage />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    const section = screen.getByRole("region", { name: "Situação das execuções" });
    for (const name of [/Em andamento: —/, /Aguardando revisão: —/, /Precisam de atenção: —/, /Verificadas: —/]) {
      expect(within(section).getByRole("button", { name })).toBeTruthy();
    }
    expect(within(section).queryByText(/% das finalizadas/)).toBeNull();
  });

  it("reads the summary again when the store reads the executions again", async () => {
    const { rerender } = render(<EmpresaPage />);
    await waitFor(() => expect(src.executionSummary).toHaveBeenCalledTimes(1));
    store.executions = [...store.executions];
    rerender(<EmpresaPage />);
    await waitFor(() => expect(src.executionSummary).toHaveBeenCalledTimes(2));
  });

  it("no rate without finished executions", () => {
    expect(verifiedShare({ ...summary, verified: 0, attention: 0 })).toBeNull();
    expect(verifiedShare({ ...summary, verified: 1, attention: 1 })).toBe(50);
  });
});

describe("Histórico with a period", () => {
  it("lists the period rows from the Core and opens on the same group", async () => {
    render(<HistoryPage focus="attention" days={30} />);
    expect(await screen.findByText(/Iniciadas nos últimos 30 dias: 3 execuções/)).toBeTruthy();
    expect(src.executionsSince).toHaveBeenCalledWith(30);
    expect(screen.getByText("Proc p1")).toBeTruthy(); // attention tab: the failed one only
    expect(screen.queryByText("Proc p2")).toBeNull();
    expect(screen.queryByText("Proc e1")).toBeNull(); // the store list is not used for a period
  });
});

describe("Histórico with a period, when the Core fails (review R9)", () => {
  it("a failed re-read keeps the rows already shown, under the error", async () => {
    const { rerender } = render(<HistoryPage focus="all" days={30} />);
    expect(await screen.findByText("Proc p1")).toBeTruthy();
    src.executionsSince.mockRejectedValueOnce(new Error("servidor indisponível"));
    store.executions = [...store.executions];
    rerender(<HistoryPage focus="all" days={30} />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Proc p1")).toBeTruthy();
    expect(screen.queryByText(/Carregando/)).toBeNull();
  });

  it("with nothing read yet, shows the error and no table (not 'loading', not 'none')", async () => {
    src.executionsSince.mockRejectedValueOnce(new Error("servidor indisponível"));
    render(<HistoryPage focus="all" days={30} />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/Carregando/)).toBeNull();
    expect(screen.queryByText("Nenhuma execução.")).toBeNull();
  });
});

describe("Processo › Ação tiles (review R2)", () => {
  it("count the period from the Core, like Empresa, and open the list with the same period", async () => {
    const { ProcessesPage } = await import("@/features/processos");
    Object.assign(store, { routines: [], run: vi.fn(), reload: vi.fn(), stepChanges: [], notifications: { unseen: 0, items: [] },
      processes: [{ id: 1, name: "A", items: [], system_key: null }, { id: 2, name: "B", items: [], system_key: null }] });
    const user = userEvent.setup();
    const { TooltipProvider } = await import("@/components/ui/tooltip");
    render(<TooltipProvider><ProcessesPage /></TooltipProvider>);
    await user.click(await screen.findByRole("button", { name: /Execuções nos últimos 30 dias\s*150/ }));
    expect(store.go).toHaveBeenLastCalledWith({ menu: "processo", page: "historico", id: undefined, days: 30 });
    await user.click(screen.getByRole("button", { name: /Precisam de atenção\s*7/ }));
    expect(store.go).toHaveBeenLastCalledWith({ menu: "processo", page: "historico", id: "attention", days: 30 });
    expect(screen.queryByText("Execuções registradas")).toBeNull(); // the capped list is no longer shown as a total
  });
});
