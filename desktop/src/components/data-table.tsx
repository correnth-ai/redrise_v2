// Reusable table of the app (reference: docs/ui/references/ui-engine-boas-vindas-20261103/rotina-tabela.png):
// tabbed filters, search, filter menu, row selection, sorting from the column
// menu, moving and hiding columns from the header, and pagination. It only
// presents the rows it receives; actions come from the screen that uses it.
import { Fragment, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ChevronsUpDown, Columns3, EyeOff, ListFilter, RotateCcw, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { hideColumn, moveColumn, paginate, reconcileLayout, searchRows, sortRows, type ColumnLayout, type Sort, type SortValue } from "@/lib/table-state";
import { cn } from "@/lib/utils";

export interface DataColumn<T> {
  id: string; header: string; cell: (row: T) => React.ReactNode;
  sortValue?: (row: T) => SortValue;
  searchText?: (row: T) => string;
  /** Stays last and visible, without a column menu (row actions). */
  fixed?: boolean;
  className?: string;
}
export interface DataTab<T> { id: string; label: string; icon?: LucideIcon; match: (row: T) => boolean }
export interface DataFilter<T> { id: string; label: string; options: { value: string; label: string; match: (row: T) => boolean }[] }

export interface DataTableProps<T> {
  label: string;
  rows: T[] | null;
  columns: DataColumn<T>[];
  rowKey: (row: T) => string;
  rowLabel?: (row: T) => string;
  tabs?: DataTab<T>[];
  initialTab?: string;
  filters?: DataFilter<T>[];
  searchPlaceholder?: string;
  empty?: string;
  pageSizes?: number[];
  /** Keeps column order and hidden columns for this person on this computer. */
  storageKey?: string;
  selectable?: boolean;
  selectionActions?: (rows: T[], clear: () => void) => React.ReactNode;
  onRowOpen?: (row: T) => void;
  toolbar?: React.ReactNode;
  /** Child rows shown right under a row (e.g. the routines of an expanded process). They stay on their parent's page
   *  and never count in the pagination; return null to show none. */
  childRows?: (row: T) => React.ReactNode;
  /** Shows "Limpar filtros" while a filter or a search is active. */
  clearable?: boolean;
}

// Row actions stay reachable in a narrow window: the other columns scroll under them. The pinned cell is opaque
// (nothing shows through it) and follows its own row: page background, the same hover mix and the selected color,
// in both themes (TEAM-ACCOUNTS-20261108 item 2: no lighter strip under Ações).
const PINNED = "sticky right-0 z-[1] bg-background shadow-[-1px_0_0_var(--border)] " +
  "group-hover/row:bg-[color-mix(in_srgb,var(--muted)_50%,var(--background))] " +
  "group-has-aria-expanded/row:bg-[color-mix(in_srgb,var(--muted)_50%,var(--background))] group-data-[state=selected]/row:bg-muted";

function readLayout(key: string | undefined, ids: string[]): ColumnLayout {
  let stored: Partial<ColumnLayout> | null = null;
  try { if (key) stored = JSON.parse(localStorage.getItem(`rr.table.${key}`) ?? "null"); } catch { /* storage unavailable or damaged: default layout */ }
  return reconcileLayout(stored, ids);
}

export function DataTable<T>({ label, rows, columns, rowKey, rowLabel, tabs, initialTab, filters, searchPlaceholder = "Buscar…", empty = "Nenhum registro.",
  pageSizes = [10, 25, 50], storageKey, selectable, selectionActions, onRowOpen, toolbar, childRows, clearable }: DataTableProps<T>) {
  const movable = columns.filter((c) => !c.fixed);
  const ids = movable.map((c) => c.id);
  const [stored, setStored] = useState<ColumnLayout>(() => readLayout(storageKey, ids));
  const [tab, setTab] = useState(initialTab ?? tabs?.[0]?.id ?? "");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [sort, setSort] = useState<Sort | null>(null);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(pageSizes[0]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const layout = reconcileLayout(stored, ids);
  const setLayout = (next: ColumnLayout) => {
    setStored(next);
    try { if (storageKey) localStorage.setItem(`rr.table.${storageKey}`, JSON.stringify(next)); } catch { /* kept for this session only */ }
  };
  const byId = (id: string) => movable.find((c) => c.id === id);
  const shownMovable = layout.order.filter((c) => !layout.hidden.includes(c)).map((c) => byId(c)!);
  const shownColumns = [...shownMovable, ...columns.filter((c) => c.fixed)];

  const all = rows ?? [];
  const searchText = (r: T) => columns.map((c) => c.searchText?.(r) ?? "").join(" ");
  let filtered = all;
  for (const f of filters ?? []) {
    const opt = f.options.find((o) => o.value === picked[f.id]);
    if (opt) filtered = filtered.filter(opt.match);
  }
  filtered = searchRows(filtered, query, searchText);
  const activeTab = tabs?.find((t) => t.id === tab);
  const inTab = activeTab ? filtered.filter(activeTab.match) : filtered;
  const view = paginate(sortRows(inTab, sort, sort ? byId(sort.column)?.sortValue : undefined), page, size);

  // Selected rows that left the data (deleted, archived) stop being selected.
  const selectedRows = useMemo(() => all.filter((r) => selected.has(rowKey(r))), [all, selected]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (selectedRows.length !== selected.size) setSelected(new Set(selectedRows.map(rowKey)));
  }, [selectedRows, selected]); // eslint-disable-line react-hooks/exhaustive-deps

  const pageKeys = view.rows.map(rowKey);
  const onPage = pageKeys.filter((k) => selected.has(k)).length;
  const toggle = (keys: string[], on: boolean) => setSelected((cur) => {
    const next = new Set(cur);
    for (const k of keys) { if (on) next.add(k); else next.delete(k); }
    return next;
  });
  const activeFilters = (filters ?? []).filter((f) => f.options.some((o) => o.value === picked[f.id])).length;
  const span = shownColumns.length + (selectable ? 1 : 0);
  const toFirst = () => setPage(1);

  return (
    <div className="space-y-3" role="group" aria-label={label}>
      <div className="flex flex-wrap items-center gap-2">
        {!!tabs?.length && (
          <Tabs value={tab} onValueChange={(v) => { setTab(v); toFirst(); }}>
            <TabsList aria-label={`Filtrar ${label}`}>
              {tabs.map((t) => (
                <TabsTrigger key={t.id} value={t.id}>
                  {t.icon && <t.icon aria-hidden />}{t.label}
                  <Badge variant="secondary" className="ml-0.5 px-1.5 py-0 text-[11px] tabular-nums">{filtered.filter(t.match).length}</Badge>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Input type="search" aria-label={`Buscar em ${label}`} placeholder={searchPlaceholder} className="h-8 w-64" value={query}
            onChange={(e) => { setQuery(e.target.value); toFirst(); }} />
          {!!filters?.length && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline"><ListFilter aria-hidden /> Filtrar{activeFilters > 0 && <Badge className="ml-1 px-1.5 py-0 text-[11px]">{activeFilters}</Badge>}</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {filters.map((f, i) => (
                  <div key={f.id}>
                    {i > 0 && <DropdownMenuSeparator />}
                    <DropdownMenuLabel>{f.label}</DropdownMenuLabel>
                    <DropdownMenuRadioGroup value={picked[f.id] ?? ""} onValueChange={(v) => { setPicked((p) => ({ ...p, [f.id]: v })); toFirst(); }}>
                      <DropdownMenuRadioItem value="">Todos</DropdownMenuRadioItem>
                      {f.options.map((o) => <DropdownMenuRadioItem key={o.value} value={o.value}>{o.label}</DropdownMenuRadioItem>)}
                    </DropdownMenuRadioGroup>
                  </div>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {clearable && (activeFilters > 0 || query.trim() !== "") && (
            <Button size="sm" variant="ghost" onClick={() => { setPicked({}); setQuery(""); toFirst(); }}><X aria-hidden /> Limpar filtros</Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" variant="outline"><Columns3 aria-hidden /> Colunas</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Colunas visíveis</DropdownMenuLabel>
              {movable.map((c) => (
                <DropdownMenuCheckboxItem key={c.id} checked={!layout.hidden.includes(c.id)} onSelect={(e) => e.preventDefault()}
                  disabled={!layout.hidden.includes(c.id) && shownMovable.length <= 1}
                  onCheckedChange={(on) => setLayout(hideColumn(layout, c.id, !on))}>{c.header}</DropdownMenuCheckboxItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => setLayout(reconcileLayout(null, ids))}><RotateCcw aria-hidden /> Restaurar colunas</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {toolbar}
        </div>
      </div>
      {selectable && selectedRows.length > 0 && (
        <div role="status" className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/50 px-3 py-1.5 text-sm">
          <span className="font-medium tabular-nums">{selectedRows.length} {selectedRows.length === 1 ? "selecionada" : "selecionadas"}</span>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}><X aria-hidden /> Limpar seleção</Button>
          <span className="ml-auto flex flex-wrap gap-2">{selectionActions?.(selectedRows, () => setSelected(new Set()))}</span>
        </div>
      )}
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="group/row">
              {selectable && (
                <TableHead className="w-9">
                  <Checkbox aria-label="Selecionar as linhas desta página" disabled={!pageKeys.length}
                    checked={onPage === 0 ? false : onPage === pageKeys.length ? true : "indeterminate"}
                    onCheckedChange={(c) => toggle(pageKeys, c === true)} />
                </TableHead>
              )}
              {shownColumns.map((c, i) => (
                <TableHead key={c.id} className={cn(c.className, c.fixed && PINNED)}
                  aria-sort={sort?.column === c.id ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}>
                  {c.fixed ? c.header : (
                    <ColumnMenu column={c} sort={sort} first={i === 0} last={i === shownMovable.length - 1} canHide={shownMovable.length > 1}
                      onSort={(s) => { setSort(s); toFirst(); }} onMove={(d) => setLayout(moveColumn(layout, c.id, d))} onHide={() => setLayout(hideColumn(layout, c.id, true))} />
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows === null && <TableRow><TableCell colSpan={span} className="text-muted-foreground">Carregando…</TableCell></TableRow>}
            {rows !== null && !view.rows.length && <TableRow><TableCell colSpan={span} className="text-muted-foreground">{all.length ? "Nenhum registro corresponde à busca e aos filtros." : empty}</TableCell></TableRow>}
            {view.rows.map((r) => {
              const key = rowKey(r);
              const children = childRows?.(r);
              return (
                <Fragment key={key}>
                <TableRow data-state={selected.has(key) ? "selected" : undefined}
                  className={cn("group/row", onRowOpen && "cursor-pointer")} tabIndex={onRowOpen ? 0 : undefined}
                  onClick={onRowOpen ? () => onRowOpen(r) : undefined}
                  onKeyDown={onRowOpen ? (k) => { if (k.target === k.currentTarget && (k.key === "Enter" || k.key === " ")) { k.preventDefault(); onRowOpen(r); } } : undefined}>
                  {selectable && (
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Checkbox aria-label={`Selecionar ${rowLabel?.(r) ?? key}`} checked={selected.has(key)} onCheckedChange={(c) => toggle([key], c === true)} />
                    </TableCell>
                  )}
                  {shownColumns.map((c) => (
                    <TableCell key={c.id} className={cn(c.className, c.fixed && PINNED)} onClick={c.fixed ? (e) => e.stopPropagation() : undefined}>{c.cell(r)}</TableCell>
                  ))}
                </TableRow>
                {children && <TableRow className="hover:bg-transparent"><TableCell colSpan={span} className="p-0">{children}</TableCell></TableRow>}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <nav aria-label={`Paginação de ${label}`} className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <p className="text-muted-foreground" aria-live="polite">{view.total ? `Mostrando ${view.from} a ${view.to} de ${view.total} ${view.total === 1 ? "linha" : "linhas"}` : "Nenhuma linha"}</p>
        <div className="ml-auto flex items-center gap-2">
          <label htmlFor={`${label}-size`} className="font-medium">Linhas por página</label>
          <Select value={String(size)} onValueChange={(v) => { setSize(Number(v)); toFirst(); }}>
            <SelectTrigger id={`${label}-size`} size="sm" className="w-20"><SelectValue /></SelectTrigger>
            <SelectContent>{pageSizes.map((n) => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <span className="font-medium tabular-nums">Página {view.page} de {view.pages}</span>
        <div className="flex gap-1">
          <PageButton label="Primeira página" disabled={view.page <= 1} onClick={() => setPage(1)} icon={ChevronsLeft} />
          <PageButton label="Página anterior" disabled={view.page <= 1} onClick={() => setPage(view.page - 1)} icon={ChevronLeft} />
          <PageButton label="Próxima página" disabled={view.page >= view.pages} onClick={() => setPage(view.page + 1)} icon={ChevronRight} />
          <PageButton label="Última página" disabled={view.page >= view.pages} onClick={() => setPage(view.pages)} icon={ChevronsRight} />
        </div>
      </nav>
    </div>
  );
}

function PageButton({ label, disabled, onClick, icon: Icon }: { label: string; disabled: boolean; onClick: () => void; icon: LucideIcon }) {
  return <Button size="icon" variant="outline" className="size-8" aria-label={label} title={label} disabled={disabled} onClick={onClick}><Icon aria-hidden /></Button>;
}

function ColumnMenu<T>({ column, sort, first, last, canHide, onSort, onMove, onHide }: { column: DataColumn<T>; sort: Sort | null; first: boolean; last: boolean;
  canHide: boolean; onSort: (s: Sort | null) => void; onMove: (d: -1 | 1) => void; onHide: () => void }) {
  const dir = sort?.column === column.id ? sort.dir : null;
  const Icon = dir === "asc" ? ArrowUp : dir === "desc" ? ArrowDown : ChevronsUpDown;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label={`Opções da coluna ${column.header}`}
          className={cn("-ml-1 inline-flex items-center gap-1 rounded-sm px-1 py-0.5 font-medium outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring")}>
          {column.header}<Icon aria-hidden className={cn("size-3.5", !dir && "text-muted-foreground")} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {column.sortValue && <>
          <DropdownMenuItem disabled={dir === "asc"} onSelect={() => onSort({ column: column.id, dir: "asc" })}><ArrowUp aria-hidden /> Ordem crescente</DropdownMenuItem>
          <DropdownMenuItem disabled={dir === "desc"} onSelect={() => onSort({ column: column.id, dir: "desc" })}><ArrowDown aria-hidden /> Ordem decrescente</DropdownMenuItem>
          {dir && <DropdownMenuItem onSelect={() => onSort(null)}><X aria-hidden /> Remover ordenação</DropdownMenuItem>}
          <DropdownMenuSeparator />
        </>}
        <DropdownMenuItem disabled={first} onSelect={() => onMove(-1)}><ArrowLeft aria-hidden /> Mover para a esquerda</DropdownMenuItem>
        <DropdownMenuItem disabled={last} onSelect={() => onMove(1)}><ArrowRight aria-hidden /> Mover para a direita</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={!canHide} onSelect={onHide}><EyeOff aria-hidden /> Ocultar coluna</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
