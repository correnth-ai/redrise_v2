import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WelcomePage } from "@/features/auth";
import { AppError, type Diagnostic } from "@/lib/api";

// PROCESS-LIST-INSTALLER-20261110 item 2: the first open follows the role chosen in the installer wizard, without asking
// again. The installer writing the intent and the app consuming it are proved on the lab install (native), not here.
const call = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), call, api: vi.fn() }));
const diag = (code: string): Diagnostic => ({ schema: "redrise.diagnostic/1", error_code: code, category: "communication", what_happened: code, completed: "", pending: "",
  effect_state: "none", next_action: "", retry: "after_fix", details_summary: "", reported_by: "RR-RUNNER", module_hints: ["RR-RUNNER"], diagnosis_status: "unconfirmed",
  correlation_id: "c1", boundary: null, version: {}, technical_details: {}, cause: null, params: {} });

beforeEach(() => vi.clearAllMocks());

describe("Primeira abertura conforme o uso escolhido na instalação", () => {
  it("server: only the team setup, no connect form", () => {
    render(<WelcomePage role="server" onDone={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.getByText("Criar equipe neste computador")).toBeTruthy();
    expect(screen.queryByText("Conectar a uma equipe")).toBeNull();
    expect(screen.getByRole("status").textContent).toMatch(/servidor da equipe/);
  });

  it("station: only the connection; a server that does not answer leaves it pending, never a local server", async () => {
    const u = userEvent.setup();
    call.mockRejectedValueOnce(new AppError(diag("CORE-UNREACHABLE")));
    render(<WelcomePage role="station" onDone={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.queryByText("Criar equipe neste computador")).toBeNull();
    await u.type(screen.getByLabelText("Código da equipe"), "rr1:servidor:47800:abc");
    await u.type(screen.getByLabelText("Nome desta estação"), "estacao-1");
    await u.type(screen.getByLabelText("Usuário administrador"), "admin");
    await u.type(screen.getByLabelText("Senha"), "senha-forte-1");
    await u.click(screen.getByRole("button", { name: "Conectar" }));
    expect(await screen.findByText(/Conexão pendente/)).toBeTruthy();
    expect(call).toHaveBeenCalledTimes(1);
    expect(call.mock.calls[0][0]).toBe("station_join");
    expect(call).not.toHaveBeenCalledWith("host_create", expect.anything());
    expect(screen.getByRole("button", { name: "Conectar" })).toBeTruthy(); // can try again
  });

  it("no intent (update or older installer): both, as before", () => {
    render(<WelcomePage onDone={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.getByText("Criar equipe neste computador")).toBeTruthy();
    expect(screen.getByText("Conectar a uma equipe")).toBeTruthy();
  });
});
