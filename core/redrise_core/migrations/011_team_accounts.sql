-- RedRise v2 Core schema, version 11: team accounts and stations (work order TEAM-ACCOUNTS-20261108).
-- Additive. Deleting an account or a station is logical: the row stays, so executions, reviews,
-- schedules and routines keep pointing to it; it only leaves the managed lists and loses access.
ALTER TABLE users ADD COLUMN deleted_at timestamptz;
ALTER TABLE users ADD CONSTRAINT users_deleted_inactive CHECK (deleted_at IS NULL OR NOT active);

ALTER TABLE stations ADD COLUMN deleted_at timestamptz;
ALTER TABLE stations ADD CONSTRAINT stations_deleted_revoked CHECK (deleted_at IS NULL OR revoked_at IS NOT NULL);
-- A deleted station frees its name, so the same computer can join again under it.
ALTER TABLE stations DROP CONSTRAINT stations_name_key;
CREATE UNIQUE INDEX stations_name_live ON stations (name) WHERE deleted_at IS NULL;

-- The station a sign-in session was opened from, proved by that station's runner token at login.
ALTER TABLE sessions ADD COLUMN station_id bigint REFERENCES stations(id);

DROP TRIGGER rr_change_state ON stations;
CREATE TRIGGER rr_change_state AFTER UPDATE ON stations FOR EACH ROW
  WHEN (OLD.name IS DISTINCT FROM NEW.name OR OLD.revoked_at IS DISTINCT FROM NEW.revoked_at OR OLD.session_state IS DISTINCT FROM NEW.session_state
        OR OLD.session_reason IS DISTINCT FROM NEW.session_reason OR OLD.categories IS DISTINCT FROM NEW.categories OR OLD.runner_version IS DISTINCT FROM NEW.runner_version
        OR OLD.browsers IS DISTINCT FROM NEW.browsers OR OLD.deleted_at IS DISTINCT FROM NEW.deleted_at)
  EXECUTE FUNCTION rr_notify_change('stations');
