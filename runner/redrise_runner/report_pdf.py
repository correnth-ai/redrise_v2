"""Report of an execution as a PDF with the RedRise look (follow-up action "report").

Written with the standard library only: no new package in the private runtime.
The text comes from the real execution; the fixed words come from the routine's
config, which the desktop fills from its pt-BR mask, with English here as the
fallback. Saved under the user's Documents, first free name, never overwriting,
and read back before the step counts as verified."""

from __future__ import annotations

import hashlib
import os
import re
import struct
import zlib
from datetime import datetime
from pathlib import Path

from . import apps

FOLDERID_DOCUMENTS = "FDD39AD0-238F-46AF-ADB4-6C85480369C7"
RELATIVE = Path("RedRise") / "Relatorios"
PAGE_W, PAGE_H, MARGIN = 595, 842, 48
RED = "0.78 0.09 0.15"
INK, MUTED, RULE = "0.13 0.13 0.15", "0.42 0.43 0.47", "0.86 0.87 0.89"
LABELS = {
    "title": "Execution report", "process": "Process", "standalone": "Standalone routine", "station": "Station", "requested_by": "Requested by",
    "started": "Started", "reference": "Reference", "summary": "Summary", "summary_text": "{done} of {total} steps verified up to this report.",
    "steps": "Steps", "col_step": "Step", "col_state": "Status", "col_when": "When", "result": "Result",
    "result_ok": "All the previous steps were verified.", "result_open": "There are steps without a verified result. Check them before relying on this report.",
    "pending": "Pending", "pending_none": "Nothing is pending after this report.", "files": "Files of this execution", "files_none": "No file was recorded.",
    "generated": "Generated on", "page": "Page {n} of {total}", "this_report": "This report", "not_run": "Not run",
    "state_verified": "Verified", "state_failed": "Failed", "state_uncertain": "Uncertain", "state_refused": "Refused", "state_cancelled": "Cancelled",
    "state_error": "Error", "state_completed_unverified": "Completed, not verified", "state_awaiting_review": "Awaiting review", "state_running": "In progress",
    "state_queued": "Waiting", "state_claimed": "Preparing", "approved_by": "Approved by {who}", "message_prepared": "Message prepared, not sent",
}


def _when(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(iso)


def _pdf_text(s: str) -> bytes:
    raw = s.encode("cp1252", "replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _wrap(s: str, size: float, width: float) -> list[str]:
    limit = max(8, int(width / (size * 0.52)))  # Helvetica averages about half an em
    out, line = [], ""
    for word in s.split():
        while len(word) > limit:  # a long path has no spaces
            if line:
                out.append(line)
                line = ""
            out.append(word[:limit])
            word = word[limit:]
        if len(line) + len(word) + (1 if line else 0) > limit:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line or not out:
        out.append(line)
    return out


def _fit(s: str, size: float, width: float) -> str:
    limit = max(4, int(width / (size * 0.52)))
    return s if len(s) <= limit else s[: limit - 3] + "..."


def read_png(raw: bytes) -> tuple[int, int, bytes, bytes | None]:
    """(width, height, rgb, alpha) of an 8-bit RGB or RGBA PNG without interlace."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, w, h, ctype = 8, [], 0, 0, 0
    while pos < len(raw):
        n, kind = struct.unpack(">I4s", raw[pos:pos + 8])
        chunk = raw[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or ctype not in (2, 6) or interlace:
                raise ValueError("unsupported PNG")
        elif kind == b"IDAT":
            idat.append(chunk)
        pos += n + 12
    bpp = 4 if ctype == 6 else 3
    data, stride = zlib.decompress(b"".join(idat)), w * bpp
    prev, rgb, alpha = bytearray(stride), bytearray(), bytearray()
    for y in range(h):
        start = y * (stride + 1)
        kind, row = data[start], bytearray(data[start + 1:start + 1 + stride])
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if kind == 1:
                row[i] = (row[i] + a) & 255
            elif kind == 2:
                row[i] = (row[i] + b) & 255
            elif kind == 3:
                row[i] = (row[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = row
        if bpp == 4:
            rgb += b"".join(bytes(row[i:i + 3]) for i in range(0, stride, 4))
            alpha += bytes(row[3::4])
        else:
            rgb += row
    return w, h, bytes(rgb), bytes(alpha) if bpp == 4 else None


class _Doc:
    def __init__(self):
        self.pages: list[list[bytes]] = []
        self.y = 0.0
        self.new_page()

    def new_page(self) -> None:
        self.pages.append([])
        self.y = PAGE_H - MARGIN

    def room(self, need: float) -> None:
        if self.y - need < MARGIN + 28:
            self.new_page()

    def op(self, s: str) -> None:
        self.pages[-1].append(s.encode("ascii"))

    def text(self, x: float, y: float, s: str, font: str = "F1", size: float = 10, color: str = INK) -> None:
        self.pages[-1].append(f"BT /{font} {size} Tf {color} rg {x} {y:.1f} Td (".encode("ascii") + _pdf_text(s) + b") Tj ET")

    def rule(self, y: float, color: str = RULE, width: float = 0.75) -> None:
        self.op(f"{color} RG {width} w {MARGIN} {y:.1f} m {PAGE_W - MARGIN} {y:.1f} l S")

    def heading(self, s: str) -> None:
        self.room(40)
        self.y -= 22
        self.text(MARGIN, self.y, s, "F3", 13)
        self.y -= 8

    def para(self, s: str, size: float = 10, color: str = INK) -> None:
        for line in _wrap(s, size, PAGE_W - 2 * MARGIN):
            self.room(16)
            self.y -= 14
            self.text(MARGIN, self.y, line, "F1", size, color)


def build(execution: dict, labels: dict | None = None, logo: bytes | None = None, generated_at: datetime | None = None, this_position: int | None = None) -> bytes:
    """The PDF of this execution, as it stands when the report step runs."""
    t = {**LABELS, **{k: v for k, v in (labels or {}).items() if isinstance(v, str)}}
    now = (generated_at or datetime.now().astimezone()).strftime("%d/%m/%Y %H:%M")
    steps = execution.get("steps") or []
    previous = [s for s in steps if this_position is None or s["position"] < this_position]
    done = sum(1 for s in previous if s.get("verified"))
    doc = _Doc()
    # Top of the first page.
    top = doc.y
    x = MARGIN
    if logo:
        doc.op(f"q 28 0 0 28 {MARGIN} {top - 26:.1f} cm /Logo Do Q")
        x += 36
    doc.text(x, top - 18, "RedRise", "F2", 13, RED)
    doc.op(f"{RED} RG 2 w {MARGIN} {top - 36:.1f} m {PAGE_W - MARGIN} {top - 36:.1f} l S")
    doc.y = top - 64
    doc.text(MARGIN, doc.y, t["title"], "F3", 20)
    doc.y -= 10
    for key, value in ((t["process"], execution.get("process_name") or t["standalone"]), (t["station"], execution.get("station_name")),
                       (t["requested_by"], execution.get("requested_by")), (t["started"], _when(execution.get("created_at"))),
                       (t["reference"], execution.get("correlation_id"))):
        doc.y -= 15
        doc.text(MARGIN, doc.y, str(key), "F2", 9, MUTED)
        doc.text(MARGIN + 90, doc.y, _fit(str(value or "-"), 10, PAGE_W - 2 * MARGIN - 90), "F1", 10)
    doc.heading(t["summary"])
    doc.para(t["summary_text"].replace("{done}", str(done)).replace("{total}", str(len(previous))))
    doc.heading(t["steps"])
    cols = (MARGIN, MARGIN + 250, MARGIN + 390)
    doc.room(20)
    doc.y -= 12
    for c, label in zip(cols, (t["col_step"], t["col_state"], t["col_when"])):
        doc.text(c, doc.y, label, "F2", 9, MUTED)
    doc.y -= 5
    doc.rule(doc.y)
    produced = (execution.get("context") or {}).get("steps") or {}
    for s in steps:
        if s["position"] == this_position:
            state = t["this_report"]
        elif (produced.get(str(s["position"])) or {}).get("message", {}).get("status") == "prepared":
            state = t["message_prepared"]  # a draft for a person: never shown as if the message went out
        elif s.get("review") and s["review"].get("decided_by_name"):
            state = t["approved_by"].replace("{who}", s["review"]["decided_by_name"])
        elif s.get("state"):
            state = t.get(f"state_{s['state']}", s["state"])
        else:
            state = t["not_run"]
        lines = _wrap(state, 10, 135)[:3]  # a name in the status is never cut
        doc.room(20 + 12 * (len(lines) - 1))
        doc.y -= 15
        doc.text(cols[0], doc.y, _fit(f"{s['position']}. {s.get('name') or ''}", 10, 240), "F1", 10)
        doc.text(cols[2], doc.y, _when(s.get("finished_at") or s.get("started_at")), "F1", 10, MUTED)
        for i, line in enumerate(lines):
            if i:
                doc.y -= 12
            doc.text(cols[1], doc.y, line, "F1", 10)
        doc.y -= 4
        doc.rule(doc.y)
    doc.heading(t["result"])
    doc.para(t["result_ok"] if previous and done == len(previous) else t["result_open"])
    doc.heading(t["pending"])
    # What will still run: a link with continuation off ends the sequence there.
    after = []
    for s in steps:
        if this_position is None or s["position"] < this_position:
            continue
        if s["position"] > this_position:
            after.append(s)
        if s.get("continue_next") is False:
            break
    open_before = [s for s in previous if not s.get("verified")]
    if after or open_before:
        for s in open_before + after:
            doc.para(f"{s['position']}. {s.get('name') or ''}")
    else:
        doc.para(t["pending_none"])
    doc.heading(t["files"])
    files = []
    for produced in ((execution.get("context") or {}).get("steps") or {}).values():
        if isinstance(produced, dict):
            files += [produced[k] for k in ("output_path", "path") if isinstance(produced.get(k), str)]
            report = produced.get("report")
            if isinstance(report, dict) and isinstance(report.get("file"), str):
                files.append(report["file"])
    for f in files or [t["files_none"]]:
        doc.para(f, 9 if files else 10, INK if files else MUTED)
    return _assemble(doc, t, now, logo)


def _assemble(doc: _Doc, t: dict, now: str, logo: bytes | None) -> bytes:
    total = len(doc.pages)
    objects: dict[int, bytes] = {}
    font = lambda name: f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>".encode("ascii")  # noqa: E731
    objects[3], objects[4], objects[5] = font("Helvetica"), font("Helvetica-Bold"), font("Times-Bold")
    next_id = 6
    image = ""
    if logo:
        try:
            w, h, rgb, alpha = read_png(logo)
        except (ValueError, zlib.error, struct.error, IndexError):  # the report does not depend on the mark
            alpha, rgb, w, h = None, b"", 0, 0
        if rgb:
            smask = ""
            if alpha is not None:
                body = zlib.compress(alpha)
                objects[next_id] = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray /BitsPerComponent 8 "
                                    f"/Filter /FlateDecode /Length {len(body)} >>\nstream\n").encode("ascii") + body + b"\nendstream"
                smask = f"/SMask {next_id} 0 R "
                next_id += 1
            body = zlib.compress(rgb)
            objects[next_id] = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 {smask}"
                                f"/Filter /FlateDecode /Length {len(body)} >>\nstream\n").encode("ascii") + body + b"\nendstream"
            image = f"/XObject << /Logo {next_id} 0 R >> "
            next_id += 1
    page_ids = []
    for i, ops in enumerate(doc.pages, 1):
        foot = _Doc()
        foot.pages = [[]]
        foot.rule(MARGIN + 12)
        foot.text(MARGIN, MARGIN, f"{t['generated']} {now}", "F1", 8, MUTED)
        foot.text(PAGE_W - MARGIN - 60, MARGIN, t["page"].replace("{n}", str(i)).replace("{total}", str(total)), "F1", 8, MUTED)
        ops = ops if image else [o for o in ops if b"/Logo Do" not in o]
        body = b"\n".join(ops + foot.pages[0])
        objects[next_id] = f"<< /Length {len(body)} >>\nstream\n".encode("ascii") + body + b"\nendstream"
        objects[next_id + 1] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Contents {next_id} 0 R "
                                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> {image}>> >>").encode("ascii")
        page_ids.append(next_id + 1)
        next_id += 2
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {total} >>".encode("ascii")
    info = next_id
    objects[info] = b"<< /Title (" + _pdf_text(t["title"]) + b") /Producer (RedRise) >>"
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for n in sorted(objects):
        offsets[n] = len(out)
        out += f"{n} 0 obj\n".encode("ascii") + objects[n] + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {info + 1}\n0000000000 65535 f \n".encode("ascii")
    for n in range(1, info + 1):
        out += f"{offsets[n]:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {info + 1} /Root 1 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)


def well_formed(raw: bytes) -> int:
    """Pages of a PDF this module wrote, checked through its cross-reference table; raises ValueError."""
    if not raw.startswith(b"%PDF-") or not raw.rstrip().endswith(b"%%EOF"):
        raise ValueError("not a complete PDF")
    at = int(re.search(rb"startxref\s+(\d+)", raw[-64:]).group(1))
    if raw[at:at + 4] != b"xref":
        raise ValueError("cross-reference not where it says")
    table = raw[at:].split(b"trailer")[0].split(b"\n")[2:]
    for n, row in enumerate(table):
        if row.endswith(b"n ") and not raw[int(row[:10]):].startswith(f"{n} 0 obj".encode("ascii")):
            raise ValueError(f"object {n} not at its offset")
    return len(re.findall(rb"/Type /Page /Parent", raw))


def _safe_stem(name: str) -> str:
    return re.sub(r"\W+", "_", name).strip("_")[:60] or "Execucao"


def documents_folder() -> Path:
    return apps.known_folder(FOLDERID_DOCUMENTS) / RELATIVE


def run(job: dict, folder: Path | None = None, logo_path: Path | None = None) -> dict:
    """Local result of the report step. Never overwrites; a failure removes only what this run wrote."""
    execution, config = job.get("execution"), job.get("config") or {}
    if not isinstance(execution, dict):
        return {"state": "refused", "code": "invalid_job", "detail": "report job without execution"}
    logo = logo_path.read_bytes() if logo_path and logo_path.is_file() else None
    now = datetime.now().astimezone()
    raw = build(execution, config.get("labels"), logo, now, job.get("position"))
    stem = f"Relatorio_{_safe_stem(execution.get('process_name') or 'Execucao')}_{now.strftime('%Y%m%d-%H%M')}"
    target_dir = folder or documents_folder()
    written = None
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        for n in range(1, 1000):
            target = target_dir / (f"{stem}.pdf" if n == 1 else f"{stem}[{n}].pdf")
            try:
                with open(target, "xb") as f:
                    written = target
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
                break
            except FileExistsError:
                continue
        if written is None:
            return {"state": "failed", "code": "report_write_failed", "detail": stem}
        back = written.read_bytes()
        pages = well_formed(back)
        if back != raw or pages < 1:
            raise ValueError("what was saved differs")
    except (OSError, ValueError) as e:
        if written is not None:
            try:
                written.unlink()
            except OSError:
                return {"state": "uncertain", "code": "report_not_verified", "detail": written.name, "reason": type(e).__name__}
        return {"state": "failed", "code": "report_write_failed", "detail": stem, "reason": type(e).__name__}
    return {"state": "verified", "verified": True, "context": {"report": {
        "file": written.name, "bytes": len(back), "pages": pages, "sha256": hashlib.sha256(back).hexdigest()}}}
