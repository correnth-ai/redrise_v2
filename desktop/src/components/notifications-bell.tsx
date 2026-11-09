// Bell right after the theme toggle. The red badge counts what was not seen and is
// hidden at zero. Opening a notification marks it as seen and goes to the request in
// Marcado para mim; approving stays a separate action there.
import { Bell } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import type { NotificationItem } from "@/data/types";
import { cn, when } from "@/lib/utils";
import { useStore } from "@/state";
import { scheduleNote } from "@/features/schedules";

export function NotificationsBell() {
  const { notifications, src, reload, go } = useStore();
  const unseen = notifications?.unseen ?? 0;
  async function open(n: NotificationItem) {
    go({ menu: "processo", page: "acao", id: n.kind === "schedule" ? "schedules" : n.review_id ?? n.change_id, nonce: Date.now() });
    try { if (!n.seen_at) await src.markNotificationSeen(n.id); } finally { await reload(); }
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label={unseen ? `Notificações, ${unseen} não ${unseen === 1 ? "vista" : "vistas"}` : "Notificações"} title="Notificações"
          className="relative inline-flex size-8 items-center justify-center rounded-full text-muted-foreground outline-none hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          <Bell aria-hidden className="size-4" />
          {unseen > 0 && <span aria-hidden className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-none text-white">{unseen > 99 ? "99+" : unseen}</span>}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Notificações</DropdownMenuLabel>
        {!notifications?.items.length && <p className="px-2 py-3 text-sm text-muted-foreground">Nenhuma notificação.</p>}
        {notifications?.items.map((n) => (
          <DropdownMenuItem key={n.id} onSelect={() => void open(n)} className="items-start">
            <span aria-hidden className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.seen_at ? "bg-transparent" : "bg-red-600")} />
            <span className="min-w-0">
              <span className={cn("block truncate", !n.seen_at && "font-medium")}>{n.kind === "schedule" ? scheduleNote(n.schedule_state ?? null, n.schedule_reason ?? null) : `${n.kind === "step_change" ? "Substituição da etapa 1" : "Revisão pedida"}: ${n.step_name}`}</span>
              <span className="block truncate text-xs text-muted-foreground">{n.process_name} · {when(n.created_at)}{n.seen_at ? "" : " · não vista"}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
