// One data source for the whole UI. The shipped app always uses the Core API;
// the demonstration source exists only in a `vite --mode demo` build (fixtures,
// identified on screen) and is never a fallback for a failing backend.
import { api, call } from "@/lib/api";
import type { BrowserConfig, Execution, Me, NewExecution, Process, Routine, Station, Storage } from "./types";

export interface DataSource {
  readonly mode: "real" | "demo";
  me(): Promise<Me>;
  routines(): Promise<Routine[]>;
  processes(): Promise<Process[]>;
  executions(): Promise<Execution[]>;
  stations(): Promise<Station[]>;
  storage(): Promise<Storage>;
  createBrowserRoutine(name: string, config: BrowserConfig): Promise<void>;
  updateBrowserRoutine(id: number, name: string, config: BrowserConfig): Promise<void>;
  saveProcess(id: number | null, name: string, items: { routine_id: number; continue_next: boolean }[]): Promise<void>;
  startExecution(req: NewExecution): Promise<Execution>;
}

export const realSource: DataSource = {
  mode: "real",
  me: () => api("GET", "/api/v1/me"),
  routines: () => api("GET", "/api/v1/routines"),
  processes: () => api("GET", "/api/v1/processes"),
  executions: () => api("GET", "/api/v1/executions"),
  stations: () => api("GET", "/api/v1/stations"),
  async storage() {
    const s: Storage = await api("GET", "/api/v1/storage");
    // Local bytes of this station (data/logs folders), read by the desktop core.
    const local = await call("storage_local").catch(() => null);
    return { ...s, local };
  },
  async createBrowserRoutine(name, config) {
    await api("POST", "/api/v1/routines", { name, category: "browser", version: { kind: "browser_open", config } });
  },
  async updateBrowserRoutine(id, name, config) {
    await api("POST", `/api/v1/routines/${id}/versions`, { kind: "browser_open", config, name });
  },
  async saveProcess(id, name, items) {
    if (id === null) await api("POST", "/api/v1/processes", { name, items });
    else await api("PUT", `/api/v1/processes/${id}`, { name, items });
  },
  startExecution: (req) => api("POST", "/api/v1/executions", req),
};

export const isDemoBuild = import.meta.env.MODE === "demo";
