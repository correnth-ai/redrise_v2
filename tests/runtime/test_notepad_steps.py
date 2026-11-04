"""Boas-vindas process steps with a simulated desktop and Engine (no UI). The
real Notepad is exercised in the practical check of the installed build.
    cd tests/runtime && <python> -B -m unittest test_notepad_steps
"""

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner import notepad_steps as np  # noqa: E402

UNTITLED = "Sem título. Não modificado."


@dataclass
class Tab:
    tab_id: str
    name: str
    selected: bool = False
    text: str = ""


class FakeNotepad:
    """A tabbed Notepad: reacts to the keystrokes the steps send, records them all."""

    def __init__(self, desktop: Path, tabs=None, running=False, restored=None):
        self.folder = desktop
        self.tabs_ = list(tabs or [])
        self.hwnd = 100 if running else None
        self.restored = restored
        self.fg = 100 if running else 7
        self.prompt = None  # tab with an open discard question
        self.save_dialog = False
        self.overwrite_q = False
        self.focus = "Editor de texto"
        self.sent: list = []
        self.created = 0
        self.typed_name = None
        self.fail_next = None
        self.overwritten = False
        self.question_focus = "N\u00e3o"  # Windows puts the focus on No
        self.appear_on_save: list[str] = []  # names another program creates just before saving
        self.lost_foreground_after_open = False

    # -- Desk
    def windows(self):
        return [self.hwnd] if self.hwnd else []

    def foreground(self):
        return self.fg

    def is_window(self, h):
        return h == self.hwnd and self.hwnd is not None

    def launch(self):
        self.hwnd, self.fg = 100, 100
        self.tabs_ = self.restored or [Tab("t0", UNTITLED, True)]
        return 100

    def tabs(self, h):
        return list(self.tabs_) if h == self.hwnd else []

    def text(self, h):
        return self.sel().text

    def buttons(self, h):
        return ["Salvar", "Não salvar", "Cancelar"] if self.prompt else ["Fechar Guia"]

    def focused(self):
        return self.focus

    def dialogs(self):
        return int(self.save_dialog) + int(self.overwrite_q)

    def desktop(self):
        return self.folder

    # -- Engine
    def sel(self):
        return next(t for t in self.tabs_ if t.selected)

    def send(self, hwnd, actions):
        self.sent.extend(actions)
        if actions[0]["action"].get("vk") == np.VK_F24:  # the Engine activates the bound window before its first step
            if self.lost_foreground_after_open:
                return {"state": "failed", "code": "focus_timeout", "detail": "simulated"}
            self.fg = hwnd
            return {"state": "completed_unverified"}
        if self.fg != hwnd:
            return {"state": "failed", "code": "focus_timeout", "detail": "simulated"}
        if self.fail_next:
            state, self.fail_next = self.fail_next, None
            return {"state": state, "code": "focus_timeout", "detail": "simulated"}
        for a in actions:
            self.act(a)
        return {"state": "completed_unverified"}

    def act(self, a):
        act = a["action"]
        if act["type"] == "type_text":
            s = act["text"]["literal"]
            if self.save_dialog:
                self.typed_name = s
            else:
                self.sel().text += s
                self.sel().name = f"{s[:10]}. Modificado."
            return
        vk, mods = act["vk"], act.get("mods", {})
        if vk == np.VK_T and mods.get("ctrl"):
            self.created += 1
            for t in self.tabs_:
                t.selected = False
            self.tabs_.append(Tab(f"new{self.created}", UNTITLED, True))
        elif vk == np.VK_S and mods.get("ctrl"):
            self.save_dialog = True
        elif vk == np.VK_RETURN and self.save_dialog and not self.overwrite_q:
            self.confirm_save()
        elif vk == np.VK_TAB and self.overwrite_q:
            if self.focus in ("Sim", "N\u00e3o"):
                self.focus = "N\u00e3o" if self.focus == "Sim" else "Sim"
        elif vk == np.VK_RETURN and self.overwrite_q:
            if self.focus != "N\u00e3o":
                self.overwritten = True
            self.overwrite_q = False
            self.focus = "Nome do arquivo"
        elif vk == np.VK_ESCAPE and self.prompt:
            self.prompt = None
            self.focus = "Editor de texto"
        elif vk == np.VK_TAB and mods.get("ctrl"):
            i = next(i for i, t in enumerate(self.tabs_) if t.selected)
            self.tabs_[i].selected = False
            self.tabs_[(i + 1) % len(self.tabs_)].selected = True
        elif vk == np.VK_TAB and self.prompt:
            self.focus = "Não salvar"
        elif vk == np.VK_RETURN and self.prompt:
            self.remove(self.prompt)
            self.prompt = None
            self.focus = "Editor de texto"
        elif vk == np.VK_W and mods.get("ctrl"):
            t = self.sel()
            if t.name.endswith(" Modificado."):
                self.prompt = t
                self.focus = "Salvar"
            else:
                self.remove(t)

    def confirm_save(self):
        name = self.typed_name
        self.typed_name = None
        if name is None or Path(name).is_absolute():  # Enter after typing the folder: the dialog just navigates
            return
        for extra in self.appear_on_save:
            (self.folder / extra).write_text("de outro programa", encoding="utf-8")
        self.appear_on_save = []
        path = self.folder / name
        if path.exists():
            self.overwrite_q = True
            self.focus = self.question_focus
            return
        path.write_text(self.sel().text, encoding="utf-8")
        self.sel().name = f"{path.stem}. Não modificado."
        self.save_dialog = False

    def remove(self, t):
        i = self.tabs_.index(t)
        self.tabs_.remove(t)
        if not self.tabs_:
            self.hwnd = None
            return
        if t.selected:
            self.tabs_[min(i, len(self.tabs_) - 1)].selected = True


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.desk_dir = Path(self.tmp.name)
        for name in ("SAVE_TIMEOUT_S", "CLOSE_TIMEOUT_S"):
            orig = getattr(np, name)
            setattr(np, name, 0.3)
            self.addCleanup(setattr, np, name, orig)

    def run_all(self, d: FakeNotepad):
        ctx: dict = {}
        out = []
        for step in ("open", "save", "close"):
            r = np.run(step, ctx, d, d.send)
            out.append(r)
            if r["state"] != "verified":
                break
            ctx = r["context"]
        return out

    def keys(self, d, vk):
        return [a for a in d.sent if a["action"].get("vk") == vk]


class FreeNameTests(Base):
    def test_free_name_sequence(self):
        self.assertEqual(np.free_name(self.desk_dir), "Boas_Vindas.txt")
        (self.desk_dir / "Boas_Vindas.txt").write_text("x")
        self.assertEqual(np.free_name(self.desk_dir), "Boas_Vindas[2].txt")
        (self.desk_dir / "Boas_Vindas[2].txt").write_text("x")
        (self.desk_dir / "Boas_Vindas[4].txt").write_text("x")
        self.assertEqual(np.free_name(self.desk_dir), "Boas_Vindas[3].txt")


class FlowTests(Base):
    def test_clean_start_reuses_the_tab_and_closes_the_window(self):
        d = FakeNotepad(self.desk_dir)
        rs = self.run_all(d)
        self.assertEqual([r["state"] for r in rs], ["verified"] * 3)
        ref = rs[0]["context"]["notepad"]
        self.assertEqual((ref["mode"], ref["window_of_run"], ref["tab_id"], ref["tabs_before"]), ("clean", True, "t0", []))
        self.assertEqual(d.created, 0)
        self.assertEqual((self.desk_dir / "Boas_Vindas.txt").read_text(encoding="utf-8"), np.TEXT)
        self.assertEqual(rs[1]["context"]["output_name"], "Boas_Vindas.txt")
        self.assertTrue(rs[2]["context"]["final"]["window_closed"])
        self.assertIsNone(d.hwnd)

    def test_open_window_keeps_unsaved_tab_and_stays_open(self):
        mine = Tab("u1", "rascunho. Modificado.", True, "texto da pessoa")
        d = FakeNotepad(self.desk_dir, [mine], running=True)
        rs = self.run_all(d)
        self.assertEqual([r["state"] for r in rs], ["verified"] * 3)
        self.assertEqual(rs[0]["context"]["notepad"]["mode"], "already_open")
        self.assertEqual([t.tab_id for t in d.tabs_], ["u1"])
        self.assertEqual(mine.text, "texto da pessoa")
        self.assertEqual(rs[2]["context"]["final"], {"window_closed": False, "tabs_closed": 1, "extra_tabs_closed": 0, "tabs_kept": 1, "earlier_tabs_kept": 1})
        self.assertEqual(d.hwnd, 100)
        self.assertFalse(self.keys(d, np.VK_RETURN)[-1]["action"].get("mods"))  # no discard path was needed

    def test_restored_session_gets_a_dedicated_tab(self):
        restored = [Tab("r1", "antigo. Modificado.", True, "antigo"), Tab("r2", "Boas_Vindas. Não modificado.", False, "x")]
        d = FakeNotepad(self.desk_dir, restored=restored)
        rs = self.run_all(d)
        self.assertEqual([r["state"] for r in rs], ["verified"] * 3)
        self.assertEqual(rs[0]["context"]["notepad"]["mode"], "restored_session")
        self.assertFalse(rs[0]["context"]["notepad"]["window_of_run"])
        self.assertEqual([t.tab_id for t in d.tabs_], ["r1", "r2"])
        self.assertEqual(d.hwnd, 100)

    def test_single_untitled_tab_with_text_is_not_clean(self):
        d = FakeNotepad(self.desk_dir, restored=[Tab("r1", UNTITLED, True, "conteudo restaurado")])
        r = np.run("open", {}, d, d.send)
        self.assertEqual(r["context"]["notepad"]["mode"], "restored_session")
        self.assertEqual(d.created, 1)

    def test_own_extra_tabs_of_a_dedicated_window_are_closed_with_discard(self):
        d = FakeNotepad(self.desk_dir)
        ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
        d.tabs_.append(Tab("x1", "Boas-vindas. Modificado.", False, np.TEXT))
        d.tabs_.append(Tab("x2", UNTITLED, False))
        r = np.run("close", ctx, d, d.send)
        self.assertEqual(r["state"], "verified")
        self.assertEqual(r["context"]["final"], {"window_closed": True, "tabs_closed": 3, "extra_tabs_closed": 2})
        self.assertIsNone(d.hwnd)
        self.assertTrue((self.desk_dir / "Boas_Vindas.txt").exists())

    def test_other_tab_in_a_dedicated_window_is_never_discarded(self):
        for other in (Tab("x1", "de uma pessoa. Modificado.", False, "de uma pessoa"),
                      Tab("x1", UNTITLED, False, "digitado sem titulo"),
                      Tab("x1", "antigo. N\u00e3o modificado.", False, "")):
            with self.subTest(other=other.name):
                d = FakeNotepad(Path(tempfile.mkdtemp(dir=self.desk_dir)))
                ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
                d.tabs_.append(other)
                r = np.run("close", ctx, d, d.send)
                self.assertEqual(r["state"], "verified")
                self.assertEqual([t.tab_id for t in d.tabs_], ["x1"])
                self.assertEqual(d.hwnd, 100)
                self.assertEqual(r["context"]["final"]["window_closed"], False)

    def test_own_and_other_extras_together(self):
        d = FakeNotepad(self.desk_dir)
        ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
        d.tabs_.append(Tab("mine", UNTITLED, False))
        d.tabs_.append(Tab("theirs", "dela. Modificado.", False, "dela"))
        r = np.run("close", ctx, d, d.send)
        self.assertEqual([t.tab_id for t in d.tabs_], ["theirs"])
        self.assertEqual(r["context"]["final"]["tabs_closed"], 2)

    def test_text_typed_after_the_check_is_not_discarded(self):
        d = FakeNotepad(self.desk_dir)
        ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
        late = Tab("x1", UNTITLED, False)
        d.tabs_.append(late)
        real = d.send

        def send(hwnd, actions):
            if actions[0]["action"].get("vk") == np.VK_W and d.sel() is late:  # a person types just before Ctrl+W
                late.text, late.name = "de uma pessoa", "de uma pessoa. Modificado."
            return real(hwnd, actions)
        r = np.run("close", ctx, d, send)
        self.assertEqual((r["state"], r["code"]), ("failed", "notepad_close_unexpected_changes"))
        self.assertIn(late, d.tabs_)
        self.assertEqual(late.text, "de uma pessoa")

    def test_an_empty_read_of_the_tabs_is_not_proof_of_closing(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", "x. Modificado.", True, "x")], running=True)
        ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
        real_tabs, real_act = d.tabs, d.act
        blind = []

        def act(a):
            if a["action"].get("vk") == np.VK_W:
                blind.append(True)  # Ctrl+W sent, nothing closes and the tab strip reads empty
                return
            real_act(a)
        d.act = act
        d.tabs = lambda h: [] if blind else real_tabs(h)
        r = np.run("close", ctx, d, d.send)
        self.assertEqual((r["state"], r["code"]), ("uncertain", "notepad_close_unconfirmed"))

    def test_tab_of_shared_window_with_unexpected_changes_is_not_discarded(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", "x. Modificado.", True, "x")], running=True)
        ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
        d.sel().name = "alterada. Modificado."
        r = np.run("close", ctx, d, d.send)
        self.assertEqual((r["state"], r["code"]), ("failed", "notepad_close_unexpected_changes"))
        self.assertEqual([t.tab_id for t in d.tabs_], ["u1", "new1"])
        self.assertFalse(self.keys(d, np.VK_RETURN)[-1]["expect"] == np.MAIN_CLASS)  # Enter never reached the prompt

    def test_user_tab_opened_later_in_shared_window_is_kept(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", "x. Modificado.", True, "x")], running=True)
        ctx = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)["context"]
        d.tabs_.append(Tab("later", "nova. Modificado.", False, "nova"))
        self.assertEqual(np.run("close", ctx, d, d.send)["state"], "verified")
        self.assertEqual({t.tab_id for t in d.tabs_}, {"u1", "later"})


class CollisionTests(Base):
    def test_existing_files_are_preserved_and_brackets_used(self):
        (self.desk_dir / "Boas_Vindas.txt").write_text("original", encoding="utf-8")
        d = FakeNotepad(self.desk_dir)
        rs = self.run_all(d)
        self.assertEqual(rs[1]["context"]["output_name"], "Boas_Vindas[2].txt")
        self.assertEqual((self.desk_dir / "Boas_Vindas.txt").read_text(encoding="utf-8"), "original")
        self.assertEqual((self.desk_dir / "Boas_Vindas[2].txt").read_text(encoding="utf-8"), np.TEXT)

    def test_conflict_in_the_dialog_refuses_and_takes_the_next_free_name(self):
        d = FakeNotepad(self.desk_dir)
        d.appear_on_save = ["Boas_Vindas.txt"]
        ctx = np.run("open", {}, d, d.send)["context"]
        r = np.run("save", ctx, d, d.send)
        self.assertEqual(r["state"], "verified")
        self.assertEqual((r["context"]["output_name"], r["context"]["name_conflicts"]), ("Boas_Vindas[2].txt", ["Boas_Vindas.txt"]))
        self.assertEqual((self.desk_dir / "Boas_Vindas.txt").read_text(encoding="utf-8"), "de outro programa")
        self.assertFalse(d.overwritten)

    def test_conflict_with_focus_on_yes_moves_to_no_before_answering(self):
        d = FakeNotepad(self.desk_dir)
        d.appear_on_save = ["Boas_Vindas.txt"]
        d.question_focus = "Sim"
        r = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)
        self.assertEqual(r["state"], "verified")
        self.assertFalse(d.overwritten)

    def test_conflict_with_unknown_focus_answers_nothing(self):
        d = FakeNotepad(self.desk_dir)
        d.appear_on_save = ["Boas_Vindas.txt"]
        d.question_focus = "Outro"
        r = np.run("save", np.run("open", {}, d, d.send)["context"], d, d.send)
        self.assertEqual((r["state"], r["code"]), ("uncertain", "notepad_save_unconfirmed"))
        self.assertFalse(d.overwritten)


class StopTests(Base):
    def opened(self, d):
        return np.run("open", {}, d, d.send)["context"]

    def test_no_context_stops_before_input(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", UNTITLED, True)], running=True)
        r = np.run("save", {}, d, d.send)
        self.assertEqual((r["state"], r["code"]), ("refused", "notepad_context_missing"))
        self.assertEqual(d.sent, [])

    def test_lost_window_stops_before_typing(self):
        d = FakeNotepad(self.desk_dir)
        ctx = self.opened(d)
        d.hwnd = None
        r = np.run("save", ctx, d, d.send)
        self.assertEqual((r["state"], r["code"]), ("failed", "notepad_target_lost"))
        self.assertEqual(d.sent, [])

    def test_other_tab_selected_stops_before_typing(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", "x. Modificado.", False, "x")], running=True)
        d.tabs_[0].selected = True
        ctx = self.opened(d)
        d.tabs_[1].selected, d.tabs_[0].selected = False, True
        sent = len(d.sent)
        r = np.run("save", ctx, d, d.send)
        self.assertEqual(r["code"], "notepad_target_lost")
        self.assertEqual(len(d.sent), sent)
        self.assertEqual(d.tabs_[0].text, "x")

    def test_tab_already_with_text_stops_before_typing(self):
        d = FakeNotepad(self.desk_dir)
        ctx = self.opened(d)
        d.sel().text = "alguem digitou"
        r = np.run("save", ctx, d, d.send)
        self.assertEqual(r["code"], "notepad_target_lost")
        self.assertEqual(d.sent, [])

    def test_foreground_not_obtained_stops_before_input(self):
        d = FakeNotepad(self.desk_dir)
        ctx = self.opened(d)
        d.fg, d.lost_foreground_after_open = 7, True
        r = np.run("close", ctx, d, d.send)
        self.assertEqual(r["code"], "notepad_target_lost")
        self.assertEqual([a["action"]["vk"] for a in d.sent], [np.VK_F24])  # only the key without effect

    def test_open_window_behind_another_app_is_brought_forward(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", "x. Modificado.", True, "x")], running=True)
        d.fg = 7
        r = np.run("open", {}, d, d.send)
        self.assertEqual((r["state"], r["context"]["notepad"]["mode"]), ("verified", "already_open"))
        self.assertEqual(d.sent[0]["action"]["vk"], np.VK_F24)

    def test_missing_earlier_tab_stops_before_closing(self):
        d = FakeNotepad(self.desk_dir, [Tab("u1", "x. Modificado.", True, "x")], running=True)
        ctx = np.run("save", self.opened(d), d, d.send)["context"]
        d.tabs_ = [t for t in d.tabs_ if t.tab_id != "u1"]
        sent = len(d.sent)
        r = np.run("close", ctx, d, d.send)
        self.assertEqual(r["code"], "notepad_target_lost")
        self.assertEqual(len(d.sent), sent)

    def test_engine_failure_while_saving_is_uncertain_and_not_repeated(self):
        d = FakeNotepad(self.desk_dir)
        ctx = self.opened(d)
        real = d.send

        def send(hwnd, actions):
            if actions[0]["action"].get("vk") == np.VK_S:
                d.fail_next = "failed"
            return real(hwnd, actions)
        r = np.run("save", ctx, d, send)
        self.assertEqual((r["state"], r["code"]), ("uncertain", "focus_timeout"))
        self.assertEqual(len(self.keys(d, np.VK_S)), 1)

    def test_tabs_unavailable_is_refused(self):
        d = FakeNotepad(self.desk_dir, restored=[])
        d.launch = lambda: (setattr(d, "hwnd", 100), 100)[1]
        r = np.run("open", {}, d, d.send)
        self.assertEqual((r["state"], r["code"]), ("refused", "notepad_tabs_unavailable"))

    def test_unknown_step_is_refused(self):
        d = FakeNotepad(self.desk_dir)
        self.assertEqual(np.run("x", {}, d, d.send)["code"], "invalid_job")


if __name__ == "__main__":
    unittest.main()
