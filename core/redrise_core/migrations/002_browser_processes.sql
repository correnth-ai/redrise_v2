-- RedRise v2 Core schema, version 2: Browser routines, processes and
-- executions (update Browser, 2026-11). Additive: existing routines, versions,
-- jobs and history are preserved unchanged.

-- A Browser opening routine is a versioned registration (G26/G27): its config
-- (origin, browser, address/path, isolated) lives in the version row, so an
-- edit creates a new version and running executions keep the one they started with.
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_kind_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_kind_check
  CHECK (kind IN ('template', 'procedure', 'browser_open'));
ALTER TABLE routine_versions ADD COLUMN config jsonb;
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_check
  CHECK ((kind = 'template' AND template_id IS NOT NULL) OR (kind = 'procedure' AND procedure IS NOT NULL)
         OR (kind = 'browser_open' AND config IS NOT NULL));

-- Browsers detected by each station's Runner (registered sources and known
-- paths). NULL = not reported (older Runner); [] = reported, none found.
ALTER TABLE stations ADD COLUMN browsers jsonb;

-- Process = ordered links to reusable routines; continuation belongs to the link (G17/G20).
CREATE TABLE processes (
  id          bigserial PRIMARY KEY,
  name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  created_by  bigint NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  archived    boolean NOT NULL DEFAULT false
);

CREATE TABLE process_items (
  process_id    bigint NOT NULL REFERENCES processes(id),
  position      integer NOT NULL CHECK (position >= 1),
  routine_id    bigint NOT NULL REFERENCES routines(id),
  continue_next boolean NOT NULL,
  PRIMARY KEY (process_id, position)
);

-- Execution = one run of a process (or of an isolated routine, process_id NULL).
-- `snapshot` fixes the routine versions and links at start (G27); `context`
-- belongs to this execution only (G24), never to a reusable routine.
CREATE TABLE executions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id     text NOT NULL UNIQUE,
  process_id     bigint REFERENCES processes(id),
  station_id     bigint NOT NULL REFERENCES stations(id),
  requested_by   bigint NOT NULL REFERENCES users(id),
  snapshot       jsonb NOT NULL,
  state          text NOT NULL CHECK (state IN ('running', 'finished')),
  outcome        text CHECK (outcome IN ('completed_unverified', 'verified', 'failed', 'uncertain', 'refused', 'cancelled', 'error')),
  end_reason     text CHECK (end_reason IN ('sequence_end', 'continuation_off', 'not_verified', 'cancelled')),
  context        jsonb NOT NULL DEFAULT '{}',
  correlation_id text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz
);
CREATE INDEX executions_created ON executions (created_at DESC);

-- Each executed routine is a job of its execution; one job per position at
-- most, so a duplicated result report can never start the next routine twice.
ALTER TABLE jobs ADD COLUMN execution_id uuid REFERENCES executions(id);
ALTER TABLE jobs ADD COLUMN position integer;
CREATE UNIQUE INDEX jobs_execution_position ON jobs (execution_id, position) WHERE execution_id IS NOT NULL;
