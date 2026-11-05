// Shared app state: one store read by every panel, so tables, grid, Kanban,
// log, timeline and feed always show the same persisted execution records.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AppError } from "@/lib/api";
import type { DataSource } from "@/data/source";
import type { Execution, Me, Notifications, Process, Review, Routine, Station, StepChange } from "@/data/types";
import type { Route } from "@/routes";

export interface Store {
  src: DataSource; me: Me; go: (r: Route) => void;
  routines: Routine[] | null; processes: Process[] | null; executions: Execution[] | null; stations: Station[] | null;
  reviews: Review[] | null; stepChanges: StepChange[] | null; notifications: Notifications | null;
  error: unknown; reload: () => Promise<void>;
  /** Grows each time the Core says something changed: for screens that read their own data. */
  changeTick: number;
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
export const CHANGE_WAIT_S = 18, SETTLE_MS = 250, CHANGE_RETRY_MS = 5000;

export function StoreProvider({ src, me, go, run, signOut, onSessionEnded, children }: { src: DataSource; me: Me; go: (r: Route) => void;
  run: (t: RunTarget) => void; signOut: () => void; onSessionEnded: () => void; children: React.ReactNode }) {
  const [routines, setR] = useState<Routine[] | null>(null);
  const [processes, setP] = useState<Process[] | null>(null);
  const [executions, setE] = useState<Execution[] | null>(null);
  const [stations, setS] = useState<Station[] | null>(null);
  const [reviews, setV] = useState<Review[] | null>(null);
  const [notifications, setN] = useState<Notifications | null>(null);
  const [stepChanges, setC] = useState<StepChange[] | null>(null);
  const [changeTick, setTick] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const alive = useRef(true);
  const busy = useRef(false);
  const onEnded = useRef(onSessionEnded);
  onEnded.current = onSessionEnded;
  const lastRead = useRef(0);
  const reload = useCallback(async () => {
    const mine = ++lastRead.current; // a slow older read never overwrites a newer one
    try {
      const [r, p, e, s, v, n, c] = await Promise.all([src.routines(), src.processes(), src.executions(), src.stations(), src.reviews(), src.notifications(), src.stepChanges()]);
      if (!alive.current || mine !== lastRead.current) return;
      setR(r); setP(p); setE(e); setS(s); setV(v); setN(n); setC(c); setError(null);
      busy.current = e.some((x) => x.state === "running");
    } catch (err) {
      if (err instanceof AppError && err.diagnostic.error_code === "AUTH-REQUIRED") { onEnded.current(); return; }
      if (alive.current && mine === lastRead.current) setError(err); // views show the error, never stale fixture numbers
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
  useEffect(() => {
    // Live tables (docs/ui/LIVE-TABLES.md): waits for the Core to say something changed, then reads again. Stops while
    // hidden. Failing costs only speed: the periodic read above goes on.
    let on = true;
    let epoch: string | null = null;
    let seq: number | null = null;
    const pause = (ms: number) => new Promise((res) => window.setTimeout(res, ms));
    const loop = async () => {
      while (on) {
        if (document.visibilityState !== "visible") { await pause(1000); continue; }
        try {
          const out = await src.changes(epoch, seq, seq === null ? 0 : CHANGE_WAIT_S);
          const first = seq === null;
          epoch = out.epoch; seq = out.seq;
          if (on && !first && out.domains.length) {
            await pause(SETTLE_MS); // a burst of changes becomes one read
            await reload();
            setTick((n) => n + 1);
          }
        } catch { await pause(CHANGE_RETRY_MS); }
      }
    };
    void loop();
    return () => { on = false; };
  }, [src, reload]);
  return <Ctx.Provider value={{ changeTick, src, me, go, routines, processes, executions, stations, reviews, stepChanges, notifications, error, reload, run, signOut }}>{children}</Ctx.Provider>;
}
