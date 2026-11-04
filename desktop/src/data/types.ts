// Shapes returned by the Core API /api/v1 (see core/redrise_core/service.py).
export type Role = "admin" | "operator";
export interface Me { id: number; username: string; display: string; role: Role }

export type Origin = "site" | "html";
export interface BrowserConfig {
  origin: Origin;
  browser: string | null; // site only: discovered browser id (chrome, msedge, firefox, chromium)
  url: string | null;     // site only
  path: string | null;    // html only: full local path
  isolated: boolean;      // "Esta rotina pode ser executada isoladamente"
}

export interface Routine {
  id: number; name: string; category: string; created_at: string;
  version_id: number; version: number; kind: "template" | "procedure" | "browser_open" | "notepad_step";
  template_id: string | null; template_version: string | null; platform: string | null;
  inputs: Record<string, string>; params: { name: string; role: string }[] | null;
  config: BrowserConfig | null;
}

export interface ProcessItem { position: number; routine_id: number; routine_name: string; continue_next: boolean;
  kind: string; config: BrowserConfig | null }
export interface Process { id: number; name: string; system_key?: string | null; created_at: string; updated_at: string; items: ProcessItem[];
  last_execution: { id: string; state: string; outcome: string | null; end_reason: string | null; created_at: string } | null }

export type JobState = "queued" | "claimed" | "running" | "completed_unverified" | "verified" | "failed" | "uncertain" |
  "refused" | "cancelled" | "error";

export interface ExecutionStep {
  diagnostic?: import("@/lib/api").Diagnostic | null;
  position: number; routine_id: number; routine_version_id: number; name: string; continue_next: boolean;
  job_id: string | null; state: JobState | null; verified: boolean; error_code: string | null;
  started_at: string | null; finished_at: string | null;
}
export interface Execution {
  id: string; request_id: string; process_id: number | null; process_name: string | null; station_id: number;
  station_name: string; requested_by: string; state: "running" | "finished"; outcome: JobState | null;
  end_reason: string | null; context: Record<string, unknown>; correlation_id: string; created_at: string;
  finished_at: string | null; steps: ExecutionStep[];
}

export interface DiscoveredBrowser { id: string; name: string; path: string; version: string | null; source: string;
  homologated: boolean }
export interface Station {
  id: number; name: string; is_host: boolean; platform: string | null; categories: string[]; runner_version: string | null;
  session_state: string | null; session_reason: string | null; last_seen_at: string | null; revoked: boolean;
  online: boolean; browsers: DiscoveredBrowser[] | null;
}

export interface Storage {
  db_bytes: number | null;
  counts: { routines: number; processes: number; executions: number; jobs: number };
  local?: { data_bytes: number | null; logs_bytes: number | null } | null;
}

export interface NewExecution { request_id: string; station_id: number; process_id?: number; routine_id?: number }
