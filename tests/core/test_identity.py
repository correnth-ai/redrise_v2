"""Identity on the real Core (isolated PostgreSQL on C:, HTTPS API with pinning)
with a simulated provider over HTTP. No Supabase project is called here: this
proves the Core contract, not the remote configuration.

    cd tests/core && <lab python> -B -m unittest test_identity
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import test_core
from test_core import PW, Harness

from redrise_core import auth, identity

DEVICE = {"installation_id": "inst-aaaa-0001", "name": "PC-TESTE", "windows_user": "maria"}
OTHER_DEVICE = {"installation_id": "inst-bbbb-0002", "name": "PC-CASA", "windows_user": "maria"}


def account(sub, email=None, name="Maria da Conceição", **over):
    return {"id": sub, "aud": "authenticated", "email": email or f"{sub}@exemplo.test", "email_confirmed_at": "2026-11-02T10:00:00Z",
            "user_metadata": {"full_name": name}, "app_metadata": {}, **over}


class Provider:
    """/auth/v1/user: token -> user record; anything else is refused like the service does."""

    def __init__(self):
        self.tokens, self.down, self.seen_key = {}, False, None
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.seen_key = self.headers.get("apikey")
                if outer.down:
                    self.send_response(503); self.end_headers(); return
                user = outer.tokens.get((self.headers.get("Authorization") or "").removeprefix("Bearer "))
                if self.path != "/auth/v1/user" or user is None:
                    self.send_response(401); self.end_headers(); return
                body = json.dumps(user).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"


class IdentityTest(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    client, expect, admin, su = Harness.client, Harness.expect, classmethod(Harness.admin.__func__), Harness.su

    @classmethod
    def tearDownClass(cls):
        cls.provider.httpd.shutdown()
        cls.provider.httpd.server_close()
        Harness.tearDownClass.__func__(cls)

    @classmethod
    def setUpClass(cls):
        Harness.setUpClass.__func__(cls)
        cls.provider = Provider()
        cls.h.core.verifier = identity.SupabaseVerifier(cls.provider.url, "chave-publica")

    def setUp(self):
        self.provider.down = False

    # ---------------------------------------------------------------- helpers
    def member(self, username, role="operator"):
        self.admin().call("POST", "/api/v1/users", {"username": username, "display": username, "password": PW, "role": role})

    def session(self, token, **kw):
        return self.client().call("POST", "/api/v1/identity/session", {"access_token": token, **kw})

    def link(self, token, username, password=PW, **kw):
        return self.client().call("POST", "/api/v1/identity/link", {"access_token": token, "username": username, "password": password, **kw})

    def linked(self, sub, username, **acct):
        self.member(username)
        self.provider.tokens[sub] = account(sub, **acct)
        return self.link(sub, username)

    def count(self, table):
        with self.su() as c:
            c.execute("SET search_path TO public")
        with self.h.database.tx() as c:
            return c.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]

    # ---------------------------------------------------------------- tests
    def test_01_not_configured_is_honest_and_local_login_stays(self):
        v, self.h.core.verifier = self.h.core.verifier, None
        try:
            self.provider.tokens["x"] = account("x")
            self.expect("IDENTITY-NOT-CONFIGURED", lambda: self.session("x"), 503)
        finally:
            self.h.core.verifier = v
        self.assertTrue(self.client().call("POST", "/api/v1/login", {"username": "admin", "password": PW})["token"]) if self.admin() else None

    def test_02_refused_tokens(self):
        self.expect("IDENTITY-INVALID", lambda: self.session("desconhecido"), 401)
        self.expect("VALIDATION", lambda: self.session(""), 400)
        self.provider.tokens["aud"] = account("aud", aud="anon")
        self.expect("IDENTITY-INVALID", lambda: self.session("aud"), 401)

    def test_03_unconfirmed_blocked_by_the_backend(self):
        self.provider.tokens["pend"] = account("pend", email_confirmed_at=None)
        self.expect("IDENTITY-UNCONFIRMED", lambda: self.session("pend"), 403)
        # V1 password account confirmed administratively: the timestamp alone is not proof of possession.
        self.provider.tokens["v1"] = account("v1", app_metadata={"redrise_password_account": True, "redrise_email_possession": False})
        self.expect("IDENTITY-UNCONFIRMED", lambda: self.session("v1"), 403)
        self.provider.tokens["v1ok"] = account("v1ok", app_metadata={"redrise_password_account": True, "redrise_email_possession": True})
        self.expect("IDENTITY-NO-MEMBERSHIP", lambda: self.session("v1ok"), 403)

    def test_04_provider_down_is_recoverable(self):
        self.provider.tokens["down"] = account("down")
        self.provider.down = True
        self.expect("IDENTITY-PROVIDER-UNAVAILABLE", lambda: self.session("down"), 503)

    def test_05_account_alone_grants_nothing(self):
        self.admin()
        before = self.count("users")
        self.provider.tokens["novo"] = account("novo", user_metadata={"full_name": "Novo", "role": "admin"}, app_metadata={"role": "admin"})
        self.expect("IDENTITY-NO-MEMBERSHIP", lambda: self.session("novo"), 403)
        self.assertEqual(self.count("users"), before)
        self.assertEqual(self.provider.seen_key, "chave-publica")

    def test_06_link_needs_both_proofs_and_keeps_the_role(self):
        self.member("oper.link")
        self.provider.tokens["s-link"] = account("s-link")
        self.expect("AUTH-INVALID", lambda: self.link("s-link", "oper.link", "senha-errada-1"), 401)
        self.expect("AUTH-INVALID", lambda: self.link("s-link", "nao.existe"), 401)
        self.expect("IDENTITY-NO-MEMBERSHIP", lambda: self.session("s-link"), 403)
        out = self.link("s-link", "oper.link")
        self.assertEqual((out["user"]["username"], out["user"]["role"]), ("oper.link", "operator"))
        self.assertIsNone(out["device"])
        me = self.client(out["token"])
        self.assertEqual(me.call("GET", "/api/v1/me")["username"], "oper.link")
        self.expect("AUTH-FORBIDDEN", lambda: me.call("GET", "/api/v1/users"), 403)
        again = self.session("s-link")
        self.assertEqual(again["user"]["username"], "oper.link")

    def test_07_name_is_presentation_with_accents(self):
        out = self.linked("s-nome", "oper.nome", name="José Antônio Conceição")
        self.assertEqual(out["profile"]["full_name"], "José Antônio Conceição")
        p = self.client(out["token"]).call("GET", "/api/v1/identity/profile")
        self.assertEqual((p["full_name"], p["linked"], p["role"]), ("José Antônio Conceição", True, "operator"))
        row = next(u for u in self.admin().call("GET", "/api/v1/users") if u["username"] == "oper.nome")
        self.assertEqual((row["full_name"], row["role"]), ("José Antônio Conceição", "operator"))
        self.provider.tokens["s-nome"]["user_metadata"]["full_name"] = "Admin"  # renaming changes no permission
        self.assertEqual(self.session("s-nome")["user"]["role"], "operator")

    def test_08_one_account_one_member_and_no_match_by_email(self):
        self.linked("s-a", "oper.a", email="mesma@exemplo.test")
        self.member("oper.b")
        self.provider.tokens["s-b"] = account("s-b", email="mesma@exemplo.test")
        self.expect("IDENTITY-NO-MEMBERSHIP", lambda: self.session("s-b"), 403)  # same e-mail, other subject
        self.expect("IDENTITY-ALREADY-LINKED", lambda: self.link("s-b", "oper.a"), 409)  # member taken
        self.expect("IDENTITY-ALREADY-LINKED", lambda: self.link("s-a", "oper.b"), 409)  # account taken

    def test_09_not_remembered_creates_no_device(self):
        self.linked("s-mem", "oper.mem")
        before = self.count("remembered_devices")
        out = self.session("s-mem", remember=False, device=DEVICE)
        self.assertIsNone(out["device"])
        self.assertEqual(self.count("remembered_devices"), before)
        self.assertEqual(self.client(out["token"]).call("GET", "/api/v1/identity/devices"), [])

    def test_10_remember_is_absolute_and_updates_the_same_entry(self):
        self.linked("s-rem", "oper.rem")
        first = self.session("s-rem", remember=True, device=DEVICE)
        exp = datetime.fromisoformat(first["device"]["expires_at"])
        self.assertLess(abs(exp - datetime.now(timezone.utc) - timedelta(days=30)), timedelta(minutes=5))
        again = self.session("s-rem", remember=True, device={**DEVICE, "name": "PC-RENOMEADO"})
        self.assertEqual(again["device"], first["device"])  # same entry, deadline not extended
        restored = self.session("s-rem", device_id=first["device"]["id"])
        self.assertEqual(restored["device"], first["device"])
        rows = self.client(restored["token"]).call("GET", "/api/v1/identity/devices")
        self.assertEqual([(r["name"], r["current"]) for r in rows], [("PC-RENOMEADO", True)])
        self.assertFalse({"token", "token_hash", "refresh_token", "subject"} & set(rows[0]))
        self.assertNotIn("email", rows[0])

    def test_11_expired_device_needs_a_new_sign_in(self):
        self.linked("s-exp", "oper.exp")
        d = self.session("s-exp", remember=True, device=DEVICE)["device"]["id"]
        with self.h.database.tx() as c:
            c.execute("UPDATE remembered_devices SET expires_at = now() - interval '1 minute' WHERE id = %s", (d,))
        self.expect("IDENTITY-SESSION-EXPIRED", lambda: self.session("s-exp", device_id=d), 401)
        fresh = self.session("s-exp", remember=True, device=DEVICE)
        self.assertNotEqual(fresh["device"]["id"], d)

    def test_12_devices_are_isolated_between_people(self):
        self.linked("s-x", "oper.x")
        self.linked("s-y", "oper.y")
        dx = self.session("s-x", remember=True, device=DEVICE)
        dy = self.session("s-y", remember=True, device=DEVICE)
        self.assertNotEqual(dx["device"]["id"], dy["device"]["id"])
        cy = self.client(dy["token"])
        self.assertEqual([r["id"] for r in cy.call("GET", "/api/v1/identity/devices")], [dy["device"]["id"]])
        self.expect("NOT-FOUND", lambda: cy.call("DELETE", f"/api/v1/identity/devices/{dx['device']['id']}"), 404)
        self.expect("IDENTITY-SESSION-EXPIRED", lambda: self.session("s-y", device_id=dx["device"]["id"]), 401)
        admin = self.admin()
        self.assertEqual(admin.call("GET", "/api/v1/identity/devices"), [])  # an administrator sees only their own
        self.assertEqual(self.client(dx["token"]).call("GET", "/api/v1/me")["username"], "oper.x")

    def test_13_forget_revokes_that_device_and_its_sessions(self):
        self.linked("s-f", "oper.f")
        a = self.session("s-f", remember=True, device=DEVICE)
        b = self.session("s-f", remember=True, device=OTHER_DEVICE)
        ca, cb = self.client(a["token"]), self.client(b["token"])
        self.assertEqual(len(ca.call("GET", "/api/v1/identity/devices")), 2)
        ca.call("DELETE", f"/api/v1/identity/devices/{b['device']['id']}")
        self.expect("AUTH-REQUIRED", lambda: cb.call("GET", "/api/v1/me"), 401)
        self.expect("IDENTITY-SESSION-EXPIRED", lambda: self.session("s-f", device_id=b["device"]["id"]), 401)
        self.assertEqual(ca.call("GET", "/api/v1/me")["username"], "oper.f")  # the other device goes on
        self.expect("NOT-FOUND", lambda: ca.call("DELETE", f"/api/v1/identity/devices/{b['device']['id']}"), 404)

    def test_14_logout_ends_only_this_device(self):
        self.linked("s-l", "oper.l")
        a = self.session("s-l", remember=True, device=DEVICE)
        b = self.session("s-l", remember=True, device=OTHER_DEVICE)
        ca, cb = self.client(a["token"]), self.client(b["token"])
        ca.call("POST", "/api/v1/logout")
        self.expect("AUTH-REQUIRED", lambda: ca.call("GET", "/api/v1/me"), 401)
        self.expect("IDENTITY-SESSION-EXPIRED", lambda: self.session("s-l", device_id=a["device"]["id"]), 401)
        self.assertEqual(cb.call("GET", "/api/v1/me")["username"], "oper.l")
        self.assertEqual([r["id"] for r in cb.call("GET", "/api/v1/identity/devices")], [b["device"]["id"]])

    def test_15_deactivated_member_loses_access(self):
        out = self.linked("s-off", "oper.off")
        self.admin().call("PATCH", f"/api/v1/users/{out['user']['id']}", {"active": False})
        self.expect("AUTH-INVALID", lambda: self.session("s-off"), 401)

    def test_16_tokens_never_come_back_in_errors(self):
        self.provider.tokens["segredo-do-token"] = account("seg", email_confirmed_at=None)
        e = self.expect("IDENTITY-UNCONFIRMED", lambda: self.session("segredo-do-token"), 403)
        self.assertNotIn("segredo-do-token", json.dumps(e.diagnostic.to_dict()))


class SignUpTest(unittest.TestCase):
    """Sign-up on the Core (user decision of 02/11/2026): records the account, no e-mail, no access by itself."""
    setUpClass = classmethod(Harness.setUpClass.__func__)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    client, expect, admin = Harness.client, Harness.expect, classmethod(Harness.admin.__func__)

    def setUp(self):
        # Each test starts with the limits of a fresh Core: this class signs up more than 5 times from
        # one address in a few minutes, which the sign-up limit refuses (test_limits covers that rule).
        self.h.core.limits = auth.AttemptLimiter()

    def register(self, email, password="abcdefgh", name="Maria da Conceição"):
        return self.client().call("POST", "/api/v1/register", {"full_name": name, "email": email, "password": password})

    def row(self, email):
        return next(u for u in self.admin().call("GET", "/api/v1/users") if u["email"] == email)

    def login(self, who, password="abcdefgh"):
        return self.client().call("POST", "/api/v1/login", {"username": who, "password": password})

    def test_01_password_rule_and_input(self):
        self.admin()
        self.expect("VALIDATION", lambda: self.register("a@exemplo.test", password="abcdefg"), 400)
        self.assertEqual(self.register("sete@exemplo.test", password="abcdefgh"), {"pending": True})
        self.expect("VALIDATION", lambda: self.register("sem-arroba"), 400)
        self.expect("VALIDATION", lambda: self.register("b@exemplo.test", name="   "), 400)

    def test_02_recorded_as_inactive_operator_with_accents(self):
        self.admin()
        self.register("Nova.Pessoa@Exemplo.test")
        u = self.row("nova.pessoa@exemplo.test")
        self.assertEqual((u["display"], u["role"], u["active"], u["username"]), ("Maria da Conceição", "operator", False, "nova.pessoa"))

    def test_03_no_access_until_an_administrator_activates(self):
        self.admin()
        self.register("ativar@exemplo.test")
        self.expect("AUTH-INVALID", lambda: self.login("ativar@exemplo.test"), 401)
        u = self.row("ativar@exemplo.test")
        self.admin().call("PATCH", f"/api/v1/users/{u['id']}", {"active": True})
        out = self.login("ATIVAR@exemplo.test")
        me = self.client(out["token"])
        self.assertEqual(me.call("GET", "/api/v1/me")["role"], "operator")
        self.expect("AUTH-FORBIDDEN", lambda: me.call("GET", "/api/v1/users"), 403)
        p = me.call("GET", "/api/v1/identity/profile")
        self.assertEqual((p["full_name"], p["email"]), ("Maria da Conceição", "ativar@exemplo.test"))

    def test_04_one_account_per_email_and_distinct_usernames(self):
        self.admin()
        self.register("igual@exemplo.test")
        self.expect("ACCOUNT-EXISTS", lambda: self.register("IGUAL@exemplo.test", password="outrasenha"), 409)
        self.expect("AUTH-INVALID", lambda: self.login("igual@exemplo.test", "outrasenha"), 401)
        self.register("igual@outro.test")
        self.assertEqual(self.row("igual@outro.test")["username"], "igual.2")

    def test_05_existing_team_user_still_signs_in_by_username(self):
        self.admin()
        self.assertTrue(self.login("admin", PW)["token"])


class ProviderRecord(unittest.TestCase):
    def test_name_prefers_full_name_and_never_a_role(self):
        i = identity.identity_of(account("s", user_metadata={"name": "Outro", "full_name": "  Maria  ", "role": "admin"}))
        self.assertEqual((i.subject, i.full_name), ("s", "Maria"))
        self.assertIsNone(identity.identity_of(account("s", user_metadata={})).full_name)

    def test_only_https_configuration_is_loaded(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertIsNone(identity.load_verifier(root))
            (root / "identity.json").write_text(json.dumps({"supabase_url": "http://x.test", "publishable_key": "k"}), encoding="utf-8")
            self.assertIsNone(identity.load_verifier(root))
            (root / "identity.json").write_text("{", encoding="utf-8")
            self.assertIsNone(identity.load_verifier(root))
            (root / "identity.json").write_text(json.dumps({"supabase_url": "https://x.test/", "publishable_key": "k"}), encoding="utf-8")
            self.assertEqual(identity.load_verifier(root).url, "https://x.test")


if __name__ == "__main__":
    unittest.main()
