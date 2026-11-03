// Four-topic diagnostic (U27): what happened, result, next action, details;
// the code/modules footer is always the last visible line.
import { useState } from "react";
import { AppError, type Diagnostic, diagnosticText, effectText, FOOTER } from "@/lib/api";
import { label, userText } from "@/lib/locale";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function DiagnosticBox({ d }: { d: Diagnostic }) {
  const [copied, setCopied] = useState<string | null>(null);
  const tech = diagnosticText(d, true).split("\n").slice(4, -1).join("\n");
  const eff = effectText(d);
  return (
    <div role="alert" className={cn("my-3 rounded-md border-l-4 bg-bad-soft px-4 py-3 text-sm",
      d.effect_state === "unknown" || d.effect_state === "partial" ? "border-warn bg-warn-soft" : "border-destructive")}>
      <p className="my-1"><b>{label("what", "What happened")}: </b>{userText(d, "what")}</p>
      <p className="my-1"><b>{label("result", "Result")}: </b>{userText(d, "completed")} {userText(d, "pending")}{eff && <em>{eff}</em>}</p>
      <p className="my-1"><b>{label("next", "Next action")}: </b>{userText(d, "next")}</p>
      <details className="my-1">
        <summary className="cursor-pointer">{label("details", "Diagnostic details")}</summary>
        <p>{userText(d, "details")} {label("reference", "Reference")}: {d.correlation_id}.</p>
        <pre className="my-2">{tech}</pre>
        <Button size="sm" variant="outline" type="button" onClick={async () => {
          try { await navigator.clipboard.writeText(diagnosticText(d, true)); setCopied(label("copied", "Copied")); }
          catch { setCopied(label("copy_failed", "Could not copy")); }
        }}>{copied ?? label("copy", "Copy diagnostic")}</Button>
      </details>
      <p className="mt-2 border-t border-dashed pt-1.5 font-mono text-xs text-muted-foreground">{FOOTER(d)}</p>
    </div>
  );
}

export function ErrorView({ error }: { error: unknown }) {
  if (!error) return null;
  if (error instanceof AppError) return <DiagnosticBox d={error.diagnostic} />;
  return <div role="alert" className="my-3 rounded-md border-l-4 border-destructive bg-bad-soft px-4 py-3 text-sm">{String(error)}</div>;
}
