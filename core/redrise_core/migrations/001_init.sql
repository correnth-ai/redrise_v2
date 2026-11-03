-- RedRise v2 Core schema, version 1. One team per server (D04).
CREATE TABLE team (
  id          integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  name        text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id          bigserial PRIMARY KEY,
  username    text NOT NULL UNIQUE CHECK (username ~ '^[a-z0-9._-]{3,40}$'),
  display     text NOT NULL,
  pw_hash     text NOT NULL,
  role        text NOT NULL CHECK (role IN ('admin', 'operator')),
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  token_hash  bytea PRIMARY KEY,
  user_id     bigint NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL,
  revoked     boolean NOT NULL DEFAULT false
);

CREATE TABLE stations (
  id             bigserial PRIMARY KEY,
  name           text NOT NULL UNIQUE,
  token_hash     bytea NOT NULL UNIQUE,
  created_by     bigint NOT NULL REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now(),
  revoked_at     timestamptz,
  is_host        boolean NOT NULL DEFAULT false,
  platform       text,
  categories     text[] NOT NULL DEFAULT '{}',
  runner_version text,
  session_state  text,
  session_reason text,
  last_seen_at   timestamptz
);

CREATE TABLE routines (
  id          bigserial PRIMARY KEY,
  name        text NOT NULL,
  category    text NOT NULL CHECK (category IN ('browser', 'windows', 'mac', 'linux')),
  created_by  bigint NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  archived    boolean NOT NULL DEFAULT false
);

CREATE TABLE routine_versions (
  id               bigserial PRIMARY KEY,
  routine_id       bigint NOT NULL REFERENCES routines(id),
  version          integer NOT NULL,
  kind             text NOT NULL CHECK (kind IN ('template', 'procedure')),
  template_id      text,
  template_version text,
  procedure        jsonb,
  procedure_sha256 text,
  platform         text,
  inputs           jsonb NOT NULL DEFAULT '{}',
  note             text,
  created_by       bigint NOT NULL REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (routine_id, version),
  CHECK ((kind = 'template' AND template_id IS NOT NULL) OR (kind = 'procedure' AND procedure IS NOT NULL))
);

CREATE TABLE jobs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id         text NOT NULL UNIQUE,
  routine_version_id bigint NOT NULL REFERENCES routine_versions(id),
  station_id         bigint NOT NULL REFERENCES stations(id),
  inputs             jsonb NOT NULL DEFAULT '{}',
  requested_by       bigint NOT NULL REFERENCES users(id),
  state              text NOT NULL CHECK (state IN ('queued', 'claimed', 'running', 'completed_unverified', 'verified',
                                                  'failed', 'uncertain', 'refused', 'cancelled', 'error')),
  lease_id           uuid,
  lease_expires_at   timestamptz,
  attempt            integer NOT NULL DEFAULT 0,
  cancel_requested   boolean NOT NULL DEFAULT false,
  waiting_reason     text,
  result             jsonb,
  diagnostic         jsonb,
  verified           boolean NOT NULL DEFAULT false,
  correlation_id     text NOT NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  claimed_at         timestamptz,
  started_at         timestamptz,
  finished_at        timestamptz
);
CREATE INDEX jobs_station_state ON jobs (station_id, state);

CREATE TABLE job_events (
  id      bigserial PRIMARY KEY,
  job_id  uuid NOT NULL REFERENCES jobs(id),
  at      timestamptz NOT NULL DEFAULT now(),
  state   text NOT NULL,
  detail  jsonb
);
