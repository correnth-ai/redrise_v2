import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssignedToMe } from "@/features/reviews";

const change = (over = {}) => ({ id: "c1", process_id: 3, process_name: "Pedidos", status: "pending", old_routine_name: "Abrir antigo", new_routine_name: "Abrir novo",
  requested_at: "2026-11-04T10:00:00Z", decided_at: null, requested_by: 2, requested_by_name: "Pessoa Dois", decided_by_name: null, can_approve: true, ...over });
const src = { execution: vi.fn(), approveReview: vi.fn(), approveStepChange: vi.fn(async () => undefined), cancelStepChange: vi.fn(async () => undefined) };
const store: any = { src, me: { id: 1, display: "Pessoa Um", role: "operator" }, reload: vi.fn(async () => undefined), reviews: [], stepChanges: [] };
vi.mock("@/state", () => ({ useStore: () => store }));

beforeEach(() => { vi.clearAllMocks(); store.me = { id: 1, display: "Pessoa Um", role: "operator" }; });

describe("Substituição da etapa 1 em Marcado para mim", () => {
  it("shows the change and approves on its own button, apart from a review", async () => {
    const user = userEvent.setup();
    store.stepChanges = [change()];
    render(<AssignedToMe />);
    expect(screen.getByText("Abrir novo")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Aprovado!" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancelar pedido" })).toBeNull(); // neither requester nor administrator
    await user.click(screen.getByRole("button", { name: "Aprovar substituição" }));
    await waitFor(() => expect(src.approveStepChange).toHaveBeenCalledWith("c1"));
    expect(store.reload).toHaveBeenCalled();
    expect(src.approveReview).not.toHaveBeenCalled();
  });

  it("who asked and cannot approve sees only cancel", async () => {
    const user = userEvent.setup();
    store.me = { id: 2, display: "Pessoa Dois", role: "admin" };
    store.stepChanges = [change({ can_approve: false })];
    render(<AssignedToMe />);
    expect(screen.queryByRole("button", { name: "Aprovar substituição" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Cancelar pedido" }));
    await waitFor(() => expect(src.cancelStepChange).toHaveBeenCalledWith("c1"));
  });

  it("a decided change keeps author and time, with no buttons", () => {
    store.stepChanges = [change({ status: "approved", decided_at: "2026-11-04T11:00:00Z", decided_by_name: "Pessoa Um", can_approve: false })];
    render(<AssignedToMe />);
    expect(screen.getByText(/Aprovada por Pessoa Um em/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Aprovar substituição" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancelar pedido" })).toBeNull();
  });
});
