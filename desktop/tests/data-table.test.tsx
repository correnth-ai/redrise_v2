import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type DataColumn, type DataTableProps } from "@/components/data-table";

interface Row { id: number; name: string; state: string }
const rows: Row[] = Array.from({ length: 12 }, (_, i) => ({ id: i + 1, name: `Rotina ${i + 1}`, state: i % 3 ? "ok" : "falha" }));
const columns: DataColumn<Row>[] = [
  { id: "name", header: "Nome", cell: (r) => r.name, sortValue: (r) => r.name, searchText: (r) => r.name },
  { id: "state", header: "Situação", cell: (r) => r.state, sortValue: (r) => r.state },
  { id: "actions", header: "Ações", fixed: true, cell: () => <button type="button">agir</button> },
];
const setup = (extra: Partial<DataTableProps<Row>> = {}) => {
  const user = userEvent.setup();
  render(<DataTable<Row> label="Teste" rows={rows} columns={columns} rowKey={(r) => String(r.id)} rowLabel={(r) => r.name} {...extra} />);
  return user;
};
const headers = () => screen.getAllByRole("columnheader").map((h) => h.textContent);
const firstCell = () => within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0].textContent;

describe("DataTable", () => {
  it("shows loading, empty and no-match states", async () => {
    const { rerender } = render(<DataTable<Row> label="T" rows={null} columns={columns} rowKey={(r) => String(r.id)} empty="Nada aqui." />);
    expect(screen.getByText("Carregando…")).toBeTruthy();
    rerender(<DataTable<Row> label="T" rows={[]} columns={columns} rowKey={(r) => String(r.id)} empty="Nada aqui." />);
    expect(screen.getByText("Nada aqui.")).toBeTruthy();
    rerender(<DataTable<Row> label="T" rows={rows} columns={columns} rowKey={(r) => String(r.id)} empty="Nada aqui." />);
    await userEvent.setup().type(screen.getByRole("searchbox"), "inexistente");
    expect(screen.getByText("Nenhum registro corresponde à busca e aos filtros.")).toBeTruthy();
  });

  it("paginates and goes back to page 1 when searching", async () => {
    const user = setup();
    expect(screen.getByText("Mostrando 1 a 10 de 12 linhas")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Próxima página" }));
    expect(screen.getByText("Mostrando 11 a 12 de 12 linhas")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Próxima página" }) as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByRole("searchbox"), "rotina 1");
    expect(screen.getByText("Mostrando 1 a 4 de 4 linhas")).toBeTruthy();
  });

  it("filters by tab and counts each tab", async () => {
    const user = setup({ tabs: [{ id: "all", label: "Todas", match: () => true }, { id: "bad", label: "Falhas", match: (r) => r.state === "falha" }] });
    expect(screen.getByRole("tab", { name: /Falhas/ }).textContent).toContain("4");
    await user.click(screen.getByRole("tab", { name: /Falhas/ }));
    expect(screen.getByText("Mostrando 1 a 4 de 4 linhas")).toBeTruthy();
  });

  it("sorts from the column menu and exposes aria-sort", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Opções da coluna Nome" }));
    await user.click(await screen.findByRole("menuitem", { name: "Ordem decrescente" }));
    expect(firstCell()).toBe("Rotina 12");
    expect(screen.getAllByRole("columnheader")[0].getAttribute("aria-sort")).toBe("descending");
  });

  it("moves and hides columns from the header, keeps actions last and remembers the layout", async () => {
    const user = setup({ storageKey: "t" });
    await user.click(screen.getByRole("button", { name: "Opções da coluna Nome" }));
    await user.click(await screen.findByRole("menuitem", { name: "Mover para a direita" }));
    expect(headers()).toEqual(["Situação", "Nome", "Ações"]);
    await user.click(screen.getByRole("button", { name: "Opções da coluna Situação" }));
    await user.click(await screen.findByRole("menuitem", { name: "Ocultar coluna" }));
    expect(headers()).toEqual(["Nome", "Ações"]);
    expect(JSON.parse(localStorage.getItem("rr.table.t")!)).toEqual({ order: ["state", "name"], hidden: ["state"] });
  });

  it("selects rows, selects the page and hands the rows to the actions", async () => {
    const act = vi.fn();
    const user = setup({ selectable: true, selectionActions: (sel) => <button type="button" onClick={() => act(sel.map((r) => r.id))}>acao em lote</button> });
    await user.click(screen.getByRole("checkbox", { name: "Selecionar Rotina 2" }));
    expect(screen.getByText("1 selecionada")).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "Selecionar as linhas desta página" }).getAttribute("data-state")).toBe("indeterminate");
    await user.click(screen.getByRole("checkbox", { name: "Selecionar as linhas desta página" }));
    expect(screen.getByText("10 selecionadas")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "acao em lote" }));
    expect(act.mock.calls[0][0]).toHaveLength(10);
  });

  it("drops the selection of rows that left the data", async () => {
    const user = userEvent.setup();
    const el = (data: Row[]) => <DataTable<Row> label="T" rows={data} columns={columns} rowKey={(r) => String(r.id)} rowLabel={(r) => r.name} selectable />;
    const { rerender } = render(el(rows));
    await user.click(screen.getByRole("checkbox", { name: "Selecionar Rotina 1" }));
    rerender(el(rows.slice(1)));
    expect(screen.queryByText("1 selecionada")).toBeNull();
  });

  it("opens a row by click and keyboard, but not from its actions or selection", async () => {
    const open = vi.fn();
    const user = setup({ onRowOpen: open, selectable: true });
    await user.click(screen.getAllByRole("button", { name: "agir" })[0]);
    await user.click(screen.getByRole("checkbox", { name: "Selecionar Rotina 1" }));
    expect(open).not.toHaveBeenCalled();
    await user.click(screen.getByText("Rotina 3"));
    expect(open).toHaveBeenCalledTimes(1);
    screen.getAllByRole("row")[1].focus();
    await user.keyboard("{Enter}");
    expect(open).toHaveBeenCalledTimes(2);
  });
});
