import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AccountWizard } from "@/features/account-wizard";
import { StationsPage, STATIONS_POLL_MS, TeamPage } from "@/features/configuracoes";
import { AppError, type Diagnostic } from "@/lib/api";

// TEAM-ACCOUNTS-20261108 items 1 and 4. The Core is mocked here; persistence and permissions are proved by
// tests/core/test_team_accounts.py and by the installed-app proof, not by these tests.
const api = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api, call: vi.fn(async () => null) }));
const store: any = {};
vi.mock("@/state", () => ({ useStore: () => store }));

const diag = (code: string): Diagnostic => ({ schema: "redrise.diagnostic/1", error_code: code, category: "precondition", what_happened: code, completed: "", pending: "",
  effect_state: "none", next_action: "", retry: "after_fix", details_summary: "", reported_by: "RR-CORE", module_hints: ["RR-CORE"], diagnosis_status: "unconfirmed",
  correlation_id: "c1", boundary: null, version: {}, technical_details: {}, cause: null, params: {} });
const user = (id: number, over = {}) => ({ id, username: `u${id}`, display: `Pessoa ${id}`, full_name: `Pessoa ${id}`, email: `p${id}@x.com.br`, role: "operator", active: true, ...over });
const station = (id: number, over = {}) => ({ id, name: `st${id}`, is_host: false, platform: "windows-x86_64", categories: ["windows"], runner_version: "x",
  session_state: "ready", session_reason: null, last_seen_at: null, revoked: false, online: true, browsers: [], current: false, ...over });

let users: any[];
beforeEach(() => {
  vi.clearAllMocks();
  users = [user(1, { role: "admin" }), user(2, { active: false })];
  api.mockImplementation(async (method: string, path: string) => {
    if (path === "/api/v1/identity/profile") return { full_name: "Admin", email: "admin@x.com.br", username: "admin" };
    if (method === "GET" && path === "/api/v1/users") return users;
    return { ok: true };
  });
  Object.assign(store, { src: { mode: "real", stations: vi.fn() }, changeTick: 0, me: { id: 1, role: "admin" }, go: vi.fn(), reload: vi.fn(async () => undefined) });
});

const page = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("Equipe", () => {
  it("offers + Nova Conta in Meu perfil, and no inline form", async () => {
    page(<TeamPage />);
    const profile = (await screen.findByText("Meu perfil")).closest("[data-slot=card]") as HTMLElement;
    await userEvent.click(within(profile).getByRole("button", { name: /Nova Conta/ }));
    expect(store.go).toHaveBeenCalledWith({ menu: "configuracao", page: "nova-conta" });
    expect(screen.queryByRole("button", { name: "Adicionar" })).toBeNull();
    expect(screen.queryByLabelText("Usuário")).toBeNull();
  });

  it("operators get neither the button nor the list", async () => {
    store.me = { id: 9, role: "operator" };
    page(<TeamPage />);
    await screen.findByText("Meu perfil");
    expect(screen.queryByRole("button", { name: /Nova Conta/ })).toBeNull();
    expect(api).not.toHaveBeenCalledWith("GET", "/api/v1/users");
  });

  it("an inactive account has Reativar and the trash; cancel changes nothing; delete removes the row after the Core", async () => {
    const u = userEvent.setup();
    page(<TeamPage />);
    const active = (await screen.findAllByText("Pessoa 1")).at(-1)!.closest("tr")!;
    expect(within(active).getByRole("button", { name: "Desativar" })).toBeTruthy();
    expect(within(active).queryByRole("button", { name: "Excluir conta" })).toBeNull();
    const inactive = screen.getByText("Pessoa 2").closest("tr")!;
    expect(within(inactive).getByRole("button", { name: "Reativar" })).toBeTruthy();
    await u.click(within(inactive).getByRole("button", { name: "Excluir conta" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Pessoa 2 \(p2@x.com.br\)/)).toBeTruthy();
    expect(within(dialog).getByText(/o e-mail fica livre para uma conta nova/)).toBeTruthy(); // erased, e-mail reusable
    await u.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(api).not.toHaveBeenCalledWith("DELETE", expect.anything());
    expect(screen.getByText("Pessoa 2")).toBeTruthy();
    await u.click(within(screen.getByText("Pessoa 2").closest("tr")!).getByRole("button", { name: "Excluir conta" }));
    api.mockImplementationOnce(async () => { users = users.filter((x) => x.id !== 2); return { deleted: true }; });
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Excluir conta" }));
    expect(api).toHaveBeenCalledWith("DELETE", "/api/v1/users/2");
    await waitFor(() => expect(screen.queryByText("Pessoa 2")).toBeNull());
  });

  it("a refused delete keeps the account and shows the diagnostic", async () => {
    const u = userEvent.setup();
    page(<TeamPage />);
    await u.click(within((await screen.findByText("Pessoa 2")).closest("tr")!).getByRole("button", { name: "Excluir conta" }));
    api.mockImplementationOnce(async () => { throw new AppError(diag("ACCOUNT-ACTIVE")); });
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Excluir conta" }));
    expect(await within(screen.getByRole("dialog")).findByText(/Código: ACCOUNT-ACTIVE/)).toBeTruthy();
    expect(screen.getAllByText("Pessoa 2").length).toBeGreaterThan(0);
  });
});

describe("+ Nova Conta", () => {
  const next = () => userEvent.click(screen.getByRole("button", { name: /Continuar|Criar conta/ }));

  it("one field per step, in order, validated before going on; Voltar keeps the values", async () => {
    render(<AccountWizard />);
    expect(screen.getByRole("list", { name: "Etapas do cadastro" }).textContent).toMatch(/1Nome.*2E-mail.*3Senha.*4Confirmar senha/);
    await userEvent.type(screen.getByLabelText("Nome completo"), "   ");
    await next();
    expect(screen.getByRole("alert").textContent).toMatch(/nome completo/);
    await userEvent.clear(screen.getByLabelText("Nome completo"));
    await userEvent.type(screen.getByLabelText("Nome completo"), "Maria Souza");
    await next();
    expect(screen.queryByLabelText("Nome completo")).toBeNull();
    await userEvent.type(screen.getByLabelText("E-mail"), "maria");
    await next();
    expect(screen.getByRole("alert").textContent).toMatch(/e-mail válido/);
    await userEvent.type(screen.getByLabelText("E-mail"), "@empresa.com.br");
    await next();
    const pw = screen.getByLabelText(/^Senha/);
    expect(pw.getAttribute("type")).toBe("password");
    await userEvent.type(pw, "1234567");
    await next();
    expect(screen.getByRole("alert").textContent).toMatch(/8 caracteres/);
    await userEvent.type(screen.getByLabelText(/^Senha/), "8");
    await next();
    await userEvent.type(screen.getByLabelText("Confirmar senha"), "outra-senha");
    await next();
    expect(screen.getByRole("alert").textContent).toMatch(/não coincidem/);
    await userEvent.click(screen.getByRole("button", { name: "Voltar" }));
    await userEvent.click(screen.getByRole("button", { name: "Voltar" }));
    expect((screen.getByLabelText("E-mail") as HTMLInputElement).value).toBe("maria@empresa.com.br");
    expect(api).not.toHaveBeenCalled(); // nothing is saved between steps
  });

  async function fill(pw = "senha-forte-1") {
    await userEvent.type(screen.getByLabelText("Nome completo"), "Maria Souza"); await next();
    await userEvent.type(screen.getByLabelText("E-mail"), "maria@empresa.com.br"); await next();
    await userEvent.type(screen.getByLabelText(/^Senha/), pw); await next();
    await userEvent.type(screen.getByLabelText("Confirmar senha"), pw);
  }

  it("creates the account once, busy while sending, and returns to Equipe", async () => {
    let finish: () => void = () => undefined;
    api.mockImplementation(() => new Promise((res) => { finish = () => res({ id: 5 }); }));
    render(<AccountWizard />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
    const busy = screen.getByRole("button", { name: "Criando…" }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    await userEvent.click(busy);
    expect(api).toHaveBeenCalledTimes(1);
    expect(api).toHaveBeenCalledWith("POST", "/api/v1/accounts", { full_name: "Maria Souza", email: "maria@empresa.com.br", password: "senha-forte-1" });
    expect(store.go).not.toHaveBeenCalled(); // success only after the Core confirms
    await act(async () => finish());
    expect(store.go).toHaveBeenCalledWith({ menu: "configuracao", page: "equipe" });
  });

  it("a refused e-mail goes back to its step with the diagnostic; cancel creates nothing", async () => {
    api.mockImplementation(async () => { throw new AppError(diag("ACCOUNT-EXISTS")); });
    render(<AccountWizard />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
    expect(await screen.findByText(/Código: ACCOUNT-EXISTS/)).toBeTruthy();
    expect((screen.getByLabelText("E-mail") as HTMLInputElement).value).toBe("maria@empresa.com.br");
    api.mockClear();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(api).not.toHaveBeenCalled();
    expect(store.go).toHaveBeenCalledWith({ menu: "configuracao", page: "equipe" });
  });

  it("is only for administrators", () => {
    store.me = { id: 9, role: "operator" };
    render(<AccountWizard />);
    expect(screen.getByText("Somente administradores criam contas.")).toBeTruthy();
    expect(screen.queryByLabelText("Nome completo")).toBeNull();
  });
});

describe("Estação", () => {
  it("separates Status from Estado and protects the station in use", async () => {
    store.src.stations.mockResolvedValue([station(1, { current: true, is_host: true }), station(2, { online: false }), station(3, { session_state: "locked", session_reason: "tela bloqueada" }),
      station(4, { revoked: true, online: false })]);
    page(<StationsPage />);
    const row = async (n: string) => (await screen.findByText(n)).closest("tr")!;
    const here = await row("st1");
    expect(within(here).getByText("Esta estação")).toBeTruthy();
    expect(within(here).getByText("Online")).toBeTruthy();
    expect((within(here).getByRole("button", { name: "Revogar" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(here).getByText("Em uso por esta sessão")).toBeTruthy();
    expect(within(await row("st2")).getByText("Offline")).toBeTruthy();
    expect(within(await row("st2")).getByText("aguardando conexão")).toBeTruthy();
    const locked = await row("st3");
    expect(within(locked).getByText("Online")).toBeTruthy(); // online is not ready
    expect(within(locked).getByText("aguardando: tela bloqueada")).toBeTruthy();
    const revoked = await row("st4");
    expect(within(revoked).getByText("revogada")).toBeTruthy();
    await userEvent.click(within(revoked).getByRole("button", { name: "Excluir estação" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Excluir estação" }));
    expect(api).toHaveBeenCalledWith("POST", "/api/v1/stations/4/remove");
    expect(store.reload).toHaveBeenCalled();
  });

  it("reads again on its own, and a failed read shows Desconhecido, not Offline", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      store.src.stations.mockResolvedValueOnce([station(1)]).mockRejectedValueOnce(new AppError(diag("CORE-UNREACHABLE")));
      page(<StationsPage />);
      expect(await screen.findByText("Online")).toBeTruthy();
      await act(async () => { await vi.advanceTimersByTimeAsync(STATIONS_POLL_MS + 50); });
      expect(await screen.findByText("Desconhecido")).toBeTruthy();
      expect(screen.queryByText("Offline")).toBeNull();
      expect(screen.getByText(/Código: CORE-UNREACHABLE/)).toBeTruthy();
      expect(store.src.stations).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });
});
