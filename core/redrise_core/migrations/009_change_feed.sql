-- RedRise v2 Core schema, version 9: what changed, for live tables (work order
-- UI-ENGINE-BOAS-VINDAS-20261103). Additive and without new data: NOTIFY reaches
-- the Core only on commit, and two writers never wait on each other because of it.
-- Inventory of tables and rules: docs/ui/LIVE-TABLES.md.
CREATE FUNCTION rr_notify_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_notify('rr_changes', TG_ARGV[0]);
  RETURN NULL;
END $$;

CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON routines FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('routines');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON routine_versions FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('routines');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON processes FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('processes');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON process_items FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('processes');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON executions FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('executions');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON review_requests FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('reviews');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON step_change_requests FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('step_changes');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON notifications FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('notifications');
CREATE TRIGGER rr_change AFTER INSERT OR UPDATE OR DELETE ON users FOR EACH STATEMENT EXECUTE FUNCTION rr_notify_change('users');

-- These two get a write at every heartbeat: only what a screen shows counts.
CREATE TRIGGER rr_change_new AFTER INSERT ON jobs FOR EACH ROW EXECUTE FUNCTION rr_notify_change('jobs');
CREATE TRIGGER rr_change_state AFTER UPDATE ON jobs FOR EACH ROW
  WHEN (OLD.state IS DISTINCT FROM NEW.state OR OLD.waiting_reason IS DISTINCT FROM NEW.waiting_reason OR OLD.cancel_requested IS DISTINCT FROM NEW.cancel_requested)
  EXECUTE FUNCTION rr_notify_change('jobs');
CREATE TRIGGER rr_change_new AFTER INSERT OR DELETE ON stations FOR EACH ROW EXECUTE FUNCTION rr_notify_change('stations');
CREATE TRIGGER rr_change_state AFTER UPDATE ON stations FOR EACH ROW
  WHEN (OLD.name IS DISTINCT FROM NEW.name OR OLD.revoked_at IS DISTINCT FROM NEW.revoked_at OR OLD.session_state IS DISTINCT FROM NEW.session_state
        OR OLD.session_reason IS DISTINCT FROM NEW.session_reason OR OLD.categories IS DISTINCT FROM NEW.categories OR OLD.runner_version IS DISTINCT FROM NEW.runner_version
        OR OLD.browsers IS DISTINCT FROM NEW.browsers)
  EXECUTE FUNCTION rr_notify_change('stations');
