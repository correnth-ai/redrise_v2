// Pure rules of the reusable table: search, sort, pagination and column
// layout. No React here, so they are tested without a screen.
export type SortDir = "asc" | "desc";
export interface Sort { column: string; dir: SortDir }
export interface ColumnLayout { order: string[]; hidden: string[] }
export type SortValue = string | number | null | undefined;

export const normalize = (s: string): string => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();

export function searchRows<T>(rows: T[], query: string, text: (row: T) => string): T[] {
  const q = normalize(query);
  return q ? rows.filter((r) => normalize(text(r)).includes(q)) : rows;
}

/** Empty values always go last, in either direction. Numbers inside text sort as numbers. */
export function compareValues(a: SortValue, b: SortValue, dir: SortDir): number {
  const emptyA = a === null || a === undefined || a === "", emptyB = b === null || b === undefined || b === "";
  if (emptyA || emptyB) return emptyA === emptyB ? 0 : emptyA ? 1 : -1;
  const n = typeof a === "number" && typeof b === "number" ? a - b
    : String(a).localeCompare(String(b), "pt-BR", { numeric: true, sensitivity: "base" });
  return dir === "asc" ? n : -n;
}

export function sortRows<T>(rows: T[], sort: Sort | null, value: ((row: T) => SortValue) | undefined): T[] {
  if (!sort || !value) return rows;
  return rows.map((r, i) => [r, i] as const)
    .sort(([x, i], [y, j]) => compareValues(value(x), value(y), sort.dir) || i - j)
    .map(([r]) => r);
}

export interface PageView<T> { rows: T[]; page: number; pages: number; from: number; to: number; total: number }

/** `page` is 1-based and is clamped: a row removed by an update never leaves an empty page on screen. */
export function paginate<T>(rows: T[], page: number, size: number): PageView<T> {
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / size));
  const p = Math.min(Math.max(1, page), pages);
  const start = (p - 1) * size;
  return { rows: rows.slice(start, start + size), page: p, pages, from: total ? start + 1 : 0, to: Math.min(start + size, total), total };
}

/** A stored layout never hides or loses a column of this version: unknown ids go, new ones are appended. */
export function reconcileLayout(stored: Partial<ColumnLayout> | null | undefined, ids: string[]): ColumnLayout {
  const known = new Set(ids);
  const order = (Array.isArray(stored?.order) ? stored.order : []).filter((c) => known.has(c));
  return { order: [...new Set(order), ...ids.filter((c) => !order.includes(c))],
    hidden: (Array.isArray(stored?.hidden) ? stored.hidden : []).filter((c) => known.has(c)) };
}

/** Moves a column among the visible ones, keeping hidden columns where they are. */
export function moveColumn(layout: ColumnLayout, id: string, delta: -1 | 1): ColumnLayout {
  const shown = layout.order.filter((c) => !layout.hidden.includes(c));
  const i = shown.indexOf(id);
  const other = shown[i + delta];
  if (i < 0 || other === undefined) return layout;
  const a = layout.order.indexOf(id), b = layout.order.indexOf(other);
  const order = [...layout.order];
  [order[a], order[b]] = [order[b], order[a]];
  return { ...layout, order };
}

export function hideColumn(layout: ColumnLayout, id: string, hide: boolean): ColumnLayout {
  const shown = layout.order.filter((c) => !layout.hidden.includes(c));
  if (hide && shown.length <= 1) return layout; // at least one column stays on screen
  return { ...layout, hidden: hide ? [...new Set([...layout.hidden, id])] : layout.hidden.filter((c) => c !== id) };
}
