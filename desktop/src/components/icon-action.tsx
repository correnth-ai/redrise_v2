// Small icon button of a table row, with tooltip and accessible name. A disabled one stays
// focusable through its wrapper, so the tooltip still says why it is unavailable.
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function IconAction({ label, onClick, disabled, children, expanded }: { label: string; onClick: () => void; disabled?: boolean;
  children: React.ReactNode; expanded?: boolean }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={disabled ? 0 : -1}>
          <Button size="icon" variant="ghost" className="size-8" aria-label={label} aria-expanded={expanded} onClick={onClick} disabled={disabled}>{children}</Button>
        </span>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
