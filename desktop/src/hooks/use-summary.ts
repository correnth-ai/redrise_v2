import { useEffect, useState } from "react";
import type { ExecutionSummary } from "@/data/types";
import { useStore } from "@/state";

/** Executions of the last 30 days by situation, counted by the Core (not the 100 most recent the store holds).
 *  Read again on every store read (change feed or periodic read): each one gives a new executions list.
 *  On failure the summary is null and the error is returned: callers show "—" and the diagnostic, never zero. */
export function useExecutionSummary(): { summary: ExecutionSummary | null; error: unknown } {
  const { src, executions } = useStore();
  const [summary, setSummary] = useState<ExecutionSummary | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let on = true;
    src.executionSummary().then((s) => { if (on) { setSummary(s); setError(null); } },
      (e) => { if (on) { setSummary(null); setError(e); } });
    return () => { on = false; };
  }, [src, executions]);
  return { summary, error };
}
