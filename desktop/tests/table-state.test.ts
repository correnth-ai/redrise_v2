import { describe, expect, it } from "vitest";
import { compareValues, hideColumn, moveColumn, paginate, reconcileLayout, searchRows, sortRows } from "@/lib/table-state";

describe("search", () => {
  it("ignores case and accents", () => {
    const rows = ["Relatório Mensal", "Boas-vindas"];
    expect(searchRows(rows, "relatorio", (r) => r)).toEqual(["Relatório Mensal"]);
    expect(searchRows(rows, "  ", (r) => r)).toEqual(rows);
  });
});

describe("sort", () => {
  it("keeps empty values last in both directions and numbers in text in numeric order", () => {
    const rows = ["Etapa 10", null, "Etapa 2"];
    expect(sortRows(rows, { column: "c", dir: "asc" }, (r) => r)).toEqual(["Etapa 2", "Etapa 10", null]);
    expect(sortRows(rows, { column: "c", dir: "desc" }, (r) => r)).toEqual(["Etapa 10", "Etapa 2", null]);
    expect(compareValues(1, 2, "asc")).toBeLessThan(0);
  });
  it("is stable and does not change the input", () => {
    const rows = [{ k: 1, n: "a" }, { k: 1, n: "b" }];
    expect(sortRows(rows, { column: "c", dir: "desc" }, (r) => r.k).map((r) => r.n)).toEqual(["a", "b"]);
    expect(sortRows(rows, null, undefined)).toBe(rows);
  });
});

describe("pagination", () => {
  it("reports the range and clamps a page that no longer exists", () => {
    const rows = Array.from({ length: 25 }, (_, i) => i);
    expect(paginate(rows, 1, 10)).toMatchObject({ page: 1, pages: 3, from: 1, to: 10, total: 25 });
    expect(paginate(rows, 9, 10)).toMatchObject({ page: 3, from: 21, to: 25 });
    expect(paginate([], 4, 10)).toMatchObject({ page: 1, pages: 1, from: 0, to: 0, total: 0, rows: [] });
  });
});

describe("column layout", () => {
  const ids = ["a", "b", "c"];
  it("drops unknown stored columns and appends new ones", () => {
    expect(reconcileLayout({ order: ["c", "x", "a"], hidden: ["x", "a"] }, ids)).toEqual({ order: ["c", "a", "b"], hidden: ["a"] });
    expect(reconcileLayout(null, ids)).toEqual({ order: ids, hidden: [] });
    expect(reconcileLayout({ order: "bad" as any }, ids)).toEqual({ order: ids, hidden: [] });
  });
  it("moves among visible columns, jumping over hidden ones", () => {
    const l = { order: ids, hidden: ["b"] };
    expect(moveColumn(l, "a", 1).order).toEqual(["c", "b", "a"]);
    expect(moveColumn(l, "a", -1)).toBe(l);
    expect(moveColumn(l, "c", 1)).toBe(l);
  });
  it("never hides the last visible column", () => {
    const l = { order: ids, hidden: ["a", "b"] };
    expect(hideColumn(l, "c", true)).toBe(l);
    expect(hideColumn(l, "a", false).hidden).toEqual(["b"]);
  });
});
