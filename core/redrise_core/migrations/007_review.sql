-- RedRise v2 Core schema, version 7: follow-up with review (work order
-- UI-ENGINE-BOAS-VINDAS-20261103). Additive. A followup routine acts after a
-- step of a process; `action` is in its config. A review pauses the execution
-- until its current assignee approves; the row lock on the request settles
-- reassignment and approval, so there is one decision and one resumption.
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_kind_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_kind_check
  CHECK (kind IN ('template', 'procedure', 'browser_open', 'notepad_step', 'app_open', 'followup'));
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_check
  CHECK ((kind = 'template' AND template_id IS NOT NULL) OR (kind = 'procedure' AND procedure IS NOT NULL)
         OR (kind IN ('browser_open', 'notepad_step', 'app_open', 'followup') AND config IS NOT NULL));

ALTER TABLE executions DROP CONSTRAINT executions_state_check;
ALTER TABLE executions ADD CONSTRAINT executions_state_check CHECK (state IN ('running', 'waiting_review', 'finished'));

CREATE TABLE review_requests (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id  uuid NOT NULL REFERENCES executions(id),
  position      integer NOT NULL,
  routine_id    bigint NOT NULL REFERENCES routines(id),
  assignee_id   bigint NOT NULL REFERENCES users(id),
  status        text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved')),
  requested_at  timestamptz NOT NULL DEFAULT now(),
  decided_by    bigint REFERENCES users(id),
  decided_at    timestamptz,
  UNIQUE (execution_id, position)
);
CREATE INDEX review_requests_assignee ON review_requests (assignee_id, status);
CREATE INDEX review_requests_pending ON review_requests (routine_id) WHERE status = 'pending';

CREATE TABLE notifications (
  id          bigserial PRIMARY KEY,
  user_id     bigint NOT NULL REFERENCES users(id),
  kind        text NOT NULL CHECK (kind IN ('review_request')),
  review_id   uuid NOT NULL REFERENCES review_requests(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  seen_at     timestamptz
);
CREATE INDEX notifications_user ON notifications (user_id, created_at DESC);
