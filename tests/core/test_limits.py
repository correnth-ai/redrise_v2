"""S3 (2026-11-07): sign-in and sign-up attempt limits, request and connection limits with a
margin for the Runner and cancel, and the close of TLS sockets. The clock of the limiter is
controlled by the test; accounts and data are synthetic, on an isolated cluster.

    cd tests/core && <lab python> -B -m unittest test_limits"""

import gc
import http.client
import json
import socket
import ssl
import threading
import time
import unittest
import uuid
import warnings

import test_core
from test_core import PW, Harness
from redrise_core import api, auth, db


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class LimiterUnitTest(unittest.TestCase):
    """The policy alone: 5 counted attempts in 5 minutes -> 60 s, doubling up to 15 min."""

    def setUp(self):
        self.clock = Clock()
        self.lim = auth.AttemptLimiter(self.clock)
        self.keys = (("account", "user:1"), ("client", "10.0.0.5"))

    def fail(self, n, keys=None, account="user:1"):
        for _ in range(n):
            self.lim.hit(keys or self.keys, account)

    def test_wait_starts_at_the_fifth_failure_and_ends(self):
        self.fail(4)
        self.assertEqual(self.lim.wait_s(self.keys), 0)
        self.fail(1)
        self.assertEqual(self.lim.wait_s(self.keys), 60)
        self.clock.advance(59.5)
        self.assertEqual(self.lim.wait_s(self.keys), 1)
        self.clock.advance(0.5)
        self.assertEqual(self.lim.wait_s(self.keys), 0)

    def test_each_new_wait_doubles_up_to_fifteen_minutes(self):
        waits = []
        for _ in range(7):
            self.fail(5)
            waits.append(self.lim.wait_s(self.keys))
            self.clock.advance(waits[-1])
        self.assertEqual(waits, [60, 120, 240, 480, 900, 900, 900])

    def test_failures_spread_over_more_than_the_window_never_wait(self):
        for _ in range(20):
            self.fail(1)
            self.clock.advance(76)  # any 5 consecutive failures span 304 s, more than the 5-minute window
        self.assertEqual(self.lim.wait_s(self.keys), 0)

    def test_success_starts_the_account_over(self):
        self.fail(5)
        self.clock.advance(60)
        self.lim.success(*self.keys, "user:1")
        self.assertEqual(self.lim.wait_s(self.keys), 0)
        self.fail(4)
        self.assertEqual(self.lim.wait_s(self.keys), 0)
        self.fail(1)
        self.assertEqual(self.lim.wait_s(self.keys), 60, "level back to the first wait")

    def test_success_keeps_what_the_client_did_on_other_accounts(self):
        client = ("client", "10.0.0.5")
        for i in range(4):
            self.lim.hit((("account", f"name:x{i}"), client), f"name:x{i}")
        self.lim.hit((("account", "user:1"), client), "user:1")
        self.assertEqual(self.lim.wait_s((client,)), 60)
        self.clock.advance(60)
        self.lim.success(("account", "user:1"), client, "user:1")
        self.lim.hit((("account", "name:x9"), client), "name:x9")
        self.fail(4, keys=((("account", "name:y"), client)), account="name:y")
        self.assertEqual(self.lim.wait_s((client,)), 120, "the client's level was kept")

    def test_a_quiet_key_is_forgotten(self):
        for _ in range(3):
            self.fail(5)
            self.clock.advance(self.lim.wait_s(self.keys))
        self.clock.advance(auth.AttemptLimiter.MAX_WAIT_S)
        self.fail(5)
        self.assertEqual(self.lim.wait_s(self.keys), 60)

    def test_attempt_checks_and_counts_in_one_step(self):
        for _ in range(5):
            self.assertEqual(self.lim.attempt(self.keys, "user:1"), 0)  # each one counted before its password check
        self.assertEqual(self.lim.attempt(self.keys, "user:1"), 60)
        self.clock.advance(30)
        self.assertEqual(self.lim.attempt(self.keys, "user:1"), 30, "a refused attempt is not counted")
        self.clock.advance(30)
        self.assertEqual(self.lim.attempt(self.keys, "user:1"), 0)
        self.lim.success(*self.keys, "user:1")  # the right password forgets what was counted
        for _ in range(4):
            self.assertEqual(self.lim.attempt(self.keys, "user:1"), 0)
        self.lim.success(*self.keys, "user:1")
        self.assertEqual(self.lim.wait_s(self.keys), 0, "four attempts and a success leave no wait")

    def test_parallel_attempts_cannot_pass_the_check_together(self):
        results, start = [], threading.Barrier(32)

        def go():
            start.wait()
            results.append(self.lim.attempt(self.keys, "user:1"))

        threads = [threading.Thread(target=go) for _ in range(32)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(0), 5, "only the first five reach the password check")

    def test_memory_is_bounded(self):
        self.lim.MAX_KEYS = 50
        for i in range(500):
            self.lim.hit((("account", f"name:{i}"),), f"name:{i}")
        self.assertLessEqual(len(self.lim._keys), 51)


class _Pinned:
    """HTTPS with the pinned certificate, returning status, headers and body (CoreClient hides headers)."""

    def __init__(self, t):
        self.t = t
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def call(self, method, path, body=None, token=None):
        conn = http.client.HTTPSConnection("127.0.0.1", self.t.port, context=self.ctx, timeout=15)
        try:
            h = {"Content-Type": "application/json"}
            if token:
                h["Authorization"] = f"Bearer {token}"
            conn.request(method, path, body=json.dumps(body or {}).encode() if method != "GET" else None, headers=h)
            r = conn.getresponse()
            return r.status, dict(r.getheaders()), json.loads(r.read() or b"{}")
        finally:
            conn.close()


class AttemptLimitTest(Harness, unittest.TestCase):
    """Through the API, with the Core's limiter on a test clock."""

    def setUp(self):
        self.admin()  # team set up before the limiter is replaced
        self.clock = Clock()
        self.h.core.limits = auth.AttemptLimiter(self.clock)
        self.raw = _Pinned(self)

    def login(self, user, pw):
        return self.raw.call("POST", "/api/v1/login", {"username": user, "password": pw})

    def assert_limited(self, out, wait):
        status, headers, body = out
        self.assertEqual(status, 429)
        self.assertEqual(body["diagnostic"]["error_code"], "AUTH-RATE-LIMITED")
        self.assertEqual(body["diagnostic"]["effect_state"], "none")
        self.assertEqual(headers.get("Retry-After"), str(wait))
        self.assertEqual(body["diagnostic"]["params"]["retry_after_s"], str(wait))

    def test_01_refused_then_recovers_after_the_wait(self):
        self.admin().call("POST", "/api/v1/users", {"username": "lim1", "display": "L", "password": PW, "role": "operator"})
        for _ in range(5):
            self.assertEqual(self.login("lim1", "errada-000")[0], 401)
        self.assert_limited(self.login("lim1", PW), 60)  # even the right password waits: nothing is checked
        self.clock.advance(30)
        self.assert_limited(self.login("lim1", "errada-000"), 30)  # refused attempts do not lengthen it
        self.clock.advance(30)
        status, _, body = self.login("lim1", PW)
        self.assertEqual(status, 200)
        self.assertTrue(body["token"])
        for _ in range(4):
            self.assertEqual(self.login("lim1", "errada-000")[0], 401, "the success started the count over")

    def test_02_user_name_and_email_share_one_count(self):
        self.client().call("POST", "/api/v1/register", {"full_name": "Lim Dois", "email": "lim2@exemplo.test", "password": PW})
        uid = next(u["id"] for u in self.admin().call("GET", "/api/v1/users") if u["display"] == "Lim Dois")
        name = next(u["username"] for u in self.admin().call("GET", "/api/v1/users") if u["id"] == uid)
        self.admin().call("PATCH", f"/api/v1/users/{uid}", {"active": True})
        self.clock.advance(3600)  # the sign-up above counted on this address
        self.h.core.limits = auth.AttemptLimiter(self.clock)
        for who in ("lim2@exemplo.test", name, "LIM2@exemplo.test", name, "lim2@exemplo.test"):
            self.assertEqual(self.login(who, "errada-000")[0], 401)
        self.assert_limited(self.login(name, PW), 60)

    def test_03_one_address_failing_on_many_accounts_waits(self):
        for i in range(5):
            self.assertEqual(self.login(f"ninguem{i}", "errada-000")[0], 401)
        self.assert_limited(self.login("admin", PW), 60)  # the address waits, whatever the account

    def test_04_no_permanent_lock_after_the_longest_wait(self):
        self.admin().call("POST", "/api/v1/users", {"username": "lim4", "display": "L", "password": PW, "role": "operator"})
        for wait in (60, 120, 240, 480, 900, 900):
            for _ in range(5):
                self.assertEqual(self.login("lim4", "errada-000")[0], 401)
            self.assert_limited(self.login("lim4", PW), wait)
            self.clock.advance(wait)
        self.assertEqual(self.login("lim4", PW)[0], 200)

    def test_05_sign_up_attempts_count_per_address(self):
        for i in range(5):  # accepted or refused, every request counts
            body = {"full_name": f"Cad {i}", "email": f"cad{i}@exemplo.test" if i % 2 else "invalido", "password": PW}
            self.assertIn(self.raw.call("POST", "/api/v1/register", body)[0], (200, 400))
        out = self.raw.call("POST", "/api/v1/register", {"full_name": "Cad 9", "email": "cad9@exemplo.test", "password": PW})
        self.assert_limited(out, 60)
        self.clock.advance(60)
        self.assertEqual(self.raw.call("POST", "/api/v1/register", {"full_name": "Cad 9", "email": "cad9@exemplo.test", "password": PW})[0], 200)

    def test_07_parallel_wrong_passwords_get_five_checks(self):
        """Review R1: 16 parallel requests used to pass the wait check before any failure was counted."""
        self.admin().call("POST", "/api/v1/users", {"username": "lim7", "display": "L", "password": PW, "role": "operator"})
        out, start = [], threading.Barrier(16)

        def go(i):
            start.wait()
            out.append(self.login("lim7", f"errada-{i:03d}")[0])

        threads = [threading.Thread(target=go, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual((out.count(401), out.count(429)), (5, 11), out)

    def test_06_restart_clears_the_limits(self):
        for _ in range(5):
            self.login("admin", "errada-000")
        self.assert_limited(self.login("admin", PW), 60)
        self.h.core.limits = auth.AttemptLimiter(self.clock)  # what a new Core process starts with
        self.assertEqual(self.login("admin", PW)[0], 200)


class ServerLimitTest(Harness, unittest.TestCase):
    """Request slots with a margin, the database cap, connection caps and TLS socket close."""

    def setUp(self):
        self.admin()
        self.raw = _Pinned(self)
        self.httpd = self.h.api.httpd
        self.wait_idle()

    def wait_idle(self, timeout=5.0):
        end = time.monotonic() + timeout
        while self.httpd.connections() and time.monotonic() < end:
            time.sleep(0.02)
        self.assertEqual(self.httpd.connections(), 0, "every connection was released")

    def test_01_busy_requests_are_refused_but_runner_and_cancel_pass(self):
        sid, runner, hb = self.station("lim-est")
        adm = self.h.api.admission
        adm.__init__(slots=1, reserved=1, wait_s=0.3)
        gate, entered = threading.Event(), threading.Event()
        original = self.h.api.handlers.templates

        def slow(*a, **kw):
            entered.set()
            gate.wait(10)
            return original(*a, **kw)

        self.h.api.handlers.templates = slow
        token = type(self)._admin
        held = threading.Thread(target=lambda: self.raw.call("GET", "/api/v1/templates", token=token))
        try:
            held.start()
            self.assertTrue(entered.wait(5))
            t0 = time.monotonic()
            status, headers, body = self.raw.call("GET", "/api/v1/me", token=token)
            self.assertEqual((status, body["diagnostic"]["error_code"]), (503, "CORE-BUSY"))
            self.assertEqual((body["diagnostic"]["effect_state"], body["diagnostic"]["retry"]), ("none", "safe"))
            self.assertEqual(headers.get("Retry-After"), str(api.RETRY_AFTER_S))
            self.assertGreaterEqual(time.monotonic() - t0, 0.25, "it waited for a slot first")
            runner.call("POST", "/api/v1/runner/heartbeat", hb)  # reserved slot
            self.expect("NOT-FOUND", lambda: self.admin().call("POST", f"/api/v1/jobs/{uuid.uuid4()}/cancel"), 404)
            self.assertEqual(self.raw.call("POST", "/api/v1/changes", {"wait_s": 0}, token=token)[0], 200, "no slot")
        finally:
            gate.set()
            held.join(10)
            self.h.api.handlers.templates = original
            adm.__init__()
        self.assertEqual(self.raw.call("GET", "/api/v1/me", token=token)[0], 200)

    def test_02_database_cap_waits_then_refuses_without_deadlock(self):
        small = db.Database(self.h.database.info, max_open=1, wait_s=0.2)
        with small.tx() as c:
            with small.tx() as c2:  # nested on the same thread: no second place needed
                self.assertEqual(c2.execute("SELECT 1 AS one").fetchone()["one"], 1)
            out = []
            t = threading.Thread(target=lambda: out.append(self._try(small)))
            t.start()
            t.join(5)
            self.assertEqual(out, ["PoolBusy"])
        self.assertEqual(self._try(small), "ok", "the place came back")
        live, self.h.core.db = self.h.core.db, small
        hold, release = threading.Event(), threading.Event()

        def keep():
            with small.tx():
                hold.set()
                release.wait(10)

        k = threading.Thread(target=keep)
        try:
            k.start()
            self.assertTrue(hold.wait(5))
            status, _, body = self.raw.call("GET", "/api/v1/me", token=type(self)._admin)
            self.assertEqual((status, body["diagnostic"]["error_code"]), (503, "CORE-STORAGE-UNAVAILABLE"))
            self.assertEqual(body["diagnostic"]["params"]["reason"], "PoolBusy")
        finally:
            release.set()
            k.join(10)
            self.h.core.db = live
            small.close()

    @staticmethod
    def _try(database):
        try:
            with database.tx() as c:
                c.execute("SELECT 1")
            return "ok"
        except db.PoolBusy:
            return "PoolBusy"

    def tls(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        return ctx.wrap_socket(socket.create_connection(("127.0.0.1", self.port), timeout=5))

    def test_03_connection_caps_close_extra_connections(self):
        self.httpd.max_per_client = 2
        held = []
        try:
            held = [self.tls(), self.tls()]
            end = time.monotonic() + 5
            while self.httpd.connections() < 2 and time.monotonic() < end:
                time.sleep(0.02)
            refused = self.httpd.refused
            with self.assertRaises((ssl.SSLError, OSError)):
                self.tls().close()  # the server closes it before TLS, so the handshake itself fails
            self.assertEqual(self.httpd.refused, refused + 1)
        finally:
            for s in held:
                s.close()
            self.httpd.max_per_client = api.MAX_CONNECTIONS_PER_CLIENT
        self.wait_idle()
        self.assertEqual(self.raw.call("GET", "/api/v1/status")[0], 200)
        self.httpd.max_connections = 1
        try:
            keep = self.tls()
            end = time.monotonic() + 5
            while self.httpd.connections() < 1 and time.monotonic() < end:
                time.sleep(0.02)
            with self.assertRaises((ssl.SSLError, OSError)):
                self.raw.call("GET", "/api/v1/status")
            keep.close()
        finally:
            self.httpd.max_connections = api.MAX_CONNECTIONS
        self.wait_idle()
        self.assertEqual(self.raw.call("GET", "/api/v1/status")[0], 200)

    def test_04_tls_sockets_are_closed_on_every_ending(self):
        self.httpd.io_timeout_s = 0.5
        server_side = f"{self.port})"

        def leaks(w):
            return [str(x.message) for x in w if issubclass(x.category, ResourceWarning)
                    and f"laddr=('127.0.0.1', {self.port})" in str(x.message)]

        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always", ResourceWarning)
                for _ in range(5):  # completed exchanges
                    self.client().call("GET", "/api/v1/status")
                s = self.tls()  # interrupted in the middle of a request
                s.sendall(b"GET /api/v1/status HTTP/1.1\r\nHost: x")
                s.close()
                s = self.tls()  # interrupted after the handshake, before any request
                s.close()
                r = socket.create_connection(("127.0.0.1", self.port), timeout=5)  # handshake never sent
                time.sleep(0.8)
                r.close()
                r = socket.create_connection(("127.0.0.1", self.port), timeout=5)  # not TLS at all
                r.sendall(b"GET / HTTP/1.0\r\n\r\n")
                r.close()
                r = socket.create_connection(("127.0.0.1", self.port), timeout=5)  # closed at once
                r.close()
                self.wait_idle()
                gc.collect()
                self.assertEqual(leaks(w), [], server_side)
        finally:
            self.httpd.io_timeout_s = api.IO_TIMEOUT_S
        self.assertEqual(self.raw.call("GET", "/api/v1/status")[0], 200)


if __name__ == "__main__":
    unittest.main()
