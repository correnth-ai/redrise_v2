"""Team accounts, stations, process links and routine deletion (work order TEAM-ACCOUNTS-20261108) on the real
Core: isolated PostgreSQL on C:, HTTPS API with pinning, Runner calls made by the test as a declared simulated
Runner, the scheduler pass called with a controlled clock. Synthetic team only.

    cd tests/core && <lab python> -B -m unittest test_team_accounts
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import test_core
from test_core import PW, Harness

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}


def mail():
    return f"p{uuid.uuid4().hex[:8]}@exemplo.com.br"


class TeamAccountsTest(Harness, unittest.TestCase):
    # ---------------------------------------------------------------- helpers
    def bound_admin(self):
        """An administrator session opened from station `self.here`, proved by its runner token (as the desktop does)."""
        tok = self.client().call("POST", "/api/v1/login", {"username": "admin", "password": PW, "station_token": self.here_token})
        self.assertEqual(tok["station_id"], self.here)
        return self.client(tok["token"])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        a = cls.admin()
        s = a.call("POST", "/api/v1/stations", {"name": "aqui"})
        cls.here, cls.here_token = s["station"]["id"], s["runner_token"]

    def account(self, client=None, **kw):
        body = {"full_name": "Pessoa Sintética", "email": mail(), "password": PW, **kw}
        return (client or self.admin()).call("POST", "/api/v1/accounts", body), body

    def login(self, email, pw=PW):
        return self.client().call("POST", "/api/v1/login", {"username": email, "password": pw})

    def users(self):
        return {u["id"]: u for u in self.admin().call("GET", "/api/v1/users")}

    def operator(self):
        u, b = self.account()
        return u, self.client(self.login(b["email"])["token"])

    def routine(self, link=None, kind="app"):
        body = {"name": f"r-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": CALC}}
        if link:
            body["link"] = link
        return self.admin().call("POST", "/api/v1/routines", body)["routine"]["id"]

    def review_step(self, pid, after, assignee):
        return self.admin().call("POST", "/api/v1/routines", {"name": f"f-{uuid.uuid4().hex[:6]}", "category": "windows",
            "version": {"kind": "followup", "config": {"action": "review", "assignee_id": assignee}},
            "link": {"process_id": pid, "after_position": after}})["routine"]["id"]

    def process(self, steps=0):
        pid = self.admin().call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})["id"]
        ids = []
        for i in range(steps):
            rid = self.routine(link={"process_id": pid}) if i == 0 else self.routine()
            if i:
                self.admin().call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": rid})
            ids.append(rid)
        return pid, ids

    def items(self, pid):
        return [(i["position"], i["routine_id"], i["continue_next"]) for i in self.admin().call("GET", f"/api/v1/processes/{pid}")["items"]]

    def save(self, pid, links, client=None):
        return (client or self.admin()).call("PUT", f"/api/v1/processes/{pid}", {"name": f"p-{pid}", "items": [
            {"routine_id": r, "continue_next": c} for r, c in links]})

    def start(self, sid, pid):
        return self.admin().call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})

    # ---------------------------------------------------------------- 1. + Nova Conta
    def test_01_new_account_signs_in_at_once_with_its_email(self):
        before = self.users()
        u, b = self.account(full_name="  Maria da Silva  ")
        self.assertEqual((u["display"], u["email"], u["role"], u["active"]), ("Maria da Silva", b["email"], "operator", True))
        self.assertEqual(u["username"], b["email"].split("@")[0])  # internal user name from the e-mail
        after = self.users()
        self.assertEqual(set(after) - set(before), {u["id"]})  # exactly one account
        # The new account's own sign-in, not the administrator's session: login, logout, login again.
        s = self.login(b["email"].upper())
        me = self.client(s["token"]).call("GET", "/api/v1/me")
        self.assertEqual((me["id"], me["role"]), (u["id"], "operator"))
        self.client(s["token"]).call("POST", "/api/v1/logout")
        self.expect("AUTH-REQUIRED", lambda: self.client(s["token"]).call("GET", "/api/v1/me"), 401)
        self.assertEqual(self.client(self.login(b["email"])["token"]).call("GET", "/api/v1/me")["id"], u["id"])
        self.expect("AUTH-INVALID", lambda: self.login(b["email"], "senha-errada-9"), 401)
        # A second account whose e-mail has the same name part gets another internal user name.
        u2, _ = self.account(email=b["email"].split("@")[0] + "@outro.com.br")
        self.assertEqual(u2["username"], u["username"] + ".2")
        self.assertEqual(self.admin().call("GET", "/api/v1/me")["username"], "admin")  # older accounts unchanged

    def test_02_new_account_rules_checked_by_the_core(self):
        a = self.admin()
        _, b = self.account()
        self.expect("ACCOUNT-EXISTS", lambda: self.account(email=b["email"].upper()), 409)
        self.expect("VALIDATION", lambda: self.account(full_name="   "), 400)
        self.expect("VALIDATION", lambda: self.account(email="sem-arroba"), 400)
        self.expect("VALIDATION", lambda: self.account(password="1234567"), 400)  # minimum 8
        self.account(password="12345678")
        _, op = self.operator()
        self.expect("AUTH-FORBIDDEN", lambda: self.account(client=op), 403)
        self.expect("AUTH-REQUIRED", lambda: self.account(client=self.client()), 401)
        n = len(a.call("GET", "/api/v1/users"))
        self.expect("VALIDATION", lambda: self.account(password="curta"), 400)
        self.assertEqual(len(a.call("GET", "/api/v1/users")), n)  # nothing partial is kept

    # ---------------------------------------------------------------- 1.3 deleting an inactive account
    def test_03_only_an_inactive_account_is_deleted_and_it_loses_all_access(self):
        a = self.admin()
        u, b = self.account()
        s = self.login(b["email"])["token"]
        self.expect("ACCOUNT-ACTIVE", lambda: a.call("DELETE", f"/api/v1/users/{u['id']}"), 409)  # direct call refused too
        _, op = self.operator()
        a.call("PATCH", f"/api/v1/users/{u['id']}", {"active": False})
        self.expect("AUTH-FORBIDDEN", lambda: op.call("DELETE", f"/api/v1/users/{u['id']}"), 403)
        self.assertEqual(a.call("DELETE", f"/api/v1/users/{u['id']}"), {"deleted": True})
        self.assertNotIn(u["id"], self.users())
        self.expect("AUTH-INVALID", lambda: self.login(b["email"]), 401)
        self.expect("AUTH-REQUIRED", lambda: self.client(s).call("GET", "/api/v1/me"), 401)
        self.expect("NOT-FOUND", lambda: a.call("PATCH", f"/api/v1/users/{u['id']}", {"active": True}), 404)  # no reactivation
        self.expect("NOT-FOUND", lambda: a.call("DELETE", f"/api/v1/users/{u['id']}"), 404)
        self.expect("ACCOUNT-EMAIL-RESERVED", lambda: self.account(email=b["email"]), 409)  # reserved, never relinked
        with self.su() as c:  # the row stays (history), inactive and marked deleted
            row = c.execute("SELECT active, deleted_at IS NOT NULL FROM users WHERE id = %s", (u["id"],)).fetchone()
        self.assertEqual(row, (False, True))

    def test_04_a_reactivation_from_another_screen_wins_over_a_stale_delete(self):
        a = self.admin()
        u, _ = self.account()
        a.call("PATCH", f"/api/v1/users/{u['id']}", {"active": False})
        # Another session reactivates while this screen still shows it inactive: the delete reads it again.
        a.call("PATCH", f"/api/v1/users/{u['id']}", {"active": True})
        self.expect("ACCOUNT-ACTIVE", lambda: a.call("DELETE", f"/api/v1/users/{u['id']}"), 409)
        # Truly concurrent: the reactivation holds the row; the delete waits for it and then refuses.
        a.call("PATCH", f"/api/v1/users/{u['id']}", {"active": False})
        out = {}
        with self.su() as c:
            c.autocommit = False
            c.execute("UPDATE users SET active = true WHERE id = %s", (u["id"],))
            t = threading.Thread(target=lambda: out.update(e=self._try(lambda: a.call("DELETE", f"/api/v1/users/{u['id']}"))))
            t.start()
            time.sleep(1.0)
            self.assertTrue(t.is_alive())  # waiting on the row lock
            c.commit()
        t.join(10)
        self.assertEqual(out["e"], "ACCOUNT-ACTIVE")
        self.assertTrue(self.users()[u["id"]]["active"])

    @staticmethod
    def _try(fn):
        try:
            fn()
            return "ok"
        except test_core.CoreError as e:
            return e.diagnostic.error_code

    def test_05_history_reviews_and_schedules_of_a_deleted_account_stay(self):
        a = self.admin()
        sid, runner, hb = self.station(f"st-{uuid.uuid4().hex[:6]}")
        boss = a.call("POST", "/api/v1/users", {"username": f"b{uuid.uuid4().hex[:6]}", "display": "Chefe", "password": PW, "role": "admin"})
        bt = self.client(self.client().call("POST", "/api/v1/login", {"username": boss["username"], "password": PW})["token"])
        rev, rb = self.account()
        pid, (first,) = self.process(1)
        self.review_step(pid, 1, rev["id"])
        eid = bt.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})["id"]
        job = runner.call("POST", "/api/v1/runner/claim", hb)["job"]
        runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
            "schema": "redrise.job-result/1", "state": "verified", "verified": True, "details": {"context": {}}}})
        sched = bt.call("POST", "/api/v1/schedules", {"process_id": pid, "station_id": sid, "weekdays": [1, 2, 3, 4, 5, 6, 7],
                                                     "hour": 3, "minute": 0, "timezone": "America/Sao_Paulo"})
        with self.su() as c:
            counts = c.execute("""SELECT (SELECT count(*) FROM routines), (SELECT count(*) FROM processes), (SELECT count(*) FROM executions),
                                         (SELECT count(*) FROM review_requests), (SELECT count(*) FROM schedules)""").fetchone()
        for u in (boss, rev):
            a.call("PATCH", f"/api/v1/users/{u['id']}", {"active": False})
            a.call("DELETE", f"/api/v1/users/{u['id']}")
        with self.su() as c:
            self.assertEqual(c.execute("""SELECT (SELECT count(*) FROM routines), (SELECT count(*) FROM processes), (SELECT count(*) FROM executions),
                                         (SELECT count(*) FROM review_requests), (SELECT count(*) FROM schedules)""").fetchone(), counts)
            c.execute("UPDATE schedules SET enabled = false, next_run_at = NULL WHERE id <> %s", (sched["id"],))
        e = a.call("GET", f"/api/v1/executions/{eid}")
        self.assertEqual((e["requested_by"], e["state"], e["steps"][1]["review"]["status"]), (boss["username"], "waiting_review", "pending"))  # not approved
        due = datetime.fromisoformat(sched["next_run_at"])
        runner.call("POST", "/api/v1/runner/heartbeat", hb)
        out = self.h.core.schedule_tick(due + timedelta(seconds=5))
        self.assertEqual(out["started"], 0)
        row = next(s for s in a.call("GET", "/api/v1/schedules") if s["id"] == sched["id"])
        self.assertEqual((row["enabled"], row["paused_reason"]), (False, "owner_not_allowed"))  # never runs in the deleted owner's name
        self.expect("CONFLICT", lambda: a.call("PATCH", f"/api/v1/users/{a.call('GET', '/api/v1/me')['id']}", {"active": False}), 409)  # last active admin

    # ---------------------------------------------------------------- 4. stations
    def test_06_the_station_in_use_is_protected_and_identified_by_proof(self):
        a, b = self.admin(), self.bound_admin()
        other, _, _ = self.station(f"st-{uuid.uuid4().hex[:6]}")
        rows = {s["id"]: s for s in b.call("GET", "/api/v1/stations")}
        self.assertTrue(rows[self.here]["current"])
        self.assertFalse(rows[other]["current"])
        self.assertFalse(any(s["current"] for s in a.call("GET", "/api/v1/stations")))  # no proof, no current station
        self.expect("STATION-SESSION-UNBOUND", lambda: a.call("DELETE", f"/api/v1/stations/{other}"), 409)  # proof omitted
        forged = self.client().call("POST", "/api/v1/login", {"username": "admin", "password": PW, "station_token": "x" * 43})
        self.assertIsNone(forged["station_id"])
        self.expect("STATION-SESSION-UNBOUND", lambda: self.client(forged["token"]).call("DELETE", f"/api/v1/stations/{other}"), 409)
        self.expect("STATION-IN-USE", lambda: b.call("DELETE", f"/api/v1/stations/{self.here}"), 409)
        self.expect("STATION-IN-USE", lambda: b.call("POST", f"/api/v1/stations/{self.here}/remove"), 409)
        _, op = self.operator()
        self.expect("AUTH-FORBIDDEN", lambda: op.call("DELETE", f"/api/v1/stations/{other}"), 403)
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", f"/api/v1/stations/{other}/remove"), 403)
        b.call("DELETE", f"/api/v1/stations/{other}")  # another station can be revoked
        self.assertTrue({s["id"]: s for s in b.call("GET", "/api/v1/stations")}[other]["revoked"])

    def test_07_only_a_revoked_station_is_deleted_and_its_history_stays(self):
        b = self.bound_admin()
        name = f"st-{uuid.uuid4().hex[:6]}"
        sid, runner, hb = self.station(name)
        pid, _ = self.process(1)
        e = self.start(sid, pid)
        sched = b.call("POST", "/api/v1/schedules", {"process_id": pid, "station_id": sid, "weekdays": [1, 2, 3, 4, 5, 6, 7],
                                                    "hour": 4, "minute": 0, "timezone": "America/Sao_Paulo"})
        self.expect("STATION-NOT-REVOKED", lambda: b.call("POST", f"/api/v1/stations/{sid}/remove"), 409)
        b.call("DELETE", f"/api/v1/stations/{sid}")
        self.assertEqual(b.call("POST", f"/api/v1/stations/{sid}/remove"), {"deleted": True})
        self.assertNotIn(sid, [s["id"] for s in b.call("GET", "/api/v1/stations")])
        self.expect("NOT-FOUND", lambda: b.call("POST", f"/api/v1/stations/{sid}/remove"), 404)
        self.assertEqual(b.call("GET", f"/api/v1/executions/{e['id']}")["station_name"], name)  # history readable
        self.expect("AUTH-REQUIRED", lambda: runner.call("POST", "/api/v1/runner/heartbeat", hb), 401)  # credential revoked
        with self.su() as c:
            c.execute("UPDATE schedules SET enabled = false, next_run_at = NULL WHERE id <> %s", (sched["id"],))
        out = self.h.core.schedule_tick(datetime.fromisoformat(sched["next_run_at"]) + timedelta(seconds=5))
        self.assertEqual(out["started"], 0)
        self.assertEqual(b.call("GET", f"/api/v1/schedules/{sched['id']}/runs")[0]["reason"], "station_unavailable")
        again = b.call("POST", "/api/v1/stations", {"name": name})  # the same computer can join again under its name
        self.assertNotEqual(again["station"]["id"], sid)

    def test_08_status_is_connectivity_and_a_revoked_station_is_never_online(self):
        b = self.bound_admin()
        sid, runner, hb = self.station(f"st-{uuid.uuid4().hex[:6]}", ready=False)
        row = lambda: {s["id"]: s for s in b.call("GET", "/api/v1/stations")}[sid]
        self.assertEqual((row()["online"], row()["session_state"]), (True, "locked"))  # online, not ready
        with self.su() as c:
            c.execute("UPDATE stations SET last_seen_at = now() - interval '46 seconds' WHERE id = %s", (sid,))
        self.assertFalse(row()["online"])  # no signal for more than 45 s
        runner.call("POST", "/api/v1/runner/heartbeat", hb)
        self.assertTrue(row()["online"])  # back with a valid heartbeat
        b.call("DELETE", f"/api/v1/stations/{sid}")
        self.assertEqual((row()["revoked"], row()["online"]), (True, False))  # a fresh heartbeat does not make it a valid connection

    # ---------------------------------------------------------------- 5. removing links of a process
    def test_09_any_link_can_be_removed_and_an_invalid_start_never_runs(self):
        sid, _, _ = self.station(f"st-{uuid.uuid4().hex[:6]}")
        pid, (r1, r2, r3) = self.process(3)
        self.save(pid, [(r1, True), (r2, False), (r3, True)])
        self.expect("STEP1-NEEDS-APPROVAL", lambda: self.save(pid, [(r2, False), (r1, True), (r3, True)]), 409)  # step 1 kept, moved down
        self.save(pid, [(r2, False), (r3, True)])  # removing step 1: no approval
        self.assertEqual(self.items(pid), [(1, r2, False), (2, r3, True)])  # order and continuation kept, renumbered
        self.save(pid, [(r2, False)])  # the last one
        self.save(pid, [])  # the only one: an empty process is saved
        self.assertEqual(self.items(pid), [])
        e = self.expect("PROCESS-START-INVALID", lambda: self.start(sid, pid), 409)
        self.assertEqual(e.diagnostic.params["reason"], "no linked routine")
        self.assertIn(r1, [r["id"] for r in self.admin().call("GET", "/api/v1/routines")])  # removing a link deletes no routine
        # A follow-up left first is saved, never promoted nor run.
        uid = self.account()[0]["id"]
        pid2, (s1,) = self.process(1)
        f = self.review_step(pid2, 1, uid)
        self.save(pid2, [(f, True)])
        e = self.expect("PROCESS-START-INVALID", lambda: self.start(sid, pid2), 409)
        self.assertEqual(e.diagnostic.params["reason"], "step 1 is a follow-up")
        self.save(pid2, [(s1, True), (f, True)])  # valid again
        self.assertEqual(self.start(sid, pid2)["state"], "running")

    def test_10_a_shared_routine_stays_in_the_other_processes_and_running_snapshots_keep(self):
        sid, runner, hb = self.station(f"st-{uuid.uuid4().hex[:6]}")
        pa, (a1, a2) = self.process(2)
        pb, (b1,) = self.process(1)
        self.save(pb, [(b1, True), (a2, True)])  # a2 in both processes
        e = self.start(sid, pa)
        self.save(pa, [(a2, True)])  # a1 removed while an execution runs
        self.assertEqual([s["routine_id"] for s in self.admin().call("GET", f"/api/v1/executions/{e['id']}")["steps"]], [a1, a2])
        self.assertEqual(self.items(pb), [(1, b1, True), (2, a2, True)])

    def test_11_a_pending_step_1_replacement_that_no_longer_fits_is_cancelled(self):
        a = self.admin()
        pid, (r1, r2) = self.process(2)
        new = self.routine()
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        self.save(pid, [(r2, True)])  # step 1 removed: the request would replace another routine
        done = next(x for x in a.call("GET", "/api/v1/step-changes") if x["id"] == q["id"])
        self.assertEqual(done["status"], "cancelled")
        self.assertEqual(self.items(pid), [(1, r2, True)])
        self.assertIsNone(a.call("GET", f"/api/v1/processes/{pid}")["pending_change"])
        with self.su() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE change_id = %s", (q["id"],)).fetchone()[0], 0)

    # ---------------------------------------------------------------- 6. deleting routines
    def test_12_deleting_a_linked_routine_takes_it_out_of_every_process_at_once(self):
        a = self.admin()
        sid, runner, hb = self.station(f"st-{uuid.uuid4().hex[:6]}")
        pa, (a1, a2, a3) = self.process(3)
        self.save(pa, [(a1, True), (a2, False), (a3, True)])
        pb, (b1,) = self.process(1)
        self.save(pb, [(b1, True), (a2, True)])
        e = self.start(sid, pa)
        out = a.call("DELETE", f"/api/v1/routines/{a2}")
        self.assertEqual(sorted(out["processes"]), sorted([f"p-{pa}", f"p-{pb}"]))
        self.assertEqual(self.items(pa), [(1, a1, True), (2, a3, True)])
        self.assertEqual(self.items(pb), [(1, b1, True)])
        self.assertNotIn(a2, [r["id"] for r in a.call("GET", "/api/v1/routines")])
        self.assertEqual(len(a.call("GET", f"/api/v1/routines/{a2}/versions")), 1)  # versions kept
        self.assertEqual([s["routine_id"] for s in a.call("GET", f"/api/v1/executions/{e['id']}")["steps"]], [a1, a2, a3])  # snapshot kept
        alone = self.routine()
        a.call("DELETE", f"/api/v1/routines/{alone}")  # a standalone one, as before
        self.expect("NOT-FOUND", lambda: a.call("DELETE", f"/api/v1/routines/{alone}"), 404)
        # The first and only step: the process is left empty and does not run (nor does its schedule).
        pc, (c1,) = self.process(1)
        sched = a.call("POST", "/api/v1/schedules", {"process_id": pc, "station_id": sid, "weekdays": [1, 2, 3, 4, 5, 6, 7],
                                                    "hour": 5, "minute": 0, "timezone": "America/Sao_Paulo"})
        a.call("DELETE", f"/api/v1/routines/{c1}")
        self.assertEqual(self.items(pc), [])
        self.expect("PROCESS-START-INVALID", lambda: self.start(sid, pc), 409)
        with self.su() as c:
            c.execute("UPDATE schedules SET enabled = false, next_run_at = NULL WHERE id <> %s", (sched["id"],))
        runner.call("POST", "/api/v1/runner/heartbeat", hb)
        self.h.core.schedule_tick(datetime.fromisoformat(sched["next_run_at"]) + timedelta(seconds=5))
        row = next(s for s in a.call("GET", "/api/v1/schedules") if s["id"] == sched["id"])
        self.assertEqual((row["enabled"], row["paused_reason"]), (False, "process_unavailable"))

    def test_13_deletion_rules_kept(self):
        a = self.admin()
        _, op = self.operator()
        r = self.routine()
        self.expect("AUTH-FORBIDDEN", lambda: op.call("DELETE", f"/api/v1/routines/{r}"), 403)
        welcome = next(p for p in a.call("GET", "/api/v1/processes") if p["system_key"])
        self.expect("VALIDATION", lambda: a.call("DELETE", f"/api/v1/routines/{welcome['items'][0]['routine_id']}"), 400)
        self.assertEqual(len(next(p for p in a.call("GET", "/api/v1/processes") if p["system_key"])["items"]), 3)
        # A pending replacement whose new routine is deleted is cancelled, never applied.
        pid, (r1,) = self.process(1)
        new = self.routine()
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        a.call("DELETE", f"/api/v1/routines/{new}")
        self.assertEqual(next(x for x in a.call("GET", "/api/v1/step-changes") if x["id"] == q["id"])["status"], "cancelled")
        self.assertEqual(self.items(pid), [(1, r1, True)])


if __name__ == "__main__":
    unittest.main()
