"""Core domain operations: team bootstrap, accounts, stations, routines and
versions, jobs with leases (P05-D6..D10). Every refusal is an `ApiError`
carrying a redrise.diagnostic/1; the HTTP layer only maps it."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from psycopg.types.json import Jsonb

from redrise_contracts import diagnostics as dg

from . import __version__, auth, changes, identity
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
PROCESS_KINDS = ("browser_open", "notepad_step", "app_open", "followup")
FOLLOWUP_ACTIONS = ("review", "report", "notify")
MAIL_IDS = ("outlook", "thunderbird", "default")  # redrise_runner.notify_draft.MAIL_IDS
WEBMAIL_IDS = ("gmail", "outlook")
PREPARED_KINDS = ("browser_open", "app_open")  # what the Nova Rotina assistant registers
MAX_STATION_APPS = 1000
# A routine stays what it is: a new version may not turn it into another kind, or it would skip
# the rules of the link it already has. Template and procedure are the two forms of a recorded routine.
KIND_FAMILY = {"template": "recorded", "procedure": "recorded"}
ASSISTANT_RUNNER = (0, 3, 10)  # first Runner that honours a job's mode; an older one would open on "prepare"
WELCOME_KEY = "boas-vindas"
WELCOME_PROCESS = "Boas-vindas"
# Routines of the ready-made process; the Runner reads `step` (redrise_runner.notepad_steps).
WELCOME_STEPS = (("Abrir e identificar", "open"), ("Digitar e salvar", "save"), ("Fechar e verificar", "close"))
_URL = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
_FULL_PATH = re.compile(r"^([a-zA-Z]:\\|\\\\[^\\]+\\[^\\]+\\).+$")
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
_MAIL_TO = re.compile(r"^[A-Za-z0-9._+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


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


def app_config(cfg) -> dict:
    """Validates an app_open registration: an installed application of the station, or a chosen file."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("target"), dict):
        raise err(400, "VALIDATION", reason="config needs a target")
    if not isinstance(cfg.get("isolated"), bool):
        raise err(400, "VALIDATION", reason="isolated must be true or false")
    t = cfg["target"]
    name = t.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise err(400, "VALIDATION", reason="target needs a name")
    if t.get("kind") == "app":
        if not isinstance(t.get("app_id"), str) or not 1 <= len(t["app_id"]) <= 1000:
            raise err(400, "VALIDATION", reason="choose an application of the list")
        target = {"kind": "app", "app_id": t["app_id"], "name": name.strip()}
    elif t.get("kind") == "file":
        path = t.get("path")
        if not isinstance(path, str) or len(path) > 1000 or not _FULL_PATH.match(path.strip()):
            raise err(400, "VALIDATION", reason="full path of a file expected")
        target = {"kind": "file", "path": path.strip(), "name": name.strip()}
    else:
        raise err(400, "VALIDATION", reason="target must be an application or a file")
    return {"target": target, "isolated": cfg["isolated"]}


def followup_config(cfg) -> dict:
    """A follow-up acts after a step of a process, so it never runs alone."""
    if not isinstance(cfg, dict) or cfg.get("action") not in FOLLOWUP_ACTIONS:
        raise err(400, "VALIDATION", reason="unknown follow-up action")
    if cfg["action"] in ("report", "notify"):  # the fixed words, from the mask of the desktop that registered it
        labels = cfg.get("labels")
        if not isinstance(labels, dict) or len(labels) > 60 or not all(
                isinstance(k, str) and len(k) <= 40 and isinstance(v, str) and len(v) <= 200 for k, v in labels.items()):
            raise err(400, "VALIDATION", reason="invalid report labels")
        if cfg["action"] == "report":
            return {"action": "report", "labels": labels, "isolated": False}
        to, channel = cfg.get("to"), cfg.get("channel")
        if not isinstance(to, str) or len(to) > 254 or not _MAIL_TO.match(to.strip()):  # plain: it goes into a mailto-like field
            raise err(400, "VALIDATION", reason="invalid e-mail")
        if not isinstance(channel, dict):
            raise err(400, "VALIDATION", reason="choose where to prepare the message")
        name = str(channel.get("name") or "")[:120]
        if channel.get("kind") == "app" and channel.get("mail_id") in MAIL_IDS:
            kept = {"kind": "app", "mail_id": channel["mail_id"], "name": name}
        elif channel.get("kind") == "webmail" and channel.get("provider") in WEBMAIL_IDS and channel.get("browser") in BROWSER_IDS:
            kept = {"kind": "webmail", "provider": channel["provider"], "browser": channel["browser"], "name": name}
        else:
            raise err(400, "VALIDATION", reason="choose where to prepare the message")
        return {"action": "notify", "to": to.strip(), "channel": kept, "labels": labels, "isolated": False}
    if not isinstance(cfg.get("assignee_id"), int):
        raise err(400, "VALIDATION", reason="choose a team member")
    return {"action": cfg["action"], "assignee_id": cfg["assignee_id"], "isolated": False}


def _is_review(item: dict) -> bool:
    return (item.get("config") or {}).get("action") == "review"


def _station_apps(raw) -> list[dict] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for a in raw[:MAX_STATION_APPS]:
        if isinstance(a, dict) and isinstance(a.get("id"), str) and isinstance(a.get("name"), str) and a["id"] and a["name"]:
            item = {"id": a["id"][:1000], "name": a["name"][:200]}
            if a.get("browser_id") in BROWSER_IDS:
                item["browser_id"] = a["browser_id"]
            if a.get("mail_id") in MAIL_IDS:
                item["mail_id"] = a["mail_id"]
            out.append(item)
    return out


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
        self.changes = changes.ChangeFeed(getattr(db, "info", None))
        self.limits = auth.AttemptLimiter()  # sign-in and sign-up attempts; memory only, a restart clears it

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

    def _attempt(self, keys, account=None) -> None:
        """Counts this attempt before any slow check, or refuses it while a key waits (nothing counted)."""
        left = self.limits.attempt(keys, account)
        if left:
            raise err(429, "AUTH-RATE-LIMITED", retry_after_s=left)

    def register(self, full_name, email, password, client: str | None = None) -> dict:
        """Sign-up: records the account and nothing else. It starts inactive, as an operator, so creating an
        account grants no access to the team until an administrator activates it in Configuracao > Equipe.
        Every sign-up request counts against its client address, accepted or not."""
        key = ("signup", client or "-")
        self._attempt((key,))
        full_name, email = self._account_fields(full_name, email, password)
        with self.db.tx() as c:
            if not c.execute("SELECT 1 FROM team").fetchone():
                raise err(409, "VALIDATION", reason="team not set up")
            if c.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone():
                raise err(409, "ACCOUNT-EXISTS")
            c.execute("INSERT INTO users (username, display, pw_hash, role, active, email) VALUES (%s, %s, %s, 'operator', false, %s)",
                      (self._new_username(c, email), full_name, auth.hash_password(password), email))
        return {"pending": True}

    @staticmethod
    def _account_fields(full_name, email, password) -> tuple[str, str]:
        """Full name and e-mail of a new account, checked the same way for sign-up and for an administrator."""
        if not isinstance(full_name, str) or not 1 <= len(full_name.strip()) <= 120:
            raise err(400, "VALIDATION", reason="full name required")
        if not isinstance(email, str) or len(email) > 254 or not _EMAIL.match(email.strip()):
            raise err(400, "VALIDATION", reason="invalid e-mail")
        _check_password(password)
        return full_name.strip(), email.strip().lower()

    @staticmethod
    def _new_username(c, email: str) -> str:
        """Internal user name from the e-mail: the part before @, normalized; a taken one gets .2, .3..."""
        base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0])[:32].ljust(3, "0")
        username, n = base, 1
        while c.execute("SELECT 1 FROM users WHERE username = %s", (username,)).fetchone():
            n += 1
            username = f"{base}.{n}"
        return username

    def _session_station(self, c, station_token) -> int | None:
        """The station a sign-in comes from, only when proved by that station's own runner token."""
        if not isinstance(station_token, str) or not station_token:
            return None
        s = c.execute("SELECT id FROM stations WHERE token_hash = %s AND revoked_at IS NULL",
                      (auth.token_hash(station_token),)).fetchone()
        return s["id"] if s else None

    def login(self, username: str, password: str, client: str | None = None, station_token=None) -> dict:
        """Failures count per account (the user when it exists, so user name and e-mail share one
        count; otherwise the name typed) and per client address; see auth.AttemptLimiter.
        `station_token` (sent by the desktop, never typed) ties the session to the station it runs on."""
        who = username.strip().lower()[:254] if isinstance(username, str) else None
        with self.db.tx() as c:
            u = c.execute("SELECT * FROM users WHERE username = %s OR email = %s", (who, who)).fetchone() if who else None
        account = f"user:{u['id']}" if u else f"name:{who}"
        keys = (("account", account), ("client", client or "-"))
        self._attempt(keys, account)  # counted now; a right password below forgets it
        ok = auth.verify_password(password if isinstance(password, str) else "", u["pw_hash"] if u else auth.DUMMY_HASH)
        if not u or not ok or not u["active"]:
            raise err(401, "AUTH-INVALID")
        self.limits.success(keys[0], keys[1], account)
        with self.db.tx() as c:
            token, h = auth.new_token()
            station = self._session_station(c, station_token)
            c.execute("INSERT INTO sessions (token_hash, user_id, expires_at, station_id) VALUES (%s, %s, now() + %s, %s)",
                      (h, u["id"], SESSION_TTL, station))
        return {"token": token, "user": _public_user(u), "expires_in_s": int(SESSION_TTL.total_seconds()), "station_id": station}

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
            u = c.execute("""SELECT u.*, s.station_id AS session_station_id FROM sessions s JOIN users u ON u.id = s.user_id
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
            rows = c.execute("""SELECT u.*, l.full_name, COALESCE(u.email, l.email) AS email FROM users u LEFT JOIN identity_links l ON l.user_id = u.id
                                WHERE u.deleted_at IS NULL ORDER BY u.id""")
            return [{**_public_user(u), "full_name": u["full_name"], "email": u["email"]} for u in rows]

    def create_account(self, actor: dict, full_name, email, password) -> dict:
        """Configuracao > Equipe > + Nova Conta: an active operator who can sign in at once with this e-mail
        and password. The internal user name comes from the e-mail; the e-mail of a deleted account stays reserved."""
        self.require_admin(actor)
        full_name, email = self._account_fields(full_name, email, password)
        try:
            with self.db.tx() as c:
                prior = c.execute("SELECT deleted_at FROM users WHERE email = %s", (email,)).fetchone()
                if prior:
                    raise err(409, "ACCOUNT-EMAIL-RESERVED" if prior["deleted_at"] else "ACCOUNT-EXISTS")
                u = c.execute("""INSERT INTO users (username, display, pw_hash, role, active, email)
                                 VALUES (%s, %s, %s, 'operator', true, %s) RETURNING *""",
                              (self._new_username(c, email), full_name, auth.hash_password(password), email)).fetchone()
        except psycopg.errors.UniqueViolation:  # the same e-mail or user name created at the same moment
            raise err(409, "ACCOUNT-EXISTS") from None
        return {**_public_user(u), "email": u["email"]}

    def delete_user(self, actor: dict, user_id: int) -> dict:
        """Logical and final: only an inactive account, read again under its row lock (a reactivation from another
        screen waits for this, or this sees it). The row stays for the history; access and sessions end."""
        self.require_admin(actor)
        with self.db.tx() as c:
            u = c.execute("SELECT * FROM users WHERE id = %s AND deleted_at IS NULL FOR UPDATE", (user_id,)).fetchone()
            if not u:
                raise err(404, "NOT-FOUND", what_missing="user")
            if u["active"]:
                raise err(409, "ACCOUNT-ACTIVE")
            c.execute("UPDATE users SET deleted_at = now() WHERE id = %s", (user_id,))
            c.execute("UPDATE sessions SET revoked = true WHERE user_id = %s", (user_id,))
        return {"deleted": True}

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
            u = c.execute("SELECT * FROM users WHERE id = %s AND deleted_at IS NULL FOR UPDATE", (user_id,)).fetchone()
            if not u:  # a deleted account is never reactivated
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

    ONLINE_S = 45  # a station is online while its last heartbeat is this recent (and it is not revoked)

    def list_stations(self, actor: dict) -> list[dict]:
        """Inventory without deleted stations. `online` is connectivity only (not readiness); a revoked station is
        never online, whatever its last heartbeat. `current`: the station this session signed in from."""
        with self.db.tx() as c:
            rows = c.execute("""SELECT id, name, is_host, platform, categories, runner_version, session_state, session_reason,
                                       browsers, last_seen_at, revoked_at IS NOT NULL AS revoked,
                                       (revoked_at IS NULL AND coalesce(last_seen_at > now() - make_interval(secs => %s), false)) AS online,
                                       id = %s AS current
                                FROM stations WHERE deleted_at IS NULL ORDER BY id""",
                             (self.ONLINE_S, actor.get("session_station_id"))).fetchall()
        return [{**_jsonable(r), "current": bool(r["current"])} for r in rows]

    @staticmethod
    def _other_station(actor: dict, station_id: int) -> None:
        """Revoking or deleting needs a session tied to its station, so the station in use cannot be the target:
        a session without that proof (omitted or forged) is refused rather than trusted."""
        if actor.get("session_station_id") is None:
            raise err(409, "STATION-SESSION-UNBOUND")
        if actor["session_station_id"] == station_id:
            raise err(409, "STATION-IN-USE")

    def station_apps(self, actor: dict, station_id: int) -> dict:
        """What this station's Runner reported it can launch; apart from the list, which is read often."""
        with self.db.tx() as c:
            s = c.execute("SELECT apps FROM stations WHERE id = %s AND revoked_at IS NULL", (station_id,)).fetchone()
        if not s:
            raise err(404, "NOT-FOUND", what_missing="station")
        return {"apps": s["apps"]}

    def remove_station(self, actor: dict, station_id: int) -> dict:
        """Logical deletion of a revoked station: it leaves the inventory; executions and schedules keep their link
        (a schedule on it keeps skipping, as for any revoked station). Its name becomes free again."""
        self.require_admin(actor)
        self._other_station(actor, station_id)
        with self.db.tx() as c:
            s = c.execute("SELECT revoked_at FROM stations WHERE id = %s AND deleted_at IS NULL FOR UPDATE", (station_id,)).fetchone()
            if not s:
                raise err(404, "NOT-FOUND", what_missing="station")
            if s["revoked_at"] is None:
                raise err(409, "STATION-NOT-REVOKED")
            c.execute("UPDATE stations SET deleted_at = now() WHERE id = %s", (station_id,))
        return {"deleted": True}

    def revoke_station(self, actor: dict, station_id: int) -> None:
        self.require_admin(actor)
        self._other_station(actor, station_id)
        with self.db.tx() as c:
            if not c.execute("UPDATE stations SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL AND deleted_at IS NULL RETURNING id",
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
            reported = _station_apps(info.get("apps"))
            if reported is not None:  # sent when it changes: keep what is stored otherwise
                c.execute("UPDATE stations SET apps = %s WHERE id = %s", (Jsonb(reported), station["id"]))
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
    def create_routine(self, actor: dict, name: str, category: str, version: dict, link=None) -> dict:
        """`link` makes it the first step of an empty process, in the same transaction."""
        self.require_admin(actor)
        if not isinstance(name, str) or not 1 <= len(name) <= 120:
            raise err(400, "VALIDATION", reason="invalid routine name")
        if category not in CATEGORIES:
            raise err(400, "VALIDATION", reason="category must be browser, windows, mac or linux")
        if (version or {}).get("kind") == "browser_open" and category != "browser":
            raise err(400, "VALIDATION", reason="browser routines use the browser category")
        follow = (version or {}).get("kind") == "followup"
        if follow and category != "windows":
            raise err(400, "VALIDATION", reason="follow-up routines use the windows category")
        if follow and not isinstance(link, dict):
            raise err(400, "VALIDATION", reason="a follow-up needs a process and a previous step")
        if not follow and link is not None and (version or {}).get("kind") not in PREPARED_KINDS:
            raise err(400, "VALIDATION", reason="only routines of the assistant start a process here")
        with self.db.tx() as c:
            r = c.execute("INSERT INTO routines (name, category, created_by) VALUES (%s, %s, %s) RETURNING *",
                          (name, category, actor["id"])).fetchone()
            v = self._insert_version(c, actor, r, version)
            if follow:
                self._link_after(c, link, r["id"])
            elif link is not None:
                self._link_start(c, link, r["id"])
        return {"routine": _jsonable(r), "version": v}

    def _changeable_process(self, c, process_id) -> dict:
        p = c.execute("SELECT id, name, system_key FROM processes WHERE id = %s AND NOT archived FOR UPDATE",
                      (process_id,)).fetchone() if isinstance(process_id, int) else None
        if not p:
            raise err(404, "NOT-FOUND", what_missing="process")
        if p["system_key"]:
            raise err(400, "VALIDATION", reason="the ready-made process cannot be changed")
        return p

    def _link_after(self, c, link: dict, routine_id: int) -> None:
        """The follow-up comes right after the chosen step, which now continues to it; later steps move down.
        Inside one execution it receives what that step produced. Running executions keep their snapshot."""
        p = self._changeable_process(c, link.get("process_id"))
        after = link.get("after_position")
        if not isinstance(after, int) or not c.execute("SELECT 1 FROM process_items WHERE process_id = %s AND position = %s",
                                                       (p["id"], after)).fetchone():
            raise err(400, "VALIDATION", reason="the previous step does not exist in this process")
        for row in c.execute("""SELECT position FROM process_items WHERE process_id = %s AND position > %s
                                ORDER BY position DESC""", (p["id"], after)).fetchall():
            c.execute("UPDATE process_items SET position = position + 1 WHERE process_id = %s AND position = %s", (p["id"], row["position"]))
        c.execute("UPDATE process_items SET continue_next = true WHERE process_id = %s AND position = %s", (p["id"], after))
        c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, %s, %s, true)",
                  (p["id"], after + 1, routine_id))
        c.execute("UPDATE processes SET updated_at = now() WHERE id = %s", (p["id"],))

    def _link_start(self, c, link, routine_id: int) -> None:
        """A process has at most one starting routine; the process row lock settles concurrent attempts."""
        p = self._changeable_process(c, link.get("process_id") if isinstance(link, dict) else None)
        if c.execute("SELECT 1 FROM process_items WHERE process_id = %s LIMIT 1", (p["id"],)).fetchone():
            raise err(409, "PROCESS-HAS-START", process=p["name"])
        c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, 1, %s, true)",
                  (p["id"], routine_id))

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
            cur = c.execute("SELECT kind, config FROM routine_versions WHERE routine_id = %s ORDER BY version DESC LIMIT 1", (routine_id,)).fetchone()
            new = version.get("kind")
            if cur and KIND_FAMILY.get(new, new) != KIND_FAMILY.get(cur["kind"], cur["kind"]):
                raise err(400, "VALIDATION", reason="a new version cannot change the kind of a routine")
            if cur and new == "followup" and (version.get("config") or {}).get("action") != (cur["config"] or {}).get("action"):
                raise err(400, "VALIDATION", reason="a new version cannot change the action of a follow-up")
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
        elif kind == "app_open":
            if routine["category"] != "windows":
                raise err(400, "VALIDATION", reason="application routines use the windows category")
            config = app_config(v.get("config"))
            row = (kind, None, None, None, None, "windows-x86_64", {})
        elif kind == "followup":
            config = followup_config(v.get("config"))
            if config["action"] == "review" and not c.execute("SELECT 1 FROM users WHERE id = %s AND active", (config["assignee_id"],)).fetchone():
                raise err(400, "VALIDATION", reason="choose an active team member")
            row = (kind, None, None, None, None, None if config["action"] == "review" else "windows-x86_64", {})
        else:
            raise err(400, "VALIDATION", reason="version kind must be template, procedure, browser_open, app_open or followup")
        n = c.execute("SELECT coalesce(max(version), 0) + 1 AS n FROM routine_versions WHERE routine_id = %s",
                      (routine["id"],)).fetchone()["n"]
        out = c.execute("""INSERT INTO routine_versions (routine_id, version, kind, template_id, template_version, procedure,
                                  procedure_sha256, platform, inputs, note, created_by, config)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING id, routine_id, version, kind, template_id, template_version, procedure_sha256, platform, inputs,
                                     config, created_at""",
                        (routine["id"], n, *row[:6], Jsonb(row[6]), str(v.get("note") or "")[:500], actor["id"],
                         Jsonb(config) if kind in PREPARED_KINDS + ("followup",) else None)).fetchone()
        if kind == "followup" and config["action"] == "review":
            self._move_pending_reviews(c, routine["id"], config["assignee_id"])
        return _jsonable(out)

    def _move_pending_reviews(self, c, routine_id: int, assignee_id: int) -> None:
        """Pending requests follow the responsible of the step; the previous one loses them and their
        notifications. Decided requests keep their author and time."""
        for r in c.execute("""SELECT id FROM review_requests WHERE routine_id = %s AND status = 'pending' AND assignee_id <> %s
                              ORDER BY id FOR UPDATE""", (routine_id, assignee_id)).fetchall():
            c.execute("UPDATE review_requests SET assignee_id = %s WHERE id = %s", (assignee_id, r["id"]))
            c.execute("DELETE FROM notifications WHERE review_id = %s", (r["id"],))
            c.execute("INSERT INTO notifications (user_id, kind, review_id) VALUES (%s, 'review_request', %s)", (assignee_id, r["id"]))

    def list_routines(self, actor: dict) -> list[dict]:
        with self.db.tx() as c:
            rows = c.execute("""SELECT r.id, r.name, r.category, r.created_at, v.id AS version_id, v.version, v.kind,
                                       v.template_id, v.template_version, v.platform, v.inputs, v.config,
                                       v.procedure -> 'params' AS params, a.display AS assignee_name
                                FROM routines r JOIN LATERAL (SELECT * FROM routine_versions WHERE routine_id = r.id
                                                              ORDER BY version DESC LIMIT 1) v ON true
                                LEFT JOIN users a ON a.id = (v.config ->> 'assignee_id')::bigint
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

    def archive_routine(self, actor: dict, routine_id: int) -> dict:
        """Deleting a routine (Rotina > Lista): archived, and taken out of every process in the same transaction,
        the other steps keeping their order and continuation (TEAM-ACCOUNTS-20261108 item 6). Versions, running
        executions (their snapshot) and the history stay. A process left empty or starting with a follow-up is
        saved, and refused when it is run (PROCESS-START-INVALID)."""
        self.require_admin(actor)
        with self.db.tx() as c:
            # Processes first, then the routine: the order every process edit uses (process row, then _items).
            ids = [r["process_id"] for r in c.execute("SELECT DISTINCT process_id FROM process_items WHERE routine_id = %s ORDER BY 1",
                                                      (routine_id,)).fetchall()]
            procs = c.execute("SELECT id, name FROM processes WHERE id = ANY(%s) AND NOT archived ORDER BY id FOR UPDATE",
                              (ids,)).fetchall() if ids else []
            if not c.execute("SELECT 1 FROM routines WHERE id = %s AND NOT archived FOR UPDATE", (routine_id,)).fetchone():
                raise err(404, "NOT-FOUND", what_missing="routine")
            self._refuse_ready_made(c, routine_id)
            now = {r["process_id"] for r in c.execute("""SELECT i.process_id FROM process_items i JOIN processes p ON p.id = i.process_id
                                                         WHERE i.routine_id = %s AND NOT p.archived""", (routine_id,)).fetchall()}
            if not now <= {p["id"] for p in procs}:  # linked by another screen between the two reads
                raise err(409, "CONFLICT", reason="a process changed at the same time; try again")
            for p in procs:
                links = [{"routine_id": r["routine_id"], "continue_next": r["continue_next"]} for r in c.execute(
                    "SELECT routine_id, continue_next FROM process_items WHERE process_id = %s ORDER BY position", (p["id"],)).fetchall()
                    if r["routine_id"] != routine_id]
                self._write_items(c, p["id"], links)
                c.execute("UPDATE processes SET updated_at = now() WHERE id = %s", (p["id"],))
            c.execute("UPDATE routines SET archived = true WHERE id = %s", (routine_id,))
            self._drop_stale_changes(c, None, actor["id"])
        return {"archived": True, "processes": [p["name"] for p in procs]}

    # ------------------------------------------------------------ jobs
    def create_job(self, actor: dict, request_id: str, version_id: int, station_id: int, inputs: dict,
                   correlation_id: str) -> dict:
        try:
            return self._create_job(actor, request_id, version_id, station_id, inputs, correlation_id)
        except psycopg.errors.UniqueViolation:
            # Concurrent identical request: the other one created it; answer with that job.
            return self._create_job(actor, request_id, version_id, station_id, inputs, correlation_id)

    def _assistant_job(self, actor: dict, request_id, version: dict, station: dict, inputs: dict, cid: str, mode: str) -> dict:
        reason = compat_reason(version["category"], version["platform"], station)
        if not reason and _version_tuple(station.get("runner_version")) < ASSISTANT_RUNNER:
            reason = "update the RedRise of this station"
        if reason:
            raise err(409, "STATION-INCOMPATIBLE", cid, reason=reason)
        with self.db.tx() as c:
            j = c.execute("""INSERT INTO jobs (request_id, routine_version_id, station_id, inputs, requested_by, state, correlation_id, mode)
                             VALUES (%s, %s, %s, %s, %s, 'queued', %s, %s) ON CONFLICT (request_id) DO NOTHING RETURNING *""",
                          (request_id, version["id"], station["id"], Jsonb(inputs), actor["id"], cid, mode)).fetchone()
            if not j:  # concurrent identical request: answer with that job
                return {**self._job_view(c, c.execute("SELECT * FROM jobs WHERE request_id = %s", (request_id,)).fetchone()), "duplicate": True}
            self._event(c, j["id"], "queued", {"by": actor["username"], "mode": mode})
            return self._job_view(c, j)

    def _latest_prepared(self, c, routine_id: int, cid: str) -> dict:
        v = c.execute("""SELECT v.*, r.category FROM routines r JOIN LATERAL (SELECT * FROM routine_versions WHERE routine_id = r.id
                         ORDER BY version DESC LIMIT 1) v ON true WHERE r.id = %s AND NOT r.archived""", (routine_id,)).fetchone()
        if not v:
            raise err(404, "NOT-FOUND", cid, what_missing="routine")
        if v["kind"] not in PREPARED_KINDS:
            raise err(400, "VALIDATION", cid, reason="this routine is not prepared by the assistant")
        return v

    def prepare_routine(self, actor: dict, routine_id: int, request_id, station_id, cid: str) -> dict:
        """Asks the station to resolve the destination and dependencies. Nothing is opened."""
        self.require_admin(actor)
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise err(400, "VALIDATION", cid, reason="request_id missing")
        with self.db.tx() as c:
            prior = c.execute("SELECT * FROM jobs WHERE request_id = %s", (request_id,)).fetchone()
            if prior:
                return {**self._job_view(c, prior), "duplicate": True}
            v = self._latest_prepared(c, routine_id, cid)
            s = c.execute("SELECT * FROM stations WHERE id = %s", (station_id,)).fetchone() if isinstance(station_id, int) else None
            if not s or s["revoked_at"]:
                raise err(404, "NOT-FOUND", cid, what_missing="station")
        return self._assistant_job(actor, request_id, v, s, {}, cid, "prepare")

    def test_routine(self, actor: dict, routine_id: int, request_id, prepare_job_id, cid: str) -> dict:
        """Opens the destination of the version whose preparation was verified, on the same station; the
        Runner resolves that same config again. Only for the routine that starts a process; never an
        execution of that process."""
        self.require_admin(actor)
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise err(400, "VALIDATION", cid, reason="request_id missing")
        with self.db.tx() as c:
            prior = c.execute("SELECT * FROM jobs WHERE request_id = %s", (request_id,)).fetchone()
            if prior:
                return {**self._job_view(c, prior), "duplicate": True}
            v = self._latest_prepared(c, routine_id, cid)
            if not c.execute("""SELECT 1 FROM process_items i JOIN processes p ON p.id = i.process_id
                                WHERE i.routine_id = %s AND i.position = 1 AND NOT p.archived LIMIT 1""", (routine_id,)).fetchone():
                raise err(400, "VALIDATION", cid, reason="only the routine that starts a process is tested here")
            prep = c.execute("SELECT * FROM jobs WHERE id = %s AND mode = 'prepare'", (_uuid(prepare_job_id),)).fetchone()
            resolved = (((prep or {}).get("result") or {}).get("details") or {}).get("context", {}).get("resolved")
            if not prep or prep["state"] != "verified" or prep["routine_version_id"] != v["id"] or not resolved:
                raise err(409, "PREPARE-REQUIRED", cid, routine=str(routine_id))
            s = c.execute("SELECT * FROM stations WHERE id = %s AND revoked_at IS NULL", (prep["station_id"],)).fetchone()
            if not s:
                raise err(404, "NOT-FOUND", cid, what_missing="station")
        return self._assistant_job(actor, request_id, v, s, {}, cid, "test")

    def job_progress(self, station: dict, job_id: str, lease_id: str, check) -> dict:
        """One operation of the job, as the Runner performs it. Only recorded; decides nothing."""
        job_id, lease_id = _uuid(job_id), _uuid(lease_id, "lease")
        if not isinstance(check, dict) or check.get("state") not in ("running", "ok", "failed") or not isinstance(check.get("id"), str):
            raise ApiError(400, dg.contract_violation("RR-RUNNER", "RR-CORE", "job check", "invalid check", reported_by="RR-CORE"))
        with self.db.tx() as c:
            j = self._leased(c, station, job_id, lease_id)
            detail = check.get("detail")
            self._event(c, j["id"], "check", dg.sanitize({"id": check["id"][:40], "state": check["state"],
                                                          "detail": str(detail)[:300] if detail is not None else None}))
        return {"ok": True}

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
            linked = c.execute("""SELECT p.name FROM process_items i JOIN processes p ON p.id = i.process_id
                                  WHERE i.routine_id = %s AND NOT p.archived ORDER BY p.id LIMIT 1""", (v["routine_id"],)).fetchone()
            if linked:  # a routine stored with versions of mixed kinds still runs only through its process
                raise err(409, "ROUTINE-LINKED", correlation_id, process=linked["name"])
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
            # A follow-up acts on what the execution did so far, as it stands now.
            extra = {"execution": self._execution_view(c, {"id": j["execution_id"]})} if j["kind"] == "followup" and j["execution_id"] else {}
        return {**extra, "schema": JOB_SCHEMA, "job_id": str(j["id"]), "lease_id": str(lease), "correlation_id": j["correlation_id"],
                "kind": j["kind"], "category": j["category"], "platform": j["platform"], "template_id": j["template_id"],
                "template_version": j["template_version"], "procedure": j["procedure"], "inputs": j["inputs"],
                "config": j["config"], "mode": j["mode"], "execution_id": str(j["execution_id"]) if j["execution_id"] else None,
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
        """A process may start empty: its first routine comes from the assistant or from an integration."""
        if not isinstance(items, list) or len(items) > MAX_PROCESS_ITEMS:
            raise err(400, "VALIDATION", reason=f"a process links up to {MAX_PROCESS_ITEMS} routines")
        out = []
        for it in items:
            if not isinstance(it, dict) or not isinstance(it.get("routine_id"), int) or not isinstance(it.get("continue_next"), bool):
                raise err(400, "VALIDATION", reason="each link needs routine_id and continue_next")
            v = c.execute("""SELECT v.kind FROM routines r JOIN LATERAL (SELECT kind FROM routine_versions WHERE routine_id = r.id
                             ORDER BY version DESC LIMIT 1) v ON true WHERE r.id = %s AND NOT r.archived FOR SHARE OF r""", (it["routine_id"],)).fetchone()
            if not v:
                raise err(404, "NOT-FOUND", what_missing="routine")
            if v["kind"] not in PROCESS_KINDS:
                raise err(400, "VALIDATION", reason="this kind of routine cannot be linked to a process in this version")
            out.append({"routine_id": it["routine_id"], "continue_next": it["continue_next"]})
        return out

    @staticmethod
    def _write_items(c, process_id: int, links: list[dict]) -> None:
        """Replaces the links of a process, numbered 1..n in the given order."""
        c.execute("DELETE FROM process_items WHERE process_id = %s", (process_id,))
        for i, it in enumerate(links, 1):
            c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, %s, %s, %s)",
                      (process_id, i, it["routine_id"], it["continue_next"]))

    @staticmethod
    def _drop_stale_changes(c, process_id: int | None, actor_id: int) -> None:
        """A pending replacement of step 1 that no longer fits (step 1 changed, or the new routine was deleted) is
        cancelled in the same transaction, never applied to another composition. None: every process."""
        rows = c.execute("""SELECT q.id FROM step_change_requests q JOIN routines n ON n.id = q.new_routine_id
                            WHERE q.status = 'pending' AND (%(p)s::bigint IS NULL OR q.process_id = %(p)s)
                              AND (n.archived OR q.old_routine_id IS DISTINCT FROM
                                   (SELECT routine_id FROM process_items WHERE process_id = q.process_id AND position = 1))
                            FOR UPDATE OF q""", {"p": process_id}).fetchall()
        for q in rows:
            c.execute("UPDATE step_change_requests SET status = 'cancelled', decided_by = %s, decided_at = now() WHERE id = %s",
                      (actor_id, q["id"]))
            c.execute("DELETE FROM notifications WHERE change_id = %s", (q["id"],))

    @staticmethod
    def _first_step_starts(c, links: list[dict]) -> None:
        """A follow-up needs a previous step."""
        if links and c.execute("""SELECT 1 FROM routine_versions WHERE routine_id = %s AND kind = 'followup'
                                  AND version = (SELECT max(version) FROM routine_versions WHERE routine_id = %s)""",
                               (links[0]["routine_id"], links[0]["routine_id"])).fetchone():
            raise err(400, "VALIDATION", reason="a follow-up cannot be the first step of a process")

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
            self._write_items(c, p["id"], links)
        return self.get_process(actor, p["id"])

    def update_process(self, actor: dict, process_id: int, name, items) -> dict:
        """Replaces name and links; running executions keep their snapshot. Any link may be removed, step 1
        included, and the process may end empty (TEAM-ACCOUNTS-20261108 item 5); a composition that cannot
        start is saved and refused when run. Approval is still needed to put another routine ahead of the
        current step 1 while it stays in the process (Substituir etapa 1), unless that step 1 is a follow-up."""
        self.require_admin(actor)
        name = self._process_name(name)
        with self.db.tx() as c:
            row = c.execute("SELECT id, system_key FROM processes WHERE id = %s AND NOT archived FOR UPDATE", (process_id,)).fetchone()
            if not row:
                raise err(404, "NOT-FOUND", what_missing="process")
            if row["system_key"]:
                raise err(400, "VALIDATION", reason="the ready-made process cannot be changed")
            links = self._items(c, items)
            first = c.execute("""SELECT i.routine_id, v.kind FROM process_items i JOIN LATERAL (SELECT kind FROM routine_versions
                                 WHERE routine_id = i.routine_id ORDER BY version DESC LIMIT 1) v ON true
                                 WHERE i.process_id = %s AND i.position = 1""", (process_id,)).fetchone()
            # A follow-up left first is not a start to protect: putting a routine ahead of it is the fix.
            kept = first and first["kind"] != "followup" and any(it["routine_id"] == first["routine_id"] for it in links)
            if kept and links[0]["routine_id"] != first["routine_id"]:
                raise err(409, "STEP1-NEEDS-APPROVAL")
            c.execute("UPDATE processes SET name = %s, updated_at = now() WHERE id = %s", (name, process_id))
            self._write_items(c, process_id, links)
            self._drop_stale_changes(c, process_id, actor["id"])
        return self.get_process(actor, process_id)

    def integrate_routine(self, actor: dict, process_id: int, routine_id) -> dict:
        """A standalone routine becomes the next step of a process (the first, when it is empty).
        The step before it now continues to it, or it would never run. Running executions keep their snapshot."""
        self.require_admin(actor)
        with self.db.tx() as c:
            p = self._changeable_process(c, process_id)
            if not isinstance(routine_id, int) or not self._items(c, [{"routine_id": routine_id, "continue_next": True}]):
                raise err(400, "VALIDATION", reason="routine_id expected")
            linked = c.execute("""SELECT p.name FROM process_items i JOIN processes p ON p.id = i.process_id
                                  WHERE i.routine_id = %s AND NOT p.archived ORDER BY p.id LIMIT 1""", (routine_id,)).fetchone()
            if linked:
                raise err(409, "CONFLICT", reason=f"routine already linked to {linked['name']}")
            n = c.execute("SELECT coalesce(max(position), 0) AS n FROM process_items WHERE process_id = %s", (p["id"],)).fetchone()["n"]
            if n >= MAX_PROCESS_ITEMS:
                raise err(400, "VALIDATION", reason=f"a process links up to {MAX_PROCESS_ITEMS} routines")
            if n == 0:
                self._first_step_starts(c, [{"routine_id": routine_id}])
            c.execute("UPDATE process_items SET continue_next = true WHERE process_id = %s AND position = %s", (p["id"], n))
            c.execute("INSERT INTO process_items (process_id, position, routine_id, continue_next) VALUES (%s, %s, %s, true)",
                      (p["id"], n + 1, routine_id))
            c.execute("UPDATE processes SET updated_at = now() WHERE id = %s", (p["id"],))
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
            changes = {r["process_id"]: str(r["id"]) for r in c.execute("SELECT process_id, id FROM step_change_requests WHERE status = 'pending'").fetchall()}
        out = []
        for p in procs:
            le = last.get(p["id"])
            out.append({**_jsonable(p), "pending_change": changes.get(p["id"]), "items": [_jsonable({k: v for k, v in i.items() if k != "process_id"})
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
            return self._create_execution_in(c, actor, request_id, station_id, process_id, routine_id, cid)

    def _create_execution_in(self, c, actor: dict, request_id: str, station_id, process_id, routine_id, cid: str) -> dict:
        """Inside the caller's transaction: the scheduler records the occurrence and its execution together."""
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
                raise err(400, "VALIDATION", cid, reason="this kind of routine does not run as an execution in this version")
            # A linked routine, even as the only step, runs through its process.
            linked = c.execute("""SELECT p.name FROM process_items i JOIN processes p ON p.id = i.process_id
                                  WHERE i.routine_id = %s AND NOT p.archived ORDER BY p.id LIMIT 1""", (routine_id,)).fetchone()
            if linked:
                raise err(409, "ROUTINE-LINKED", cid, process=linked["name"])
            if not (rows[0]["config"] or {}).get("isolated"):
                # G25: enforced here, not only by a disabled button.
                raise err(409, "ROUTINE-NOT-ISOLATED", cid, routine=rows[0]["name"])
        else:
            # FOR SHARE: a replacement of step 1 waits for this start, or this start sees the new step.
            proc = c.execute("SELECT id, name FROM processes WHERE id = %s AND NOT archived FOR SHARE", (process_id,)).fetchone()
            if not proc:
                raise err(404, "NOT-FOUND", cid, what_missing="process")
            rows = c.execute("""SELECT i.position, r.id AS routine_id, v.id AS routine_version_id, r.name, i.continue_next,
                                       v.kind, v.config, v.platform, r.category, r.archived
                                FROM process_items i JOIN routines r ON r.id = i.routine_id
                                JOIN LATERAL (SELECT * FROM routine_versions WHERE routine_id = r.id
                                              ORDER BY version DESC LIMIT 1) v ON true
                                WHERE i.process_id = %s ORDER BY i.position""", (process_id,)).fetchall()
            # A composition saved without a valid start never runs, not even partly (item 5); a follow-up needs the
            # context of a step before it and is never promoted to the first one.
            if not rows:
                raise err(409, "PROCESS-START-INVALID", cid, process=proc["name"], reason="no linked routine")
            if rows[0]["kind"] == "followup":
                raise err(409, "PROCESS-START-INVALID", cid, process=proc["name"], reason="step 1 is a follow-up")
            if any(r["archived"] or r["kind"] not in PROCESS_KINDS for r in rows):
                raise err(400, "VALIDATION", cid, reason="the process links a routine that cannot run")
        for r in rows:  # every step must be able to run on the chosen station; a review runs on none
            if _is_review(r):
                continue
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

    def _open_review(self, c, execution: dict, item: dict) -> None:
        """Pauses the execution. The responsible is the current one of the step, not the one when it started."""
        # FOR SHARE: a new responsible either commits before this read, or waits and then moves this request.
        c.execute("SELECT 1 FROM routines WHERE id = %s FOR SHARE", (item["routine_id"],))
        cur = c.execute("""SELECT config FROM routine_versions WHERE routine_id = %s ORDER BY version DESC LIMIT 1""",
                        (item["routine_id"],)).fetchone()
        assignee = ((cur or {}).get("config") or item.get("config") or {}).get("assignee_id")
        r = c.execute("""INSERT INTO review_requests (execution_id, position, routine_id, assignee_id) VALUES (%s, %s, %s, %s)
                         ON CONFLICT (execution_id, position) DO NOTHING RETURNING id""",
                      (execution["id"], item["position"], item["routine_id"], assignee)).fetchone()
        if r:
            c.execute("INSERT INTO notifications (user_id, kind, review_id) VALUES (%s, 'review_request', %s)", (assignee, r["id"]))
        c.execute("UPDATE executions SET state = 'waiting_review' WHERE id = %s", (execution["id"],))

    def _queue_step(self, c, execution: dict, item: dict) -> None:
        if _is_review(item):
            self._open_review(c, execution, item)
            return
        j = c.execute("""INSERT INTO jobs (request_id, routine_version_id, station_id, inputs, requested_by, state, correlation_id,
                                           execution_id, position)
                         VALUES (%s, %s, %s, '{}', %s, 'queued', %s, %s, %s)
                         ON CONFLICT DO NOTHING RETURNING id""",
                      (f"exec:{execution['id']}:{item['position']}", item["routine_version_id"], execution["station_id"],
                       execution["requested_by"], execution["correlation_id"], execution["id"], item["position"])).fetchone()
        if j:
            self._event(c, j["id"], "queued", {"execution": str(execution["id"]), "position": item["position"]})

    def _advance(self, c, execution_id, position: int, state: str, verified: bool, result,
                 cancel_requested: bool = False) -> None:
        """R04/R05/G17/G19/G21: only a verified result with continuation on and
        a next link starts the next routine; anything else ends the execution
        here, without retry. Runs inside the transaction that finished the job.
        A cancel accepted while the step ran keeps that step's real result but
        never starts the next one; the execution ends as cancelled."""
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
                if cancel_requested:
                    state, end = "cancelled", "cancelled"
                else:
                    self._queue_step(c, {**e, "context": context}, snapshot[position])
                    return
            else:
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
                                          (e["id"],)).fetchall(), self._reviews_of(c, [e["id"]]))

    @staticmethod
    def _reviews_of(c, execution_ids: list) -> list[dict]:
        return c.execute(f"{_REVIEW_SELECT} WHERE q.execution_id = ANY(%s)", (execution_ids,)).fetchall() if execution_ids else []

    @staticmethod
    def _shape(e: dict, jobs: list[dict], reviews: list[dict] | None = None) -> dict:
        by_pos = {j["position"]: j for j in jobs}
        review_at = {q["position"]: q for q in reviews or [] if q["execution_id"] == e["id"]}
        steps = []
        for it in e["snapshot"]:
            j = by_pos.get(it["position"])
            q = review_at.get(it["position"])
            if q:
                approved = q["status"] == "approved"
                steps.append({"position": it["position"], "routine_id": it["routine_id"], "routine_version_id": it["routine_version_id"],
                              "name": it["name"], "continue_next": it["continue_next"], "job_id": None,
                              "state": "verified" if approved else "awaiting_review", "verified": approved, "error_code": None, "diagnostic": None,
                              "started_at": q["requested_at"].isoformat(), "finished_at": q["decided_at"].isoformat() if q["decided_at"] else None,
                              "review": _review_view(q)})
                continue
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

    # ------------------------------------------------------------ schedules (work order SCHEDULE-PROCESS-20261107)
    # An occurrence is its local date and time in the schedule's fixed time zone ('YYYY-MM-DDTHH:MM'); the database
    # key and the execution request_id are both made from it. Creating, editing or resuming computes the next FUTURE
    # occurrence: only a schedule that stayed enabled while the Core was stopped recovers a missed one.
    SCHEDULE_GRACE = timedelta(minutes=15)  # late start after a stop, and the longest wait for step 1 to begin

    @staticmethod
    def _zone(tz) -> ZoneInfo:
        if not isinstance(tz, str) or not re.fullmatch(r"[A-Za-z0-9_+\-/]{1,64}", tz):
            raise err(400, "VALIDATION", reason="invalid time zone")
        try:
            return ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise err(400, "VALIDATION", reason="unknown time zone") from None

    @staticmethod
    def next_slot(weekdays: int, hour: int, minute: int, tz: str, after: datetime) -> tuple[str, datetime]:
        """First local occurrence strictly after `after`. A local time that does not exist that day (a clock
        jumping forward) skips the day; a repeated one (a clock going back) is its first instant only."""
        z = ZoneInfo(tz)
        local_day = after.astimezone(z).date()
        for d in range(9):
            day = local_day + timedelta(days=d)
            if not weekdays & (1 << day.weekday()):
                continue
            naive = datetime(day.year, day.month, day.day, hour, minute)
            at = naive.replace(tzinfo=z, fold=0).astimezone(timezone.utc)
            if at.astimezone(z).replace(tzinfo=None) != naive:  # does not exist in this zone that day
                continue
            if at > after:
                return naive.strftime("%Y-%m-%dT%H:%M"), at
        raise err(400, "VALIDATION", reason="no occurrence in the next week")

    @staticmethod
    def _schedule_input(b: dict) -> dict:
        days = b.get("weekdays")
        if not isinstance(days, list) or not days or any(not isinstance(x, int) or not 1 <= x <= 7 for x in days):
            raise err(400, "VALIDATION", reason="weekdays: 1 (Monday) to 7 (Sunday)")
        hour, minute = b.get("hour"), b.get("minute")
        if not isinstance(hour, int) or not 0 <= hour <= 23 or not isinstance(minute, int) or not 0 <= minute <= 59:
            raise err(400, "VALIDATION", reason="time: hour 0-23 and minute 0-59")
        Core._zone(b.get("timezone"))
        return {"weekdays": sum(1 << (x - 1) for x in set(days)), "hour": hour, "minute": minute, "timezone": b["timezone"]}

    _SCHED_SELECT = """SELECT s.*, p.name AS process_name, st.name AS station_name, u.display AS owner_name,
                              r.slot_local AS last_slot_local, r.state AS last_state, r.reason AS last_reason,
                              r.execution_id AS last_execution_id
                       FROM schedules s JOIN processes p ON p.id = s.process_id JOIN stations st ON st.id = s.station_id
                       JOIN users u ON u.id = s.owner_id
                       LEFT JOIN LATERAL (SELECT * FROM schedule_runs WHERE schedule_id = s.id ORDER BY slot_at DESC LIMIT 1) r ON true"""

    @staticmethod
    def _schedule_view(r: dict) -> dict:
        out = _jsonable({k: v for k, v in r.items() if k not in ("weekdays",)})
        out["weekdays"] = [d + 1 for d in range(7) if r["weekdays"] & (1 << d)]
        return out

    def list_schedules(self, actor: dict) -> list[dict]:
        with self.db.tx() as c:
            rows = c.execute(f"{self._SCHED_SELECT} ORDER BY p.name, s.hour, s.minute, s.id").fetchall()
        return [self._schedule_view(r) for r in rows]

    def schedule_runs(self, actor: dict, schedule_id: int) -> list[dict]:
        with self.db.tx() as c:
            if not c.execute("SELECT 1 FROM schedules WHERE id = %s", (schedule_id,)).fetchone():
                raise err(404, "NOT-FOUND", what_missing="schedule")
            rows = c.execute("""SELECT id, slot_local, slot_at, state, reason, execution_id, created_at FROM schedule_runs
                                WHERE schedule_id = %s ORDER BY slot_at DESC LIMIT 50""", (schedule_id,)).fetchall()
        return [_jsonable(r) for r in rows]

    def preview_schedule(self, actor: dict, b: dict) -> dict:
        self.require_admin(actor)
        v = self._schedule_input(b)
        slot, at = self.next_slot(v["weekdays"], v["hour"], v["minute"], v["timezone"], datetime.now(timezone.utc))
        return {"next_slot_local": slot, "next_run_at": at.isoformat()}

    def _schedule_target(self, c, process_id, station_id) -> None:
        if not isinstance(process_id, int) or not c.execute("SELECT 1 FROM processes WHERE id = %s AND NOT archived", (process_id,)).fetchone():
            raise err(404, "NOT-FOUND", what_missing="process")
        if not isinstance(station_id, int) or not c.execute("SELECT 1 FROM stations WHERE id = %s AND revoked_at IS NULL", (station_id,)).fetchone():
            raise err(404, "NOT-FOUND", what_missing="station")

    def create_schedule(self, actor: dict, b: dict) -> dict:
        self.require_admin(actor)
        v = self._schedule_input(b)
        slot, at = self.next_slot(v["weekdays"], v["hour"], v["minute"], v["timezone"], datetime.now(timezone.utc))
        with self.db.tx() as c:
            self._schedule_target(c, b.get("process_id"), b.get("station_id"))
            sid = c.execute("""INSERT INTO schedules (process_id, station_id, weekdays, hour, minute, timezone, owner_id, next_slot_local, next_run_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                            (b["process_id"], b["station_id"], v["weekdays"], v["hour"], v["minute"], v["timezone"], actor["id"], slot, at)).fetchone()["id"]
            return self._schedule_view(c.execute(f"{self._SCHED_SELECT} WHERE s.id = %s", (sid,)).fetchone())

    def update_schedule(self, actor: dict, schedule_id: int, b: dict) -> dict:
        """Edit, pause or resume. Any edit or resume recomputes the next FUTURE occurrence and makes the
        administrator who did it the owner (runs are requested in the owner's name)."""
        self.require_admin(actor)
        with self.db.tx() as c:
            cur = c.execute("SELECT * FROM schedules WHERE id = %s FOR UPDATE", (schedule_id,)).fetchone()
            if not cur:
                raise err(404, "NOT-FOUND", what_missing="schedule")
            timing = any(k in b for k in ("weekdays", "hour", "minute", "timezone"))
            v = self._schedule_input({"weekdays": [d + 1 for d in range(7) if cur["weekdays"] & (1 << d)], "hour": cur["hour"],
                                      "minute": cur["minute"], "timezone": cur["timezone"], **{k: b[k] for k in b if k in
                                      ("weekdays", "hour", "minute", "timezone")}})
            station = b.get("station_id", cur["station_id"])
            self._schedule_target(c, cur["process_id"], station)
            enabled = cur["enabled"] if "enabled" not in b else b["enabled"]
            if not isinstance(enabled, bool):
                raise err(400, "VALIDATION", reason="enabled must be true or false")
            if enabled:
                slot, at = self.next_slot(v["weekdays"], v["hour"], v["minute"], v["timezone"], datetime.now(timezone.utc))
            else:
                slot, at = None, None
            c.execute("""UPDATE schedules SET weekdays = %s, hour = %s, minute = %s, timezone = %s, station_id = %s, enabled = %s,
                                paused_reason = %s, owner_id = %s, next_slot_local = %s, next_run_at = %s, updated_at = now()
                         WHERE id = %s""",
                      (v["weekdays"], v["hour"], v["minute"], v["timezone"], station, enabled, None if enabled else "paused_by_user",
                       actor["id"] if (enabled or timing or "station_id" in b) else cur["owner_id"], slot, at, schedule_id))
            return self._schedule_view(c.execute(f"{self._SCHED_SELECT} WHERE s.id = %s", (schedule_id,)).fetchone())

    def delete_schedule(self, actor: dict, schedule_id: int) -> dict:
        self.require_admin(actor)
        with self.db.tx() as c:
            if not c.execute("DELETE FROM schedules WHERE id = %s RETURNING id", (schedule_id,)).fetchone():
                raise err(404, "NOT-FOUND", what_missing="schedule")
        return {"deleted": True}

    def _schedule_note(self, c, run_id: int, user_ids) -> None:
        for uid in user_ids:
            c.execute("INSERT INTO notifications (user_id, kind, schedule_run_id) VALUES (%s, 'schedule', %s)", (uid, run_id))

    def _schedule_run(self, c, s: dict, state: str, reason: str | None, execution_id=None, diagnostic=None) -> int | None:
        r = c.execute("""INSERT INTO schedule_runs (schedule_id, slot_local, slot_at, state, reason, execution_id, diagnostic)
                         VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (schedule_id, slot_local) DO NOTHING RETURNING id""",
                      (s["id"], s["next_slot_local"], s["next_run_at"], state, reason, execution_id,
                       Jsonb(diagnostic) if diagnostic else None)).fetchone()
        return r["id"] if r else None

    def schedule_tick(self, now: datetime | None = None) -> dict:
        """One pass of the scheduler (every 30 s on the host; the tests give the clock). Each due schedule is
        handled in ONE transaction: the occurrence, its execution and both links commit together or not at all."""
        now = now or datetime.now(timezone.utc)
        done = {"started": 0, "skipped": 0, "missed": 0, "expired": self._expire_unstarted(now)}
        with self.db.tx() as c:
            due = [r["id"] for r in c.execute("""SELECT id FROM schedules WHERE enabled AND next_run_at <= %s
                                                 ORDER BY next_run_at LIMIT 50""", (now,)).fetchall()]
        for sid in due:
            try:
                with self.db.tx() as c:
                    s = c.execute("""SELECT * FROM schedules WHERE id = %s AND enabled AND next_run_at <= %s
                                     FOR UPDATE SKIP LOCKED""", (sid, now)).fetchone()
                    if s:
                        done[self._fire(c, s, now)] += 1
            except Exception as e:  # noqa: BLE001 - one schedule never stops the others; nothing of it was committed
                done.setdefault("errors", []).append({"schedule_id": sid, "error": type(e).__name__})
        return done

    def _fire(self, c, s: dict, now: datetime) -> str:
        nxt_slot, nxt_at = self.next_slot(s["weekdays"], s["hour"], s["minute"], s["timezone"], max(now, s["next_run_at"]))
        c.execute("UPDATE schedules SET next_slot_local = %s, next_run_at = %s WHERE id = %s", (nxt_slot, nxt_at, s["id"]))
        if now - s["next_run_at"] > self.SCHEDULE_GRACE:  # the Core was stopped: never a late run, never several
            run = self._schedule_run(c, s, "missed", "core_stopped")
            if run:
                self._schedule_note(c, run, [s["owner_id"]])
            return "missed"
        owner = c.execute("SELECT * FROM users WHERE id = %s", (s["owner_id"],)).fetchone()
        if not owner or not owner["active"] or owner["role"] != "admin":  # the loop is not the API: check it here
            c.execute("UPDATE schedules SET enabled = false, paused_reason = 'owner_not_allowed', next_slot_local = NULL, next_run_at = NULL WHERE id = %s",
                      (s["id"],))
            run = self._schedule_run(c, s, "skipped", "owner_not_allowed")
            if run:
                self._schedule_note(c, run, [u["id"] for u in c.execute("SELECT id FROM users WHERE active AND role = 'admin'")])
            return "skipped"

        def skip(reason: str, diagnostic=None, pause: bool = False) -> str:
            if pause:
                c.execute("UPDATE schedules SET enabled = false, paused_reason = %s, next_slot_local = NULL, next_run_at = NULL WHERE id = %s",
                          (reason, s["id"]))
            run = self._schedule_run(c, s, "skipped", reason, diagnostic=diagnostic)
            if run:
                self._schedule_note(c, run, [owner["id"]])
            return "skipped"

        if c.execute("""SELECT 1 FROM executions WHERE schedule_id = %s AND state IN ('running', 'waiting_review') LIMIT 1""",
                     (s["id"],)).fetchone():
            return skip("previous_still_running")
        st = c.execute("""SELECT revoked_at IS NULL AS active, last_seen_at > now() - interval '45 seconds' AS online, session_state
                          FROM stations WHERE id = %s""", (s["station_id"],)).fetchone()
        if not st or not st["active"] or not st["online"] or st["session_state"] != "ready":
            return skip("station_unavailable")
        request_id = f"agenda-{s['id']}-{s['next_slot_local'].replace('-', '').replace('T', '').replace(':', '')}"
        cid = dg.new_correlation_id()
        try:
            with c.transaction():  # savepoint: a refused start leaves only the skipped occurrence
                e = self._create_execution_in(c, owner, request_id, s["station_id"], s["process_id"], None, cid)
        except ApiError as x:
            code = x.diagnostic.error_code
            pause = code in ("NOT-FOUND", "VALIDATION", "PROCESS-START-INVALID")  # archived, no valid step 1, or not runnable
            return skip("process_unavailable" if pause else "station_incompatible" if code == "STATION-INCOMPATIBLE" else code.lower(),
                        diagnostic=x.diagnostic.to_dict(), pause=pause)
        if not self._schedule_run(c, s, "started", None, execution_id=e["id"]):
            raise RuntimeError("occurrence already recorded")  # rolls the whole transaction back, execution included
        c.execute("UPDATE executions SET schedule_id = %s WHERE id = %s", (s["id"], e["id"]))
        return "started"

    def _expire_unstarted(self, now: datetime) -> int:
        """Ready at the time, but the station got busy or disconnected before step 1 began: after the grace the
        occurrence expires, step 1 is cancelled without effect and the owner is told it did not start."""
        n = 0
        with self.db.tx() as c:
            rows = c.execute("""SELECT r.id, s.owner_id, j.id AS job_id, j.state AS job_state, j.correlation_id
                                FROM schedule_runs r JOIN schedules s ON s.id = r.schedule_id
                                JOIN jobs j ON j.execution_id = r.execution_id AND j.position = 1
                                WHERE r.state = 'started' AND r.slot_at < %s AND j.state IN ('queued', 'claimed')
                                FOR UPDATE OF r, j SKIP LOCKED""", (now - self.SCHEDULE_GRACE,)).fetchall()
            for r in rows:
                d = dg.make("SCHEDULE-NOT-STARTED", reported_by="RR-CORE", correlation_id=r["correlation_id"], effect_state="none").to_dict()
                if r["job_state"] == "queued":
                    self._finish(c, r["job_id"], "cancelled", diagnostic=d)
                else:  # claimed: the Runner is told not to start; a lost lease brings it back here as queued
                    c.execute("UPDATE jobs SET cancel_requested = true WHERE id = %s", (r["job_id"],))
                    self._event(c, r["job_id"], "cancel_requested", {"by": "scheduler", "error_code": "SCHEDULE-NOT-STARTED"})
                c.execute("UPDATE schedule_runs SET state = 'expired', reason = 'not_started', diagnostic = %s WHERE id = %s",
                          (Jsonb(d), r["id"]))
                self._schedule_note(c, r["id"], [r["owner_id"]])
                n += 1
        return n

    # Situation groups shared by the summary and the UI tabs (desktop/src/data/status.ts):
    # attention = finished and not verified; verified = finished verified.
    _GROUPS = {"running": "e.state = 'running'", "waiting": "e.state = 'waiting_review'",
               "attention": "e.state = 'finished' AND e.outcome IS DISTINCT FROM 'verified'",
               "verified": "e.state = 'finished' AND e.outcome = 'verified'"}
    SUMMARY_DAYS = 30

    @staticmethod
    def _days(days) -> int | None:
        if days is None:
            return None
        try:
            n = int(days)
        except (TypeError, ValueError):
            n = 0
        if not 1 <= n <= 366:
            raise err(400, "VALIDATION", reason="days must be an integer from 1 to 366")
        return n

    def execution_summary(self, actor: dict, days=None) -> dict:
        """Counts of executions started in the last `days` days, by situation, counted in the database
        (not from a capped list). Same period and predicates as list_executions(days=...)."""
        n = self._days(days) or self.SUMMARY_DAYS
        groups = ", ".join(f"count(*) FILTER (WHERE {sql}) AS {name}" for name, sql in self._GROUPS.items())
        with self.db.tx() as c:
            self._sweep(c)
            row = c.execute(f"""SELECT now() AS until, now() - make_interval(days => %s) AS since, count(*) AS total, {groups}
                                FROM executions e WHERE e.created_at >= now() - make_interval(days => %s)""", (n, n)).fetchone()
        return {"days": n, "since": row["since"].isoformat(), "until": row["until"].isoformat(),
                "total": int(row["total"]), **{k: int(row[k]) for k in self._GROUPS}}

    def list_executions(self, actor: dict, limit: int = 100, days=None) -> list[dict]:
        """Most recent first. With `days`, only executions started in that period (the summary's), up to 500."""
        n = self._days(days)
        where, args = ("WHERE e.created_at >= now() - make_interval(days => %s)", [n]) if n else ("", [])
        if n:
            limit = 500
        with self.db.tx() as c:
            self._sweep(c)
            rows = c.execute(f"{self._EXEC_SELECT} {where} ORDER BY e.created_at DESC LIMIT %s", (*args, min(max(limit, 1), 500))).fetchall()
            ids = [r["id"] for r in rows]
            jobs = c.execute("""SELECT id, execution_id, position, state, verified, diagnostic, diagnostic ->> 'error_code' AS error_code,
                                       started_at, finished_at FROM jobs WHERE execution_id = ANY(%s)""", (ids,)).fetchall() if ids else []
            reviews = self._reviews_of(c, ids)
        return [self._shape(r, [j for j in jobs if j["execution_id"] == r["id"]], reviews) for r in rows]

    # ------------------------------------------------------------ review requests and notifications
    def list_reviews(self, actor: dict) -> list[dict]:
        """Marcado para mim: requests whose current responsible is this person, pending first, then decided."""
        with self.db.tx() as c:
            rows = c.execute(f"""{_REVIEW_SELECT} WHERE q.assignee_id = %s
                                 ORDER BY q.status = 'pending' DESC, coalesce(q.decided_at, q.requested_at) DESC LIMIT 200""",
                             (actor["id"],)).fetchall()
        return [_review_view(q) for q in rows]

    def approve_review(self, actor: dict, review_id: str, cid: str | None = None) -> dict:
        """Only the current responsible, once. The row lock serializes this with a reassignment and with a
        repeated click: there is one decision, and the same execution resumes once, at the next step."""
        review_id = _uuid(review_id)
        with self.db.tx() as c:
            q = c.execute("SELECT * FROM review_requests WHERE id = %s FOR UPDATE", (review_id,)).fetchone()
            if not q:
                raise err(404, "NOT-FOUND", cid, what_missing="review request")
            if q["status"] != "pending":
                raise err(409, "REVIEW-ALREADY-DECIDED", cid)
            if q["assignee_id"] != actor["id"]:
                raise err(403, "REVIEW-NOT-ASSIGNEE", cid)
            e = c.execute("SELECT * FROM executions WHERE id = %s FOR UPDATE", (q["execution_id"],)).fetchone()
            c.execute("""UPDATE review_requests SET status = 'approved', decided_by = %s, decided_at = now() WHERE id = %s""",
                      (actor["id"], review_id))
            c.execute("UPDATE notifications SET seen_at = coalesce(seen_at, now()) WHERE review_id = %s", (review_id,))
            self._resume(c, e, q["position"])
            row = c.execute(f"{_REVIEW_SELECT} WHERE q.id = %s", (review_id,)).fetchone()
        return _review_view(row)

    def _resume(self, c, e: dict, position: int) -> None:
        snapshot = e["snapshot"]
        item = snapshot[position - 1]
        if item["continue_next"] and position < len(snapshot):
            next_item = snapshot[position]
            if not _is_review(next_item) and c.execute("SELECT 1 FROM stations WHERE id = %s AND revoked_at IS NOT NULL", (e["station_id"],)).fetchone():
                # The station left the team during the pause: nothing would ever claim the next step.
                c.execute("UPDATE executions SET state = 'finished', outcome = 'refused', end_reason = 'not_verified', finished_at = now() WHERE id = %s", (e["id"],))
                return
            c.execute("UPDATE executions SET state = 'running' WHERE id = %s", (e["id"],))
            self._queue_step(c, e, next_item)
            return
        end = "continuation_off" if position < len(snapshot) else "sequence_end"
        c.execute("UPDATE executions SET state = 'finished', outcome = 'verified', end_reason = %s, finished_at = now() WHERE id = %s", (end, e["id"]))

    # ------------------------------------------------------------ replacing step 1, with approval
    @staticmethod
    def _eligible(c, process_id: int, requested_by: int) -> list[int]:
        """Who can approve now: active members linked to the process (who created it, responsibles of its
        review steps) and active administrators. Not the requester, unless nobody else is eligible: a team of
        one is not locked out, and the authorship stays recorded. Detailed roles come in a later step."""
        rows = c.execute("""SELECT u.id FROM users u WHERE u.active AND (u.role = 'admin'
                              OR u.id = (SELECT created_by FROM processes WHERE id = %(p)s)
                              OR u.id IN (SELECT (v.config ->> 'assignee_id')::bigint FROM process_items i
                                          JOIN LATERAL (SELECT config FROM routine_versions WHERE routine_id = i.routine_id ORDER BY version DESC LIMIT 1) v ON true
                                          WHERE i.process_id = %(p)s AND v.config ? 'assignee_id'))
                            ORDER BY u.id""", {"p": process_id}).fetchall()
        ids = [r["id"] for r in rows]
        others = [i for i in ids if i != requested_by]
        return others or ids

    @staticmethod
    def _running_execution(c, process_id: int) -> bool:
        return bool(c.execute("SELECT 1 FROM executions WHERE process_id = %s AND state <> 'finished' LIMIT 1", (process_id,)).fetchone())

    def _standalone_routine(self, c, routine_id) -> None:
        v = c.execute("""SELECT v.kind FROM routines r JOIN LATERAL (SELECT kind FROM routine_versions WHERE routine_id = r.id
                         ORDER BY version DESC LIMIT 1) v ON true WHERE r.id = %s AND NOT r.archived FOR SHARE OF r""",
                      (routine_id,)).fetchone() if isinstance(routine_id, int) else None
        if not v:
            raise err(404, "NOT-FOUND", what_missing="routine")
        if v["kind"] not in PREPARED_KINDS:
            raise err(400, "VALIDATION", reason="this kind of routine cannot start a process")
        linked = c.execute("""SELECT p.name FROM process_items i JOIN processes p ON p.id = i.process_id
                              WHERE i.routine_id = %s AND NOT p.archived ORDER BY p.id LIMIT 1""", (routine_id,)).fetchone()
        if linked:
            raise err(409, "CONFLICT", reason=f"routine already linked to {linked['name']}")

    def request_step_change(self, actor: dict, process_id: int, routine_id) -> dict:
        """Asks to replace step 1 with a standalone routine. Nothing changes until someone eligible approves."""
        self.require_admin(actor)
        with self.db.tx() as c:
            p = self._changeable_process(c, process_id)
            first = c.execute("SELECT routine_id FROM process_items WHERE process_id = %s AND position = 1", (p["id"],)).fetchone()
            if not first:
                raise err(400, "VALIDATION", reason="the process has no step 1 yet: integrate the routine instead")
            self._standalone_routine(c, routine_id)
            if self._running_execution(c, p["id"]):
                raise err(409, "PROCESS-RUNNING", process=p["name"])
            if c.execute("SELECT 1 FROM step_change_requests WHERE process_id = %s AND status = 'pending'", (p["id"],)).fetchone():
                raise err(409, "CHANGE-PENDING-EXISTS", process=p["name"])
            q = c.execute("""INSERT INTO step_change_requests (process_id, old_routine_id, new_routine_id, requested_by)
                             VALUES (%s, %s, %s, %s) RETURNING id""", (p["id"], first["routine_id"], routine_id, actor["id"])).fetchone()
            for uid in self._eligible(c, p["id"], actor["id"]):
                c.execute("INSERT INTO notifications (user_id, kind, change_id) VALUES (%s, 'step_change', %s)", (uid, q["id"]))
            return self._change_view(c, actor, q["id"])

    def approve_step_change(self, actor: dict, change_id: str) -> dict:
        """Eligibility and the rules are checked now, under the process lock; approving applies it, once."""
        change_id = _uuid(change_id)
        with self.db.tx() as c:
            ref = c.execute("SELECT process_id FROM step_change_requests WHERE id = %s", (change_id,)).fetchone()
            if not ref:
                raise err(404, "NOT-FOUND", what_missing="change request")
            p = c.execute("SELECT id, name FROM processes WHERE id = %s AND NOT archived FOR UPDATE", (ref["process_id"],)).fetchone()
            q = c.execute("SELECT * FROM step_change_requests WHERE id = %s FOR UPDATE", (change_id,)).fetchone()
            if not p or q["status"] != "pending":
                raise err(409, "CHANGE-ALREADY-DECIDED")
            if actor["id"] not in self._eligible(c, p["id"], q["requested_by"]):
                raise err(403, "CHANGE-NOT-ELIGIBLE")
            if self._running_execution(c, p["id"]):
                raise err(409, "PROCESS-RUNNING", process=p["name"])
            self._standalone_routine(c, q["new_routine_id"])
            if not c.execute("UPDATE process_items SET routine_id = %s WHERE process_id = %s AND position = 1 AND routine_id = %s RETURNING 1",
                             (q["new_routine_id"], p["id"], q["old_routine_id"])).fetchone():
                raise err(409, "CONFLICT", reason="step 1 changed after the request")
            c.execute("UPDATE processes SET updated_at = now() WHERE id = %s", (p["id"],))
            c.execute("UPDATE step_change_requests SET status = 'approved', decided_by = %s, decided_at = now() WHERE id = %s", (actor["id"], change_id))
            c.execute("UPDATE notifications SET seen_at = coalesce(seen_at, now()) WHERE change_id = %s", (change_id,))
            return self._change_view(c, actor, change_id)

    def cancel_step_change(self, actor: dict, change_id: str) -> dict:
        change_id = _uuid(change_id)
        with self.db.tx() as c:
            q = c.execute("SELECT * FROM step_change_requests WHERE id = %s FOR UPDATE", (change_id,)).fetchone()
            if not q:
                raise err(404, "NOT-FOUND", what_missing="change request")
            if q["status"] != "pending":
                raise err(409, "CHANGE-ALREADY-DECIDED")
            if q["requested_by"] != actor["id"] and actor["role"] != "admin":
                raise err(403, "AUTH-FORBIDDEN", required_role="administrator or requester")
            c.execute("UPDATE step_change_requests SET status = 'cancelled', decided_by = %s, decided_at = now() WHERE id = %s", (actor["id"], change_id))
            c.execute("DELETE FROM notifications WHERE change_id = %s", (change_id,))
            return self._change_view(c, actor, change_id)

    def _change_view(self, c, actor: dict, change_id) -> dict:
        row = c.execute(f"{_CHANGE_SELECT} WHERE q.id = %s", (change_id,)).fetchone()
        return {**_jsonable(row), "can_approve": row["status"] == "pending" and actor["id"] in self._eligible(c, row["process_id"], row["requested_by"])}

    def list_step_changes(self, actor: dict) -> list[dict]:
        """Marcado para mim: pending ones this person can approve now, and what they asked for or approved."""
        with self.db.tx() as c:
            rows = c.execute(f"""{_CHANGE_SELECT} WHERE q.status = 'pending' OR q.requested_by = %(me)s OR q.decided_by = %(me)s
                                 ORDER BY q.status = 'pending' DESC, coalesce(q.decided_at, q.requested_at) DESC LIMIT 100""", {"me": actor["id"]}).fetchall()
            out = []
            for row in rows:
                can = row["status"] == "pending" and actor["id"] in self._eligible(c, row["process_id"], row["requested_by"])
                if can or row["status"] != "pending" or row["requested_by"] == actor["id"]:
                    out.append({**_jsonable(row), "can_approve": can})
        return out

    def list_notifications(self, actor: dict) -> dict:
        with self.db.tx() as c:
            rows = c.execute("""SELECT n.id, n.kind, n.review_id, n.change_id, n.schedule_run_id, n.created_at, n.seen_at,
                                       coalesce(r.name, nr.name, '') AS step_name, q.position,
                                       coalesce(p.name, cp.name, r.name, schp.name) AS process_name,
                                       sr.state AS schedule_state, sr.reason AS schedule_reason, sr.slot_local AS schedule_slot
                                FROM notifications n LEFT JOIN review_requests q ON q.id = n.review_id
                                LEFT JOIN schedule_runs sr ON sr.id = n.schedule_run_id LEFT JOIN schedules sch ON sch.id = sr.schedule_id
                                LEFT JOIN processes schp ON schp.id = sch.process_id
                                LEFT JOIN routines r ON r.id = q.routine_id LEFT JOIN executions e ON e.id = q.execution_id
                                LEFT JOIN processes p ON p.id = e.process_id
                                LEFT JOIN step_change_requests sc ON sc.id = n.change_id LEFT JOIN routines nr ON nr.id = sc.new_routine_id
                                LEFT JOIN processes cp ON cp.id = sc.process_id
                                WHERE n.user_id = %s ORDER BY n.created_at DESC LIMIT 50""", (actor["id"],)).fetchall()
            unseen = c.execute("SELECT count(*) AS n FROM notifications WHERE user_id = %s AND seen_at IS NULL", (actor["id"],)).fetchone()["n"]
        return {"unseen": int(unseen), "items": [_jsonable(r) for r in rows]}

    def notification_seen(self, actor: dict, notification_id: int) -> dict:
        """Seen is only seen: it decides nothing about the request."""
        with self.db.tx() as c:
            r = c.execute("""UPDATE notifications SET seen_at = coalesce(seen_at, now()) WHERE id = %s AND user_id = %s
                             RETURNING id""", (notification_id, actor["id"])).fetchone()
        if not r:
            raise err(404, "NOT-FOUND", what_missing="notification")
        return {"ok": True}

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
        j = c.execute("SELECT execution_id, position, cancel_requested FROM jobs WHERE id = %s", (job_id,)).fetchone()
        if j and j["execution_id"]:
            self._advance(c, j["execution_id"], j["position"], state, verified, result, cancel_requested=j["cancel_requested"])

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


_CHANGE_SELECT = """SELECT q.id, q.process_id, q.status, q.requested_at, q.decided_at, q.requested_by, p.name AS process_name,
                           o.name AS old_routine_name, n.name AS new_routine_name, u.display AS requested_by_name, d.display AS decided_by_name
                    FROM step_change_requests q JOIN processes p ON p.id = q.process_id JOIN routines o ON o.id = q.old_routine_id
                    JOIN routines n ON n.id = q.new_routine_id JOIN users u ON u.id = q.requested_by LEFT JOIN users d ON d.id = q.decided_by"""
_REVIEW_SELECT = """SELECT q.*, r.name AS step_name, p.name AS process_name, e.context, e.state AS execution_state,
                           a.display AS assignee_name, d.display AS decided_by_name, u.display AS requested_by_name
                    FROM review_requests q JOIN routines r ON r.id = q.routine_id JOIN executions e ON e.id = q.execution_id
                    LEFT JOIN processes p ON p.id = e.process_id JOIN users a ON a.id = q.assignee_id
                    LEFT JOIN users d ON d.id = q.decided_by JOIN users u ON u.id = e.requested_by"""


def _review_view(q: dict) -> dict:
    return _jsonable({k: q.get(k) for k in ("id", "execution_id", "position", "status", "assignee_id", "assignee_name", "requested_at",
                                            "decided_at", "decided_by_name", "step_name", "process_name", "requested_by_name",
                                            "execution_state", "context")})


_JOB_SELECT = """SELECT j.id, j.request_id, j.mode, j.state, j.verified, j.inputs, j.waiting_reason, j.cancel_requested, j.attempt,
                        j.diagnostic, j.result, j.correlation_id, j.created_at, j.started_at, j.finished_at,
                        r.id AS routine_id, r.name AS routine_name, r.category, v.id AS version_id, v.version,
                        v.template_id, v.template_version, v.procedure_sha256,
                        s.id AS station_id, s.name AS station_name, u.username AS requested_by
                 FROM jobs j JOIN routine_versions v ON v.id = j.routine_version_id JOIN routines r ON r.id = v.routine_id
                 JOIN stations s ON s.id = j.station_id JOIN users u ON u.id = j.requested_by"""


def _version_tuple(v) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


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
