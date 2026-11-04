"""Core domain operations: team bootstrap, accounts, stations, routines and
versions, jobs with leases (P05-D6..D10). Every refusal is an `ApiError`
carrying a redrise.diagnostic/1; the HTTP layer only maps it."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import timedelta

import psycopg
from psycopg.types.json import Jsonb

from redrise_contracts import diagnostics as dg

from . import __version__, auth, identity
from .db import Database

SESSION_TTL = timedelta(hours=12)
REMEMBER_TTL = timedelta(days=30)  # absolute per remembered device; renewal does not extend it
LEASE = timedelta(seconds=60)
TERMINAL = ("completed_unverified", "verified", "failed", "uncertain", "refused", "cancelled", "error")
RUNNER_STATES = ("completed_unverified", "verified", "failed", "uncertain", "refused", "cancelled", "error")
CATEGORIES = ("browser", "windows", "mac", "linux")
# Browser ids a station Runner can report (redrise_runner.browsers.CANDIDATES).
BROWSER_IDS = ("chrome", "msedge", "firefox", "chromium")
MAX_PROCESS_ITEMS = 50
PROCESS_KINDS = ("browser_open", "notepad_step")
WELCOME_KEY = "boas-vindas"
WELCOME_PROCESS = "Boas-vindas"
# Routines of the ready-made process; the Runner reads `step` (redrise_runner.notepad_steps).
WELCOME_STEPS = (("Abrir e identificar", "open"), ("Digitar e salvar", "save"), ("Fechar e verificar", "close"))
_URL = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
_HTML_PATH = re.compile(r"^([a-zA-Z]:\\|\\\\[^\\]+\\[^\\]+\\).+\.html?$", re.IGNORECASE)
JOB_SCHEMA, RESULT_SCHEMA = "redrise.job/1", "redrise.job-result/1"


class ApiError(Exception):
    def __init__(self, status: int, diagnostic: dg.Diagnostic):
        super().__init__(diagnostic.error_code)
        self.status, self.diagnostic = status, diagnostic


def err(status: int, code: str, cid: str | None = None, **params) -> ApiError:
    return ApiError(status, dg.make(code, reported_by="RR-CORE", params=params, correlation_id=cid,
                                    version={"core": __version__}, technical_details=params))


_USER = re.compile(r"^[a-z0-9._-]{3,40}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _uuid(v, what: str = "identifier") -> str:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError):
        raise err(400, "VALIDATION", reason=f"invalid {what}") from None


def _check_password(pw) -> None:
    if not isinstance(pw, str) or len(pw) < auth.MIN_PASSWORD:
        raise err(400, "VALIDATION", reason=f"password must have at least {auth.MIN_PASSWORD} characters")


def browser_config(cfg) -> dict:
    """Validates a Browser opening registration (B01-B03, G25): only the
    fields of the active origin are kept; HTML never carries a browser."""
    if not isinstance(cfg, dict):
        raise err(400, "VALIDATION", reason="config must be an object")
    origin = cfg.get("origin")
    if not isinstance(cfg.get("isolated"), bool):
        raise err(400, "VALIDATION", reason="isolated must be true or false")
    if origin == "site":
        url, browser = cfg.get("url"), cfg.get("browser")
        if browser not in BROWSER_IDS:
            raise err(400, "VALIDATION", reason="choose one of the detected browsers")
        if not isinstance(url, str) or len(url) > 2000 or not _URL.match(url.strip()):
            raise err(400, "VALIDATION", reason="address must start with http:// or https://")
        return {"origin": "site", "browser": browser, "url": url.strip(), "path": None, "isolated": cfg["isolated"]}
    if origin == "html":
        path = cfg.get("path")
        if not isinstance(path, str) or len(path) > 1000 or not _HTML_PATH.match(path.strip()):
            raise err(400, "VALIDATION", reason="full path of an .html or .htm file expected")
        return {"origin": "html", "browser": None, "url": None, "path": path.strip(), "isolated": cfg["isolated"]}
    raise err(400, "VALIDATION", reason="origin must be site or html")


def _station_browsers(raw) -> list[dict] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for b in raw[:20]:
        if isinstance(b, dict) and b.get("id") in BROWSER_IDS:
            out.append({"id": b["id"], "name": str(b.get("name") or b["id"])[:60], "path": str(b.get("path") or "")[:400],
                        "version": (str(b["version"])[:40] if b.get("version") else None),
                        "source": str(b.get("source") or "")[:40], "homologated": bool(b.get("homologated"))})
    return out


def _public_user(u: dict) -> dict:
    return {k: u[k] for k in ("id", "username", "display", "role", "active")}


class Core:
    def __init__(self, db: Database, templates: dict[str, dict] | None = None, verifier: identity.Verifier | None = None):
        self.db = db
        self.templates = templates or {}  # id -> template.json of this release
        self.verifier = verifier  # identity provider adapter; None: e-mail sign-in unavailable here

    # ------------------------------------------------------------ team / accounts
    def status(self) -> dict:
        with self.db.tx() as c:
            t = c.execute("SELECT name FROM team").fetchone()
        return {"initialized": t is not None, "team": t["name"] if t else None, "core": __version__}

    def bootstrap(self, team: str, username: str, display: str, password: str) -> dict:
        if not team or not isinstance(team, str) or len(team) > 80:
            raise err(400, "VALIDATION", reason="invalid team name")
        if not isinstance(username, str) or not _USER.match(username):
            raise err(400, "VALIDATION", reason="user name: 3-40 characters a-z 0-9 . _ -")
        _check_password(password)
        with self.db.tx() as c:
            row = c.execute("INSERT INTO team (id, name) VALUES (1, %s) ON CONFLICT DO NOTHING RETURNING id", (team,)).fetchone()
            if row is None:
                raise err(409, "SETUP-ALREADY-DONE")
            u = c.execute("INSERT INTO users (username, display, pw_hash, role) VALUES (%s, %s, %s, 'admin') RETURNING *",
                          (username, display or username, auth.hash_password(password))).fetchone()
        self.ensure_welcome_process()
        return _public_user(u)

    def ensure_welcome_process(self) -> None:
        """The ready-made Boas-vindas process, created once per team (at setup, or at the first start
        of this version on an existing team). Without an administrator there is no team yet."""
        with self.db.tx() as c:
            if c.execute("SELECT 1 FROM processes WHERE system_key = %s", (WELCOME_KEY,)).fetchone():
                return
            admin = c.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1").fetchone()
            if not admin:
                return
            p = c.execute("INSERT INTO processes (name, created_by, system_key) VALUES (%s, %s, %s) RETURNING id",
                          (WELCOME_PROCESS, admin["id"], WELCOME_KEY)).fetchone()
            for i, (name, step) in enumerate(WELCOME_STEPS, 1):
                r = c.execute("INSERT INTO routines (name, category, created_by) VALUES (%s, 'windows', %s) RETURNING id",
                              (name, admin["id"])).fetchone()
                c.execute("""INSERT INTO routine_versions (routine_id, version, kind, platform, inputs, note, created_by, config)
                             VALUES (%s, 1, 'notepad_step', 'windows-x86_64', '{}', %s, %s, %s)""",
                          (r["id"], "ready-made Boas-vindas process", admin["id"], Jsonb({"step": step, "isolated": False})))
                c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, %s, %s, true)",
                          (p["id"], i, r["id"]))

    def register(self, full_name, email, password) -> dict:
        """Sign-up: records the account and nothing else. It starts inactive, as an operator, so creating an
        account grants no access to the team until an administrator activates it in Configuracao > Equipe."""
        if not isinstance(full_name, str) or not 1 <= len(full_name.strip()) <= 120:
            raise err(400, "VALIDATION", reason="full name required")
        if not isinstance(email, str) or len(email) > 254 or not _EMAIL.match(email.strip()):
            raise err(400, "VALIDATION", reason="invalid e-mail")
        _check_password(password)
        email = email.strip().lower()
        base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0])[:32].ljust(3, "0")
        with self.db.tx() as c:
            if not c.execute("SELECT 1 FROM team").fetchone():
                raise err(409, "VALIDATION", reason="team not set up")
            if c.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone():
                raise err(409, "ACCOUNT-EXISTS")
            username, n = base, 1
            while c.execute("SELECT 1 FROM users WHERE username = %s", (username,)).fetchone():
                n += 1
                username = f"{base}.{n}"
            c.execute("INSERT INTO users (username, display, pw_hash, role, active, email) VALUES (%s, %s, %s, 'operator', false, %s)",
                      (username, full_name.strip(), auth.hash_password(password), email))
        return {"pending": True}

    def login(self, username: str, password: str) -> dict:
        with self.db.tx() as c:
            who = username.strip().lower() if isinstance(username, str) else username
            u = c.execute("SELECT * FROM users WHERE username = %s OR email = %s", (who, who)).fetchone()
            ok = auth.verify_password(password or "", u["pw_hash"] if u else auth.DUMMY_HASH)
            if not u or not ok or not u["active"]:
                raise err(401, "AUTH-INVALID")
            token, h = auth.new_token()
            c.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, now() + %s)",
                      (h, u["id"], SESSION_TTL))
        return {"token": token, "user": _public_user(u), "expires_in_s": int(SESSION_TTL.total_seconds())}

    # ------------------------------------------------------------ identity (provider subject -> team member)
    def _verified(self, access_token) -> identity.Identity:
        if self.verifier is None:
            raise err(503, "IDENTITY-NOT-CONFIGURED", reason="identity.json")
        if not isinstance(access_token, str) or not access_token:
            raise err(400, "VALIDATION", reason="access token required")
        try:
            return self.verifier.verify(access_token)
        except identity.ProviderUnavailable as e:
            raise err(503, "IDENTITY-PROVIDER-UNAVAILABLE", reason=str(e)) from None
        except identity.EmailUnconfirmed:
            raise err(403, "IDENTITY-UNCONFIRMED") from None
        except identity.TokenRefused:
            raise err(401, "IDENTITY-INVALID") from None

    @staticmethod
    def _device_meta(device) -> tuple[str, str, str | None]:
        d = device if isinstance(device, dict) else {}
        inst, name, win = d.get("installation_id"), d.get("name"), d.get("windows_user")
        if not isinstance(inst, str) or not 8 <= len(inst) <= 80 or not isinstance(name, str) or not 1 <= len(name) <= 120:
            raise err(400, "VALIDATION", reason="invalid device")
        return inst, name, win if isinstance(win, str) and len(win) <= 120 else None

    def _open_device(self, c, who: identity.Identity, remember, device, device_id) -> dict | None:
        """Remembered device of this session. Restoring never extends the absolute deadline."""
        if device_id is not None:
            row = c.execute("""UPDATE remembered_devices SET last_used_at = now()
                               WHERE id = %s AND subject = %s AND revoked_at IS NULL AND expires_at > now() RETURNING *""",
                            (str(device_id), who.subject)).fetchone()
            if not row:
                raise err(401, "IDENTITY-SESSION-EXPIRED", reason="device revoked or expired")
            return row
        if remember is not True:
            return None
        inst, name, win = self._device_meta(device)
        c.execute("UPDATE remembered_devices SET revoked_at = now() WHERE subject = %s AND installation_id = %s AND revoked_at IS NULL AND expires_at <= now()",
                  (who.subject, inst))
        return c.execute("""INSERT INTO remembered_devices (id, subject, installation_id, device_name, windows_user, expires_at)
                            VALUES (%s, %s, %s, %s, %s, now() + %s)
                            ON CONFLICT (subject, installation_id) WHERE revoked_at IS NULL
                            DO UPDATE SET device_name = excluded.device_name, windows_user = excluded.windows_user, last_used_at = now()
                            RETURNING *""", (uuid.uuid4().hex, who.subject, inst, name, win, REMEMBER_TTL)).fetchone()

    def _identity_session(self, c, who: identity.Identity, user: dict, remember, device, device_id) -> dict:
        if not user["active"]:
            raise err(401, "AUTH-INVALID")
        c.execute("UPDATE identity_links SET email = %s, full_name = %s, email_confirmed_at = %s, last_seen_at = now() WHERE subject = %s",
                  (who.email, who.full_name, who.email_confirmed_at, who.subject))
        dev = self._open_device(c, who, remember, device, device_id)
        token, h = auth.new_token()
        c.execute("INSERT INTO sessions (token_hash, user_id, expires_at, device_id) VALUES (%s, %s, now() + %s, %s)",
                  (h, user["id"], SESSION_TTL, dev["id"] if dev else None))
        return {"token": token, "user": _public_user(user), "expires_in_s": int(SESSION_TTL.total_seconds()),
                "profile": {"full_name": who.full_name, "email": who.email},
                "device": {"id": dev["id"], "expires_at": dev["expires_at"].isoformat()} if dev else None}

    def identity_session(self, access_token, remember=False, device=None, device_id=None) -> dict:
        """Provider token -> Core session. Having an account grants nothing: a link to a team member is required."""
        who = self._verified(access_token)
        with self.db.tx() as c:
            u = c.execute("SELECT u.* FROM identity_links l JOIN users u ON u.id = l.user_id WHERE l.subject = %s", (who.subject,)).fetchone()
            if not u:
                raise err(403, "IDENTITY-NO-MEMBERSHIP")
            return self._identity_session(c, who, u, remember, device, device_id)

    def identity_link(self, access_token, username, password, remember=False, device=None) -> dict:
        """One explicit link: proof of the account (token) plus proof of the team user (local password)."""
        who = self._verified(access_token)
        with self.db.tx() as c:
            u = c.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
            ok = auth.verify_password(password or "", u["pw_hash"] if u else auth.DUMMY_HASH)
            if not u or not ok or not u["active"]:
                raise err(401, "AUTH-INVALID")
            linked = c.execute("""INSERT INTO identity_links (subject, user_id, email, full_name, email_confirmed_at) VALUES (%s, %s, %s, %s, %s)
                                  ON CONFLICT DO NOTHING RETURNING subject""",
                               (who.subject, u["id"], who.email, who.full_name, who.email_confirmed_at)).fetchone()
            if not linked:
                raise err(409, "IDENTITY-ALREADY-LINKED")
            return self._identity_session(c, who, u, remember, device, None)

    def identity_profile(self, who: dict) -> dict:
        with self.db.tx() as c:
            link = c.execute("SELECT email, full_name, email_confirmed_at, linked_at FROM identity_links WHERE user_id = %s", (who["id"],)).fetchone()
        out = {"username": who["username"], "display": who["display"], "role": who["role"], "linked": link is not None,
               "email": who.get("email"), "full_name": who["display"], "email_confirmed_at": None}
        if link:
            out.update(email=link["email"], full_name=link["full_name"],
                       email_confirmed_at=link["email_confirmed_at"].isoformat() if link["email_confirmed_at"] else None)
        return out

    def list_devices(self, who: dict, token: str | None) -> list[dict]:
        """Remembered devices of this person only; never a token, and being listed does not mean online."""
        with self.db.tx() as c:
            cur = c.execute("SELECT device_id FROM sessions WHERE token_hash = %s", (auth.token_hash(token or ""),)).fetchone()
            rows = c.execute("""SELECT d.id, d.device_name, d.windows_user, d.created_at, d.last_used_at, d.expires_at
                                FROM remembered_devices d JOIN identity_links l ON l.subject = d.subject
                                WHERE l.user_id = %s AND d.revoked_at IS NULL AND d.expires_at > now()
                                ORDER BY d.last_used_at DESC""", (who["id"],)).fetchall()
        current = cur["device_id"] if cur else None
        return [{"id": r["id"], "name": r["device_name"], "windows_user": r["windows_user"], "current": r["id"] == current,
                 "created_at": r["created_at"].isoformat(), "last_used_at": r["last_used_at"].isoformat(),
                 "expires_at": r["expires_at"].isoformat()} for r in rows]

    def forget_device(self, who: dict, device_id: str) -> dict:
        """Revokes one device of this person and the Core sessions derived from it."""
        with self.db.tx() as c:
            row = c.execute("""UPDATE remembered_devices d SET revoked_at = now() FROM identity_links l
                               WHERE d.id = %s AND l.subject = d.subject AND l.user_id = %s AND d.revoked_at IS NULL RETURNING d.id""",
                            (device_id, who["id"])).fetchone()
            if not row:
                raise err(404, "NOT-FOUND", what_missing="device")
            c.execute("UPDATE sessions SET revoked = true WHERE device_id = %s", (device_id,))
        return {"ok": True}

    def user_for(self, token: str | None) -> dict:
        if not token:
            raise err(401, "AUTH-REQUIRED")
        with self.db.tx() as c:
            u = c.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                             WHERE s.token_hash = %s AND NOT s.revoked AND s.expires_at > now() AND u.active""",
                          (auth.token_hash(token),)).fetchone()
        if not u:
            raise err(401, "AUTH-REQUIRED")
        return u

    def logout(self, token: str) -> None:
        with self.db.tx() as c:
            s = c.execute("UPDATE sessions SET revoked = true WHERE token_hash = %s RETURNING device_id", (auth.token_hash(token),)).fetchone()
            if s and s["device_id"]:  # leaving on a remembered device also ends what was derived from it, on this device only
                c.execute("UPDATE remembered_devices SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL", (s["device_id"],))
                c.execute("UPDATE sessions SET revoked = true WHERE device_id = %s", (s["device_id"],))

    @staticmethod
    def require_admin(u: dict) -> None:
        if u["role"] != "admin":
            raise err(403, "AUTH-FORBIDDEN", required_role="administrator")

    def list_users(self, actor: dict) -> list[dict]:
        self.require_admin(actor)
        with self.db.tx() as c:
            rows = c.execute("""SELECT u.*, l.full_name, COALESCE(u.email, l.email) AS email FROM users u LEFT JOIN identity_links l ON l.user_id = u.id ORDER BY u.id""")
            return [{**_public_user(u), "full_name": u["full_name"], "email": u["email"]} for u in rows]

    def create_user(self, actor: dict, username: str, display: str, password: str, role: str) -> dict:
        self.require_admin(actor)
        if not isinstance(username, str) or not _USER.match(username):
            raise err(400, "VALIDATION", reason="user name: 3-40 characters a-z 0-9 . _ -")
        if role not in ("admin", "operator"):
            raise err(400, "VALIDATION", reason="role must be admin or operator")
        _check_password(password)
        try:
            with self.db.tx() as c:
                u = c.execute("INSERT INTO users (username, display, pw_hash, role) VALUES (%s, %s, %s, %s) RETURNING *",
                              (username, display or username, auth.hash_password(password), role)).fetchone()
        except psycopg.errors.UniqueViolation:
            raise err(409, "CONFLICT", reason="user already exists") from None
        return _public_user(u)

    def update_user(self, actor: dict, user_id: int, role: str | None = None, active: bool | None = None,
                    password: str | None = None) -> dict:
        self.require_admin(actor)
        if role is not None and role not in ("admin", "operator"):
            raise err(400, "VALIDATION", reason="role must be admin or operator")
        if password is not None:
            _check_password(password)
        with self.db.tx() as c:
            u = c.execute("SELECT * FROM users WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
            if not u:
                raise err(404, "NOT-FOUND", what_missing="user")
            new_role = role or u["role"]
            new_active = u["active"] if active is None else bool(active)
            if u["role"] == "admin" and (new_role != "admin" or not new_active):
                # Lock every admin row: two concurrent demotions cannot both pass the check.
                c.execute("SELECT id FROM users WHERE role = 'admin' FOR UPDATE")
                n = c.execute("SELECT count(*) AS n FROM users WHERE role = 'admin' AND active AND id <> %s", (user_id,)).fetchone()["n"]
                if n == 0:
                    raise err(409, "CONFLICT", reason="the team needs at least one active administrator")
            u = c.execute("UPDATE users SET role = %s, active = %s, pw_hash = coalesce(%s, pw_hash) WHERE id = %s RETURNING *",
                          (new_role, new_active, auth.hash_password(password) if password else None, user_id)).fetchone()
            if not new_active or password:
                c.execute("UPDATE sessions SET revoked = true WHERE user_id = %s", (user_id,))
        return _public_user(u)

    # ------------------------------------------------------------ stations / runners
    def register_station(self, actor: dict, name: str, is_host: bool = False) -> dict:
        self.require_admin(actor)
        if not isinstance(name, str) or not 1 <= len(name) <= 60:
            raise err(400, "VALIDATION", reason="invalid station name")
        token, h = auth.new_token()
        try:
            with self.db.tx() as c:
                s = c.execute("INSERT INTO stations (name, token_hash, created_by, is_host) VALUES (%s, %s, %s, %s) RETURNING id, name",
                              (name, h, actor["id"], bool(is_host))).fetchone()
        except psycopg.errors.UniqueViolation:
            raise err(409, "CONFLICT", reason="a station with this name already exists") from None
        return {"station": s, "runner_token": token}

    def list_stations(self, actor: dict) -> list[dict]:
        with self.db.tx() as c:
            rows = c.execute("""SELECT id, name, is_host, platform, categories, runner_version, session_state, session_reason,
                                       browsers, last_seen_at, revoked_at IS NOT NULL AS revoked,
                                       (last_seen_at > now() - interval '45 seconds') AS online
                                FROM stations ORDER BY id""").fetchall()
        return [_jsonable(r) for r in rows]

    def revoke_station(self, actor: dict, station_id: int) -> None:
        self.require_admin(actor)
        with self.db.tx() as c:
            if not c.execute("UPDATE stations SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL RETURNING id",
                             (station_id,)).fetchone():
                raise err(404, "NOT-FOUND", what_missing="station")
            # Queued jobs of a revoked station never run.
            for j in c.execute("SELECT id FROM jobs WHERE station_id = %s AND state = 'queued'", (station_id,)).fetchall():
                self._finish(c, j["id"], "refused", diagnostic=dg.make("STATION-INCOMPATIBLE", reported_by="RR-CORE",
                             params={"reason": "station revoked"}).to_dict())

    def station_for(self, token: str | None) -> dict:
        if not token:
            raise err(401, "AUTH-REQUIRED")
        with self.db.tx() as c:
            s = c.execute("SELECT * FROM stations WHERE token_hash = %s AND revoked_at IS NULL", (auth.token_hash(token),)).fetchone()
        if not s:
            raise err(401, "AUTH-REQUIRED")
        return s

    def heartbeat(self, station: dict, info: dict) -> dict:
        cats = [c for c in info.get("categories") or [] if c in CATEGORIES]
        with self.db.tx() as c:
            self._sweep(c)
            c.execute("""UPDATE stations SET platform = %s, categories = %s, runner_version = %s, session_state = %s,
                                session_reason = %s, last_seen_at = now() WHERE id = %s""",
                      (str(info.get("platform") or "")[:40], cats, str(info.get("runner_version") or "")[:20],
                       str(info.get("session_state") or "unknown")[:20], str(info.get("session_reason") or "")[:200], station["id"]))
            browsers = _station_browsers(info.get("browsers"))
            if browsers is not None:  # an older Runner does not report them: keep what is stored
                c.execute("UPDATE stations SET browsers = %s WHERE id = %s", (Jsonb(browsers), station["id"]))
            lease = info.get("lease_id")
            if info.get("job_id") and lease:
                info = {**info, "job_id": _uuid(info["job_id"]), "lease_id": _uuid(lease, "lease")}
                lease = info["lease_id"]
                c.execute("""UPDATE jobs SET lease_expires_at = now() + %s
                             WHERE id = %s AND lease_id = %s AND station_id = %s AND state IN ('claimed', 'running')""",
                          (LEASE, info["job_id"], lease, station["id"]))
            waiting = None if info.get("session_state") == "ready" else (info.get("session_reason") or "session unavailable")
            c.execute("UPDATE jobs SET waiting_reason = %s WHERE station_id = %s AND state = 'queued'", (waiting, station["id"]))
            cancel = [str(r["id"]) for r in c.execute(
                "SELECT id FROM jobs WHERE station_id = %s AND cancel_requested AND state IN ('claimed', 'running')",
                (station["id"],))]
        return {"cancel": cancel, "lease_s": int(LEASE.total_seconds())}

    # ------------------------------------------------------------ routines
    def create_routine(self, actor: dict, name: str, category: str, version: dict) -> dict:
        self.require_admin(actor)
        if not isinstance(name, str) or not 1 <= len(name) <= 120:
            raise err(400, "VALIDATION", reason="invalid routine name")
        if category not in CATEGORIES:
            raise err(400, "VALIDATION", reason="category must be browser, windows, mac or linux")
        if (version or {}).get("kind") == "browser_open" and category != "browser":
            raise err(400, "VALIDATION", reason="browser routines use the browser category")
        with self.db.tx() as c:
            r = c.execute("INSERT INTO routines (name, category, created_by) VALUES (%s, %s, %s) RETURNING *",
                          (name, category, actor["id"])).fetchone()
            v = self._insert_version(c, actor, r, version)
        return {"routine": _jsonable(r), "version": v}

    @staticmethod
    def _refuse_ready_made(c, routine_id: int) -> None:
        """The routines of the ready-made process are not changed or archived: it would stop running."""
        if c.execute("""SELECT 1 FROM process_items i JOIN processes p ON p.id = i.process_id
                        WHERE i.routine_id = %s AND p.system_key IS NOT NULL LIMIT 1""", (routine_id,)).fetchone():
            raise err(400, "VALIDATION", reason="this routine belongs to the ready-made process")

    def add_version(self, actor: dict, routine_id: int, version: dict) -> dict:
        self.require_admin(actor)
        with self.db.tx() as c:
            r = c.execute("SELECT * FROM routines WHERE id = %s AND NOT archived FOR UPDATE", (routine_id,)).fetchone()
            if not r:
                raise err(404, "NOT-FOUND", what_missing="routine")
            self._refuse_ready_made(c, routine_id)
            name = version.get("name")
            if name is not None:
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
                    raise err(400, "VALIDATION", reason="invalid routine name")
                c.execute("UPDATE routines SET name = %s WHERE id = %s", (name.strip(), routine_id))
            return self._insert_version(c, actor, r, version)

    def _insert_version(self, c, actor: dict, routine: dict, v: dict) -> dict:
        kind = v.get("kind")
        if kind == "template":
            t = self.templates.get(v.get("template_id") or "")
            if not t or t.get("shipped") is False:
                raise err(400, "VALIDATION", reason="template not available in this version")
            if t["category"] != routine["category"]:
                raise err(400, "VALIDATION", reason="template category differs from the routine")
            inputs = v.get("inputs") or {}
            unknown = set(inputs) - set(t["inputs"])
            if unknown:
                raise err(400, "VALIDATION", reason=f"unknown inputs: {sorted(unknown)}")
            platform = "windows-x86_64"
            row = (kind, t["id"], t["version"], None, None, platform, inputs)
        elif kind == "procedure":
            proc = v.get("procedure")
            if not isinstance(proc, dict) or proc.get("ir_version") not in (1, 2) or not isinstance(proc.get("steps"), list):
                raise err(400, "VALIDATION", reason="invalid procedure (IR v1/v2 expected)")
            if proc.get("category") != routine["category"]:
                raise err(400, "VALIDATION", reason="procedure category differs from the routine")
            raw = json.dumps(proc, sort_keys=True, ensure_ascii=False).encode("utf-8")
            row = (kind, None, None, Jsonb(proc), hashlib.sha256(raw).hexdigest(), proc.get("platform"), v.get("inputs") or {})
        elif kind == "browser_open":
            if routine["category"] != "browser":
                raise err(400, "VALIDATION", reason="browser routines use the browser category")
            config = browser_config(v.get("config"))
            row = (kind, None, None, None, None, None, {})
        else:
            raise err(400, "VALIDATION", reason="version kind must be template, procedure or browser_open")
        n = c.execute("SELECT coalesce(max(version), 0) + 1 AS n FROM routine_versions WHERE routine_id = %s",
                      (routine["id"],)).fetchone()["n"]
        out = c.execute("""INSERT INTO routine_versions (routine_id, version, kind, template_id, template_version, procedure,
                                  procedure_sha256, platform, inputs, note, created_by, config)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING id, routine_id, version, kind, template_id, template_version, procedure_sha256, platform, inputs,
                                     config, created_at""",
                        (routine["id"], n, *row[:6], Jsonb(row[6]), str(v.get("note") or "")[:500], actor["id"],
                         Jsonb(config) if kind == "browser_open" else None)).fetchone()
        return _jsonable(out)

    def list_routines(self, actor: dict) -> list[dict]:
        with self.db.tx() as c:
            rows = c.execute("""SELECT r.id, r.name, r.category, r.created_at, v.id AS version_id, v.version, v.kind,
                                       v.template_id, v.template_version, v.platform, v.inputs, v.config,
                                       v.procedure -> 'params' AS params
                                FROM routines r JOIN LATERAL (SELECT * FROM routine_versions WHERE routine_id = r.id
                                                              ORDER BY version DESC LIMIT 1) v ON true
                                WHERE NOT r.archived ORDER BY r.id""").fetchall()
        return [_jsonable(r) for r in rows]

    def routine_versions(self, actor: dict, routine_id: int) -> list[dict]:
        with self.db.tx() as c:
            rows = c.execute("""SELECT id, version, kind, template_id, template_version, procedure_sha256, platform, inputs, config,
                                       note, created_at
                                FROM routine_versions WHERE routine_id = %s ORDER BY version""", (routine_id,)).fetchall()
        if not rows:
            raise err(404, "NOT-FOUND", what_missing="routine")
        return [_jsonable(r) for r in rows]

    def archive_routine(self, actor: dict, routine_id: int) -> None:
        self.require_admin(actor)
        with self.db.tx() as c:
            self._refuse_ready_made(c, routine_id)
            if not c.execute("UPDATE routines SET archived = true WHERE id = %s RETURNING id", (routine_id,)).fetchone():
                raise err(404, "NOT-FOUND", what_missing="routine")

    # ------------------------------------------------------------ jobs
    def create_job(self, actor: dict, request_id: str, version_id: int, station_id: int, inputs: dict,
                   correlation_id: str) -> dict:
        try:
            return self._create_job(actor, request_id, version_id, station_id, inputs, correlation_id)
        except psycopg.errors.UniqueViolation:
            # Concurrent identical request: the other one created it; answer with that job.
            return self._create_job(actor, request_id, version_id, station_id, inputs, correlation_id)

    def _create_job(self, actor: dict, request_id: str, version_id: int, station_id: int, inputs: dict,
                    correlation_id: str) -> dict:
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise err(400, "VALIDATION", correlation_id, reason="request_id missing")
        if not isinstance(inputs, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in inputs.items()):
            raise err(400, "VALIDATION", correlation_id, reason="inputs must be text")
        with self.db.tx() as c:
            prior = c.execute("SELECT * FROM jobs WHERE request_id = %s", (request_id,)).fetchone()
            if prior:  # idempotent creation: the same request never creates a second job
                if prior["requested_by"] != actor["id"]:
                    raise err(409, "CONFLICT", correlation_id, reason="request_id already used")
                return {**self._job_view(c, prior), "duplicate": True}
            v = c.execute("""SELECT v.*, r.category, r.archived FROM routine_versions v JOIN routines r ON r.id = v.routine_id
                             WHERE v.id = %s""", (version_id,)).fetchone()
            if not v or v["archived"]:
                raise err(404, "NOT-FOUND", correlation_id, what_missing="routine version")
            if v["kind"] in PROCESS_KINDS:
                raise err(400, "VALIDATION", correlation_id, reason="these routines run through executions")
            s = c.execute("SELECT * FROM stations WHERE id = %s", (station_id,)).fetchone()
            if not s or s["revoked_at"]:
                raise err(404, "NOT-FOUND", correlation_id, what_missing="station")
            reason = compat_reason(v["category"], v["platform"], s)
            if reason:
                raise err(409, "STATION-INCOMPATIBLE", correlation_id, reason=reason)
            if v["kind"] == "template":
                t = self.templates.get(v["template_id"]) or {}
                unknown = set(inputs) - set(t.get("inputs", {}))
                if unknown:
                    raise err(400, "VALIDATION", correlation_id, reason=f"unknown inputs: {sorted(unknown)}")
            merged = {**(v["inputs"] or {}), **inputs}
            j = c.execute("""INSERT INTO jobs (request_id, routine_version_id, station_id, inputs, requested_by, state, correlation_id)
                             VALUES (%s, %s, %s, %s, %s, 'queued', %s) RETURNING *""",
                          (request_id, version_id, station_id, Jsonb(merged), actor["id"], correlation_id)).fetchone()
            self._event(c, j["id"], "queued", {"by": actor["username"]})
            return self._job_view(c, j)

    def claim(self, station: dict, info: dict) -> dict | None:
        if info.get("session_state") != "ready":
            # D9: no claim while the session is unavailable; queued jobs show why.
            with self.db.tx() as c:
                c.execute("UPDATE jobs SET waiting_reason = %s WHERE station_id = %s AND state = 'queued'",
                          (str(info.get("session_reason") or "session unavailable")[:200], station["id"]))
            return None
        with self.db.tx() as c:
            self._sweep(c)
            j = c.execute("""SELECT j.*, v.kind, v.template_id, v.template_version, v.procedure, v.platform, v.config, r.category,
                                    e.context AS execution_context
                             FROM jobs j JOIN routine_versions v ON v.id = j.routine_version_id JOIN routines r ON r.id = v.routine_id
                             LEFT JOIN executions e ON e.id = j.execution_id
                             WHERE j.station_id = %s AND j.state = 'queued' AND NOT j.cancel_requested
                             ORDER BY j.created_at LIMIT 1 FOR UPDATE OF j SKIP LOCKED""", (station["id"],)).fetchone()
            if not j:
                return None
            reason = compat_reason(j["category"], j["platform"], {**station, "categories": info.get("categories") or [],
                                                                  "platform": info.get("platform")})
            if reason:  # re-checked at claim (resumed/old jobs)
                self._finish(c, j["id"], "refused", diagnostic=dg.make("STATION-INCOMPATIBLE", reported_by="RR-CORE",
                             correlation_id=j["correlation_id"], params={"reason": reason}).to_dict())
                return None
            lease = uuid.uuid4()
            c.execute("""UPDATE jobs SET state = 'claimed', lease_id = %s, lease_expires_at = now() + %s, claimed_at = now(),
                                attempt = attempt + 1, waiting_reason = NULL WHERE id = %s""", (lease, LEASE, j["id"]))
            self._event(c, j["id"], "claimed", {"station": station["name"], "lease_id": str(lease)})
        return {"schema": JOB_SCHEMA, "job_id": str(j["id"]), "lease_id": str(lease), "correlation_id": j["correlation_id"],
                "kind": j["kind"], "category": j["category"], "platform": j["platform"], "template_id": j["template_id"],
                "template_version": j["template_version"], "procedure": j["procedure"], "inputs": j["inputs"],
                "config": j["config"], "execution_id": str(j["execution_id"]) if j["execution_id"] else None,
                "position": j["position"], "context": j["execution_context"] or {}}

    def start_job(self, station: dict, job_id: str, lease_id: str) -> dict:
        job_id, lease_id = _uuid(job_id), _uuid(lease_id, "lease")
        with self.db.tx() as c:
            j = self._leased(c, station, job_id, lease_id)
            if j["cancel_requested"]:
                self._finish(c, j["id"], "cancelled", diagnostic=dg.make("RUN-CANCELLED", reported_by="RR-CORE",
                             correlation_id=j["correlation_id"], effect_state="none").to_dict())
                return {"proceed": False, "reason": "cancelled"}
            if j["state"] != "claimed":
                raise err(409, "CONFLICT", j["correlation_id"], reason=f"state {j['state']}")
            c.execute("UPDATE jobs SET state = 'running', started_at = now() WHERE id = %s", (j["id"],))
            self._event(c, j["id"], "running", None)
        return {"proceed": True}

    def report_result(self, station: dict, job_id: str, lease_id: str, result: dict) -> dict:
        job_id, lease_id = _uuid(job_id), _uuid(lease_id, "lease")
        if not isinstance(result, dict) or result.get("schema") != RESULT_SCHEMA or result.get("state") not in RUNNER_STATES:
            raise ApiError(400, dg.contract_violation("RR-RUNNER", "RR-CORE", RESULT_SCHEMA,
                                                      f"state {result.get('state') if isinstance(result, dict) else '?'!r}",
                                                      reported_by="RR-CORE"))
        diag = result.get("diagnostic")
        if diag is not None and dg.validate(diag):
            raise ApiError(400, dg.contract_violation("RR-RUNNER", "RR-CORE", "redrise.diagnostic/1",
                                                      "; ".join(dg.validate(diag))[:300], reported_by="RR-CORE"))
        with self.db.tx() as c:
            j = c.execute("SELECT * FROM jobs WHERE id = %s AND station_id = %s FOR UPDATE", (job_id, station["id"])).fetchone()
            if not j:
                raise err(404, "NOT-FOUND", what_missing="run")
            if j["state"] in TERMINAL:
                same = str(j["lease_id"]) == lease_id and j["state"] == result["state"]
                if same:  # retransmitted report (lost ack): idempotent
                    return {"duplicate": True, "state": j["state"]}
                raise err(409, "CONFLICT", j["correlation_id"], reason=f"run already finished as {j['state']}")
            if str(j["lease_id"]) != lease_id:
                raise err(409, "CONFLICT", j["correlation_id"], reason="lease does not match")
            self._finish(c, j["id"], result["state"], result=_strip(result), diagnostic=diag,
                         verified=bool(result.get("verified")) and result["state"] == "verified")
        return {"duplicate": False, "state": result["state"]}

    def cancel_job(self, actor: dict, job_id: str) -> dict:
        job_id = _uuid(job_id)
        with self.db.tx() as c:
            j = c.execute("SELECT * FROM jobs WHERE id = %s FOR UPDATE", (job_id,)).fetchone()
            if not j:
                raise err(404, "NOT-FOUND", what_missing="run")
            if actor["role"] != "admin" and j["requested_by"] != actor["id"]:
                raise err(403, "AUTH-FORBIDDEN", required_role="administrator or run author")
            if j["state"] == "queued":
                self._finish(c, j["id"], "cancelled", diagnostic=dg.make("RUN-CANCELLED", reported_by="RR-CORE",
                             correlation_id=j["correlation_id"], effect_state="none").to_dict())
                return {"state": "cancelled"}
            if j["state"] in ("claimed", "running"):
                c.execute("UPDATE jobs SET cancel_requested = true WHERE id = %s", (j["id"],))
                self._event(c, j["id"], "cancel_requested", {"by": actor["username"]})
                return {"state": j["state"], "cancel_requested": True}
            raise err(409, "CONFLICT", j["correlation_id"], reason=f"run already finished as {j['state']}")

    def list_jobs(self, actor: dict, limit: int = 100) -> list[dict]:
        with self.db.tx() as c:
            self._sweep(c)  # leases of offline/revoked stations still expire
            rows = c.execute(f"""{_JOB_SELECT} ORDER BY j.created_at DESC LIMIT %s""", (min(max(limit, 1), 500),)).fetchall()
        return [_jsonable(r) for r in rows]

    def get_job(self, actor: dict, job_id: str) -> dict:
        job_id = _uuid(job_id)
        with self.db.tx() as c:
            self._sweep(c)
            j = c.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()
            if not j:
                raise err(404, "NOT-FOUND", what_missing="run")
            out = self._job_view(c, j)
            out["events"] = [_jsonable(e) for e in c.execute(
                "SELECT at, state, detail FROM job_events WHERE job_id = %s ORDER BY id", (job_id,))]
        return out

    # ------------------------------------------------------------ processes (update Browser)
    def _items(self, c, items) -> list[dict]:
        if not isinstance(items, list) or not 1 <= len(items) <= MAX_PROCESS_ITEMS:
            raise err(400, "VALIDATION", reason=f"a process links 1 to {MAX_PROCESS_ITEMS} routines")
        out = []
        for it in items:
            if not isinstance(it, dict) or not isinstance(it.get("routine_id"), int) or not isinstance(it.get("continue_next"), bool):
                raise err(400, "VALIDATION", reason="each link needs routine_id and continue_next")
            v = c.execute("""SELECT v.kind FROM routines r JOIN LATERAL (SELECT kind FROM routine_versions WHERE routine_id = r.id
                             ORDER BY version DESC LIMIT 1) v ON true WHERE r.id = %s AND NOT r.archived""", (it["routine_id"],)).fetchone()
            if not v:
                raise err(404, "NOT-FOUND", what_missing="routine")
            if v["kind"] not in PROCESS_KINDS:
                raise err(400, "VALIDATION", reason="only browser routines can be linked to a process in this version")
            out.append({"routine_id": it["routine_id"], "continue_next": it["continue_next"]})
        return out

    def _process_name(self, name) -> str:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise err(400, "VALIDATION", reason="invalid process name")
        return name.strip()

    def create_process(self, actor: dict, name, items) -> dict:
        """Saving a process never starts an execution (R03/G27)."""
        self.require_admin(actor)
        name = self._process_name(name)
        with self.db.tx() as c:
            links = self._items(c, items)
            p = c.execute("INSERT INTO processes (name, created_by) VALUES (%s, %s) RETURNING id", (name, actor["id"])).fetchone()
            for i, it in enumerate(links, 1):
                c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, %s, %s, %s)",
                          (p["id"], i, it["routine_id"], it["continue_next"]))
        return self.get_process(actor, p["id"])

    def update_process(self, actor: dict, process_id: int, name, items) -> dict:
        """Replaces name and links; running executions keep their snapshot."""
        self.require_admin(actor)
        name = self._process_name(name)
        with self.db.tx() as c:
            row = c.execute("SELECT id, system_key FROM processes WHERE id = %s AND NOT archived FOR UPDATE", (process_id,)).fetchone()
            if not row:
                raise err(404, "NOT-FOUND", what_missing="process")
            if row["system_key"]:
                raise err(400, "VALIDATION", reason="the ready-made process cannot be changed")
            links = self._items(c, items)
            c.execute("UPDATE processes SET name = %s, updated_at = now() WHERE id = %s", (name, process_id))
            c.execute("DELETE FROM process_items WHERE process_id = %s", (process_id,))
            for i, it in enumerate(links, 1):
                c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, %s, %s, %s)",
                          (process_id, i, it["routine_id"], it["continue_next"]))
        return self.get_process(actor, process_id)

    def list_processes(self, actor: dict, process_id: int | None = None) -> list[dict]:
        with self.db.tx() as c:
            procs = c.execute("""SELECT id, name, system_key, created_at, updated_at FROM processes
                                 WHERE NOT archived AND (%s::bigint IS NULL OR id = %s) ORDER BY id""",
                              (process_id, process_id)).fetchall()
            items = c.execute("""SELECT i.process_id, i.position, i.routine_id, i.continue_next, r.name AS routine_name, v.kind, v.config
                                 FROM process_items i JOIN routines r ON r.id = i.routine_id
                                 JOIN LATERAL (SELECT kind, config FROM routine_versions WHERE routine_id = r.id
                                               ORDER BY version DESC LIMIT 1) v ON true
                                 ORDER BY i.process_id, i.position""").fetchall()
            last = {r["process_id"]: r for r in c.execute(
                """SELECT DISTINCT ON (process_id) process_id, id, state, outcome, end_reason, created_at FROM executions
                   WHERE process_id IS NOT NULL ORDER BY process_id, created_at DESC""").fetchall()}
        out = []
        for p in procs:
            le = last.get(p["id"])
            out.append({**_jsonable(p), "items": [_jsonable({k: v for k, v in i.items() if k != "process_id"})
                                                   for i in items if i["process_id"] == p["id"]],
                        "last_execution": _jsonable({k: v for k, v in le.items() if k != "process_id"}) if le else None})
        return out

    def get_process(self, actor: dict, process_id: int) -> dict:
        found = self.list_processes(actor, process_id)
        if not found:
            raise err(404, "NOT-FOUND", what_missing="process")
        return found[0]

    # ------------------------------------------------------------ executions (one use case for every entry point)
    def create_execution(self, actor: dict, request_id, station_id, process_id, routine_id, correlation_id: str) -> dict:
        try:
            return self._create_execution(actor, request_id, station_id, process_id, routine_id, correlation_id)
        except psycopg.errors.UniqueViolation:
            # Concurrent identical request: the other one created it; answer with that execution.
            return self._create_execution(actor, request_id, station_id, process_id, routine_id, correlation_id)

    def _create_execution(self, actor: dict, request_id, station_id, process_id, routine_id, cid: str) -> dict:
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise err(400, "VALIDATION", cid, reason="request_id missing")
        if (process_id is None) == (routine_id is None):
            raise err(400, "VALIDATION", cid, reason="give either process_id or routine_id")
        with self.db.tx() as c:
            prior = c.execute("SELECT * FROM executions WHERE request_id = %s", (request_id,)).fetchone()
            if prior:  # idempotent: a repeated request never starts a second execution (no duplicate tab)
                if prior["requested_by"] != actor["id"]:
                    raise err(409, "CONFLICT", cid, reason="request_id already used")
                return {**self._execution_view(c, prior), "duplicate": True}
            s = c.execute("SELECT * FROM stations WHERE id = %s", (station_id,)).fetchone() if isinstance(station_id, int) else None
            if not s or s["revoked_at"]:
                raise err(404, "NOT-FOUND", cid, what_missing="station")
            if routine_id is not None:
                rows = c.execute("""SELECT 1 AS position, r.id AS routine_id, v.id AS routine_version_id, r.name, false AS continue_next,
                                           v.kind, v.config, v.platform, r.category, r.archived
                                    FROM routines r JOIN LATERAL (SELECT * FROM routine_versions WHERE routine_id = r.id
                                                                  ORDER BY version DESC LIMIT 1) v ON true
                                    WHERE r.id = %s""", (routine_id,)).fetchall()
                if not rows or rows[0]["archived"]:
                    raise err(404, "NOT-FOUND", cid, what_missing="routine")
                if rows[0]["kind"] not in PROCESS_KINDS:
                    raise err(400, "VALIDATION", cid, reason="only browser routines run as executions in this version")
                # A linked routine, even as the only step, runs through its process.
                linked = c.execute("""SELECT p.name FROM process_items i JOIN processes p ON p.id = i.process_id
                                      WHERE i.routine_id = %s AND NOT p.archived ORDER BY p.id LIMIT 1""", (routine_id,)).fetchone()
                if linked:
                    raise err(409, "ROUTINE-LINKED", cid, process=linked["name"])
                if not (rows[0]["config"] or {}).get("isolated"):
                    # G25: enforced here, not only by a disabled button.
                    raise err(409, "ROUTINE-NOT-ISOLATED", cid, routine=rows[0]["name"])
            else:
                if not c.execute("SELECT id FROM processes WHERE id = %s AND NOT archived", (process_id,)).fetchone():
                    raise err(404, "NOT-FOUND", cid, what_missing="process")
                rows = c.execute("""SELECT i.position, r.id AS routine_id, v.id AS routine_version_id, r.name, i.continue_next,
                                           v.kind, v.config, v.platform, r.category, r.archived
                                    FROM process_items i JOIN routines r ON r.id = i.routine_id
                                    JOIN LATERAL (SELECT * FROM routine_versions WHERE routine_id = r.id
                                                  ORDER BY version DESC LIMIT 1) v ON true
                                    WHERE i.process_id = %s ORDER BY i.position""", (process_id,)).fetchall()
                if not rows:
                    raise err(400, "VALIDATION", cid, reason="the process has no linked routine")
                if any(r["archived"] or r["kind"] not in PROCESS_KINDS for r in rows):
                    raise err(400, "VALIDATION", cid, reason="the process links a routine that cannot run")
            for r in rows:  # every step must be able to run on the chosen station
                reason = compat_reason(r["category"], r["platform"], s)
                if reason:
                    raise err(409, "STATION-INCOMPATIBLE", cid, reason=reason)
            # G27: versions and links fixed at start; later edits only affect new executions.
            snapshot = [{"position": i, "routine_id": r["routine_id"], "routine_version_id": r["routine_version_id"],
                         "name": r["name"], "continue_next": bool(r["continue_next"]), "config": r["config"]}
                        for i, r in enumerate(rows, 1)]
            e = c.execute("""INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, correlation_id)
                             VALUES (%s, %s, %s, %s, %s, 'running', %s) RETURNING *""",
                          (request_id, process_id, station_id, actor["id"], Jsonb(snapshot), cid)).fetchone()
            self._queue_step(c, e, snapshot[0])  # G22: always the first linked routine
            return self._execution_view(c, e)

    def _queue_step(self, c, execution: dict, item: dict) -> None:
        j = c.execute("""INSERT INTO jobs (request_id, routine_version_id, station_id, inputs, requested_by, state, correlation_id,
                                           execution_id, position)
                         VALUES (%s, %s, %s, '{}', %s, 'queued', %s, %s, %s)
                         ON CONFLICT DO NOTHING RETURNING id""",
                      (f"exec:{execution['id']}:{item['position']}", item["routine_version_id"], execution["station_id"],
                       execution["requested_by"], execution["correlation_id"], execution["id"], item["position"])).fetchone()
        if j:
            self._event(c, j["id"], "queued", {"execution": str(execution["id"]), "position": item["position"]})

    def _advance(self, c, execution_id, position: int, state: str, verified: bool, result) -> None:
        """R04/R05/G17/G19/G21: only a verified result with continuation on and
        a next link starts the next routine; anything else ends the execution
        here, without retry. Runs inside the transaction that finished the job."""
        e = c.execute("SELECT * FROM executions WHERE id = %s FOR UPDATE", (execution_id,)).fetchone()
        if not e or e["state"] != "running":
            return
        snapshot = e["snapshot"]
        item = snapshot[position - 1]
        context = dict(e["context"] or {})
        produced = ((result or {}).get("details") or {}).get("context")
        if state == "verified" and verified and isinstance(produced, dict):
            # Context of this execution only (G24): what the routine produced, for the next routine.
            context["last"] = produced
            context.setdefault("steps", {})[str(position)] = produced
            c.execute("UPDATE executions SET context = %s WHERE id = %s", (Jsonb(context), execution_id))
        if state == "verified" and verified:
            if item["continue_next"] and position < len(snapshot):
                self._queue_step(c, {**e, "context": context}, snapshot[position])
                return
            end = "continuation_off" if position < len(snapshot) else "sequence_end"
        else:
            end = "cancelled" if state == "cancelled" else "not_verified"
        c.execute("UPDATE executions SET state = 'finished', outcome = %s, end_reason = %s, finished_at = now() WHERE id = %s",
                  (state, end, execution_id))

    _EXEC_SELECT = """SELECT e.*, p.name AS process_name, s.name AS station_name, u.username AS requested_by_name
                      FROM executions e LEFT JOIN processes p ON p.id = e.process_id
                      JOIN stations s ON s.id = e.station_id JOIN users u ON u.id = e.requested_by"""

    def _execution_view(self, c, e: dict) -> dict:
        row = c.execute(f"{self._EXEC_SELECT} WHERE e.id = %s", (e["id"],)).fetchone()
        return self._shape(row, c.execute("""SELECT id, position, state, verified, diagnostic, diagnostic ->> 'error_code' AS error_code,
                                                    started_at, finished_at FROM jobs WHERE execution_id = %s""",
                                          (e["id"],)).fetchall())

    @staticmethod
    def _shape(e: dict, jobs: list[dict]) -> dict:
        by_pos = {j["position"]: j for j in jobs}
        steps = []
        for it in e["snapshot"]:
            j = by_pos.get(it["position"])
            steps.append({"position": it["position"], "routine_id": it["routine_id"], "routine_version_id": it["routine_version_id"],
                          "name": it["name"], "continue_next": it["continue_next"], "job_id": str(j["id"]) if j else None,
                          "state": j["state"] if j else None, "verified": bool(j and j["verified"]),
                          "error_code": j["error_code"] if j else None, "diagnostic": j["diagnostic"] if j else None,
                          "started_at": j["started_at"].isoformat() if j and j["started_at"] else None,
                          "finished_at": j["finished_at"].isoformat() if j and j["finished_at"] else None})
        out = _jsonable({k: v for k, v in e.items() if k not in ("snapshot", "requested_by", "requested_by_name")})
        out["requested_by"] = e["requested_by_name"]
        out["steps"] = steps
        return out

    def list_executions(self, actor: dict, limit: int = 100) -> list[dict]:
        with self.db.tx() as c:
            self._sweep(c)
            rows = c.execute(f"{self._EXEC_SELECT} ORDER BY e.created_at DESC LIMIT %s", (min(max(limit, 1), 500),)).fetchall()
            ids = [r["id"] for r in rows]
            jobs = c.execute("""SELECT id, execution_id, position, state, verified, diagnostic, diagnostic ->> 'error_code' AS error_code,
                                       started_at, finished_at FROM jobs WHERE execution_id = ANY(%s)""", (ids,)).fetchall() if ids else []
        return [self._shape(r, [j for j in jobs if j["execution_id"] == r["id"]]) for r in rows]

    def get_execution(self, actor: dict, execution_id: str) -> dict:
        execution_id = _uuid(execution_id)
        with self.db.tx() as c:
            self._sweep(c)
            e = c.execute("SELECT id FROM executions WHERE id = %s", (execution_id,)).fetchone()
            if not e:
                raise err(404, "NOT-FOUND", what_missing="execution")
            return self._execution_view(c, e)

    def storage(self, actor: dict) -> dict:
        """Measured database bytes and record counts, kept in separate units."""
        with self.db.tx() as c:
            size = c.execute("SELECT pg_database_size(current_database()) AS n").fetchone()["n"]
            n = c.execute("""SELECT (SELECT count(*) FROM routines WHERE NOT archived) AS routines,
                                    (SELECT count(*) FROM processes WHERE NOT archived) AS processes,
                                    (SELECT count(*) FROM executions) AS executions, (SELECT count(*) FROM jobs) AS jobs""").fetchone()
        return {"db_bytes": int(size), "counts": {k: int(v) for k, v in n.items()}}

    # ------------------------------------------------------------ internals
    def _leased(self, c, station: dict, job_id: str, lease_id: str) -> dict:
        j = c.execute("SELECT * FROM jobs WHERE id = %s AND station_id = %s FOR UPDATE", (job_id, station["id"])).fetchone()
        if not j:
            raise err(404, "NOT-FOUND", what_missing="run")
        if str(j["lease_id"]) != lease_id or j["state"] not in ("claimed", "running"):
            raise err(409, "CONFLICT", j["correlation_id"], reason="lease expired or replaced")
        return j

    def _finish(self, c, job_id, state: str, result=None, diagnostic=None, verified: bool = False) -> None:
        c.execute("""UPDATE jobs SET state = %s, result = %s, diagnostic = %s, verified = %s, finished_at = now(),
                            lease_expires_at = NULL WHERE id = %s""",
                  (state, Jsonb(result) if result is not None else None, Jsonb(diagnostic) if diagnostic else None,
                   verified, job_id))
        self._event(c, job_id, state, {"error_code": (diagnostic or {}).get("error_code")} if diagnostic else None)
        j = c.execute("SELECT execution_id, position FROM jobs WHERE id = %s", (job_id,)).fetchone()
        if j and j["execution_id"]:
            self._advance(c, j["execution_id"], j["position"], state, verified, result)

    def _event(self, c, job_id, state: str, detail) -> None:
        c.execute("INSERT INTO job_events (job_id, state, detail) VALUES (%s, %s, %s)",
                  (job_id, state, Jsonb(detail) if detail is not None else None))

    def _sweep(self, c) -> None:
        """Expired leases: a claimed job (never started) returns to the queue;
        a running job becomes uncertain and is never re-run automatically."""
        for j in c.execute("""SELECT id, state, correlation_id FROM jobs WHERE state IN ('claimed', 'running')
                              AND lease_expires_at < now() FOR UPDATE SKIP LOCKED""").fetchall():
            if j["state"] == "claimed":
                c.execute("UPDATE jobs SET state = 'queued', lease_id = NULL, lease_expires_at = NULL WHERE id = %s", (j["id"],))
                self._event(c, j["id"], "queued", {"reason": "lease_expired_before_start"})
            else:
                self._finish(c, j["id"], "uncertain", diagnostic=dg.make(
                    "JOB-LEASE-LOST", reported_by="RR-CORE", correlation_id=j["correlation_id"]).to_dict())

    def _job_view(self, c, j: dict) -> dict:
        row = c.execute(f"{_JOB_SELECT} WHERE j.id = %s", (j["id"],)).fetchone()
        return _jsonable(row)


_JOB_SELECT = """SELECT j.id, j.request_id, j.state, j.verified, j.inputs, j.waiting_reason, j.cancel_requested, j.attempt,
                        j.diagnostic, j.result, j.correlation_id, j.created_at, j.started_at, j.finished_at,
                        r.id AS routine_id, r.name AS routine_name, r.category, v.id AS version_id, v.version,
                        v.template_id, v.template_version, v.procedure_sha256,
                        s.id AS station_id, s.name AS station_name, u.username AS requested_by
                 FROM jobs j JOIN routine_versions v ON v.id = j.routine_version_id JOIN routines r ON r.id = v.routine_id
                 JOIN stations s ON s.id = j.station_id JOIN users u ON u.id = j.requested_by"""


def compat_reason(category: str, platform: str | None, station: dict) -> str | None:
    cats = station.get("categories") or []
    if category not in cats:
        return f"category {category} not supported by the station (supports: {', '.join(cats) or 'none reported'})"
    if category != "browser" and platform and station.get("platform") and platform != station["platform"]:
        return f"routine for {platform}; station is {station['platform']}"
    if category != "browser" and platform and not station.get("platform"):
        return "station system not reported yet"
    return None


def _strip(result: dict) -> dict:
    return dg.sanitize({k: v for k, v in result.items() if k != "diagnostic"})


def _jsonable(row: dict) -> dict:
    out = {}
    for k, v in dict(row).items():
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        elif isinstance(v, uuid.UUID):
            v = str(v)
        elif isinstance(v, (bytes, memoryview)):
            continue
        out[k] = v
    return out
