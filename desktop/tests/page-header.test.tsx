import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PageHeader } from "@/components/page-header";

describe("PageHeader", () => {
  it("shows main title, subtitle, cards to the submenus and the smaller page title", async () => {
    const go = vi.fn();
    render(<PageHeader route={{ menu: "processo", page: "historico" }} go={go} />);
    expect(screen.getByRole("heading", { level: 1, name: "Processo" }).className).toContain("font-display");
    expect(screen.getByRole("heading", { level: 2, name: "Histórico" }).className).toContain("font-display");
    const nav = screen.getByRole("navigation", { name: "Atalhos de Processo" });
    expect(nav.querySelectorAll("button")).toHaveLength(3);
    expect(screen.getByRole("button", { name: /Histórico/ }).getAttribute("aria-current")).toBe("page");
    await userEvent.setup().click(screen.getByRole("button", { name: /Kanban/ }));
    expect(go).toHaveBeenCalledWith({ menu: "processo", page: "kanban" });
  });

  it("gives Empresa cards to the other menus and no smaller title", () => {
    render(<PageHeader route={{ menu: "empresa", page: "painel" }} go={() => undefined} />);
    expect(screen.getByRole("navigation", { name: "Atalhos de Empresa" }).querySelectorAll("button")).toHaveLength(3);
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  });

  it("keeps the titles but not the cards on pages reached from a screen", () => {
    render(<PageHeader route={{ menu: "rotina", page: "gravacao" }} go={() => undefined} />);
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.getByRole("heading", { level: 2, name: "Nova rotina por gravação" })).toBeTruthy();
  });
});
