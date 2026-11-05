-- RedRise v2 Core schema, version 8: replacing step 1 of a process with approval
-- (work order UI-ENGINE-BOAS-VINDAS-20261103). Additive. Apart from the review that
-- pauses an execution: this one changes the process itself, while it is not running.
CREATE TABLE step_change_requests (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  process_id      bigint NOT NULL REFERENCES processes(id),
  old_routine_id  bigint NOT NULL REFERENCES routines(id),
  new_routine_id  bigint NOT NULL REFERENCES routines(id),
  requested_by    bigint NOT NULL REFERENCES users(id),
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'cancelled')),
  requested_at    timestamptz NOT NULL DEFAULT now(),
  decided_by      bigint REFERENCES users(id),
  decided_at      timestamptz
);
CREATE UNIQUE INDEX step_change_one_pending ON step_change_requests (process_id) WHERE status = 'pending';

ALTER TABLE notifications ALTER COLUMN review_id DROP NOT NULL;
ALTER TABLE notifications ADD COLUMN change_id uuid REFERENCES step_change_requests(id);
ALTER TABLE notifications DROP CONSTRAINT notifications_kind_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check CHECK (kind IN ('review_request', 'step_change'));
ALTER TABLE notifications ADD CONSTRAINT notifications_target CHECK ((review_id IS NULL) <> (change_id IS NULL));
