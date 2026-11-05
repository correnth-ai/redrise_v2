"""Follow-up "notify": prepares a draft for a person to review and send.

RedRise never sends. It opens a compose window with the recipient, a subject and a
body written from the real execution, in the mail application or the webmail chosen
in the routine. A file is attached only where the application allows it from the
outside; otherwise the body names it. "Prepared" means the compose window or the
webmail tab was confirmed on screen, not that the person sent anything."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlencode, urlsplit

from . import app_open, apps, browser_open, browsers, report_pdf, verifiers

# How much fits where the draft goes through a command line or an address, once percent-encoded.
MAX_BODY = 1500
MAX_ENCODED = 1800
MAX_SUBJECT = 150
WEBMAIL_SETTLE_S = 3.0  # a page can still redirect to sign-in right after it appears
COMPOSE_TIMEOUT_S = 60.0  # a mail application may be starting
MAIL_IDS = ("outlook", "thunderbird", "default")
WEBMAIL = {
    "gmail": {"name": "Gmail", "compose": "https://mail.google.com/mail/?view=cm&fs=1&", "keys": ("to", "su", "body"),
              "hosts": ("mail.google.com",), "login": ("accounts.google.com",)},
    "outlook": {"name": "Outlook on the web", "compose": "https://outlook.office.com/mail/deeplink/compose?", "keys": ("to", "subject", "body"),
                "hosts": ("outlook.office.com", "outlook.office365.com", "outlook.live.com"),
                "login": ("login.microsoftonline.com", "login.live.com")},
}
LABELS = {
    "subject": "{process}: {step}", "greeting": "This message was prepared by RedRise for you to review and send.", "process": "Process", "station": "Station",
    "steps": "Steps", "files": "Files", "truncated": "(text shortened to fit)", "not_run": "Not run", "this_step": "This message",
    "state_verified": "Verified", "state_failed": "Failed", "state_uncertain": "Uncertain", "state_refused": "Refused", "state_cancelled": "Cancelled", "state_error": "Error",
    "state_completed_unverified": "Completed, not verified", "state_awaiting_review": "Awaiting review", "state_running": "In progress", "state_queued": "Waiting", "state_claimed": "Preparing",
}


def _mailto_program() -> str | None:
    """The program Windows uses for mailto:, or None."""
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.c_uint32(len(buf))
    hr = ctypes.windll.shlwapi.AssocQueryStringW(0x400, 2, "mailto", "open", buf, ctypes.byref(n))
    return buf.value if hr == 0 and buf.value and Path(buf.value).name.lower() != "openwith.exe" else None


def mail_clients(resolve: Callable[[str], tuple[Path | None, str]] = apps.resolve, app_path: Callable[[str], Path | None] = apps._app_path,
                 mailto: Callable[[], str | None] = _mailto_program) -> list[dict]:
    """What can receive a draft here. Only classic Outlook and Thunderbird take a file from outside."""
    out = []
    exe, how = resolve("outlook")
    if exe is not None and how == "classic outlook":
        out.append({"id": "mail:outlook", "name": "Microsoft Outlook", "mail_id": "outlook"})
    if app_path("thunderbird.exe"):
        out.append({"id": "mail:thunderbird", "name": "Thunderbird", "mail_id": "thunderbird"})
    if mailto():
        out.append({"id": "mail:default", "name": "Windows mail app", "mail_id": "default"})  # the mask translates it
    return out


def _when(iso: str | None) -> str:
    return report_pdf._when(iso)


def attachments_of(execution: dict, documents: Path) -> tuple[list[Path], list[str]]:
    """Files of this execution that exist here, and the names of the others, which the body only mentions."""
    found, named = [], []
    for produced in ((execution.get("context") or {}).get("steps") or {}).values():
        if not isinstance(produced, dict):
            continue
        report = produced.get("report")
        if isinstance(report, dict) and isinstance(report.get("file"), str):
            path = documents / Path(report["file"]).name  # the name only: the folder of reports is known here
            (found.append(path) if path.is_file() else named.append(report["file"]))
        out = produced.get("output_path")
        if isinstance(out, str):
            path = Path(os.path.expandvars(out))  # stored sanitized: used only if it really is there
            (found.append(path) if path.is_file() else named.append(out))
    return found, named


def draft(execution: dict, labels: dict | None, position: int | None, files: list[str], limit: int = MAX_BODY) -> tuple[str, str]:
    """Subject and body, from the real execution."""
    t = {**LABELS, **{k: v for k, v in (labels or {}).items() if isinstance(v, str)}}
    steps = execution.get("steps") or []
    me = next((s for s in steps if s.get("position") == position), {})
    process = execution.get("process_name") or me.get("name") or ""
    subject = t["subject"].replace("{process}", process).replace("{step}", str(me.get("name") or ""))[:MAX_SUBJECT]
    lines = [t["greeting"], "", f"{t['process']}: {process}", f"{t['station']}: {execution.get('station_name') or '-'}", "", f"{t['steps']}:"]
    for s in steps:
        if s.get("position") == position:
            state = t["this_step"]
        elif s.get("state"):
            state = t.get(f"state_{s['state']}", s["state"])
        else:
            state = t["not_run"]
        lines.append(f"{s.get('position')}. {s.get('name') or ''}: {state}")
    if files:
        lines += ["", f"{t['files']}:"] + files
    body = "\n".join(lines)
    if len(body) > limit:
        body = body[: limit - len(t["truncated"]) - 2] + "\n" + t["truncated"]
    while len(quote(subject)) > MAX_ENCODED // 3:  # names in any script grow when encoded
        subject = subject[: int(len(subject) * 0.85)]
    room = MAX_ENCODED - len(quote(subject))
    note = "\n" + t["truncated"]
    text = body
    while len(quote(body)) > room:  # the text shrinks each turn, and with nothing left the note alone remains
        text = text.removesuffix(note)[: int(len(text.removesuffix(note)) * 0.85)]
        body = text.rstrip() + note
        if not text:
            body = ""
            break
    return subject, body


def outlook_args(to: str, subject: str, body: str, attachment: Path | None) -> list[str]:
    """Classic Outlook opens a new message with /c ipm.note; /m takes an address and fields, like mailto."""
    fields = urlencode({"subject": subject, "body": body}, quote_via=quote)
    args = ["/c", "ipm.note", "/m", f"{quote(to, safe='@')}?{fields}"]
    if attachment:
        args += ["/a", str(attachment)]
    return args


def thunderbird_args(to: str, subject: str, body: str, attachment: Path | None) -> list[str]:
    clean = lambda s: s.replace("'", "")  # noqa: E731 - its option list uses single quotes
    parts = [f"to='{clean(to)}'", f"subject='{clean(subject)}'", f"body='{clean(body)}'"]
    if attachment:
        parts.append(f"attachment='{attachment.as_uri()}'")
    return ["-compose", ",".join(parts)]


def mailto_url(to: str, subject: str, body: str) -> str:
    return f"mailto:{quote(to, safe='@')}?" + urlencode({"subject": subject, "body": body}, quote_via=quote)


def webmail_url(provider: str, to: str, subject: str, body: str) -> str:
    w = WEBMAIL[provider]
    return w["compose"] + urlencode(dict(zip(w["keys"], (to, subject, body))), quote_via=quote)


def _host(address: str | None) -> str:
    if not address:
        return ""
    return (urlsplit(address if "://" in address else "https://" + address).hostname or "").lower()


def run_webmail(channel: dict, to: str, subject: str, body: str, probe_factory=browser_open.UiaProbe, resolve=browsers.resolve,
                open_site=browser_open.launch_site, timeout_s: float = 30.0, clock=time.monotonic, sleep=time.sleep) -> dict:
    """A new tab whose document stays on the provider. On its sign-in page the draft does not exist yet, and that
    is what is reported. An error page, a closed tab or any other site confirms nothing."""
    provider = WEBMAIL.get(channel.get("provider") or "")
    browser = resolve(channel.get("browser") or "")
    if provider is None:
        return {"state": "refused", "code": "invalid_job", "detail": "unknown webmail"}
    if browser is None:
        return {"state": "refused", "code": "browser_not_found", "detail": channel.get("browser")}
    images = {browsers.CANDIDATES[browser["id"]]["image"]}
    probe = probe_factory()
    try:
        before = browser_open._snapshot(probe, images)
        url = webmail_url(channel["provider"], to, subject, body)
        try:
            open_site(browser, url)
        except OSError as e:
            return {"state": "failed", "code": "browser_open_failed", "detail": browser["name"], "reason": type(e).__name__}
        ours = provider["hosts"] + provider["login"]
        seen = browser_open.confirm(probe, images, before, lambda a: _host(a) in ours, clock() + timeout_s, clock, sleep)
        if not isinstance(seen, dict):
            return {"state": "uncertain", "code": "notify_unconfirmed", "detail": provider["name"]}
        end = clock() + timeout_s
        on_provider_since = None
        while True:
            url = getattr(probe.document(seen["hwnd"]), "url", None)
            host = "" if not url or browser_open.is_error_page(url) else _host(url)
            now = clock()
            on_provider_since = (on_provider_since if on_provider_since is not None else now) if host in provider["hosts"] else None
            if on_provider_since is not None and now - on_provider_since >= WEBMAIL_SETTLE_S:
                return {"state": "verified", "verified": True, "opened": {"how": "webmail", "name": provider["name"], "hwnd": seen["hwnd"], "pid": seen["pid"]}}
            if now >= end:
                break
            sleep(0.5)
        if host in provider["login"]:
            return {"state": "login_required", "code": "notify_login_required", "detail": provider["name"]}
        return {"state": "uncertain", "code": "notify_unconfirmed", "detail": provider["name"]}
    finally:
        if hasattr(probe, "close"):
            probe.close()


def _open_compose(resolved: dict, launch) -> dict:
    return app_open.open_target(resolved, launch, timeout_s=COMPOSE_TIMEOUT_S)


def run_app(channel: dict, to: str, subject: str, body: str, attachment: Path | None, launch=apps.launch, shell=os.startfile, mailto=_mailto_program,
            resolve=apps.resolve, app_path=apps._app_path, opener=_open_compose) -> dict:
    """Prepared means a window of the application showing this subject in its title: its main window, opening
    or coming to the front, is not a draft. Without that it stays unconfirmed."""
    title = subject[:30].strip()
    mail_id = channel.get("mail_id")
    if mail_id == "outlook":
        exe, how = resolve("outlook")
        if exe is None or how != "classic outlook":
            return {"state": "refused", "code": "outlook_not_installed", "detail": "Microsoft Outlook"}
        args = outlook_args(to, subject, body, attachment)
        return opener({"how": "mail", "launch": "outlook", "name": "Microsoft Outlook", "image": exe.name.lower(), "title": title}, lambda _: launch(exe, args))
    if mail_id == "thunderbird":
        exe = app_path("thunderbird.exe")
        if exe is None:
            return {"state": "refused", "code": "app_target_not_found", "detail": "Thunderbird"}
        args = thunderbird_args(to, subject, body, attachment)
        return opener({"how": "mail", "launch": "thunderbird", "name": "Thunderbird", "image": exe.name.lower(), "title": title.replace("'", "")}, lambda _: launch(exe, args))
    if mail_id == "default":
        program = mailto()
        if not program:
            return {"state": "refused", "code": "app_no_association", "detail": "mailto"}
        url = mailto_url(to, subject, body)
        return opener({"how": "mail", "launch": url, "name": Path(program).name, "image": Path(program).name.lower(), "title": title}, lambda u: shell(u))
    return {"state": "refused", "code": "invalid_job", "detail": "unknown mail application"}


def run(job: dict, documents: Path | None = None, app_runner=run_app, webmail_runner=run_webmail) -> dict:
    """Local result of the notify step. Nothing here can send: no command, button or key does it."""
    execution, config = job.get("execution"), job.get("config") or {}
    if not isinstance(execution, dict):
        return {"state": "refused", "code": "invalid_job", "detail": "notify job without execution"}
    channel, to = config.get("channel") or {}, str(config.get("to") or "")
    found, named = attachments_of(execution, documents or report_pdf.documents_folder())
    takes_file = channel.get("kind") == "app" and channel.get("mail_id") in ("outlook", "thunderbird")
    attachment = found[0] if takes_file and found else None
    mention = [p.name for p in found if p != attachment] + named
    subject, body = draft(execution, config.get("labels"), job.get("position"), mention)
    if channel.get("kind") == "webmail":
        out = webmail_runner(channel, to, subject, body)
    elif channel.get("kind") == "app":
        out = app_runner(channel, to, subject, body, attachment)
    else:
        return {"state": "refused", "code": "invalid_job", "detail": "unknown channel"}
    if out.get("state") != "verified":
        return out
    opened = out.get("opened") or (out.get("context") or {}).get("opened") or {}
    return {"state": "verified", "verified": True, "context": {"message": {
        "status": "prepared", "to": to, "channel": opened.get("name") or channel.get("name"), "subject": subject,
        "attached": attachment.name if attachment else None, "mentioned": mention, "hwnd": opened.get("hwnd"), "pid": opened.get("pid")}}}
