-- RedRise v2 Core schema, version 10: scheduled processes (work order SCHEDULE-PROCESS-20261107).
-- An occurrence is identified by its local date and time in the schedule's own time zone
-- (slot_local, 'YYYY-MM-DDTHH:MM'): unique per schedule, and the base of the execution request_id.
CREATE TABLE schedules (
  id               bigserial PRIMARY KEY,
  process_id       bigint NOT NULL REFERENCES processes(id),
  station_id       bigint NOT NULL REFERENCES stations(id),
  weekdays         smallint NOT NULL CHECK (weekdays BETWEEN 1 AND 127),  -- bit 0 = Monday ... bit 6 = Sunday
  hour             smallint NOT NULL CHECK (hour BETWEEN 0 AND 23),
  minute           smallint NOT NULL CHECK (minute BETWEEN 0 AND 59),
  timezone         text NOT NULL,                                         -- fixed; changes only when an administrator edits
  enabled          boolean NOT NULL DEFAULT true,
  paused_reason    text,
  owner_id         bigint NOT NULL REFERENCES users(id),
  next_slot_local  text,
  next_run_at      timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX schedules_due ON schedules (next_run_at) WHERE enabled;

CREATE TABLE schedule_runs (
  id            bigserial PRIMARY KEY,
  schedule_id   bigint NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
  slot_local    text NOT NULL,
  slot_at       timestamptz NOT NULL,
  state         text NOT NULL CHECK (state IN ('started', 'skipped', 'missed', 'expired')),
  reason        text,
  execution_id  uuid REFERENCES executions(id),
  diagnostic    jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (schedule_id, slot_local),
  CHECK ((state = 'started') = (execution_id IS NOT NULL) OR state = 'expired')
);
CREATE INDEX schedule_runs_open ON schedule_runs (slot_at) WHERE state = 'started';

ALTER TABLE executions ADD COLUMN schedule_id bigint REFERENCES schedules(id) ON DELETE SET NULL;

ALTER TABLE notifications ADD COLUMN schedule_run_id bigint REFERENCES schedule_runs(id) ON DELETE CASCADE;
ALTER TABLE notifications DROP CONSTRAINT notifications_kind_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check CHECK (kind IN ('review_request', 'step_change', 'schedule'));
ALTER TABLE notifications DROP CONSTRAINT notifications_target;
ALTER TABLE notifications ADD CONSTRAINT notifications_target CHECK (num_nonnulls(review_id, change_id, schedule_run_id) = 1);

CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON schedules FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('schedules');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON schedule_runs FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('schedules');
