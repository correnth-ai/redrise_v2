"""Core against a real, isolated PostgreSQL cluster (temporary, on C:), through
the HTTPS API with certificate pinning. No UI, no Runner: runner calls are
made directly by the test (declared as a simulated Runner).

    cd tests/core && <lab python> -B -m unittest test_core
Env: RR_PG_BIN (PostgreSQL bin dir), RR_CORE_SITE (psycopg/cryptography site-packages)."""

import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = Path(os.environ.get("RR_LAB", r"C:\Users\raulv\RedRise-v2-dev"))
PG_BIN = Path(os.environ.get("RR_PG_BIN", LAB / "downloads/p06-core/pgsql/bin"))
SITE = Path(os.environ.get("RR_CORE_SITE", LAB / "downloads/p06-core/site-packages"))
for p in (ROOT / "core", ROOT / "contracts" / "python", ROOT / "runner", SITE):
    sys.path.insert(0, str(p))

import psycopg  # noqa: E402

from redrise_contracts import diagnostics as dg  # noqa: E402
from redrise_contracts.client import CoreClient, CoreError  # noqa: E402
from redrise_core import db, host, pg  # noqa: E402
from redrise_contracts.vault import MemoryVault  # noqa: E402

PW = "senha-forte-01"
# Tokens and accounts a test class keeps between its tests. They belong to one cluster: a class
# that starts a new cluster (or is run again) must not reuse them against another database.
CACHED = ("_admin", "_other", "_users", "_bound")


class Harness:
    """Cluster and helpers shared by the Core test modules. Not a TestCase: importing it does not
    make unittest collect and run another module's tests again (only CoreTest below is collected)."""

    @classmethod
    def setUpClass(cls):
        for name in CACHED:
            if name in vars(cls):
                delattr(cls, name)
        cls.tmp = Path(tempfile.mkdtemp(prefix="rr-core-"))
        inst = cls.tmp / "install"
        shutil.copytree(ROOT / "templates", inst / "templates")
        cls.paths = host.HostPaths(inst, cls.tmp / "data", pg_bin=PG_BIN)
        cls.vault = MemoryVault()
        cls.h = host.Host(cls.paths, cls.vault, log=lambda m: None)
        cls.info = cls.h.start(lan_port=0, bind="127.0.0.1")
        cls.port = cls.info["lan_port"]

    @classmethod
    def tearDownClass(cls):
        cls.h.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers
    def client(self, token=None, by="RR-UI"):
        return CoreClient("127.0.0.1", self.port, self.info["fingerprint"], token, reported_by=by)

    def su(self):
        cfg = json.loads(self.paths.config.read_text(encoding="utf-8"))
        return psycopg.connect(db.conninfo(cfg["pg_port"], pg.SUPERUSER, self.vault.get("pg-superuser")), autocommit=True)

    def expect(self, code, fn, status=None):
        with self.assertRaises(CoreError) as cm:
            fn()
        self.assertEqual(cm.exception.diagnostic.error_code, code)
        if status:
            self.assertEqual(cm.exception.status, status)
        self.assertEqual(dg.validate(cm.exception.diagnostic.to_dict()), [])
        self.assertTrue(cm.exception.diagnostic.render().splitlines()[-1].startswith("Code: "))
        return cm.exception

    @classmethod
    def admin(cls):
        if "_admin" not in vars(cls):  # this class's own token, created on this class's cluster
            c = CoreClient("127.0.0.1", cls.port, cls.info["fingerprint"])
            c.call("POST", "/api/v1/setup", {"team": "Equipe Teste", "username": "admin", "display": "Admin", "password": PW})
            cls._admin = c.call("POST", "/api/v1/login", {"username": "admin", "password": PW})["token"]
        return CoreClient("127.0.0.1", cls.port, cls.info["fingerprint"], cls._admin)

    @classmethod
    def bound_admin(cls):
        """An administrator session tied to a station of its own, proved at login by that station's runner token, as the
        desktop does (TEAM-ACCOUNTS-20261108): revoking or deleting stations needs it."""
        if "_bound" not in vars(cls):
            a = cls.admin()
            s = a.call("POST", "/api/v1/stations", {"name": f"sessao-{uuid.uuid4().hex[:6]}"})
            c = CoreClient("127.0.0.1", cls.port, cls.info["fingerprint"])
            cls._bound = c.call("POST", "/api/v1/login", {"username": "admin", "password": PW, "station_token": s["runner_token"]})["token"]
        return CoreClient("127.0.0.1", cls.port, cls.info["fingerprint"], cls._bound)

    def station(self, name, categories=("windows", "browser"), platform="windows-x86_64", ready=True):
        a = self.admin()
        s = a.call("POST", "/api/v1/stations", {"name": name})
        r = self.client(s["runner_token"], by="RR-RUNNER")
        hb = {"platform": platform, "categories": list(categories), "runner_version": "0.2.0",
              "session_state": "ready" if ready else "locked", "session_reason": None if ready else "tela bloqueada"}
        r.call("POST", "/api/v1/runner/heartbeat", hb)
        return s["station"]["id"], r, hb

    def routine(self, category="windows", template="boas-vindas"):
        a = self.admin()
        out = a.call("POST", "/api/v1/routines", {"name": f"r-{uuid.uuid4().hex[:6]}", "category": category,
                                                  "version": {"kind": "template", "template_id": template}})
        return out["version"]["id"]

    def job(self, version_id, station_id, **kw):
        return self.admin().call("POST", "/api/v1/jobs", {"request_id": kw.get("request_id", uuid.uuid4().hex),
                                                          "version_id": version_id, "station_id": station_id,
                                                          "inputs": kw.get("inputs", {})})



class CoreTest(Harness, unittest.TestCase):
    # ---------------------------------------------------------------- tests
    def test_01_status_setup_once_and_login(self):
        c = self.client()
        st = c.call("GET", "/api/v1/status")
        self.assertIn("initialized", st)
        self.admin()
        self.expect("SETUP-ALREADY-DONE", lambda: c.call("POST", "/api/v1/setup", {"team": "x", "username": "eve", "password": PW}), 409)
        self.expect("AUTH-INVALID", lambda: c.call("POST", "/api/v1/login", {"username": "admin", "password": "errada123"}), 401)
        self.expect("AUTH-INVALID", lambda: c.call("POST", "/api/v1/login", {"username": "ninguem", "password": PW}), 401)
        self.expect("AUTH-REQUIRED", lambda: c.call("GET", "/api/v1/me"), 401)
        self.assertEqual(self.admin().call("GET", "/api/v1/me")["role"], "admin")

    def test_02_roles_enforced_by_api(self):
        a = self.admin()
        a.call("POST", "/api/v1/users", {"username": "oper1", "display": "Operador", "password": PW, "role": "operator"})
        tok = self.client().call("POST", "/api/v1/login", {"username": "oper1", "password": PW})["token"]
        op = self.client(tok)
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", "/api/v1/users", {"username": "x2x", "password": PW, "role": "admin"}), 403)
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", "/api/v1/stations", {"name": "s"}), 403)
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", "/api/v1/routines", {"name": "r", "category": "windows"}), 403)
        op.call("GET", "/api/v1/routines")  # operator can read and run
        self.expect("VALIDATION", lambda: a.call("POST", "/api/v1/users", {"username": "oper2", "password": "curta", "role": "operator"}), 400)
        me = a.call("GET", "/api/v1/me")
        self.expect("CONFLICT", lambda: a.call("PATCH", f"/api/v1/users/{me['id']}", {"role": "operator"}), 409)  # last admin

    def test_03_incompatible_station_refused_before_queueing(self):
        sid, _, _ = self.station("so-browser", categories=("browser",))
        vid = self.routine("windows")
        e = self.expect("STATION-INCOMPATIBLE", lambda: self.job(vid, sid), 409)
        self.assertIn("category windows", e.diagnostic.details_summary)
        sid2, _, _ = self.station("mac-x", platform="macos-aarch64")
        self.expect("STATION-INCOMPATIBLE", lambda: self.job(vid, sid2), 409)

    def test_04_idempotent_creation_lease_result(self):
        sid, r, hb = self.station("estacao-a")
        vid = self.routine()
        rid = uuid.uuid4().hex
        j1 = self.job(vid, sid, request_id=rid)
        j2 = self.job(vid, sid, request_id=rid)
        self.assertEqual(j1["id"], j2["id"])
        self.assertTrue(j2["duplicate"])
        claim = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertEqual((claim["job_id"], claim["schema"], claim["template_id"]), (j1["id"], "redrise.job/1", "boas-vindas"))
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])  # no double claim
        self.assertTrue(r.call("POST", f"/api/v1/runner/jobs/{claim['job_id']}/start", {"lease_id": claim["lease_id"]})["proceed"])
        res = {"schema": "redrise.job-result/1", "state": "verified", "verified": True, "code": None}
        out = r.call("POST", f"/api/v1/runner/jobs/{claim['job_id']}/result", {"lease_id": claim["lease_id"], "result": res})
        self.assertFalse(out["duplicate"])
        again = r.call("POST", f"/api/v1/runner/jobs/{claim['job_id']}/result", {"lease_id": claim["lease_id"], "result": res})
        self.assertTrue(again["duplicate"])  # lost ack retransmission is idempotent
        self.expect("CONFLICT", lambda: r.call("POST", f"/api/v1/runner/jobs/{claim['job_id']}/result",
                                               {"lease_id": claim["lease_id"], "result": {**res, "state": "failed"}}), 409)
        got = self.admin().call("GET", f"/api/v1/jobs/{j1['id']}")
        self.assertEqual((got["state"], got["verified"]), ("verified", True))
        self.assertEqual([e["state"] for e in got["events"]], ["queued", "claimed", "running", "verified"])

    def test_05_no_claim_while_session_unavailable(self):
        sid, r, hb = self.station("bloqueada", ready=False)
        j = self.job(self.routine(), sid)
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])
        self.assertEqual(self.admin().call("GET", f"/api/v1/jobs/{j['id']}")["waiting_reason"], "tela bloqueada")

    def test_06_lease_expiry_requeues_claimed_and_uncertain_running(self):
        sid, r, hb = self.station("instavel")
        vid = self.routine()
        j1 = self.job(vid, sid)
        c1 = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        with self.su() as s:
            s.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (c1["job_id"],))
        c2 = r.call("POST", "/api/v1/runner/claim", hb)["job"]  # sweep re-queues the never-started job
        self.assertEqual(c2["job_id"], j1["id"])
        self.assertNotEqual(c2["lease_id"], c1["lease_id"])
        self.expect("CONFLICT", lambda: r.call("POST", f"/api/v1/runner/jobs/{c1['job_id']}/start", {"lease_id": c1["lease_id"]}), 409)
        r.call("POST", f"/api/v1/runner/jobs/{c2['job_id']}/start", {"lease_id": c2["lease_id"]})
        with self.su() as s:
            s.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (c2["job_id"],))
        r.call("POST", "/api/v1/runner/heartbeat", hb)
        got = self.admin().call("GET", f"/api/v1/jobs/{j1['id']}")
        self.assertEqual(got["state"], "uncertain")
        self.assertEqual(got["diagnostic"]["error_code"], "JOB-LEASE-LOST")
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])  # never re-run automatically
        late = {"schema": "redrise.job-result/1", "state": "verified", "verified": True}
        self.expect("CONFLICT", lambda: r.call("POST", f"/api/v1/runner/jobs/{c2['job_id']}/result",
                                               {"lease_id": c2["lease_id"], "result": late}), 409)

    def test_07_cancel(self):
        sid, r, hb = self.station("cancelavel")
        vid = self.routine()
        q = self.job(vid, sid)
        self.assertEqual(self.admin().call("POST", f"/api/v1/jobs/{q['id']}/cancel")["state"], "cancelled")
        j = self.job(vid, sid)
        c = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        r.call("POST", f"/api/v1/runner/jobs/{c['job_id']}/start", {"lease_id": c["lease_id"]})
        self.assertTrue(self.admin().call("POST", f"/api/v1/jobs/{j['id']}/cancel")["cancel_requested"])
        out = r.call("POST", "/api/v1/runner/heartbeat", {**hb, "job_id": c["job_id"], "lease_id": c["lease_id"]})
        self.assertEqual(out["cancel"], [j["id"]])

    def test_08_revoked_station(self):
        sid, r, hb = self.station("revogada")
        j = self.job(self.routine(), sid)
        self.bound_admin().call("DELETE", f"/api/v1/stations/{sid}")
        self.expect("AUTH-REQUIRED", lambda: r.call("POST", "/api/v1/runner/claim", hb), 401)
        self.assertEqual(self.admin().call("GET", f"/api/v1/jobs/{j['id']}")["state"], "refused")

    def test_09_contract_checks(self):
        sid, r, hb = self.station("contrato")
        self.job(self.routine(), sid)
        c = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        e = self.expect("CONTRACT-PAYLOAD", lambda: r.call("POST", f"/api/v1/runner/jobs/{c['job_id']}/result",
                                                           {"lease_id": c["lease_id"], "result": {"schema": "redrise.job-result/0", "state": "verified"}}), 400)
        self.assertEqual(e.diagnostic.boundary["producer"], "RR-RUNNER")
        bad_diag = {"schema": "redrise.job-result/1", "state": "failed", "diagnostic": {"error_code": "X"}}
        self.expect("CONTRACT-PAYLOAD", lambda: r.call("POST", f"/api/v1/runner/jobs/{c['job_id']}/result",
                                                       {"lease_id": c["lease_id"], "result": bad_diag}), 400)
        self.expect("NOT-FOUND", lambda: self.admin().call("GET", "/api/v1/nope"), 404)
        self.expect("VALIDATION", lambda: self.admin().call("POST", "/api/v1/routines",
                                                            {"name": "x", "category": "windows", "version": {"kind": "template", "template_id": "browser-formulario"}}), 400)

    def test_10_invalid_json_and_correlation(self):
        import http.client
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        conn = http.client.HTTPSConnection("127.0.0.1", self.port, context=ctx, timeout=10)
        self.addCleanup(conn.close)
        conn.request("POST", "/api/v1/login", body=b"{nope", headers={"X-Correlation-Id": "corr-1234"})
        resp = conn.getresponse()
        body = json.loads(resp.read())
        self.assertEqual((resp.status, resp.getheader("X-Correlation-Id")), (400, "corr-1234"))
        self.assertEqual(body["diagnostic"]["error_code"], "CONTRACT-PAYLOAD")
        self.assertEqual(body["diagnostic"]["correlation_id"], "corr-1234")
        self.assertTrue(body["message"].splitlines()[-1].startswith("Code: CONTRACT-PAYLOAD |"))

    def test_11_pinning_and_unreachable(self):
        bad = CoreClient("127.0.0.1", self.port, "0" * 64)
        self.expect("CORE-CERT-MISMATCH", lambda: bad.call("POST", "/api/v1/login", {"username": "admin", "password": PW}))
        off = CoreClient("127.0.0.1", pg.free_port(), self.info["fingerprint"], timeout_s=2)
        e = self.expect("CORE-UNREACHABLE", lambda: off.call("GET", "/api/v1/status"))
        self.assertEqual(e.diagnostic.effect_state, "none")

    def test_12_app_role_has_no_ddl(self):
        cfg = json.loads(self.paths.config.read_text(encoding="utf-8"))
        with psycopg.connect(db.conninfo(cfg["pg_port"], db.APP_ROLE, self.vault.get("pg-app")), autocommit=True) as c:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute("CREATE TABLE x (id int)")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute("DELETE FROM schema_migrations")

    def test_12b_setup_refused_from_lan_and_correlation_and_uuid(self):
        """Review B1: the first admin can only be created from the host itself."""
        import socket
        from redrise_core.api import ApiServer
        from redrise_core.service import Core
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent; picks the LAN interface
            lan_ip = s.getsockname()[0]
        if lan_ip.startswith("127."):
            self.skipTest("no LAN interface")
        srv = ApiServer(Core(self.h.database, {}), "0.0.0.0", 0, self.paths.host / "tls" / "host-cert.pem",
                        self.paths.host / "tls" / "host-key.pem").start()
        try:
            c = CoreClient(lan_ip, srv.port, self.info["fingerprint"])
            e = self.expect("AUTH-FORBIDDEN", lambda: c.call("POST", "/api/v1/setup", {"team": "x", "username": "intruso", "password": PW},
                                                             correlation_id="corr-lan-1"), 403)
            self.assertEqual(e.diagnostic.correlation_id, "corr-lan-1")
        finally:
            srv.stop()
        a = self.admin()
        e = self.expect("NOT-FOUND", lambda: a.call("GET", f"/api/v1/jobs/{uuid.uuid4()}", correlation_id="corr-nf-2"), 404)
        self.assertEqual(e.diagnostic.correlation_id, "corr-nf-2")  # Core errors keep the caller's id
        _, r, hb = self.station("uuid-check")
        self.expect("VALIDATION", lambda: r.call("POST", "/api/v1/runner/heartbeat", {**hb, "job_id": "x" * 36, "lease_id": "y"}), 400)

    def test_13_backup_restore_isolated_and_restart_persistence(self):
        a = self.admin()
        vid = self.routine()
        out = self.tmp / "bk" / "team.dump"
        self.h.backup(out)
        self.assertGreater(out.stat().st_size, 1000)
        target = f"restore_check_{uuid.uuid4().hex[:6]}"
        self.h.restore(out, target)
        cfg = json.loads(self.paths.config.read_text(encoding="utf-8"))
        with psycopg.connect(db.conninfo(cfg["pg_port"], pg.SUPERUSER, self.vault.get("pg-superuser"), target)) as c:
            self.assertGreaterEqual(c.execute("SELECT count(*) FROM routine_versions WHERE id = %s", (vid,)).fetchone()[0], 1)
        with self.assertRaises(pg.PgError):
            self.h.restore(out, "redrise")  # never over the live database
        # restart: stop everything, start again, data is there; no migration re-applied
        self.h.stop()
        info = self.h.start(lan_port=self.port, bind="127.0.0.1")
        self.assertEqual(info["migrations_applied"], [])
        self.assertIn(vid, [r["version_id"] for r in a.call("GET", "/api/v1/routines")])


if __name__ == "__main__":
    unittest.main()
