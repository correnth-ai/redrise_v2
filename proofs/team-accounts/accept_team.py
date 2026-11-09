"""Practical acceptance of work order TEAM-ACCOUNTS-20261108 (items 1-7, 9 and 11) on the installed candidate:
real app window, Core, Runner and Windows, with the isolated synthetic team of the lab. Run on C: with the
private runtime of the install, computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_team.py --lab <lab-test> --shots <dir> --baseline <json>

Reuses the harness of proofs/nova-rotina, proofs/stabilization and proofs/schedules (copied next to this folder
in the lab). The isolated instance is driven and closed by its own process id only: an installed RedRise that is
open stays untouched. Stops if someone uses the computer. Passwords of the synthetic accounts and the runner token
of the synthetic station are generated here, kept in memory and never printed.

 migration  the team written by the previous version reopens: every table keeps its count, migration 011 is the
            only new one, a backup was written before migrating.
 account    + Nova Conta through the screen (position in Meu perfil, validation, four steps); exactly one active
            operator; its OWN login by e-mail, logout and login again (not the administrator's session).
 delete     an inactive account: Cancelar keeps it; Excluir conta removes it after the Core; the list read again
            does not show it; it cannot sign in; reactivation is refused; its e-mail opens a new account (since
            ACCOUNT-ERASURE-20261109; before, it was refused as reserved).
 stations   Status apart from Estado; Esta estacao cannot be revoked; a synthetic station goes Online -> Offline
            within the documented limit and back; revoked through the screen, then deleted; API refusals.
 links      Processo > Acao: Cancelar keeps the composition; step 1 removed and saved without approval; the only
            routine removed: empty process saved and refused when run.
 routines   Rotina > Lista: a routine in two processes deleted (Cancelar first), then a mixed selection.
 jobs       Rotina > Atividade: only the eye shows and hides the details of its row; nothing is run.
 app        Configuracao > Aplicativo: no browser block, Sobre inside the server card, storage right below.
 visual     Lista with a selected row and Empresa/sidebar in light and dark, sidebar collapsed (screenshots).
 window     green maximizes and restores, yellow minimizes; red closes (at the end, by this instance's id).
 restart    the app reopens and the new operator signs in through the screen; data are still there."""

from __future__ import annotations

import argparse
import ctypes
import json
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "nova-rotina"))  # the private runtime runs isolated: no script folder on sys.path
sys.path.insert(0, str(HERE.parent / "stabilization"))
sys.path.insert(0, str(HERE.parent / "schedules"))

import accept_increments as base  # noqa: E402
import accept_schedule  # noqa: E402
from redrise_contracts.client import CoreClient, CoreError  # noqa: E402

Stop = base.Stop
HB = {"platform": "windows-x86_64", "categories": ["windows"], "runner_version": "0.3.11", "session_state": "ready", "session_reason": None}
ONLINE_S, POLL_S = 45, 10  # Core (service.ONLINE_S) and screen (configuracoes.STATIONS_POLL_MS)
CELL = ("Text", "DataItem")  # table cells reach UI Automation as DataItem

_u32 = ctypes.windll.user32
_k32 = ctypes.windll.kernel32


def alive(pid: int) -> bool:
    h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    _k32.GetExitCodeProcess(h, ctypes.byref(code))
    _k32.CloseHandle(h)
    return code.value == 259  # STILL_ACTIVE


def window_of(pid: int) -> int:
    found = []
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        p = ctypes.c_ulong()
        _u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        cls = ctypes.create_unicode_buffer(64)
        _u32.GetClassNameW(h, cls, 64)
        if p.value == pid and cls.value == "Tauri Window":
            found.append(h)
            return False
        return True
    _u32.EnumWindows(proto(cb), 0)
    if not found:
        raise Stop("window of the test instance not found")
    return found[0]


class Lab(accept_schedule.Lab):
    # ---------------------------------------------------------------- harness, by process id
    def start_as(self, user: str, password: str) -> None:
        env = {**base.os.environ, "REDRISE_DATA_ROOT": str(self.lab / "data"), "REDRISE_TEST_VAULT": "rrtest2",
               "WEBVIEW2_USER_DATA_FOLDER": str(self.lab / "webview")}
        self.pid = subprocess.Popen([str(base.ROOT / "RedRise.exe")], env=env, close_fds=True).pid
        (self.lab / "pid.txt").write_text(str(self.pid), encoding="ascii")
        self.wait("E-mail ou usu", timeout=120)
        self.cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        if self.cfg.get("lan_port") != base.PORT:
            raise Stop("not the isolated team")
        self.fill("E-mail ou usuário", user)
        for _ in range(3):  # right after the window comes up the first keys can be lost; the browser then blocks the empty field
            self.fill("Senha", password, check=False)
            self.invoke("Entrar")
            time.sleep(2)
            if not self.has("Preencha este campo"):
                break
        self.wait("Sair", timeout=60)

    def client(self, token: str | None = None, by: str = "RR-UI") -> CoreClient:
        return CoreClient("127.0.0.1", base.PORT, self.cfg["fingerprint"], token, reported_by=by)

    def start_app(self) -> None:
        self.start_as(self.acct["admin_user"], self.acct["admin_password"])
        # The script's own session has no station proof (as any client but the desktop): it must not revoke stations.
        self.api = self.client(self.client().call("POST", "/api/v1/login", {"username": self.acct["admin_user"], "password": self.acct["admin_password"]})["token"])
        end = time.monotonic() + 90
        while time.monotonic() < end:
            ready = [s for s in self.api.call("GET", "/api/v1/stations") if s.get("online") and s.get("session_state") == "ready"]
            if ready:
                self.station = ready[0]["id"]
                return
            time.sleep(2)
        raise Stop("station not ready")

    def close_app(self) -> None:
        if not self.pid or not alive(self.pid):
            return
        try:
            self.ui("-Do", "keys", "-Value", "{ESC}")  # closes an open dialog; needs the foreground
        except Stop:
            pass  # Fechar below is a UI Automation invoke: it does not need the foreground
        for _ in range(4):
            self.ui("-Do", "invoke", "-Name", "Fechar", "-Type", "Button")
            end = time.monotonic() + 20
            while time.monotonic() < end:
                if not alive(self.pid):
                    return
                time.sleep(1)

    # ---------------------------------------------------------------- screen helpers
    def after(self, key: str, kinds=CELL, n: int = 8) -> list[str]:
        """Names of the next n elements of the given kinds after the first cell or text containing `key` (one table row).
        Table cells reach UI Automation as DataItem."""
        out, seen = [], False
        for line in self.texts():
            kind, name = (line.split("|") + ["", ""])[:2]
            if not seen:
                seen = kind in CELL and key in name
                continue
            if kind in kinds:
                out.append(name)
                if len(out) >= n:
                    break
        if not seen:
            raise Stop(f"row not on screen: {key}")
        return out

    def button_in_row(self, key: str, button: str, stop_at: str | None = None) -> int:
        """Index of the first button `button` after the row text `key`; `stop_at` (a text marking another row) aborts."""
        idx, seen = -1, False
        for line in self.texts():
            kind, name = (line.split("|") + ["", ""])[:2]
            if seen and stop_at and kind in CELL and stop_at in name and key not in name:
                break
            if kind == "Button" and name == button:
                idx += 1
                if seen:
                    return idx
            if kind in CELL and key in name:
                seen = True
        raise Stop(f"no {button} in the row of {key}")

    def invoke_at(self, name: str, index: int, kind: str = "Button") -> None:
        out = self.ui("-Do", "invoke", "-Name", name, "-Type", kind, "-Index", str(index))
        if "invoked" not in out.stdout:
            raise Stop(f"could not invoke {name} #{index}: {out.stderr[:300]}")

    def invoke_last(self, name: str) -> None:
        """Dialog buttons are rendered after the page: the last element with this name."""
        n = sum(1 for line in self.texts() if line.startswith(f"Button|{name}|"))
        if not n:
            raise Stop(f"no button {name}")
        self.invoke_at(name, n - 1)

    def gone(self, *needles: str, timeout: float = 20.0) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            lines = self.texts()
            if not any(any(n in line for line in lines) for n in needles):
                return
            time.sleep(1)
        raise Stop(f"still on screen: {needles}")

    def items(self, pid: int) -> list[int]:
        return [i["routine_id"] for i in self.api.call("GET", f"/api/v1/processes/{pid}")["items"]]

    def code(self, fn) -> str:
        try:
            fn()
            return "accepted"
        except CoreError as e:
            return e.diagnostic.error_code

    def account(self, name: str) -> tuple[dict, str, str]:
        email, pw = f"{name.lower().replace(' ', '.')}.{self.seq}@exemplo.test", secrets.token_urlsafe(12)
        u = self.api.call("POST", "/api/v1/accounts", {"full_name": f"{name} {self.seq}", "email": email, "password": pw})
        return u, email, pw

    # ---------------------------------------------------------------- scenarios
    def s_migration(self) -> dict:
        from rollback_check import table_counts
        from redrise_contracts.vault import WindowsVault
        tables = table_counts(self.cfg["pg_port"], WindowsVault("rrtest2-host"), "redrise")
        b = self.baseline["tables"]
        kept = {t: (tables.get(t), n) for t, n in b.items() if t != "schema_migrations"}
        backups = sorted((self.lab / "data" / "host" / "backups").glob("pre-migration-*.dump"), key=lambda p: p.stat().st_mtime)
        newest = backups[-1] if backups else None
        ok = (all(now == was for now, was in kept.values()) and tables.get("schema_migrations") == b.get("schema_migrations", 0) + 1
              and newest is not None and newest.stat().st_mtime >= Path(self.baseline_path).stat().st_mtime)
        return {"passed": ok, "baseline_from": self.baseline.get("install"), "tables": tables, "baseline_tables": b,
                "changed": {t: v for t, v in kept.items() if v[0] != v[1]}, "backup_before_migration": newest.name if newest else None}

    def s_account(self) -> dict:
        self.guard()
        self.page("Equipe")
        self.wait("Meu perfil", "Nova Conta")
        if any(line.startswith("Button|Adicionar|") or line.startswith("Edit|Usuário|") for line in self.texts()):
            raise Stop("the old inline form is still on screen")
        self.shot("equipe-nova-conta")
        before = {u["id"] for u in self.api.call("GET", "/api/v1/users")}
        self.invoke("Nova Conta")
        self.wait("Nome completo", "Continuar", "Confirmar senha", timeout=15)  # the step rail names all four steps
        self.invoke("Continuar")
        self.wait("Informe o nome completo da pessoa.", timeout=10)  # validated before going on
        name, email, pw = f"Pessoa Prova {self.seq}", f"pessoa.prova.{self.seq}@exemplo.test", secrets.token_urlsafe(12)
        self.fill("Nome completo", name)
        self.invoke("Continuar")
        self.wait("E-mail", timeout=10)
        self.fill("E-mail", "sem-arroba")
        self.invoke("Continuar")
        self.wait("Informe um e-mail válido", timeout=10)
        self.fill("E-mail", email)
        self.invoke("Continuar")
        self.wait("Senha (mínimo 8 caracteres)", timeout=10)
        self.fill("Senha (mínimo 8 caracteres)", pw, check=False)
        self.invoke("Continuar")
        self.wait("Confirmar senha", timeout=10)
        self.fill("Confirmar senha", pw + "x", check=False)
        self.invoke("Criar conta")
        self.wait("As senhas não coincidem.", timeout=10)
        self.shot("nova-conta-confirmar")
        if {u["id"] for u in self.api.call("GET", "/api/v1/users")} != before:
            raise Stop("an account was saved before the last step")
        self.fill("Confirmar senha", pw, check=False)
        self.invoke("Criar conta")
        self.wait("Meu perfil", email, timeout=30)  # back on Equipe, the list read again
        self.shot("equipe-conta-criada")
        new = [u for u in self.api.call("GET", "/api/v1/users") if u["id"] not in before]
        row = self.after(email, n=3)
        own = self.client(self.client().call("POST", "/api/v1/login", {"username": email, "password": pw})["token"])
        me = own.call("GET", "/api/v1/me")
        own.call("POST", "/api/v1/logout")
        out_after_logout = self.code(lambda: own.call("GET", "/api/v1/me"))
        again = self.client(self.client().call("POST", "/api/v1/login", {"username": email, "password": pw})["token"]).call("GET", "/api/v1/me")
        self.new_account = (email, pw, name)
        ok = (len(new) == 1 and new[0]["email"] == email and new[0]["active"] and new[0]["role"] == "operator" and (new[0]["full_name"] or new[0]["display"]) == name
              and me["id"] == new[0]["id"] and out_after_logout == "AUTH-REQUIRED" and again["id"] == new[0]["id"] and "Ativa" in row)
        return {"passed": ok, "created": len(new), "role": new[0]["role"] if new else None, "row": row, "own_login": me["role"],
                "after_logout": out_after_logout, "login_again": again["id"] == (new[0]["id"] if new else None)}

    def s_delete(self) -> dict:
        b, b_mail, _ = self.account("Inativa Mantida")
        c, c_mail, c_pw = self.account("Inativa Excluida")
        self.guard()
        self.page("Aplicativo")
        self.page("Equipe")
        self.wait(c_mail, b_mail)
        for mail in (b_mail, c_mail):
            if any(x == "Excluir conta" for x in self.after(mail, kinds=("Button",), n=1)):
                raise Stop("an active account offers the trash")
            self.invoke_at("Desativar", self.button_in_row(mail, "Desativar", stop_at="@"))
            end = time.monotonic() + 15
            while time.monotonic() < end and "Reativar" not in self.after(mail, kinds=("Button",), n=1):
                time.sleep(1)
        self.shot("equipe-inativas")
        self.invoke_at("Excluir conta", self.button_in_row(b_mail, "Excluir conta", stop_at="@"))
        self.wait("Cancelar", b_mail, timeout=10)
        self.invoke_last("Cancelar")
        time.sleep(1)
        kept = any(u["id"] == b["id"] for u in self.api.call("GET", "/api/v1/users"))
        self.invoke_at("Excluir conta", self.button_in_row(c_mail, "Excluir conta", stop_at="@"))
        self.wait(f"Inativa Excluida {self.seq}", timeout=10)
        self.shot("excluir-conta-dialogo")
        self.invoke_last("Excluir conta")
        self.gone(c_mail)
        self.page("Aplicativo")
        self.page("Equipe")  # the list read again
        self.wait(b_mail)
        listed = self.has(c_mail)
        api_listed = any(u["id"] == c["id"] for u in self.api.call("GET", "/api/v1/users"))
        login = self.code(lambda: self.client().call("POST", "/api/v1/login", {"username": c_mail, "password": c_pw}))
        react = self.code(lambda: self.api.call("PATCH", f"/api/v1/users/{c['id']}", {"active": True}))
        # Since ACCOUNT-ERASURE-20261109 the e-mail of a deleted account opens a new, unrelated account.
        reuse = self.code(lambda: self.api.call("POST", "/api/v1/accounts", {"full_name": "Outra", "email": c_mail, "password": secrets.token_urlsafe(12)}))
        ok = kept and not listed and not api_listed and login == "AUTH-INVALID" and react == "NOT-FOUND" and reuse == "accepted"
        return {"passed": ok, "cancel_kept": kept, "deleted_listed_on_screen": listed, "deleted_listed_api": api_listed,
                "login": login, "reactivate": react, "email_reuse": reuse}

    def s_stations(self) -> dict:
        name = f"Prova estacao {self.seq}"
        s = self.api.call("POST", "/api/v1/stations", {"name": name})
        sid = s["station"]["id"]
        runner = self.client(s["runner_token"], by="RR-RUNNER")
        runner.call("POST", "/api/v1/runner/heartbeat", HB)
        last_hb = time.monotonic()
        self.guard()
        self.page("Estação")
        self.wait("Status", "Estado", "Esta estação", name)
        here = self.api.call("GET", "/api/v1/stations")
        host = next(x for x in here if x["id"] == self.station)
        host_row = self.after(host["name"], n=6)
        host_marked = self.has(f"{host['name']} Esta estação")
        refused_on_screen = "invoked" not in self.ui("-Do", "invoke", "-Name", "Revogar", "-Type", "Button",
                                                      "-Index", str(self.button_in_row(host["name"], "Revogar", stop_at="Prova estacao"))).stdout
        end = time.monotonic() + 20
        while time.monotonic() < end and "Online" not in self.after(name, n=4):
            time.sleep(1)
        online = "Online" in self.after(name, n=4)
        self.shot("estacao-status")
        # No more heartbeats: Offline must show by itself within 45 s (Core) + 10 s (screen) + a margin.
        offline_after = None
        end = last_hb + ONLINE_S + POLL_S + 15
        while time.monotonic() < end:
            if "Offline" in self.after(name, n=4):
                offline_after = round(time.monotonic() - last_hb, 1)
                break
            time.sleep(2)
        runner.call("POST", "/api/v1/runner/heartbeat", HB)
        t0, back_after = time.monotonic(), None
        while time.monotonic() < t0 + POLL_S + 10:
            if "Online" in self.after(name, n=4):
                back_after = round(time.monotonic() - t0, 1)
                break
            time.sleep(1)
        unbound = self.code(lambda: self.api.call("DELETE", f"/api/v1/stations/{sid}"))  # the script's session has no station proof
        self.guard()
        i = self.button_in_row(name, "Revogar")
        self.invoke_at("Revogar", i)
        time.sleep(0.8)
        self.invoke_at("Confirmar: execuções aguardando nela serão recusadas", 0)
        end = time.monotonic() + 20
        while time.monotonic() < end and "revogada" not in self.after(name, n=5):
            time.sleep(1)
        revoked_row = self.after(name, n=5)
        self.invoke_at("Excluir estação", self.button_in_row(name, "Excluir estação"))
        self.wait("Cancelar", timeout=10)
        self.invoke_last("Excluir estação")
        self.gone(name)
        api = {x["id"]: x for x in self.api.call("GET", "/api/v1/stations")}
        ok = (host_marked and "Online" in host_row and refused_on_screen and not api[self.station]["revoked"] and online
              and offline_after is not None and offline_after <= ONLINE_S + POLL_S + 5 and back_after is not None and back_after <= POLL_S + 5
              and unbound == "STATION-SESSION-UNBOUND" and "revogada" in revoked_row and "Offline" in revoked_row and sid not in api)
        return {"passed": ok, "host_marked_esta_estacao": host_marked, "host_row": host_row, "host_revoke_refused": refused_on_screen, "online_shown": online,
                "offline_after_s": offline_after, "online_again_after_s": back_after, "limit_s": ONLINE_S + POLL_S,
                "unbound_session": unbound, "revoked_row": revoked_row, "deleted": sid not in api}

    def s_links(self) -> dict:
        two = self.calc_process(f"Prova dois {self.seq}")
        extra = self.api.call("POST", "/api/v1/routines", {"name": f"Prova dois {self.seq} - segunda", "category": "windows",
                                                          "version": {"kind": "app_open", "config": two["items"][0]["config"]}})["routine"]["id"]
        self.api.call("POST", f"/api/v1/processes/{two['id']}/items", {"routine_id": extra})
        one = self.calc_process(f"Prova unica {self.seq}")
        first, only = two["items"][0]["routine_name"], one["items"][0]["routine_name"]
        self.guard()
        self.page("Ação")
        self.wait(two["name"], one["name"])
        self.invoke_at("Editar composição", self.button_in_row(two["name"], "Editar composição"))
        self.wait("Editar processo", f"Remover {first} do processo")
        self.invoke(f"Remover {first} do processo")
        self.invoke_last("Cancelar")
        time.sleep(1)
        cancel_kept = len(self.items(two["id"])) == 2
        self.invoke_at("Editar composição", self.button_in_row(two["name"], "Editar composição"))
        self.wait(f"Remover {first} do processo")
        self.invoke(f"Remover {first} do processo")
        self.shot("composicao-sem-etapa-1")
        self.invoke("Salvar processo")
        self.gone("Editar processo")
        step1_removed = self.items(two["id"]) == [extra]
        self.invoke_at("Editar composição", self.button_in_row(one["name"], "Editar composição"))
        self.wait(f"Remover {only} do processo")
        self.invoke(f"Remover {only} do processo")
        self.wait("Nenhuma rotina vinculada.")
        self.invoke("Salvar processo")
        self.gone("Editar processo")
        empty = self.items(one["id"]) == []
        self.wait(one["name"], "Sem etapa 1 para executar")
        self.shot("processo-vazio")
        run = self.code(lambda: self.api.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": self.station, "process_id": one["id"]}))
        still = [r["id"] for r in self.api.call("GET", "/api/v1/routines")]
        ok = cancel_kept and step1_removed and empty and run == "PROCESS-START-INVALID" and two["items"][0]["routine_id"] in still and one["items"][0]["routine_id"] in still
        return {"passed": ok, "cancel_kept": cancel_kept, "step1_removed_without_approval": step1_removed, "empty_saved": empty,
                "empty_run": run, "routines_kept_in_list": True}

    def s_routines(self) -> dict:
        p1 = self.calc_process(f"Prova lista A {self.seq}")
        p2 = self.calc_process(f"Prova lista B {self.seq}")
        cfg = p1["items"][0]["config"]
        mk = lambda n: self.api.call("POST", "/api/v1/routines", {"name": n, "category": "windows", "version": {"kind": "app_open", "config": cfg}})["routine"]["id"]
        shared, last, alone, linked = (mk(f"Prova compartilhada {self.seq}"), mk(f"Prova final {self.seq}"), mk(f"Prova avulsa {self.seq}"), mk(f"Prova vinculada {self.seq}"))
        a1, b1 = p1["items"][0]["routine_id"], p2["items"][0]["routine_id"]
        put = lambda p, ids: self.api.call("PUT", f"/api/v1/processes/{p['id']}", {"name": p["name"], "items": [{"routine_id": r, "continue_next": True} for r in ids]})
        put(p1, [a1, shared, last])
        put(p2, [b1, shared, linked])
        self.guard()
        self.page("Lista")
        self.wait("Buscar em Rotinas")
        self.fill("Buscar em Rotinas", self.seq)  # the list pages by 10: only this proof's routines
        self.wait(f"Prova compartilhada {self.seq}")
        self.invoke_at("Excluir", self.button_in_row(f"Prova compartilhada {self.seq}", "Excluir"))
        self.wait("Será retirada dos processos", timeout=10)
        self.shot("excluir-rotina-vinculada")
        self.invoke_last("Cancelar")
        time.sleep(1)
        cancel_kept = shared in self.items(p1["id"]) and shared in self.items(p2["id"])
        self.invoke_at("Excluir", self.button_in_row(f"Prova compartilhada {self.seq}", "Excluir"))
        self.wait("Será retirada dos processos", timeout=10)
        self.invoke_last("Excluir")
        self.gone(f"Prova compartilhada {self.seq}")
        one = self.items(p1["id"]) == [a1, last] and self.items(p2["id"]) == [b1, linked]
        for n in (f"Prova avulsa {self.seq}", f"Prova vinculada {self.seq}"):
            self.invoke(f"Selecionar {n}", "CheckBox")
        self.wait("Excluir 2")
        self.invoke("Excluir 2")
        self.wait("Excluir 2 rotinas", timeout=10)
        self.invoke_last("Excluir")
        self.gone(f"Prova avulsa {self.seq}", f"Prova vinculada {self.seq}")
        ids = [r["id"] for r in self.api.call("GET", "/api/v1/routines")]
        many = alone not in ids and linked not in ids and self.items(p2["id"]) == [b1]
        ok = cancel_kept and one and shared not in ids and many
        return {"passed": ok, "cancel_kept": cancel_kept, "shared_out_of_both": one, "selection_deleted": many}

    def s_jobs(self) -> dict:
        jobs_before = [j["id"] for j in self.api.call("GET", "/api/v1/jobs")]
        execs_before = self.api.call("GET", "/api/v1/executions/summary")["total"]
        self.guard()
        self.page("Atividade")
        self.wait("Execuções técnicas", "Mostrar detalhes")
        lines = self.texts()
        cell = next(line.split("|")[1] for line in lines[next(i for i, x in enumerate(lines) if x.startswith("DataItem|Detalhes|")) + 1:] if line.startswith("DataItem|"))
        row_click = self.ui("-Do", "click", "-Name", cell, "-Type", "DataItem")  # a cell of the first row: the row opens nothing
        opened_by_click = self.has("Ocultar detalhes")
        self.click("Mostrar detalhes")  # the eye is an expand/collapse button: clicked, as a person does
        self.wait("Ocultar detalhes", "pedida por", timeout=10)
        self.shot("execucao-tecnica-detalhes")
        self.click("Mostrar detalhes")  # another eye (the first one is now Ocultar): the details follow it
        time.sleep(1.5)
        one_open = sum(1 for line in self.texts() if line.startswith("Button|Ocultar detalhes|")) == 1
        self.click("Ocultar detalhes")
        self.gone("Ocultar detalhes", "pedida por", timeout=10)
        same = [j["id"] for j in self.api.call("GET", "/api/v1/jobs")] == jobs_before and self.api.call("GET", "/api/v1/executions/summary")["total"] == execs_before
        ok = not opened_by_click and one_open and same and "clicked" in row_click.stdout
        return {"passed": ok, "other_click_opened": opened_by_click, "one_detail_at_a_time": one_open, "nothing_run": same}

    def s_app(self) -> dict:
        self.guard()
        self.page("Aplicativo")
        self.wait("Esta estação", "Servidor da equipe (este computador)", "Sobre", "Banco PostgreSQL")
        lines = self.texts()
        browser = any("Navegador do RedRise" in x for x in lines) or any(x.startswith("Button|Abrir|") for x in lines)
        order = [i for i, x in enumerate(lines) if any(k in x for k in ("Servidor da equipe (este computador)", "Sobre", "Banco PostgreSQL"))]
        self.shot("aplicativo")
        ok = not browser and len(order) >= 3 and order == sorted(order)
        return {"passed": ok, "browser_block": browser}

    def s_visual(self) -> dict:
        self.guard()
        self.page("Lista")
        self.wait("Ações")
        name = next(line.split("|")[1] for line in self.texts() if line.startswith("CheckBox|Selecionar ") and "esta página" not in line)
        self.invoke(name, "CheckBox")
        shots = []
        for theme in ("claro", "escuro"):
            want = "Ativar modo escuro" if theme == "claro" else "Ativar modo claro"
            if not self.has(want):
                self.invoke("Ativar modo claro" if theme == "claro" else "Ativar modo escuro")
                time.sleep(0.8)
            self.shot(f"lista-acoes-{theme}")
            self.empresa()
            self.shot(f"sidebar-{theme}")
            self.page("Lista")
            shots += [f"lista-acoes-{theme}", f"sidebar-{theme}"]
        self.invoke(name, "CheckBox")
        self.invoke_at("Recolher ou expandir o menu", 0)
        time.sleep(0.8)
        self.shot("sidebar-recolhida")
        self.invoke_at("Recolher ou expandir o menu", 0)
        return {"passed": True, "shots": shots + ["sidebar-recolhida"], "note": "visual: judged on the screenshots"}

    def s_window(self) -> dict:
        self.guard()
        h = window_of(self.pid)
        xs = {n: int(self.ui("-Do", "rect", "-Name", n, "-Type", "Button").stdout.split()[0]) for n in ("Maximizar", "Minimizar", "Fechar")}
        order = sorted(xs, key=xs.get)
        self.invoke("Maximizar")
        time.sleep(1.2)
        maxed = bool(_u32.IsZoomed(h)) and self.has("Button|Restaurar|")
        self.shot("janela-maximizada")
        self.invoke("Restaurar")
        time.sleep(1.2)
        restored = not _u32.IsZoomed(h)
        self.invoke("Minimizar")
        time.sleep(1.2)
        minimized = bool(_u32.IsIconic(h))
        _u32.ShowWindow(h, 9)
        time.sleep(1)
        ok = order == ["Maximizar", "Minimizar", "Fechar"] and maxed and restored and minimized
        return {"passed": ok, "order_left_to_right": order, "maximized": maxed, "restored": restored, "minimized": minimized}

    def s_restart(self) -> dict:
        email, pw, name = self.new_account
        counts = self.api.call("GET", "/api/v1/storage")["counts"]
        self.guard()
        pid = self.pid
        self.close_app()  # red: closes this instance only
        closed = not alive(pid)
        if not closed:
            raise Stop("the test instance did not close")
        time.sleep(3)
        self.guard()
        self.start_as(email, pw)  # the new operator, through the screen
        self.page("Equipe")
        self.wait("Meu perfil", email)
        operator_view = not self.has("Nova Conta")
        self.shot("operador-logado")
        api = self.client(self.client().call("POST", "/api/v1/login", {"username": self.acct["admin_user"], "password": self.acct["admin_password"]})["token"])
        kept = api.call("GET", "/api/v1/storage")["counts"] == counts and any(u.get("email") == email and u["active"] for u in api.call("GET", "/api/v1/users"))
        return {"passed": closed and operator_view and kept, "closed_by_red": closed, "operator_signed_in": True, "no_admin_actions": operator_view, "data_kept": kept}


SCENARIOS = ("migration", "account", "delete", "stations", "links", "routines", "jobs", "app", "visual", "window", "restart")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True, help="counts recorded by the previous version (rollback_check.py --baseline-with)")
    ap.add_argument("--only", default="", help="comma-separated scenarios (a rerun on data an earlier run already migrated skips migration)")
    args = ap.parse_args()
    wanted = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]
    args.shots.mkdir(parents=True, exist_ok=True)
    lab = Lab(args.lab, args.shots)
    lab.created = []
    lab.baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    lab.baseline_path = str(args.baseline)
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "work_order": "TEAM-ACCOUNTS-20261108",
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
            except (Stop, CoreError, StopIteration, AttributeError) as e:
                report["scenarios"][s] = {"passed": False, "stopped": f"{type(e).__name__}: {str(e)[:1500]}"}
                try:
                    lab.shot(f"team-falha-{s}")
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e) or s == "restart":
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False)[:600], flush=True)
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["only"] = wanted if args.only else None
    report["passed"] = len(report["scenarios"]) == len(wanted) and all(v.get("passed") for v in report["scenarios"].values())
    out = args.lab / f"accept-team-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
