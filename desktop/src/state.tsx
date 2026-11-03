// Shared app state: one store read by every panel, so tables, grid, Kanban,
// log, timeline and feed always show the same persisted execution records.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AppError } from "@/lib/api";
import type { DataSource } from "@/data/source";
import type { Execution, Me, Process, Routine, Station } from "@/data/types";
import type { Route } from "@/routes";

export interface Store {
  src: DataSource; me: Me; go: (r: Route) => void;
  routines: Routine[] | null; processes: Process[] | null; executions: Execution[] | null; stations: Station[] | null;
  error: unknown; reload: () => Promise<void>;
  run: (target: RunTarget) => void; // opens the shared execution dialog (M06/G47)
  signOut: () => void;
}
export type RunTarget = { kind: "process"; id: number } | { kind: "routine"; id: number } | null;

const Ctx = createContext<Store | null>(null);
export const useStore = () => {
  const s = useContext(Ctx);
  if (!s) throw new Error("store outside provider");
  return s;
};

export const ACTIVE_POLL_MS = 3000, IDLE_POLL_MS = 30000;

export function StoreProvider({ src, me, go, run, signOut, onSessionEnded, children }: { src: DataSource; me: Me; go: (r: Route) => void;
  run: (t: RunTarget) => void; signOut: () => void; onSessionEnded: () => void; children: React.ReactNode }) {
  const [routines, setR] = useState<Routine[] | null>(null);
  const [processes, setP] = useState<Process[] | null>(null);
  const [executions, setE] = useState<Execution[] | null>(null);
  const [stations, setS] = useState<Station[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const alive = useRef(true);
  const busy = useRef(false);
  const onEnded = useRef(onSessionEnded);
  onEnded.current = onSessionEnded;
  const reload = useCallback(async () => {
    try {
      const [r, p, e, s] = await Promise.all([src.routines(), src.processes(), src.executions(), src.stations()]);
      if (!alive.current) return;
      setR(r); setP(p); setE(e); setS(s); setError(null);
      busy.current = e.some((x) => x.state === "running");
    } catch (err) {
      if (err instanceof AppError && err.diagnostic.error_code === "AUTH-REQUIRED") { onEnded.current(); return; }
      if (alive.current) setError(err); // views show the error, never stale fixture numbers
    }
  }, [src]);
  useEffect(() => {
    // Fast only while an execution runs; nothing while the window is hidden (F4).
    alive.current = true;
    let t = 0;
    const tick = async () => {
      window.clearTimeout(t);
      if (document.visibilityState === "visible") await reload();
      if (alive.current) t = window.setTimeout(tick, busy.current ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };
    void tick();
    document.addEventListener("visibilitychange", tick);
    return () => { alive.current = false; window.clearTimeout(t); document.removeEventListener("visibilitychange", tick); };
  }, [reload]);
  return <Ctx.Provider value={{ src, me, go, routines, processes, executions, stations, error, reload, run, signOut }}>{children}</Ctx.Provider>;
}
