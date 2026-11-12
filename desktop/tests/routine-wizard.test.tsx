import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RoutineWizard, validUrl, versionOf } from "@/features/routine-wizard";

const check = (id: string, state = "ok") => ({ at: "t", state: "check", detail: { id, state, detail: null } });
const verified = { id: "job-1", state: "verified", events: [check("session"), check("target"), check("launch")] };
const failed = { id: "job-1", state: "failed", events: [check("session"), check("target", "failed")],
  diagnostic: { schema: "redrise.diagnostic/1", error_code: "APP-TARGET-NOT-FOUND", category: "precondition", what_happened: "x", completed: "x", pending: "x", effect_state: "none",
    next_action: "x", retry: "after_fix", details_summary: "x", reported_by: "RR-APP-OPEN", module_hints: ["RR-APP-OPEN"], diagnosis_status: "unconfirmed", correlation_id: "c", boundary: null, version: {}, technical_details: {}, cause: null, params: { target: "Calculadora" } } };

const src = {
  apps: vi.fn(async () => ({ apps: [{ id: "Calc!App", name: "Calculadora" }, { id: "browser:msedge", name: "Microsoft Edge", browser_id: "msedge" }] })),
  pickFile: vi.fn(async () => "C:\\Exemplos\\manual.html"),
  createRoutine: vi.fn(async () => 7), addRoutineVersion: vi.fn(async () => undefined),
  prepareRoutine: vi.fn(async () => verified as any), testRoutine: vi.fn(async () => ({ id: "job-2", state: "verified" }) as any),
  job: vi.fn(async () => verified as any), cancelJob: vi.fn(async () => undefined),
  members: vi.fn(async () => [{ id: 5, display: "Pessoa Ativa", username: "ativa", active: true }, { id: 6, display: "Pessoa Inativa", username: "inativa", active: false }]),
};
const store = {
  src, go: vi.fn(), reload: vi.fn(async () => undefined), routines: [] as any[],
  stations: [{ id: 1, name: "estacao", online: true, revoked: false }],
  processes: [{ id: 10, name: "Sem etapa", items: [], system_key: null }, { id: 11, name: "Com etapa", items: [{ routine_id: 1, position: 1, routine_name: "Abrir pedidos" }], system_key: null },
    { id: 12, name: "Boas-vindas", items: [], system_key: "boas-vindas" }],
};
vi.mock("@/state", () => ({ useStore: () => store }));

beforeEach(() => { vi.clearAllMocks(); store.routines = []; src.prepareRoutine.mockImplementation(async () => verified as any); });

async function pickFrom(user: ReturnType<typeof userEvent.setup>, box: HTMLElement, option: RegExp) {
  await user.click(box);
  await user.click(await screen.findByRole("option", { name: option }));
}

async function toStep2(user: ReturnType<typeof userEvent.setup>, mode: "Rotina avulsa" | "Iniciar um processo") {
  await user.type(screen.getByLabelText("Nome da rotina"), "Abrir calculadora");
  await user.click(screen.getByRole("radio", { name: new RegExp(mode) }));
  if (mode === "Iniciar um processo") await pickFrom(user, screen.getByLabelText("Processo"), /Sem etapa/);
  await user.click(screen.getByRole("button", { name: "Continuar" }));
}

describe("versionOf", () => {
  it("maps each destination to what the Core stores", () => {
    expect(versionOf({ kind: "app", app_id: "A!1", name: "A" }, "")).toEqual({ category: "windows", version: { kind: "app_open", config: { target: { kind: "app", app_id: "A!1", name: "A" }, isolated: true } } });
    expect(versionOf({ kind: "file", path: "C:\\x\\a.xlsx", name: "a.xlsx" }, "").version.kind).toBe("app_open");
    // A local HTML keeps the Browser rules (B03): no browser is stored.
    expect(versionOf({ kind: "file", path: "C:\\x\\a.HTM", name: "a.HTM" }, "")).toEqual({ category: "browser", version: { kind: "browser_open", config: { origin: "html", browser: null, url: null, path: "C:\\x\\a.HTM", isolated: true } } });
    expect(versionOf({ kind: "browser", browser_id: "msedge", name: "Edge" }, " https://x.test/ ").version.config).toMatchObject({ origin: "site", browser: "msedge", url: "https://x.test/" });
    expect(validUrl("x.test")).toBe(false);
  });
});

describe("Nova Rotina", () => {
  it("offers only processes without a first step, the ready-made one too (PROCESS-ACTIONS-20261111)", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await user.click(screen.getByRole("radio", { name: /Iniciar um processo/ }));
    expect((screen.getByRole("button", { name: "Continuar" }) as HTMLButtonElement).disabled).toBe(true);
    await user.click(screen.getByLabelText("Processo"));
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Sem etapa", "Boas-vindas"]);
  });

  it("a starting routine: preparing shows the checks and never opens; only the link tests", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await toStep2(user, "Iniciar um processo");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.createRoutine).toHaveBeenCalledWith("Abrir calculadora", "windows", expect.objectContaining({ kind: "app_open" }), { process_id: 10 });
    expect(src.prepareRoutine).toHaveBeenCalledTimes(1);
    expect(src.testRoutine).not.toHaveBeenCalled();
    expect(screen.getAllByText(/\(concluído\)/).length).toBeGreaterThanOrEqual(4);
    await user.click(screen.getByRole("button", { name: "Quer testar?" }));
    await waitFor(() => expect(src.testRoutine).toHaveBeenCalledWith(7, expect.any(String), "job-1"));
    await screen.findByText("Janela confirmada na estação.");
  });

  it("a standalone routine has no link to process and no test", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await toStep2(user, "Rotina avulsa");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await screen.findByText(/A rotina já pode executar pela Lista/);
    expect(src.createRoutine.mock.calls[0][3]).toBeNull();
    expect(screen.queryByRole("button", { name: "Quer testar?" })).toBeNull();
  });

  it("a browser asks for the address before saving; Outro… can bring a local HTML", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await toStep2(user, "Rotina avulsa");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Microsoft Edge/);
    expect((screen.getByRole("button", { name: "Salvar e preparar" }) as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByLabelText("Endereço do site"), "https://pedidos.exemplo.test/");
    expect((screen.getByRole("button", { name: "Salvar e preparar" }) as HTMLButtonElement).disabled).toBe(false);
    await pickFrom(user, screen.getByLabelText("O que abrir"), /Outro/);
    await screen.findByText(/manual\.html/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.createRoutine.mock.calls[0].slice(1, 2)).toEqual(["browser"]);
  });

  it("a failed preparation shows the diagnostic, no link, and checks again without a new routine or version", async () => {
    const user = userEvent.setup();
    src.prepareRoutine.mockImplementationOnce(async () => failed as any);
    render(<RoutineWizard />);
    await toStep2(user, "Iniciar um processo");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await screen.findByRole("button", { name: "Verificar de novo" });
    expect(screen.queryByText(/Deu tudo certo!/)).toBeNull();
    expect(screen.getByText(/APP-TARGET-NOT-FOUND/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Verificar de novo" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.createRoutine).toHaveBeenCalledTimes(1);
    expect(src.addRoutineVersion).not.toHaveBeenCalled();
    expect(src.prepareRoutine).toHaveBeenCalledTimes(2);
  });

  it("once saved, it cannot go back to change what the routine is", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await toStep2(user, "Rotina avulsa");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    expect(screen.getByRole("button", { name: "Voltar" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await user.click(await screen.findByRole("button", { name: "Voltar e ajustar" }));
    expect(screen.queryByRole("button", { name: "Voltar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeTruthy();
  });

  it("one click on the test opens once while the request is on its way", async () => {
    const user = userEvent.setup();
    let answer: (j: any) => void = () => undefined;
    src.testRoutine.mockImplementationOnce(() => new Promise((res) => { answer = res; }) as any);
    render(<RoutineWizard />);
    await toStep2(user, "Iniciar um processo");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await screen.findByRole("button", { name: "Quer testar?" });
    await user.click(screen.getByRole("button", { name: "Quer testar?" }));
    await user.click(screen.getByRole("button", { name: "Quer testar?" }));
    expect(src.testRoutine).toHaveBeenCalledTimes(1);
    await act(async () => { answer({ id: "job-2", state: "verified" }); });
  });

  it("a preparation refused before reaching the station stops waiting and can be repeated", async () => {
    const user = userEvent.setup();
    src.prepareRoutine.mockImplementationOnce(async () => { throw new Error("refused"); });
    render(<RoutineWizard />);
    await toStep2(user, "Rotina avulsa");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await user.click(await screen.findByRole("button", { name: "Verificar de novo" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.createRoutine).toHaveBeenCalledTimes(1);
  });

  it("polls a queued preparation until it ends", async () => {
    const user = userEvent.setup();
    src.prepareRoutine.mockImplementationOnce(async () => ({ id: "job-1", state: "queued", events: [] }) as any);
    render(<RoutineWizard />);
    await toStep2(user, "Rotina avulsa");
    await pickFrom(user, await screen.findByLabelText("O que abrir"), /Calculadora/);
    await user.click(screen.getByRole("button", { name: "Salvar e preparar" }));
    await screen.findByText(/Aguardando estacao/);
    await act(async () => { await new Promise((r) => setTimeout(r, 900)); });
    await screen.findByText(/Deu tudo certo!/);
    expect(src.job).toHaveBeenCalledWith("job-1");
  });

  it("a follow-up picks the previous step by process or routine, a member, and has no test link", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await user.type(screen.getByLabelText("Nome da rotina"), "Revisar pedido");
    await user.click(screen.getByRole("radio", { name: /Fazer follow-up/ }));
    await user.type(screen.getByLabelText("Etapa anterior"), "abrir");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Com etapa · Etapa 1Abrir pedidos"]);
    await user.click(screen.getByRole("option"));
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await pickFrom(user, screen.getByLabelText("Responsável pela revisão"), /Pessoa Ativa/);
    expect(screen.queryByRole("option", { name: /Pessoa Inativa/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.createRoutine).toHaveBeenCalledWith("Revisar pedido", "windows", { kind: "followup", config: { action: "review", assignee_id: 5 } }, { process_id: 11, after_position: 1 });
    expect(src.prepareRoutine).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Quer testar?" })).toBeNull();
  });

  it("a report follow-up stores the fixed words of the mask and needs no member", async () => {
    const user = userEvent.setup();
    render(<RoutineWizard />);
    await user.type(screen.getByLabelText("Nome da rotina"), "Gerar PDF");
    await user.click(screen.getByRole("radio", { name: /Fazer follow-up/ }));
    await pickFrom(user, screen.getByLabelText("Etapa anterior"), /Com etapa/);
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await user.click(screen.getByRole("radio", { name: /Gerar relatório/ }));
    expect(screen.queryByLabelText("Responsável pela revisão")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await screen.findByText(/Deu tudo certo!/);
    const version = (src.createRoutine.mock.calls[0] as any[])[2];
    expect(version.config.action).toBe("report");
    expect(version.config.labels.title).toBe("Relatório de execução");
    expect(screen.queryByRole("button", { name: "Quer testar?" })).toBeNull();
  });

  it("a notify follow-up needs a valid address and a place, and offers mail apps and browsers only", async () => {
    const user = userEvent.setup();
    src.apps.mockImplementation(async () => ({ apps: [{ id: "Calc!App", name: "Calculadora" }, { id: "browser:msedge", name: "Microsoft Edge", browser_id: "msedge" },
      { id: "mail:outlook", name: "Microsoft Outlook", mail_id: "outlook" }, { id: "mail:default", name: "Windows mail app", mail_id: "default" }] }) as any);
    render(<RoutineWizard />);
    await user.type(screen.getByLabelText("Nome da rotina"), "Avisar");
    await user.click(screen.getByRole("radio", { name: /Fazer follow-up/ }));
    await pickFrom(user, screen.getByLabelText("Etapa anterior"), /Com etapa/);
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await user.click(screen.getByRole("radio", { name: /Notificar alguém/ }));
    const save = () => screen.getByRole("button", { name: "Salvar" }) as HTMLButtonElement;
    expect(save().disabled).toBe(true);
    await user.type(screen.getByLabelText("Para"), "sem-arroba");
    expect(screen.getByText(/endereço de e-mail completo/)).toBeTruthy();
    await user.clear(screen.getByLabelText("Para"));
    await user.type(screen.getByLabelText("Para"), "pessoa@exemplo.test");
    await user.click(screen.getByLabelText("Preparar em"));
    await waitFor(() => expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(expect.arrayContaining([expect.stringContaining("Microsoft Outlook"), expect.stringContaining("Aplicativo de e-mail do Windows")])));
    expect(screen.queryByRole("option", { name: /Calculadora/ })).toBeNull();
    await user.click(screen.getByRole("option", { name: /Microsoft Outlook/ }));
    expect(save().disabled).toBe(false);
    await user.click(save());
    await screen.findByText(/Deu tudo certo!/);
    const version = (src.createRoutine.mock.calls[0] as any[])[2];
    expect(version.config).toMatchObject({ action: "notify", to: "pessoa@exemplo.test", channel: { kind: "app", mail_id: "outlook" } });
    expect(version.config.labels.greeting).toContain("revisar e enviar");
    expect(src.prepareRoutine).not.toHaveBeenCalled();
    src.apps.mockImplementation(async () => ({ apps: [{ id: "Calc!App", name: "Calculadora" }, { id: "browser:msedge", name: "Microsoft Edge", browser_id: "msedge" }] }) as any);
  });

  it("changing the responsible of a follow-up adds a version and tells what moves", async () => {
    const user = userEvent.setup();
    store.routines = [{ id: 8, name: "Revisar", category: "windows", version: 1, kind: "followup", config: { action: "review", assignee_id: 6, isolated: false } }];
    render(<RoutineWizard id={8} />);
    expect(screen.getByText(/Pedidos ainda pendentes passam para o novo responsável/)).toBeTruthy();
    await pickFrom(user, screen.getByLabelText("Responsável pela revisão"), /Pessoa Ativa/);
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.addRoutineVersion).toHaveBeenCalledWith(8, "Revisar", { kind: "followup", config: { action: "review", assignee_id: 5 } });
  });

  it("editing starts at the destination and adds a version", async () => {
    const user = userEvent.setup();
    store.routines = [{ id: 7, name: "Abrir calculadora", category: "windows", version: 2, kind: "app_open", config: { target: { kind: "app", app_id: "Calc!App", name: "Calculadora" }, isolated: true } }];
    render(<RoutineWizard id={7} />);
    expect(screen.getByText(/Salvar cria a versão 3/)).toBeTruthy();
    await screen.findByLabelText("O que abrir");
    expect(screen.queryByRole("option", { name: /Microsoft Edge/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Salvar e verificar" }));
    await screen.findByText(/Deu tudo certo!/);
    expect(src.addRoutineVersion).toHaveBeenCalledWith(7, "Abrir calculadora", expect.objectContaining({ kind: "app_open" }));
    expect(src.createRoutine).not.toHaveBeenCalled();
  });
});
