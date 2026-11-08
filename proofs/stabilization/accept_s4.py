"""Practical acceptance of S4 of work order STABILIZATION-REAL-UI-20261107 on the installed
candidate: the fixes of S1 to S3 and the short flow of the work order, on the real app, Core,
Runner and Windows, with the isolated synthetic team of the lab. Run on C: with the private
runtime of the install, computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_s4.py --lab <lab-test> --shots <dir> [--only a,b]

Reuses the harness of proofs/nova-rotina/accept_increments.py (copied next to this file in the
lab): isolated data folder and vault namespace, stops if someone uses the computer, opens only
the Calculator and closes only windows it opened. Passwords are read from the lab account file or
generated here and never printed.

 migration      the team written by the previous version reopens on this one: every table count and the
                API counts equal the baseline the previous version recorded just before (--baseline,
                from rollback_check.py --baseline-with), taken before this proof adds anything.
 empresa        every Empresa indicator equals what the Core counts; the attention card opens the
                Historico with the same period total and exactly summary.attention rows listed.
 radios         the assistant's radios have names in the Windows tree and the name alone chooses one.
 start          cadastrar rotina -> preparar (opens nothing) -> testar (opens it).   [accept_increments]
 review         execute process -> pause -> bell -> Aprovado! -> verified.          [accept_increments]
 report         execute -> PDF saved -> Historico row -> Veja aqui! opens its folder.  [accept_increments]
 cancel         cancel accepted while step 1 runs on the real Runner: step 2 never starts.
 roles          operator reads, administrator-only actions refused to the operator.
 empresa_after  with Empresa open, a new execution changes the cards without navigating, and they
                equal the Core again (Marcados para mim included).
 limits         5 wrong passwords -> 429 with Retry-After; a signed-in session keeps working;
                after the wait the right password signs in."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "nova-rotina"))  # the private runtime runs isolated: no script folder on sys.path

import accept_increments as base  # noqa: E402
from redrise_contracts.client import CoreClient, CoreError  # noqa: E402

Stop = base.Stop
GROUPS = {"running": "Em andamento", "waiting": "Aguardando revisão", "attention": "Precisam de atenção", "verified": "Verificadas"}
CARD = re.compile(r"^Button\|(.+?): (.+?)\. (Ver no histórico|Ver processos|Ver pedidos|Ver estações)\|?")


class Lab(base.Lab):
    baseline: dict | None = None

    # ---------------------------------------------------------------- helpers
    def cards(self) -> dict[str, str]:
        out = {}
        for line in self.texts():
            m = CARD.match(line)
            if m:
                out[m.group(1)] = m.group(2)
        return out

    def expected(self) -> dict[str, str]:
        s = self.api.call("GET", "/api/v1/executions/summary")
        st = self.api.call("GET", "/api/v1/stations")
        active = [x for x in st if not x.get("revoked")]  # the same rule as the screen (features/empresa.tsx)
        ready = [x for x in active if x.get("online") and x.get("session_state") == "ready"]
        exp = {"Processos cadastrados": str(len(self.api.call("GET", "/api/v1/processes"))),
               f"Execuções nos últimos {s['days']} dias": str(s["total"]),
               "Estações disponíveis": f"{len(ready)} de {len(active)}"}
        exp.update({GROUPS[g]: str(s[g]) for g in GROUPS})
        exp["Marcados para mim"] = str(len([r for r in self.api.call("GET", "/api/v1/reviews") if r.get("status") == "pending"]))
        return exp

    def compare_empresa(self, tries: int = 6) -> dict:
        """Screen against Core. The screen follows changes within seconds; a few reads absorb that."""
        last = {}
        for _ in range(tries):
            exp, seen = self.expected(), self.cards()
            diff = {k: {"screen": seen.get(k), "core": v} for k, v in exp.items() if seen.get(k) != v}
            last = {"expected": exp, "screen": seen, "diff": diff}
            if not diff:
                return {"passed": True, **last}
            time.sleep(2)
        return {"passed": False, **last}

    def empresa(self) -> None:
        """Empresa is a top-level menu button in the sidebar (the sub-items, like Lista, are links)."""
        self.invoke("Empresa", "Button")
        time.sleep(1.2)

    def calc(self) -> dict:
        return next(a for a in self.api.call("GET", f"/api/v1/stations/{self.station}/apps")["apps"] if a["name"] == base.APP)

    # ---------------------------------------------------------------- scenarios
    def s_migration(self) -> dict:
        """Run first, before this proof adds anything (review R4)."""
        if not self.baseline:
            raise Stop("no --baseline: data preservation cannot be compared")
        sys.path.insert(0, str(HERE))
        from rollback_check import table_counts
        from redrise_contracts.vault import WindowsVault
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        tables = table_counts(cfg["pg_port"], WindowsVault("rrtest2-host"), "redrise")
        api = {"processes": len(self.api.call("GET", "/api/v1/processes")), "routines": len(self.api.call("GET", "/api/v1/routines")),
               "executions_listed": len(self.api.call("GET", "/api/v1/executions")), "users": len(self.api.call("GET", "/api/v1/users"))}
        welcome = [p for p in self.api.call("GET", "/api/v1/processes") if p["system_key"]]
        b_api = {k: self.baseline["api"].get(k) for k in api}
        ok = tables == self.baseline["tables"] and api == b_api and len(welcome) == 1 and len(welcome[0]["items"]) == 3
        return {"passed": ok, "baseline_from": self.baseline.get("install"), "tables": tables, "baseline_tables": self.baseline["tables"],
                "api": api, "baseline_api": b_api}

    def s_empresa(self) -> dict:
        self.empresa()
        self.wait("Ver no histórico", timeout=30)
        time.sleep(2)
        out = self.compare_empresa()
        self.shot("s4-empresa")
        s = self.api.call("GET", "/api/v1/executions/summary")
        label = f"{GROUPS['attention']}: {s['attention']}. Ver no histórico"
        self.invoke(label)
        self.wait("Iniciadas nos últimos", "Ver todas as recentes", timeout=20)
        time.sleep(1.5)
        lines = self.texts()  # the banner reaches the Windows tree in pieces (text, number, text): join them
        i = next((k for k, line in enumerate(lines) if "Iniciadas nos últimos" in line), 0)
        banner = "".join(line.split("|")[1] for line in lines[i:i + 8] if line.startswith("Text|")).split("Ver todas")[0]
        m = re.search(r"Iniciadas nos últimos \s*(\d+)\s* dias\s*:\s*(\d+)\s*execuç", banner)
        period_rows = int(m.group(2)) if m and int(m.group(1)) == s["days"] else None
        rows = self.api.call("GET", f"/api/v1/executions?days={s['days']}")
        shown = next((line for line in lines if "Mostrando " in line or "Nenhuma linha" in line), "")
        n = re.search(r"de (\d+) linhas?", shown)
        tab_rows = int(n.group(1)) if n else (0 if "Nenhuma linha" in shown else None)
        self.shot("s4-historico-periodo")
        out.update({"opened": label, "banner": banner[:120], "period_rows_screen": period_rows, "period_rows_core": len(rows),
                    "summary_total": s["total"], "attention_rows_screen": tab_rows, "summary_attention": s["attention"]})
        out["passed"] = out["passed"] and period_rows == s["total"] == len(rows) and tab_rows == s["attention"]
        return out

    def s_radios(self) -> dict:
        self.guard()
        self.page("Lista")
        self.invoke("Nova Rotina")
        self.wait("Nome da rotina")
        time.sleep(1)
        radios = [line.split("|")[1] for line in self.texts() if line.startswith("RadioButton|")]
        self.fill("Nome da rotina", f"Radios {self.seq}")
        chosen = self.ui("-Do", "invoke", "-Name", "Fazer follow-up", "-Type", "RadioButton").stdout  # the name alone, no label click
        if "invoked" not in chosen:
            chosen = self.ui("-Do", "click", "-Name", "Fazer follow-up", "-Type", "RadioButton").stdout
        end = time.monotonic() + 5
        while time.monotonic() < end and not self.has("Etapa anterior"):
            time.sleep(0.4)
        took = self.has("Etapa anterior")
        self.shot("s4-radios")
        self.invoke("Cancelar")
        time.sleep(1)
        created = [r for r in self.api.call("GET", "/api/v1/routines") if r["name"] == f"Radios {self.seq}"]
        want = {"Iniciar um processo", "Fazer follow-up", "Rotina avulsa"}
        return {"passed": want <= set(radios) and all(radios) and took and not created, "radios": radios,
                "chosen_by_name": took, "routine_created": bool(created)}

    def s_cancel(self) -> dict:
        calc = self.calc()
        cfg = {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}
        tries = []
        for attempt in range(3):
            p = self.empty_process(f"Prova cancelar {self.seq}-{attempt}")
            self.api.call("POST", "/api/v1/routines", {"name": f"Cancelar 1 {self.seq}-{attempt}", "category": "windows", "version": cfg, "link": {"process_id": p["id"]}})
            r2 = self.api.call("POST", "/api/v1/routines", {"name": f"Cancelar 2 {self.seq}-{attempt}", "category": "windows", "version": cfg})["routine"]["id"]
            self.api.call("POST", f"/api/v1/processes/{p['id']}/items", {"routine_id": r2})
            items = self.api.call("GET", f"/api/v1/processes/{p['id']}")["items"]
            self.guard()
            before = base.calc_windows()
            e = self.api.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": self.station, "process_id": p["id"]})
            state, answer = None, None
            end = time.monotonic() + 30
            while time.monotonic() < end:
                step = self.api.call("GET", f"/api/v1/executions/{e['id']}")["steps"][0]
                if step["state"] == "running":
                    try:
                        answer = self.api.call("POST", f"/api/v1/jobs/{step['job_id']}/cancel")
                        state = "running"
                    except CoreError as err:
                        answer = {"refused": err.diagnostic.error_code}
                    break
                if step["state"] not in (None, "queued", "claimed"):
                    break
                time.sleep(0.15)
            done = self.wait_execution(e["id"], ("finished",), timeout=90)
            time.sleep(1)
            left = self.close_new_calc(before)
            t = {"cancel_while": state, "answer": answer, "outcome": done["outcome"], "end_reason": done.get("end_reason"),
                 "steps": [s["state"] for s in done["steps"]], "continue_next": [i.get("continue_next") for i in items], "not_closed": len(left)}
            tries.append(t)
            if state == "running" and not (answer or {}).get("refused"):
                ok = (done["outcome"] == "cancelled" and done["steps"][1]["state"] is None and len(items) == 2 and not left)
                self.page("Histórico")
                time.sleep(1.5)
                self.shot("s4-cancelada")
                return {"passed": ok, "attempts": tries}
        return {"passed": False, "attempts": tries, "note": "step 1 never seen running before it finished"}

    def s_roles(self) -> dict:
        name = f"oper.s4.{self.seq}"
        pw = secrets.token_urlsafe(12)
        self.api.call("POST", "/api/v1/users", {"username": name, "display": f"Operador S4 {self.seq}", "password": pw, "role": "operator"})
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        tok = CoreClient("127.0.0.1", base.PORT, cfg["fingerprint"]).call("POST", "/api/v1/login", {"username": name, "password": pw})["token"]
        op = CoreClient("127.0.0.1", base.PORT, cfg["fingerprint"], tok)

        def code(fn):
            try:
                fn()
                return "allowed"
            except CoreError as e:
                return e.diagnostic.error_code

        out = {
            "operator_reads_summary": code(lambda: op.call("GET", "/api/v1/executions/summary")),
            "operator_reads_processes": code(lambda: op.call("GET", "/api/v1/processes")),
            "operator_lists_users": code(lambda: op.call("GET", "/api/v1/users")),
            "operator_creates_user": code(lambda: op.call("POST", "/api/v1/users", {"username": f"x.{self.seq}", "password": secrets.token_urlsafe(12), "role": "admin"})),
            "operator_registers_station": code(lambda: op.call("POST", "/api/v1/stations", {"name": f"x-{self.seq}"})),
            "operator_creates_routine": code(lambda: op.call("POST", "/api/v1/routines", {"name": f"x-{self.seq}", "category": "windows"})),
            "no_token_reads_summary": code(lambda: CoreClient("127.0.0.1", base.PORT, cfg["fingerprint"]).call("GET", "/api/v1/executions/summary")),
        }
        uid = next(u["id"] for u in self.api.call("GET", "/api/v1/users") if u["username"] == name)
        self.api.call("PATCH", f"/api/v1/users/{uid}", {"active": False})
        out["after_deactivation"] = code(lambda: op.call("GET", "/api/v1/me"))
        self._op = (name, pw, uid)
        want = {"operator_reads_summary": "allowed", "operator_reads_processes": "allowed", "operator_lists_users": "AUTH-FORBIDDEN",
                "operator_creates_user": "AUTH-FORBIDDEN", "operator_registers_station": "AUTH-FORBIDDEN",
                "operator_creates_routine": "AUTH-FORBIDDEN", "no_token_reads_summary": "AUTH-REQUIRED", "after_deactivation": "AUTH-REQUIRED"}
        return {"passed": out == want, **out}

    def s_empresa_after(self) -> dict:
        self.empresa()
        self.wait("Ver no histórico", timeout=30)
        time.sleep(2)
        before = self.compare_empresa()
        total0 = int(before["screen"].get(f"Execuções nos últimos 30 dias", "-1") or -1)
        calc = self.calc()
        rid = self.api.call("POST", "/api/v1/routines", {"name": f"Ao vivo empresa {self.seq}", "category": "windows", "version": {
            "kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}})["routine"]["id"]
        self.guard()
        wins = base.calc_windows()
        e = self.api.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": self.station, "routine_id": rid})
        self.wait_execution(e["id"], ("finished",))
        time.sleep(1)
        left = self.close_new_calc(wins)
        start = time.monotonic()
        seen_total = None
        while time.monotonic() - start < 15:  # no navigation: only the change feed and the periodic read move it
            seen_total = self.cards().get("Execuções nos últimos 30 dias")
            if seen_total == str(total0 + 1):
                break
            time.sleep(0.5)
        after = self.compare_empresa()
        self.shot("s4-empresa-depois")
        return {"passed": before["passed"] and after["passed"] and seen_total == str(total0 + 1) and not left,
                "total_before": total0, "total_on_screen_after": seen_total, "seconds": round(time.monotonic() - start, 1),
                "before": before["diff"], "after": after}

    def s_limits(self) -> dict:
        """Last: the client address of this computer waits after it, and the app shares it."""
        name, pw, uid = getattr(self, "_op", (None, None, None))
        if not name:
            raise Stop("roles must run first (it creates the synthetic operator)")
        self.api.call("PATCH", f"/api/v1/users/{uid}", {"active": True})
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        import http.client
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE

        def login(password):
            conn = http.client.HTTPSConnection("127.0.0.1", base.PORT, context=ctx, timeout=15)
            try:
                conn.request("POST", "/api/v1/login", body=json.dumps({"username": name, "password": password}).encode(),
                             headers={"Content-Type": "application/json"})
                r = conn.getresponse()
                body = json.loads(r.read() or b"{}")
                return r.status, r.getheader("Retry-After"), (body.get("diagnostic") or {}).get("error_code")
            finally:
                conn.close()

        wrong = [login("errada-" + secrets.token_hex(4)) for _ in range(5)]
        limited = login(pw)
        session_ok = self.api.call("GET", "/api/v1/me")["username"] is not None  # the signed-in admin keeps working
        wait = int(limited[1] or 0)
        time.sleep(wait + 1)
        recovered = login(pw)
        self.api.call("PATCH", f"/api/v1/users/{uid}", {"active": False})
        ok = (all(w[0] == 401 for w in wrong) and limited[0] == 429 and limited[2] == "AUTH-RATE-LIMITED" and wait == 60
              and session_ok and recovered[0] == 200)
        return {"passed": ok, "wrong": [w[0] for w in wrong], "limited": list(limited), "session_kept": session_ok,
                "after_wait": recovered[0], "core": self.api.call("GET", "/api/v1/status")["core"]}


SCENARIOS = ("migration", "empresa", "radios", "start", "review", "report", "cancel", "roles", "empresa_after", "limits")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--baseline", type=Path, help="counts recorded by the previous version (rollback_check.py --baseline-with)")
    args = ap.parse_args()
    args.shots.mkdir(parents=True, exist_ok=True)
    wanted = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]
    lab = Lab(args.lab, args.shots)
    if args.baseline:
        lab.baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "work_order": "STABILIZATION-REAL-UI-20261107/S4",
                    "install": base.ROOT.name, "scenarios": {}}
    started = time.time()
    try:
        lab.guard()
        lab.start_app()
        report["core"] = lab.api.call("GET", "/api/v1/status")["core"]
        for s in wanted:
            print("scenario", s, flush=True)
            try:
                report["scenarios"][s] = getattr(lab, f"s_{s}")()
            except (Stop, CoreError) as e:
                report["scenarios"][s] = {"passed": False, "stopped": str(e)[:1500]}
                try:
                    lab.shot(f"s4-falha-{s}")
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e):
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False)[:500], flush=True)
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["passed"] = bool(report["scenarios"]) and len(report["scenarios"]) == len(wanted) and all(v.get("passed") for v in report["scenarios"].values())
    out = args.lab / f"accept-s4-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
