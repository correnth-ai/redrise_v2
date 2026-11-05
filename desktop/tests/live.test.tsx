import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StoreProvider, useStore } from "@/state";
import type { DataSource } from "@/data/source";

function source(changes: DataSource["changes"]) {
  return { mode: "real", routines: vi.fn(async () => []), processes: vi.fn(async () => []), executions: vi.fn(async () => []), stations: vi.fn(async () => []),
    reviews: vi.fn(async () => []), notifications: vi.fn(async () => ({ unseen: 0, items: [] })), stepChanges: vi.fn(async () => []), changes } as unknown as DataSource;
}
function Tick() { return <span data-testid="tick">{useStore().changeTick}</span>; }
const mount = (src: DataSource) => render(
  <StoreProvider src={src} me={{ id: 1, username: "a", display: "A", role: "admin" }} go={() => undefined} run={() => undefined} signOut={() => undefined} onSessionEnded={() => undefined}><Tick /></StoreProvider>);

/** A feed the test answers by hand: each call waits for the next answer. */
function feed() {
  const calls: { args: any[]; answer: (v: any) => void; fail: (e: unknown) => void }[] = [];
  const changes = vi.fn((...args: any[]) => new Promise((answer, fail) => { calls.push({ args, answer, fail }); })) as any;
  return { calls, changes };
}

beforeEach(() => { vi.clearAllMocks(); });

describe("live tables", () => {
  it("first asks for the current position without waiting, then waits from it", async () => {
    const f = feed();
    mount(source(f.changes));
    await waitFor(() => expect(f.calls.length).toBe(1));
    expect(f.calls[0].args).toEqual([null, null, 0]);
    await act(async () => { f.calls[0].answer({ epoch: "e", seq: 5, domains: ["routines"] }); });
    await waitFor(() => expect(f.calls.length).toBe(2));
    expect(f.calls[1].args).toEqual(["e", 5, 18]);
    expect(screen.getByTestId("tick").textContent).toBe("0"); // the first answer is a position, not a change
    cleanup();
  });

  it("a change reads everything again and tells the screens that read their own data", async () => {
    const f = feed();
    const src = source(f.changes);
    mount(src);
    await waitFor(() => expect(f.calls.length).toBe(1));
    await act(async () => { f.calls[0].answer({ epoch: "e", seq: 5, domains: [] }); });
    await waitFor(() => expect(f.calls.length).toBe(2));
    const before = (src.routines as any).mock.calls.length;
    await act(async () => { f.calls[1].answer({ epoch: "e", seq: 6, domains: ["routines"] }); });
    await waitFor(() => expect(screen.getByTestId("tick").textContent).toBe("1"));
    expect((src.routines as any).mock.calls.length).toBe(before + 1);
    await waitFor(() => expect(f.calls.length).toBe(3));
    expect(f.calls[2].args).toEqual(["e", 6, 18]);
    cleanup();
  });

  it("a wait that ended with nothing new reads nothing", async () => {
    const f = feed();
    const src = source(f.changes);
    mount(src);
    await waitFor(() => expect(f.calls.length).toBe(1));
    await act(async () => { f.calls[0].answer({ epoch: "e", seq: 5, domains: [] }); });
    await waitFor(() => expect(f.calls.length).toBe(2));
    const before = (src.routines as any).mock.calls.length;
    await act(async () => { f.calls[1].answer({ epoch: "e", seq: 5, domains: [] }); });
    await waitFor(() => expect(f.calls.length).toBe(3));
    expect((src.routines as any).mock.calls.length).toBe(before);
    cleanup();
  });

  it("a failing feed costs only speed: the screen keeps working and it tries again later", async () => {
    const f = feed();
    mount(source(f.changes));
    await waitFor(() => expect(f.calls.length).toBe(1));
    await act(async () => { f.calls[0].fail(new Error("down")); });
    expect(screen.getByTestId("tick").textContent).toBe("0");
    expect(f.calls.length).toBe(1); // no busy loop
    cleanup();
  });
});
