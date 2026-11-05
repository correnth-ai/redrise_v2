// Searchable list with a text field (combobox pattern): the list filters as the
// person types and works by keyboard. Reused where a plain select would be too long.
import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { normalize } from "@/lib/table-state";
import { cn } from "@/lib/utils";

export interface SearchOption { value: string; label: string; hint?: string; /** Always listed, whatever is typed. */ pinned?: boolean }

export function SearchableSelect({ id, options, value, onChange, placeholder, empty = "Nada encontrado.", disabled }: {
  id?: string; options: SearchOption[]; value: string | null; onChange: (value: string) => void;
  placeholder?: string; empty?: string; disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();
  const q = normalize(query);
  const shown = options.filter((o) => o.pinned || !q || normalize(`${o.label} ${o.hint ?? ""}`).includes(q));
  const picked = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) close(); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  function close() { setOpen(false); setQuery(""); setActive(0); }
  function choose(o: SearchOption | undefined) { if (o) { onChange(o.value); close(); } }
  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return setOpen(true);
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((a) => (shown.length ? (a + step + shown.length) % shown.length : 0));
    } else if (e.key === "Enter" && open) {
      e.preventDefault();
      choose(shown[active]);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      close();
    }
  }
  return (
    <div ref={root} className="relative">
      <Input id={id} role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" autoComplete="off" disabled={disabled}
        aria-activedescendant={open && shown[active] ? `${listId}-${active}` : undefined} className="pr-8"
        value={open ? query : picked?.label ?? ""} placeholder={picked?.label ?? placeholder}
        onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onKeyDown={onKey}
        onChange={(e) => { setQuery(e.target.value); setActive(0); setOpen(true); }} />
      <ChevronsUpDown aria-hidden className="pointer-events-none absolute right-2 top-2.5 size-4 text-muted-foreground" />
      {open && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-md border bg-popover p-1 text-sm shadow-md">
          {!shown.length && <li className="px-2 py-1.5 text-muted-foreground">{empty}</li>}
          {shown.map((o, i) => (
            <li key={o.value} id={`${listId}-${i}`} role="option" aria-selected={o.value === value}
              className={cn("flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5", i === active && "bg-accent text-accent-foreground")}
              onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(o)}>
              <span className="min-w-0 flex-1"><span className="block truncate">{o.label}</span>
                {o.hint && <span className="block truncate text-xs text-muted-foreground">{o.hint}</span>}</span>
              {o.value === value && <Check aria-hidden className="size-4 shrink-0" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
