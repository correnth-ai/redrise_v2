"""HTTPS JSON API `/api/v1` (P05-D1, D5, D11). Errors are always a
redrise.diagnostic/1 body; `X-Correlation-Id` is accepted and echoed."""

from __future__ import annotations

import json
import re
import ssl
import threading
import traceback
from urllib.parse import parse_qs, urlsplit
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psycopg

from redrise_contracts import diagnostics as dg

from . import __version__, db
from .service import ApiError, Core, err

MAX_BODY = 4 * 1024 * 1024
_CID = re.compile(r"^[A-Za-z0-9-]{4,64}$")

# Concurrency (S3, 2026-11-07). A connection holds one thread; a request holds one admission slot
# while it is handled. Runner calls and cancelling a job may also use reserved slots, so a burst of
# screen reads cannot delay heartbeats or a cancel. The change feed waits without a slot (it only
# reads the session, then waits on memory). The database has its own cap (db.Database.max_open).
MAX_CONNECTIONS = 64            # open connections being served
MAX_CONNECTIONS_PER_CLIENT = 16  # per client address, so one computer cannot take all of them
IO_TIMEOUT_S = 30.0             # handshake, idle keep-alive and each read/write
REQUEST_SLOTS, RESERVED_SLOTS = 16, 4
ADMISSION_WAIT_S = 5.0
RETRY_AFTER_S = 2
PRIORITY = {"rn_heartbeat", "rn_claim", "rn_start", "rn_progress", "rn_result", "job_cancel"}
NO_SLOT = {"changes"}

# (method, pattern, handler name, auth: None | "user" | "admin" | "runner")
ROUTES = [
    ("GET", r"/api/v1/status", "status", None),
    ("POST", r"/api/v1/setup", "setup", None),
    ("POST", r"/api/v1/login", "login", None),
    ("POST", r"/api/v1/register", "register", None),
    ("POST", r"/api/v1/logout", "logout", "user"),
    ("POST", r"/api/v1/identity/session", "identity_session", None),
    ("POST", r"/api/v1/identity/link", "identity_link", None),
    ("GET", r"/api/v1/identity/profile", "identity_profile", "user"),
    ("GET", r"/api/v1/identity/devices", "identity_devices", "user"),
    ("DELETE", r"/api/v1/identity/devices/([0-9a-f]{32})", "identity_forget", "user"),
    ("GET", r"/api/v1/me", "me", "user"),
    ("GET", r"/api/v1/users", "users", "user"),
    ("POST", r"/api/v1/users", "user_create", "user"),
    ("PATCH", r"/api/v1/users/(\d+)", "user_update", "user"),
    ("DELETE", r"/api/v1/users/(\d+)", "user_delete", "user"),
    ("POST", r"/api/v1/accounts", "account_create", "user"),
    ("GET", r"/api/v1/stations", "stations", "user"),
    ("POST", r"/api/v1/stations", "station_create", "user"),
    ("GET", r"/api/v1/stations/(\d+)/apps", "station_apps", "user"),
    ("DELETE", r"/api/v1/stations/(\d+)", "station_revoke", "user"),
    ("POST", r"/api/v1/stations/(\d+)/remove", "station_remove", "user"),
    ("GET", r"/api/v1/templates", "templates", "user"),
    ("GET", r"/api/v1/routines", "routines", "user"),
    ("POST", r"/api/v1/routines", "routine_create", "user"),
    ("GET", r"/api/v1/routines/(\d+)/versions", "routine_versions", "user"),
    ("POST", r"/api/v1/routines/(\d+)/versions", "routine_add_version", "user"),
    ("DELETE", r"/api/v1/routines/(\d+)", "routine_archive", "user"),
    ("POST", r"/api/v1/routines/(\d+)/prepare", "routine_prepare", "user"),
    ("POST", r"/api/v1/routines/(\d+)/test", "routine_test", "user"),
    ("GET", r"/api/v1/jobs", "jobs", "user"),
    ("POST", r"/api/v1/jobs", "job_create", "user"),
    ("GET", r"/api/v1/jobs/([0-9a-f-]{36})", "job_get", "user"),
    ("POST", r"/api/v1/jobs/([0-9a-f-]{36})/cancel", "job_cancel", "user"),
    ("GET", r"/api/v1/processes", "processes", "user"),
    ("POST", r"/api/v1/processes", "process_create", "user"),
    ("GET", r"/api/v1/processes/(\d+)", "process_get", "user"),
    ("PUT", r"/api/v1/processes/(\d+)", "process_update", "user"),
    ("POST", r"/api/v1/processes/(\d+)/items", "process_integrate", "user"),
    ("POST", r"/api/v1/processes/(\d+)/step1", "process_step_change", "user"),
    ("GET", r"/api/v1/step-changes", "step_changes", "user"),
    ("POST", r"/api/v1/step-changes/([0-9a-f-]{36})/approve", "step_change_approve", "user"),
    ("POST", r"/api/v1/step-changes/([0-9a-f-]{36})/cancel", "step_change_cancel", "user"),
    ("GET", r"/api/v1/executions", "executions", "user"),
    ("GET", r"/api/v1/executions/summary", "execution_summary", "user"),
    ("POST", r"/api/v1/executions", "execution_create", "user"),
    ("GET", r"/api/v1/executions/([0-9a-f-]{36})", "execution_get", "user"),
    ("GET", r"/api/v1/reviews", "reviews", "user"),
    ("POST", r"/api/v1/reviews/([0-9a-f-]{36})/approve", "review_approve", "user"),
    ("GET", r"/api/v1/notifications", "notifications", "user"),
    ("POST", r"/api/v1/notifications/(\d+)/seen", "notification_seen", "user"),
    ("POST", r"/api/v1/changes", "changes", "user"),
    ("GET", r"/api/v1/storage", "storage", "user"),
    ("GET", r"/api/v1/schedules", "schedules", "user"),
    ("POST", r"/api/v1/schedules", "schedule_create", "user"),
    ("POST", r"/api/v1/schedules/preview", "schedule_preview", "user"),
    ("PATCH", r"/api/v1/schedules/(\d+)", "schedule_update", "user"),
    ("DELETE", r"/api/v1/schedules/(\d+)", "schedule_delete", "user"),
    ("GET", r"/api/v1/schedules/(\d+)/runs", "schedule_runs", "user"),
    ("POST", r"/api/v1/runner/heartbeat", "rn_heartbeat", "runner"),
    ("POST", r"/api/v1/runner/claim", "rn_claim", "runner"),
    ("POST", r"/api/v1/runner/jobs/([0-9a-f-]{36})/start", "rn_start", "runner"),
    ("POST", r"/api/v1/runner/jobs/([0-9a-f-]{36})/result", "rn_result", "runner"),
    ("POST", r"/api/v1/runner/jobs/([0-9a-f-]{36})/progress", "rn_progress", "runner"),
]
_QUERY = {"executions", "execution_summary"}  # handlers that read the query string
_COMPILED = [(m, re.compile(p + r"$"), h, a) for m, p, h, a in ROUTES]


class Handlers:
    def __init__(self, core: Core):
        self.core = core

    def status(self, b, who, cid):
        return self.core.status()

    def setup(self, b, who, cid):
        return self.core.bootstrap(b.get("team"), b.get("username"), b.get("display"), b.get("password"))

    def register(self, b, who, cid, client=None):
        return self.core.register(b.get("full_name"), b.get("email"), b.get("password"), client=client)

    def login(self, b, who, cid, client=None):
        return self.core.login(b.get("username"), b.get("password"), client=client, station_token=b.get("station_token"))

    def identity_session(self, b, who, cid):
        return self.core.identity_session(b.get("access_token"), b.get("remember"), b.get("device"), b.get("device_id"))

    def identity_link(self, b, who, cid):
        return self.core.identity_link(b.get("access_token"), b.get("username"), b.get("password"), b.get("remember"), b.get("device"))

    def identity_profile(self, b, who, cid):
        return self.core.identity_profile(who)

    def identity_devices(self, b, who, cid, token=None):
        return self.core.list_devices(who, token)

    def identity_forget(self, b, who, cid, device_id):
        return self.core.forget_device(who, device_id)

    def logout(self, b, who, cid, token=None):
        self.core.logout(token)
        return {"ok": True}

    def me(self, b, who, cid):
        return {k: who[k] for k in ("id", "username", "display", "role")}

    def users(self, b, who, cid):
        return self.core.list_users(who)

    def user_create(self, b, who, cid):
        return self.core.create_user(who, b.get("username"), b.get("display"), b.get("password"), b.get("role"))

    def user_update(self, b, who, cid, uid):
        return self.core.update_user(who, int(uid), b.get("role"), b.get("active"), b.get("password"))

    def user_delete(self, b, who, cid, uid):
        return self.core.delete_user(who, int(uid))

    def account_create(self, b, who, cid):
        return self.core.create_account(who, b.get("full_name"), b.get("email"), b.get("password"))

    def stations(self, b, who, cid):
        return self.core.list_stations(who)

    def station_create(self, b, who, cid):
        return self.core.register_station(who, b.get("name"), bool(b.get("is_host")))

    def station_apps(self, b, who, cid, sid):
        return self.core.station_apps(who, int(sid))

    def station_revoke(self, b, who, cid, sid):
        self.core.revoke_station(who, int(sid))
        return {"ok": True}

    def station_remove(self, b, who, cid, sid):
        return self.core.remove_station(who, int(sid))

    def templates(self, b, who, cid):
        return [{k: t.get(k) for k in ("id", "version", "title", "purpose", "category", "inputs", "preconditions")}
                for t in self.core.templates.values() if t.get("shipped", True)]

    def routines(self, b, who, cid):
        return self.core.list_routines(who)

    def routine_create(self, b, who, cid):
        return self.core.create_routine(who, b.get("name"), b.get("category"), b.get("version") or {}, b.get("link"))

    def routine_versions(self, b, who, cid, rid):
        return self.core.routine_versions(who, int(rid))

    def routine_add_version(self, b, who, cid, rid):
        return self.core.add_version(who, int(rid), b)

    def routine_archive(self, b, who, cid, rid):
        return {"ok": True, **self.core.archive_routine(who, int(rid))}

    def routine_prepare(self, b, who, cid, rid):
        return self.core.prepare_routine(who, int(rid), b.get("request_id"), b.get("station_id"), cid)

    def routine_test(self, b, who, cid, rid):
        return self.core.test_routine(who, int(rid), b.get("request_id"), b.get("prepare_job_id"), cid)

    def jobs(self, b, who, cid):
        return self.core.list_jobs(who)

    def job_create(self, b, who, cid):
        return self.core.create_job(who, b.get("request_id"), b.get("version_id"), b.get("station_id"),
                                    b.get("inputs") or {}, cid)

    def job_get(self, b, who, cid, jid):
        return self.core.get_job(who, jid)

    def job_cancel(self, b, who, cid, jid):
        return self.core.cancel_job(who, jid)

    def processes(self, b, who, cid):
        return self.core.list_processes(who)

    def process_create(self, b, who, cid):
        return self.core.create_process(who, b.get("name"), b.get("items"))

    def process_get(self, b, who, cid, pid):
        return self.core.get_process(who, int(pid))

    def process_update(self, b, who, cid, pid):
        return self.core.update_process(who, int(pid), b.get("name"), b.get("items"))

    def process_integrate(self, b, who, cid, pid):
        return self.core.integrate_routine(who, int(pid), b.get("routine_id"))

    def process_step_change(self, b, who, cid, pid):
        return self.core.request_step_change(who, int(pid), b.get("routine_id"))

    def step_changes(self, b, who, cid):
        return self.core.list_step_changes(who)

    def step_change_approve(self, b, who, cid, cid_):
        return self.core.approve_step_change(who, cid_)

    def step_change_cancel(self, b, who, cid, cid_):
        return self.core.cancel_step_change(who, cid_)

    def executions(self, b, who, cid, query=None):
        return self.core.list_executions(who, days=(query or {}).get("days"))

    def execution_summary(self, b, who, cid, query=None):
        return self.core.execution_summary(who, (query or {}).get("days"))

    def execution_create(self, b, who, cid):
        return self.core.create_execution(who, b.get("request_id"), b.get("station_id"), b.get("process_id"),
                                          b.get("routine_id"), cid)

    def execution_get(self, b, who, cid, eid):
        return self.core.get_execution(who, eid)

    def reviews(self, b, who, cid):
        return self.core.list_reviews(who)

    def review_approve(self, b, who, cid, rid):
        return self.core.approve_review(who, rid, cid)

    def notifications(self, b, who, cid):
        return self.core.list_notifications(who)

    def notification_seen(self, b, who, cid, nid):
        return self.core.notification_seen(who, int(nid))

    def changes(self, b, who, cid):
        return self.core.changes.since(b.get("seq"), b.get("epoch"), b.get("wait_s", 0.0))

    def storage(self, b, who, cid):
        return self.core.storage(who)

    def schedules(self, b, who, cid):
        return self.core.list_schedules(who)

    def schedule_create(self, b, who, cid):
        return self.core.create_schedule(who, b)

    def schedule_preview(self, b, who, cid):
        return self.core.preview_schedule(who, b)

    def schedule_update(self, b, who, cid, sid):
        return self.core.update_schedule(who, int(sid), b)

    def schedule_delete(self, b, who, cid, sid):
        return self.core.delete_schedule(who, int(sid))

    def schedule_runs(self, b, who, cid, sid):
        return self.core.schedule_runs(who, int(sid))

    def rn_heartbeat(self, b, who, cid):
        return self.core.heartbeat(who, b)

    def rn_claim(self, b, who, cid):
        return {"job": self.core.claim(who, b)}

    def rn_start(self, b, who, cid, jid):
        return self.core.start_job(who, jid, str(b.get("lease_id")))

    def rn_progress(self, b, who, cid, jid):
        return self.core.job_progress(who, jid, str(b.get("lease_id")), b.get("check"))

    def rn_result(self, b, who, cid, jid):
        return self.core.report_result(who, jid, str(b.get("lease_id")), b.get("result"))


class Admission:
    """Request slots: `slots` for everyone, `reserved` more only for priority routes. A request
    waits at most `wait_s` for a slot, then is refused with CORE-BUSY before anything is done."""

    def __init__(self, slots=REQUEST_SLOTS, reserved=RESERVED_SLOTS, wait_s=ADMISSION_WAIT_S):
        self.wait_s = wait_s
        self._all, self._reserved = threading.BoundedSemaphore(slots), threading.BoundedSemaphore(reserved)

    def acquire(self, priority: bool):
        """The semaphore to release afterwards, or None when no slot came in time."""
        if priority:
            if self._all.acquire(blocking=False):
                return self._all
            return self._reserved if self._reserved.acquire(timeout=self.wait_s) else None
        return self._all if self._all.acquire(timeout=self.wait_s) else None


def make_handler(handlers: Handlers, log=None, admission: Admission | None = None):
    admission = admission or Admission()

    class H(BaseHTTPRequestHandler):
        server_version = f"redrise-core/{__version__}"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # no request lines with tokens/paths in stderr
            if log:
                log(f"{self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")

        def _send(self, status: int, obj, cid: str, retry_after=None):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Correlation-Id", cid)
            self.send_header("Cache-Control", "no-store")
            if retry_after:
                self.send_header("Retry-After", str(retry_after))
            self.end_headers()
            self.wfile.write(body)

        def _dispatch(self):
            cid = self.headers.get("X-Correlation-Id") or ""
            cid = cid if _CID.match(cid) else dg.new_correlation_id()
            path = self.path.split("?")[0]
            slot = None
            try:
                # Body first: any refusal below leaves the keep-alive connection in sync.
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                if n < 0 or n > MAX_BODY:
                    self.close_connection = True  # unread body: do not reuse this connection
                    raise err(413, "VALIDATION", cid, reason="request body too large or invalid")
                raw = self.rfile.read(n) if n else b""
                route = next(((h, a, m.groups()) for meth, rx, h, a in _COMPILED
                              if meth == self.command and (m := rx.match(path))), None)
                if route is None:
                    raise err(404, "NOT-FOUND", cid, what_missing="rota")
                name, need, args = route
                if name not in NO_SLOT:
                    slot = admission.acquire(name in PRIORITY)
                    if slot is None:
                        raise err(503, "CORE-BUSY", cid, retry_after_s=RETRY_AFTER_S)
                if name == "setup" and self.client_address[0] not in ("127.0.0.1", "::1"):
                    # First admin only from the host computer itself (the LAN can reach the port).
                    raise err(403, "AUTH-FORBIDDEN", cid, required_role="acesso local no computador servidor")
                try:
                    body = json.loads(raw.decode("utf-8")) if raw else {}
                except (ValueError, UnicodeDecodeError):
                    raise ApiError(400, dg.contract_violation("RR-UI", "RR-CORE", "api/v1 JSON", "invalid JSON",
                                                              reported_by="RR-CORE", correlation_id=cid)) from None
                if not isinstance(body, dict):
                    raise ApiError(400, dg.contract_violation("RR-UI", "RR-CORE", "api/v1 JSON", "objeto esperado",
                                                              reported_by="RR-CORE", correlation_id=cid))
                token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip() or None
                who = None
                if need == "user":
                    who = handlers.core.user_for(token)
                elif need == "runner":
                    who = handlers.core.station_for(token)
                fn = getattr(handlers, name)
                extra = {"token": token} if name in ("logout", "identity_devices") else {}
                if name in ("login", "register"):
                    extra["client"] = self.client_address[0]
                if name in _QUERY:  # last value of each parameter of the query string
                    extra["query"] = {k: v[-1] for k, v in parse_qs(urlsplit(self.path).query).items()}
                out = fn(body, who, cid, *args, **extra)
                self._send(200, out, cid)
            except ApiError as e:
                d = e.diagnostic
                d.correlation_id = cid  # the caller's correlation id always comes back (P05-D11)
                self._send(e.status, {"diagnostic": d.to_dict(), "message": d.render()}, cid,
                           retry_after=d.params.get("retry_after_s") if e.status in (429, 503) else None)
            except (psycopg.OperationalError, db.PoolBusy) as e:
                d = dg.make("CORE-STORAGE-UNAVAILABLE", reported_by="RR-CORE", correlation_id=cid,
                            params={"reason": type(e).__name__}, version={"core": __version__})
                self._send(503, {"diagnostic": d.to_dict(), "message": d.render()}, cid)
            except Exception as e:  # noqa: BLE001 - last resort: diagnostic, never a stack trace to the client
                if log:
                    log("internal error: " + "".join(traceback.format_exception_only(type(e), e)).strip())
                d = dg.make("CORE-INTERNAL", reported_by="RR-CORE", correlation_id=cid,
                            params={"reason": type(e).__name__}, version={"core": __version__})
                self._send(500, {"diagnostic": d.to_dict(), "message": d.render()}, cid)
            finally:
                if slot is not None:
                    slot.release()

        do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = _dispatch

    return H


class _TlsServer(ThreadingHTTPServer):
    """TLS handshake inside each connection's thread, with a timeout: a client
    that never completes the handshake cannot block accept() for everyone.

    Connections over MAX_CONNECTIONS, or over MAX_CONNECTIONS_PER_CLIENT from one
    address, are closed at once without a thread. The TLS socket is the one that
    owns the connection after the handshake, so it is the one shut down and closed
    when the connection ends, whether the exchange finished or was interrupted."""

    daemon_threads = True
    tls: ssl.SSLContext | None = None
    io_timeout_s = IO_TIMEOUT_S
    max_connections, max_per_client = MAX_CONNECTIONS, MAX_CONNECTIONS_PER_CLIENT

    def __init__(self, *a, **kw):
        self._count_lock = threading.Lock()
        self.active: dict[str, int] = {}  # client address -> connections being served
        self.refused = 0
        super().__init__(*a, **kw)

    def connections(self) -> int:
        with self._count_lock:
            return sum(self.active.values())

    def process_request(self, request, client_address):
        addr = client_address[0]
        with self._count_lock:
            full = sum(self.active.values()) >= self.max_connections or self.active.get(addr, 0) >= self.max_per_client
            if full:
                self.refused += 1
            else:
                self.active[addr] = self.active.get(addr, 0) + 1
        if full:
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:  # the thread did not start: give the place back
            self._release(addr)
            self.shutdown_request(request)
            raise

    def _release(self, addr: str) -> None:
        with self._count_lock:
            n = self.active.get(addr, 0) - 1
            if n > 0:
                self.active[addr] = n
            else:
                self.active.pop(addr, None)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release(client_address[0])

    def finish_request(self, request, client_address):
        request.settimeout(self.io_timeout_s)
        if self.tls is None:
            return super().finish_request(request, client_address)
        try:
            conn = self.tls.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return  # the TLS socket closed itself; the plain socket is closed by the caller
        try:
            super().finish_request(conn, client_address)
        finally:
            self.shutdown_request(conn)


class ApiServer:
    def __init__(self, core: Core, host: str, port: int, cert: Path | None, key: Path | None, log=None,
                 admission: Admission | None = None):
        self.handlers, self.admission = Handlers(core), admission or Admission()
        self.httpd = _TlsServer((host, port), make_handler(self.handlers, log, self.admission))
        if cert:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(str(cert), str(key))
            self.httpd.tls = ctx
        self.port = self.httpd.server_address[1]
        self._t: threading.Thread | None = None

    def start(self):
        self._t = threading.Thread(target=self.httpd.serve_forever, name="core-api", daemon=True)
        self._t.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
