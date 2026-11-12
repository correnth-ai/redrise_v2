import { render as rtl, screen, waitFor, within } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScheduleDialog, SchedulesSection, scheduleNote } from "@/features/schedules";

// SCHEDULE-PROCESS-20261107: the next time comes from the Core; the list shows real states; admins act.
const sched = (over = {}) => ({ id: 7, process_id: 1, process_name: "Fechamento", station_id: 1, station_name: "st1", owner_name: "Admin",
  weekdays: [1, 2, 3, 4, 5], hour: 8, minute: 5, timezone: "America/Sao_Paulo", enabled: true, paused_reason: null,
  next_slot_local: "2026-11-09T08:05", next_run_at: "2026-11-09T11:05:00+00:00",
  last_slot_local: "2026-11-07T08:05", last_state: "expired", last_reason: "not_started", last_execution_id: "e1", ...over });

const src = {
  schedules: vi.fn(async () => [sched(), sched({ id: 8, process_name: "Conferência", enabled: false, paused_reason: "owner_not_allowed", next_slot_local: null, last_state: null })] as any),
  previewSchedule: vi.fn(async () => ({ next_slot_local: "2026-11-09T08:00", next_run_at: "x" })),
  createSchedule: vi.fn(async () => sched() as any),
  updateSchedule: vi.fn(async () => sched() as any),
  deleteSchedule: vi.fn(async () => undefined),
};
const store: any = {};
const render = (ui: React.ReactNode) => rtl(<TooltipProvider>{ui}</TooltipProvider>);
vi.mock("@/state", () => ({ useStore: () => store }));

beforeEach(() => {
  vi.clearAllMocks();
  Object.assign(store, { src, changeTick: 0, me: { id: 1, role: "admin" },
    stations: [{ id: 1, name: "st1", revoked: false }, { id: 2, name: "velha", revoked: true }] });
});

describe("Agendamentos", () => {
  it("lists the real state of each schedule, including an occurrence that did not start", async () => {
    render(<SchedulesSection />);
    expect(await screen.findByText("Fechamento")).toBeTruthy();
    expect(screen.getAllByText("Seg, Ter, Qua, Qui, Sex às 08:05")).toHaveLength(2);
    expect(screen.getByText("09/11/2026 08:05")).toBeTruthy();
    expect(screen.getByText(/Não iniciada \(07\/11\/2026 08:05\) · Não iniciado por desconexão\./)).toBeTruthy();
    expect(screen.getByText("Quem agendou não é mais administrador ativo")).toBeTruthy();
  });

  it("administrators pause, resume and delete by icons; deleting asks first; the list is read again after each action", async () => {
    const user = userEvent.setup();
    render(<SchedulesSection />);
    await user.click(await screen.findByRole("button", { name: "Pausar agendamento de Fechamento" }));
    expect(src.updateSchedule).toHaveBeenCalledWith(7, { enabled: false });
    await user.click(screen.getByRole("button", { name: "Retomar agendamento de Conferência" }));
    expect(src.updateSchedule).toHaveBeenLastCalledWith(8, { enabled: true });
    await user.click(screen.getByRole("button", { name: "Excluir agendamento de Fechamento" }));
    let dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(src.deleteSchedule).not.toHaveBeenCalled(); // the icon alone deletes nothing
    await user.click(screen.getByRole("button", { name: "Excluir agendamento de Fechamento" }));
    dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Seg, Ter, Qua, Qui, Sex às 08:05, st1/)).toBeTruthy();
    await user.click(within(dialog).getByRole("button", { name: "Excluir agendamento" }));
    expect(src.deleteSchedule).toHaveBeenCalledWith(7);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(src.schedules.mock.calls.length).toBeGreaterThanOrEqual(4));
  });

  it("a failed pause keeps the row and shows the diagnostic; the icon is busy while it waits", async () => {
    const user = userEvent.setup();
    let fail!: (e: unknown) => void;
    src.updateSchedule.mockImplementationOnce(() => new Promise((_, r) => { fail = r; }) as any);
    render(<SchedulesSection />);
    await user.click(await screen.findByRole("button", { name: "Pausar agendamento de Fechamento" }));
    const busy = screen.getByRole("button", { name: "Pausar agendamento de Fechamento" });
    expect(busy.getAttribute("aria-busy")).toBe("true");
    expect((screen.getByRole("button", { name: "Excluir agendamento de Fechamento" }) as HTMLButtonElement).disabled).toBe(true);
    fail(new Error("servidor indisponível"));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Fechamento")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Pausar agendamento de Fechamento" }).getAttribute("aria-busy")).toBeNull();
  });

  it("operators see the list without actions", async () => {
    store.me = { id: 2, role: "operator" };
    render(<SchedulesSection />);
    expect(await screen.findByText("Fechamento")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Pausar|Retomar|Excluir/ })).toBeNull();
  });

  it("a failed read shows the diagnostic, not an empty list", async () => {
    src.schedules.mockRejectedValueOnce(new Error("servidor indisponível"));
    render(<SchedulesSection />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("Nenhum processo agendado.")).toBeNull();
  });

  it("the dialog shows the next time from the Core and saves days, time, station and this computer's time zone", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ScheduleDialog process={{ id: 1, name: "Fechamento" } as any} onClose={onClose} />);
    expect(await screen.findByText("Próxima execução: 09/11/2026 08:00")).toBeTruthy();
    await user.click(screen.getByRole("checkbox", { name: "Sáb" }));
    await waitFor(() => expect(src.previewSchedule).toHaveBeenLastCalledWith(expect.objectContaining({ weekdays: [1, 2, 3, 4, 5, 6], station_id: 1, hour: 8, minute: 0 })));
    await user.click(await screen.findByRole("button", { name: "Agendar" }));
    expect(src.createSchedule).toHaveBeenCalledWith(expect.objectContaining({ process_id: 1, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }));
    expect(onClose).toHaveBeenCalled();
  });

  it("bell texts, including the one decided for an occurrence that did not start", () => {
    expect(scheduleNote("expired", "not_started")).toBe("Não iniciado por desconexão");
    expect(scheduleNote("skipped", "station_unavailable")).toBe("Agendamento pulado: estação indisponível no horário");
    expect(scheduleNote("skipped", "owner_not_allowed")).toBe("Agendamento pausado: quem agendou não é mais administrador ativo");
    expect(scheduleNote("missed", "core_stopped")).toBe("Agendamento perdido: servidor desligado no horário");
  });
});
