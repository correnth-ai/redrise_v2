"""Practical acceptance of work order ACCOUNT-ERASURE-20261109 on the installed candidate: real app window, Core
and Windows, with the isolated synthetic team of the lab. Run on C: with the private runtime of the install,
computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_erasure.py --lab <lab-test> --shots <dir> --baseline <json>

Reuses proofs/team-accounts (and what it reuses), copied next to this folder in the lab. The isolated instance is
driven and closed by its own process id only. Passwords of the synthetic accounts are generated here, kept in memory
and never printed.

 migration  the team written by the previous version reopens: every table keeps its count, migration 012 is the only
            new one, a backup was written before migrating, and every account deleted before it is erased
            (no e-mail, no password, no identity link).
 reuse      the user's case: an account is deleted through the screen (its dialog says the e-mail becomes free), then
            + Nova Conta with the same e-mail goes through the four steps and creates a new, active account with
            another id and user name; it signs in with its own password; the deleted one stays erased and out of the list."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "team-accounts"))
sys.path.insert(0, str(HERE.parent / "nova-rotina"))
sys.path.insert(0, str(HERE.parent / "stabilization"))
sys.path.insert(0, str(HERE.parent / "schedules"))

import accept_team  # noqa: E402
from accept_team import Stop, base  # noqa: E402
from redrise_contracts.client import CoreError  # noqa: E402


class Lab(accept_team.Lab):
    def sql(self, query: str, params=()) -> list[tuple]:
        """Read-only look at the isolated lab database (synthetic team, lab vault rrtest2)."""
        import psycopg
        from redrise_contracts.vault import WindowsVault
        from redrise_core import db, pg
        pw = WindowsVault("rrtest2-host").get("pg-superuser")
        with psycopg.connect(db.conninfo(self.cfg["pg_port"], pg.SUPERUSER, pw, "redrise")) as c:
            return c.execute(query, params).fetchall()

    def s_migration(self) -> dict:
        out = super().s_migration()
        names = [r[0] for r in self.sql("SELECT name FROM schema_migrations ORDER BY name")]
        left = self.sql("""SELECT count(*) FROM users u WHERE u.deleted_at IS NOT NULL
                           AND (u.email IS NOT NULL OR u.pw_hash <> '!' OR EXISTS (SELECT 1 FROM identity_links l WHERE l.user_id = u.id))""")[0][0]
        deleted = self.sql("SELECT count(*) FROM users WHERE deleted_at IS NOT NULL")[0][0]
        out.update(newest_migration=names[-1], deleted_accounts=deleted, deleted_not_erased=left)
        out["passed"] = out["passed"] and names[-1] == "012_account_erasure.sql" and left == 0
        return out

    def s_reuse(self) -> dict:
        old, mail, old_pw = self.account("Conta Reusada")
        self.api.call("PATCH", f"/api/v1/users/{old['id']}", {"active": False})
        self.guard()
        self.page("Aplicativo")
        self.page("Equipe")
        self.wait(mail)
        self.invoke_at("Excluir conta", self.button_in_row(mail, "Excluir conta", stop_at="@"))
        self.wait("o e-mail fica livre para uma conta nova", timeout=10)
        self.shot("excluir-conta-email-livre")
        self.invoke_last("Excluir conta")
        self.gone(mail)
        before = {u["id"] for u in self.api.call("GET", "/api/v1/users")}
        self.invoke("Nova Conta")
        self.wait("Nome completo", "Continuar", timeout=15)
        name, pw = f"Conta Nova {self.seq}", secrets.token_urlsafe(12)
        self.fill("Nome completo", name)
        self.invoke("Continuar")
        self.wait("E-mail", timeout=10)
        self.fill("E-mail", mail)
        self.invoke("Continuar")
        self.wait("Senha (mínimo 8 caracteres)", timeout=10)
        self.fill("Senha (mínimo 8 caracteres)", pw, check=False)
        self.invoke("Continuar")
        self.wait("Confirmar senha", timeout=10)
        self.fill("Confirmar senha", pw, check=False)
        self.invoke("Criar conta")
        self.wait("Meu perfil", mail, timeout=30)  # back on Equipe: created, no refusal
        self.shot("nova-conta-email-reusado")
        refused = self.has("ACCOUNT-EMAIL-RESERVED")
        new = [u for u in self.api.call("GET", "/api/v1/users") if u["id"] not in before]
        row = self.after(mail, n=3)
        me = self.client(self.client().call("POST", "/api/v1/login", {"username": mail, "password": pw})["token"]).call("GET", "/api/v1/me")
        old_login = self.code(lambda: self.client().call("POST", "/api/v1/login", {"username": mail, "password": old_pw}))
        erased = self.sql("SELECT email IS NULL, pw_hash = '!', deleted_at IS NOT NULL, display, username FROM users WHERE id = %s", (old["id"],))[0]
        one = len(new) == 1
        ok = (not refused and one and new[0]["id"] != old["id"] and new[0]["email"] == mail and new[0]["active"]
              and new[0]["username"] != old["username"] and me["id"] == new[0]["id"] and old_login == "AUTH-INVALID"
              and erased[:3] == (True, True, True) and erased[3] == old["display"] and erased[4] == old["username"] and "Ativa" in row)
        return {"passed": ok, "refused_on_screen": refused, "created": len(new), "new_is_another_account": one and new[0]["id"] != old["id"],
                "new_username_differs": one and new[0]["username"] != old["username"], "row": row, "own_login": me["id"] == (new[0]["id"] if one else None),
                "old_password": old_login, "old_row": {"email_erased": erased[0], "password_erased": erased[1], "deleted": erased[2],
                                                       "display_kept_for_history": erased[3] == old["display"]}}


SCENARIOS = ("migration", "reuse")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True, help="counts recorded by the previous version (rollback_check.py --baseline-with)")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    wanted = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]
    args.shots.mkdir(parents=True, exist_ok=True)
    lab = Lab(args.lab, args.shots)
    lab.created = []
    lab.baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    lab.baseline_path = str(args.baseline)
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "work_order": "ACCOUNT-ERASURE-20261109",
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
            except (Stop, CoreError, StopIteration, AttributeError, IndexError) as e:
                report["scenarios"][s] = {"passed": False, "stopped": f"{type(e).__name__}: {str(e)[:1500]}"}
                try:
                    lab.shot(f"erasure-falha-{s}")
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e):
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False)[:600], flush=True)
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["only"] = wanted if args.only else None
    report["passed"] = len(report["scenarios"]) == len(wanted) and all(v.get("passed") for v in report["scenarios"].values())
    out = args.lab / f"accept-erasure-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
