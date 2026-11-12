// Small icon button of a table row, with tooltip and accessible name. A disabled one stays
// focusable through its wrapper, so the tooltip still says why it is unavailable. While busy it
// shows a spinner, says so to assistive technology and does not accept another click.
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function IconAction({ label, onClick, disabled, busy, children, expanded, describedBy, destructive }: { label: string; onClick: () => void;
  disabled?: boolean; busy?: boolean; children: React.ReactNode; expanded?: boolean; describedBy?: string; destructive?: boolean }) {
  const off = disabled || busy;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={off ? 0 : -1} className="inline-flex rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Button size="icon" variant="ghost" className={destructive ? "size-8 text-destructive hover:text-destructive" : "size-8"} aria-label={label}
            aria-expanded={expanded} aria-describedby={describedBy} aria-busy={busy || undefined} onClick={onClick} disabled={off}>
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : children}</Button>
        </span>
      </TooltipTrigger>
      <TooltipContent>{busy ? `${label}…` : label}</TooltipContent>
    </Tooltip>
  );
}
