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

export interface AppTarget { kind: "app" | "file"; app_id?: string; path?: string; name: string }
export type MailChannel = { kind: "app"; mail_id: string; name: string } | { kind: "webmail"; provider: string; browser: string; name: string };
export type RoutineConfig = BrowserConfig & { target?: AppTarget; action?: string; assignee_id?: number; to?: string; channel?: MailChannel };
export type RoutineVersionInput = { kind: "browser_open"; config: BrowserConfig } | { kind: "app_open"; config: { target: AppTarget; isolated: boolean } }
  | { kind: "followup"; config: { action: "review"; assignee_id: number } | { action: "report"; labels: Record<string, string> }
    | { action: "notify"; to: string; channel: MailChannel; labels: Record<string, string> } };
export type RoutineLink = { process_id: number; after_position?: number };
export interface Member { id: number; display: string; username: string; active: boolean }
export interface Review { id: string; execution_id: string; position: number; status: "pending" | "approved"; assignee_id: number; assignee_name: string;
  requested_at: string; decided_at: string | null; decided_by_name: string | null; step_name: string; process_name: string | null; requested_by_name: string;
  execution_state: string; context: Record<string, unknown> }
export interface StepChange { id: string; process_id: number; process_name: string; status: "pending" | "approved" | "cancelled"; old_routine_name: string; new_routine_name: string;
  requested_at: string; decided_at: string | null; requested_by: number; requested_by_name: string; decided_by_name: string | null; can_approve: boolean }
export interface NotificationItem { id: number; kind: string; review_id: string | null; change_id: string | null; created_at: string; seen_at: string | null; step_name: string; position: number | null; process_name: string;
  schedule_run_id?: number | null; schedule_state?: string | null; schedule_reason?: string | null; schedule_slot?: string | null }
export interface Notifications { unseen: number; items: NotificationItem[] }
export interface StationApp { id: string; name: string; browser_id?: string; mail_id?: string }
export interface Job { id: string; mode?: string; state: string; diagnostic?: import("@/lib/api").Diagnostic | null; waiting_reason?: string | null;
  events?: { at: string; state: string; detail: any }[] }

export interface Routine {
  id: number; name: string; category: string; created_at: string;
  version_id: number; version: number; kind: "template" | "procedure" | "browser_open" | "notepad_step" | "app_open" | "followup"; assignee_name?: string | null;
  template_id: string | null; template_version: string | null; platform: string | null;
  inputs: Record<string, string>; params: { name: string; role: string }[] | null;
  config: RoutineConfig | null;
}

export interface ProcessItem { position: number; routine_id: number; routine_name: string; continue_next: boolean;
  kind: string; config: RoutineConfig | null }
export interface Process { id: number; name: string; system_key?: string | null; pending_change?: string | null; created_at: string; updated_at: string; items: ProcessItem[];
  last_execution: { id: string; state: string; outcome: string | null; end_reason: string | null; created_at: string } | null;
  /** End of the most recent execution finished as `verified`, over the whole history (Core 0.3.10); null: never. */
  last_success_at?: string | null }

export type JobState = "awaiting_review" | "queued" | "claimed" | "running" | "completed_unverified" | "verified" | "failed" | "uncertain" |
  "refused" | "cancelled" | "error";

export interface ExecutionStep {
  diagnostic?: import("@/lib/api").Diagnostic | null;
  position: number; routine_id: number; routine_version_id: number; name: string; continue_next: boolean;
  job_id: string | null; state: JobState | null; verified: boolean; error_code: string | null;
  started_at: string | null; finished_at: string | null; review?: Review;
}
export interface Execution {
  id: string; request_id: string; process_id: number | null; process_name: string | null; station_id: number;
  station_name: string; requested_by: string; state: "running" | "waiting_review" | "finished"; outcome: JobState | null;
  end_reason: string | null; context: Record<string, unknown>; correlation_id: string; created_at: string;
  finished_at: string | null; steps: ExecutionStep[];
  /** Set when a schedule started it (SCHEDULE-PROCESS-20261107). */
  schedule_id?: number | null;
  /** The process was deleted (PROCESS-ACTIONS-20261111): its id and name stay on its executions. */
  process_archived?: boolean | null;
}

/** The Kanban of one day (PROCESS-ACTIONS-20261111 item 4.3): per process, its latest execution started that day in the team zone. */
export interface KanbanDay { day: string; today: string; timezone: string; since: string; until: string; executions: Execution[] }
export interface ProcessDeleted { archived: boolean; already: boolean; process_id: number; name: string; routines: number[];
  schedules_disabled: number; changes_cancelled: number }

export interface ScheduleInput { process_id: number; station_id: number; weekdays: number[]; hour: number; minute: number; timezone: string }
export interface Schedule {
  id: number; process_id: number; process_name: string; station_id: number; station_name: string; owner_name: string;
  weekdays: number[]; hour: number; minute: number; timezone: string; enabled: boolean; paused_reason: string | null;
  next_slot_local: string | null; next_run_at: string | null;
  last_slot_local: string | null; last_state: "started" | "skipped" | "missed" | "expired" | null; last_reason: string | null; last_execution_id: string | null;
}

export interface DiscoveredBrowser { id: string; name: string; path: string; version: string | null; source: string;
  homologated: boolean }
export interface Station {
  id: number; name: string; is_host: boolean; platform: string | null; categories: string[]; runner_version: string | null;
  session_state: string | null; session_reason: string | null; last_seen_at: string | null; revoked: boolean;
  online: boolean; browsers: DiscoveredBrowser[] | null;
  /** The station this sign-in session runs on (proved by its own credential at login). */
  current?: boolean;
}

export interface Storage {
  db_bytes: number | null;
  counts: { routines: number; processes: number; executions: number; jobs: number };
  local?: { data_bytes: number | null; logs_bytes: number | null } | null;
}

/** Executions started in the last `days` days, counted by the Core per situation (GET /api/v1/executions/summary). */
export interface ExecutionSummary {
  days: number; since: string; until: string; total: number; running: number; waiting: number; attention: number; verified: number;
}

export interface NewExecution { request_id: string; station_id: number; process_id?: number; routine_id?: number }
