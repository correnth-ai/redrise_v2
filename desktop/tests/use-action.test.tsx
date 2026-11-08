import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { useAction } from "@/hooks/use-action";

function Probe({ fn }: { fn: () => Promise<unknown> }) {
  const [error, setError] = useState<unknown>(null);
  const a = useAction(setError);
  return <>
    <button type="button" onClick={() => { void a.run(fn); void a.run(fn); }} disabled={a.busy}>Salvar</button>
    {error ? <p role="alert">{String(error)}</p> : null}
  </>;
}

describe("useAction", () => {
  it("sends once while busy, then enables again", async () => {
    let done: () => void = () => undefined;
    const fn = vi.fn(() => new Promise<void>((r) => { done = r; }));
    render(<Probe fn={fn} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Salvar" }));
    expect(fn).toHaveBeenCalledTimes(1); // the second run in the same click is refused
    expect((screen.getByRole("button", { name: "Salvar" }) as HTMLButtonElement).disabled).toBe(true);
    done();
    await waitFor(() => expect((screen.getByRole("button", { name: "Salvar" }) as HTMLButtonElement).disabled).toBe(false));
  });

  it("a failure reaches the screen and frees the control", async () => {
    render(<Probe fn={() => Promise.reject(new Error("recusado"))} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Salvar" }));
    expect((await screen.findByRole("alert")).textContent).toContain("recusado");
    expect((screen.getByRole("button", { name: "Salvar" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
