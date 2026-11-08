// One action at a time for a control that calls the Core or the desktop: `busy` disables
// it while the call runs (no double send), and a failure goes to the screen's error.
import { useCallback, useRef, useState } from "react";

export function useAction(onError: (e: unknown) => void) {
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const report = useRef(onError);
  report.current = onError;
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    try { await fn(); } catch (e) { report.current(e); } finally { running.current = false; setBusy(false); }
  }, []);
  return { busy, run };
}
