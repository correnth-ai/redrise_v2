// One data source for the whole UI. The shipped app always uses the Core API;
// the demonstration source exists only in a `vite --mode demo` build (fixtures,
// identified on screen) and is never a fallback for a failing backend.
import { api, call } from "@/lib/api";
import type { Execution, ExecutionSummary, Job, Me, Member, NewExecution, Notifications, Process, Review, Routine, RoutineLink, RoutineVersionInput, Station, StationApp, StepChange, Storage } from "./types";

export interface DataSource {
  readonly mode: "real" | "demo";
  me(): Promise<Me>;
  routines(): Promise<Routine[]>;
  processes(): Promise<Process[]>;
  executions(): Promise<Execution[]>;
  /** Counts for the period, from the Core; never from the capped list above. */
  executionSummary(): Promise<ExecutionSummary>;
  /** Executions started in the last `days` days, newest first, up to 500: the rows behind the summary. */
  executionsSince(days: number): Promise<Execution[]>;
  stations(): Promise<Station[]>;
  storage(): Promise<Storage>;
  apps(stationId: number): Promise<{ apps: StationApp[] | null }>;
  pickFile(): Promise<string | null>;
  createRoutine(name: string, category: string, version: RoutineVersionInput, link: RoutineLink | null): Promise<number>;
  addRoutineVersion(id: number, name: string, version: RoutineVersionInput): Promise<void>;
  prepareRoutine(id: number, requestId: string, stationId: number): Promise<Job>;
  testRoutine(id: number, requestId: string, prepareJobId: string): Promise<Job>;
  job(id: string): Promise<Job>;
  cancelJob(id: string): Promise<void>;
  integrateRoutine(processId: number, routineId: number): Promise<void>;
  members(): Promise<Member[]>;
  execution(id: string): Promise<Execution>;
  reviews(): Promise<Review[]>;
  approveReview(id: string): Promise<void>;
  notifications(): Promise<Notifications>;
  markNotificationSeen(id: number): Promise<void>;
  openReportFolder(name: string): Promise<void>;
  changes(epoch: string | null, seq: number | null, waitS: number): Promise<{ epoch: string; seq: number; domains: string[] }>;
  stepChanges(): Promise<StepChange[]>;
  requestStepChange(processId: number, routineId: number): Promise<void>;
  approveStepChange(id: string): Promise<void>;
  cancelStepChange(id: string): Promise<void>;
  archiveRoutine(id: number): Promise<void>;
  saveProcess(id: number | null, name: string, items: { routine_id: number; continue_next: boolean }[]): Promise<void>;
  startExecution(req: NewExecution): Promise<Execution>;
}

export const realSource: DataSource = {
  mode: "real",
  me: () => api("GET", "/api/v1/me"),
  routines: () => api("GET", "/api/v1/routines"),
  processes: () => api("GET", "/api/v1/processes"),
  executions: () => api("GET", "/api/v1/executions"),
  executionSummary: () => api("GET", "/api/v1/executions/summary"),
  executionsSince: (days) => api("GET", `/api/v1/executions?days=${Math.trunc(days)}`),
  stations: () => api("GET", "/api/v1/stations"),
  async storage() {
    const s: Storage = await api("GET", "/api/v1/storage");
    // Local bytes of this station (data/logs folders), read by the desktop core.
    const local = await call("storage_local").catch(() => null);
    return { ...s, local };
  },
  apps: (stationId) => api("GET", `/api/v1/stations/${stationId}/apps`),
  pickFile: () => call("pick_file"),
  async createRoutine(name, category, version, link) {
    const out = await api("POST", "/api/v1/routines", { name, category, version, ...(link ? { link } : {}) });
    return out.routine.id;
  },
  async addRoutineVersion(id, name, version) {
    await api("POST", `/api/v1/routines/${id}/versions`, { ...version, name });
  },
  prepareRoutine: (id, requestId, stationId) => api("POST", `/api/v1/routines/${id}/prepare`, { request_id: requestId, station_id: stationId }),
  testRoutine: (id, requestId, prepareJobId) => api("POST", `/api/v1/routines/${id}/test`, { request_id: requestId, prepare_job_id: prepareJobId }),
  job: (id) => api("GET", `/api/v1/jobs/${id}`),
  async cancelJob(id) {
    await api("POST", `/api/v1/jobs/${id}/cancel`);
  },
  async integrateRoutine(processId, routineId) {
    await api("POST", `/api/v1/processes/${processId}/items`, { routine_id: routineId });
  },
  members: () => api("GET", "/api/v1/users"),
  execution: (id) => api("GET", `/api/v1/executions/${id}`),
  reviews: () => api("GET", "/api/v1/reviews"),
  async approveReview(id) {
    await api("POST", `/api/v1/reviews/${id}/approve`);
  },
  notifications: () => api("GET", "/api/v1/notifications"),
  async markNotificationSeen(id) {
    await api("POST", `/api/v1/notifications/${id}/seen`);
  },
  async openReportFolder(name) {
    await call("open_report_folder", { name });
  },
  changes: (epoch, seq, waitS) => api("POST", "/api/v1/changes", { epoch, seq, wait_s: waitS }),
  stepChanges: () => api("GET", "/api/v1/step-changes"),
  async requestStepChange(processId, routineId) {
    await api("POST", `/api/v1/processes/${processId}/step1`, { routine_id: routineId });
  },
  async approveStepChange(id) {
    await api("POST", `/api/v1/step-changes/${id}/approve`);
  },
  async cancelStepChange(id) {
    await api("POST", `/api/v1/step-changes/${id}/cancel`);
  },
  async archiveRoutine(id) {
    await api("DELETE", `/api/v1/routines/${id}`);
  },
  async saveProcess(id, name, items) {
    if (id === null) await api("POST", "/api/v1/processes", { name, items });
    else await api("PUT", `/api/v1/processes/${id}`, { name, items });
  },
  startExecution: (req) => api("POST", "/api/v1/executions", req),
};

export const isDemoBuild = import.meta.env.MODE === "demo";
