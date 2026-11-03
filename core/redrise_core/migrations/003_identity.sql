-- Identity (REDRISE-IDENTITY-UI-20261102): link of a provider subject to a team
-- member, and remembered devices. Additive: local users, sessions and roles stay.
CREATE TABLE identity_links (
  subject             text PRIMARY KEY,
  user_id             bigint NOT NULL UNIQUE REFERENCES users(id),
  email               text NOT NULL,
  full_name           text,
  email_confirmed_at  timestamptz,
  linked_at           timestamptz NOT NULL DEFAULT now(),
  last_seen_at        timestamptz
);

CREATE TABLE remembered_devices (
  id               text PRIMARY KEY,
  subject          text NOT NULL REFERENCES identity_links(subject),
  installation_id  text NOT NULL,
  device_name      text NOT NULL,
  windows_user     text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  last_used_at     timestamptz NOT NULL DEFAULT now(),
  expires_at       timestamptz NOT NULL,
  revoked_at       timestamptz
);
CREATE UNIQUE INDEX remembered_devices_active ON remembered_devices (subject, installation_id) WHERE revoked_at IS NULL;

ALTER TABLE sessions ADD COLUMN device_id text REFERENCES remembered_devices(id);
