import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationsBell } from "@/components/notifications-bell";
import { AssignedToMe } from "@/features/reviews";

const review = (over = {}) => ({ id: "r1", execution_id: "e1", position: 2, status: "pending", assignee_id: 1, assignee_name: "Pessoa Um", requested_at: "2026-11-04T10:00:00Z",
  decided_at: null, decided_by_name: null, step_name: "Conferir pedido", process_name: "Pedidos", requested_by_name: "Pessoa Dois", execution_state: "waiting_review", context: { last: { output_path: "C:\\x\\a.txt" } }, ...over });
const execution = { id: "e1", state: "waiting_review", steps: [{ position: 1, name: "Abrir", state: "verified", started_at: null, finished_at: null, diagnostic: null }] };
const src = { execution: vi.fn(async () => execution as any), approveReview: vi.fn(async () => undefined), markNotificationSeen: vi.fn(async () => undefined) };
const store: any = { src, me: { id: 1, display: "Pessoa Um" }, reload: vi.fn(async () => undefined), go: vi.fn(), reviews: [], notifications: { unseen: 0, items: [] } };
vi.mock("@/state", () => ({ useStore: () => store }));

beforeEach(() => { vi.clearAllMocks(); store.reviews = []; store.notifications = { unseen: 0, items: [] }; });

describe("Marcado para mim", () => {
  it("groups pending and approved and shows the count", () => {
    store.reviews = [review(), review({ id: "r2", status: "approved", decided_at: "2026-11-04T11:00:00Z", decided_by_name: "Pessoa Um" })];
    render(<AssignedToMe />);
    expect(screen.getByText("1 pedido pendente")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Aguardando revisão" })).getAllByRole("button")).toHaveLength(1);
    expect(within(screen.getByRole("region", { name: "Aprovados" })).getAllByRole("button")).toHaveLength(1);
  });

  it("opening shows context and results; Aprovado! is a separate click", async () => {
    const user = userEvent.setup();
    store.reviews = [review()];
    render(<AssignedToMe />);
    await user.click(screen.getByRole("button", { name: /Conferir pedido/ }));
    await screen.findByText("Registro da execução (1)");
    expect(screen.getByText(/a\.txt/, { selector: "span" })).toBeTruthy();
    expect(src.approveReview).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Aprovado!" }));
    await waitFor(() => expect(src.approveReview).toHaveBeenCalledWith("r1"));
    expect(store.reload).toHaveBeenCalled();
  });

  it("a notification opens its request directly", async () => {
    store.reviews = [review()];
    render(<AssignedToMe focus="r1" />);
    expect(await screen.findByRole("button", { name: "Aprovado!" })).toBeTruthy();
  });

  it("no Aprovado! for someone who is not the responsible, and none after the decision", async () => {
    const user = userEvent.setup();
    store.reviews = [review({ assignee_id: 2, assignee_name: "Outra Pessoa" })];
    const { unmount } = render(<AssignedToMe />);
    await user.click(screen.getByRole("button", { name: /Conferir pedido/ }));
    expect(await screen.findByText("Responsável: Outra Pessoa")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Aprovado!" })).toBeNull();
    unmount();
    store.reviews = [review({ status: "approved", decided_at: "2026-11-04T11:00:00Z", decided_by_name: "Pessoa Um" })];
    render(<AssignedToMe focus="r1" />);
    expect(await screen.findByText(/^Por Pessoa Um em/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Aprovado!" })).toBeNull();
  });
});

describe("Sino", () => {
  it("hides the badge at zero", () => {
    render(<NotificationsBell />);
    const bell = screen.getByRole("button", { name: "Notificações" });
    expect(bell.querySelector("span")).toBeNull();
  });

  it("shows the unseen count; opening marks as seen, goes to the request and approves nothing", async () => {
    const user = userEvent.setup();
    store.notifications = { unseen: 2, items: [{ id: 9, kind: "review_request", review_id: "r1", created_at: "2026-11-04T10:00:00Z", seen_at: null, step_name: "Conferir pedido", position: 2, process_name: "Pedidos" }] };
    render(<NotificationsBell />);
    const bell = screen.getByRole("button", { name: "Notificações, 2 não vistas" });
    expect(bell.querySelector("span")?.textContent).toBe("2");
    await user.click(bell);
    await user.click(await screen.findByRole("menuitem", { name: /Conferir pedido/ }));
    await waitFor(() => expect(src.markNotificationSeen).toHaveBeenCalledWith(9));
    expect(store.go).toHaveBeenCalledWith(expect.objectContaining({ menu: "processo", page: "acao", id: "r1" }));
    expect(src.approveReview).not.toHaveBeenCalled();
  });

  it("does not mark again what was already seen", async () => {
    const user = userEvent.setup();
    store.notifications = { unseen: 0, items: [{ id: 9, kind: "review_request", review_id: "r1", created_at: "2026-11-04T10:00:00Z", seen_at: "2026-11-04T10:01:00Z", step_name: "Conferir", position: 2, process_name: "Pedidos" }] };
    render(<NotificationsBell />);
    await user.click(screen.getByRole("button", { name: "Notificações" }));
    await user.click(await screen.findByRole("menuitem", { name: /Conferir/ }));
    expect(store.go).toHaveBeenCalled();
    expect(src.markNotificationSeen).not.toHaveBeenCalled();
  });
});
