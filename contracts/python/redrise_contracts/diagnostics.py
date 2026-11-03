"""Structured diagnostics (U27-ERROR-DIAGNOSTICS, docs/ERROR-DIAGNOSTICS.md).

A `Diagnostic` carries the four topics (what happened; completed and pending
with the effect state; next action; separate technical details) and renders
ending with the footer line `Code: <error> | Modules: <codes>`.

Backend texts are English ASCII (contracts/errors.json). The user-facing
language is a mask applied by the desktop from `error_code` and `params`
(desktop/locale/pt-BR.json), which also renders the localized footer.

Module codes point to responsibilities to investigate (contracts/modules.json);
they are hints, never proof that a module is defective. Producers' codes and
causes are preserved when a consumer wraps them (`wrap`).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA = "redrise.diagnostic/1"
CATEGORIES = ("module_internal", "contract", "communication", "environment", "precondition", "unknown")
EFFECT_STATES = ("none", "partial", "confirmed", "unknown")
DIAGNOSIS_STATUSES = ("confirmed", "suggested", "unconfirmed")
RETRY = ("safe", "after_fix", "check_first", "not_useful")

_HERE = Path(__file__).resolve().parent


def _find(name: str) -> Path:
    # Source tree: contracts/python/redrise_contracts -> contracts/<name>;
    # installed layout: <install>/contracts/python/redrise_contracts -> <install>/contracts/<name>.
    return _HERE.parent.parent / name


def load_json(name: str) -> dict:
    return json.loads(_find(name).read_text(encoding="utf-8"))


_CATALOG: dict | None = None
_MODULES: dict | None = None


def catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = load_json("errors.json")["errors"]
    return _CATALOG


def module_codes() -> set[str]:
    global _MODULES
    if _MODULES is None:
        _MODULES = load_json("modules.json")["modules"]
    return set(_MODULES)


# ---------------------------------------------------------------- sanitizing

_SECRET_KEY = re.compile(r"pass(word|wd)?|secret|token|authori[sz]ation|cookie|connection[_-]?string|dsn|api[_-]?key|credential", re.I)
_OMIT_KEY = re.compile(r"^(argv|command_line|cmdline|environ|env)$", re.I)
_PROFILE = re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"']+")
_MAX_STR = 2000


def sanitize(value):
    """Technical details safe to show/copy: secrets redacted, process argv and
    environment omitted, user-profile paths reduced to %USERPROFILE%."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            ks = str(k)
            if _SECRET_KEY.search(ks):
                out[ks] = "[redacted]"
            elif _OMIT_KEY.match(ks):
                out[ks] = "[omitted]"
            else:
                out[ks] = sanitize(v)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        s = _PROFILE.sub("%USERPROFILE%", value)
        return s if len(s) <= _MAX_STR else s[:_MAX_STR] + "...[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize(str(value))


# ---------------------------------------------------------------- model

class _Safe(dict):
    def __missing__(self, key):  # unknown placeholder stays visible, never crashes rendering
        return "{" + key + "}"


def _fmt(text: str, params: dict) -> str:
    return text.format_map(_Safe({k: sanitize(v) for k, v in params.items()}))


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class Diagnostic:
    error_code: str
    category: str
    what_happened: str
    completed: str
    pending: str
    effect_state: str
    next_action: str
    retry: str
    details_summary: str
    reported_by: str
    module_hints: list[str]
    diagnosis_status: str = "unconfirmed"
    boundary: dict | None = None
    correlation_id: str = field(default_factory=new_correlation_id)
    version: dict = field(default_factory=dict)
    technical_details: dict = field(default_factory=dict)
    cause: "Diagnostic | None" = None
    # Placeholder values (sanitized strings) so the UI mask can render its own texts.
    params: dict = field(default_factory=dict)
    schema: str = SCHEMA

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cause"] = self.cause.to_dict() if self.cause else None
        return d

    def render(self) -> str:
        return render(self)


def make(error_code: str, *, reported_by: str, params: dict | None = None, correlation_id: str | None = None,
         version: dict | None = None, technical_details: dict | None = None, effect_state: str | None = None,
         extra_modules: list[str] | None = None, boundary: dict | None = None,
         diagnosis_status: str | None = None) -> Diagnostic:
    """Builds a diagnostic from the catalog. An unknown code becomes UNMAPPED
    (RR-DIAG) keeping the original code; no association is invented."""
    params = dict(params or {})
    entry = catalog().get(error_code)
    tech = dict(technical_details or {})
    if entry is None:
        params.setdefault("original_code", error_code)
        tech.setdefault("original_code", error_code)
        error_code, entry = "UNMAPPED", catalog()["UNMAPPED"]
    hints = list(dict.fromkeys([*entry["modules"], *(extra_modules or [])]))
    return Diagnostic(
        error_code=error_code,
        category=entry["category"],
        what_happened=_fmt(entry["what"], params),
        completed=_fmt(entry["completed"], params),
        pending=_fmt(entry["pending"], params),
        effect_state=effect_state or entry["effect_state"],
        next_action=_fmt(entry["next"], params),
        retry=entry["retry"],
        details_summary=_fmt(entry["details"], params),
        reported_by=reported_by,
        module_hints=hints,
        diagnosis_status=diagnosis_status or ("suggested" if entry["category"] == "module_internal" else "unconfirmed"),
        boundary=boundary,
        correlation_id=correlation_id or new_correlation_id(),
        version=dict(version or {}),
        technical_details=sanitize(tech),
        params={str(k): str(sanitize(v)) for k, v in params.items() if v is not None},
    )


_EFFECT_RANK = {"none": 0, "confirmed": 1, "partial": 2, "unknown": 3}


def wrap(inner: Diagnostic, error_code: str, *, reported_by: str, boundary: dict | None = None,
         params: dict | None = None, extra_modules: list[str] | None = None) -> Diagnostic:
    """A consumer adds its boundary/modules while preserving the producer's
    diagnostic as `cause`, its correlation id and the most uncertain effect."""
    outer = make(error_code, reported_by=reported_by, params=params, correlation_id=inner.correlation_id,
                 version=inner.version, boundary=boundary,
                 extra_modules=[*inner.module_hints, *(extra_modules or [])])
    if _EFFECT_RANK[inner.effect_state] > _EFFECT_RANK[outer.effect_state]:
        outer.effect_state = inner.effect_state
    outer.cause = inner
    return outer


FOOTER = "Code: {code} | Modules: {modules}"


def footer(d: Diagnostic) -> str:
    return FOOTER.format(code=d.error_code, modules=", ".join(d.module_hints or ["RR-DIAG"]))


_EFFECT_TEXT = {
    "none": "",
    "confirmed": "",
    "partial": " Part of the operation was already done.",
    "unknown": " An effect with unknown result exists.",
}


def render(d: Diagnostic, *, include_technical: bool = False) -> str:
    """Backend (English) text: four topics, footer as the last line. With
    `include_technical` (copy action) the sanitized details are appended
    before the footer, which stays last."""
    lines = [
        f"What happened: {d.what_happened}",
        f"Result: {d.completed} {d.pending}{_EFFECT_TEXT.get(d.effect_state, '')}".rstrip(),
        f"Next action: {d.next_action}",
        f"Diagnostic details: {d.details_summary} Reference: {d.correlation_id}.",
    ]
    if include_technical:
        tech = {"reported_by": d.reported_by, "category": d.category, "effect_state": d.effect_state,
                "diagnosis_status": d.diagnosis_status, "boundary": d.boundary, "version": d.version,
                "technical_details": d.technical_details,
                "cause": [c.error_code for c in _chain(d)][1:]}
        lines.append(json.dumps(sanitize(tech), ensure_ascii=False, indent=2))
    lines.append(footer(d))
    return "\n".join(lines)


def _chain(d: Diagnostic):
    while d is not None:
        yield d
        d = d.cause


# ---------------------------------------------------------------- contract

def validate(obj) -> list[str]:
    """Contract check for a diagnostic received across a boundary."""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["not an object"]
    if obj.get("schema") != SCHEMA:
        errs.append(f"schema {obj.get('schema')!r} != {SCHEMA!r}")
    for k in ("error_code", "what_happened", "completed", "pending", "next_action", "details_summary",
              "reported_by", "correlation_id"):
        if not isinstance(obj.get(k), str) or not obj.get(k):
            errs.append(f"{k} missing")
    if obj.get("category") not in CATEGORIES:
        errs.append("category invalid")
    if obj.get("effect_state") not in EFFECT_STATES:
        errs.append("effect_state invalid")
    if obj.get("diagnosis_status") not in DIAGNOSIS_STATUSES:
        errs.append("diagnosis_status invalid")
    if obj.get("retry") not in RETRY:
        errs.append("retry invalid")
    hints = obj.get("module_hints")
    if not isinstance(hints, list) or not hints or not all(isinstance(h, str) for h in hints):
        errs.append("module_hints must be a non-empty list")
    else:
        unknown = set(hints) - module_codes()
        if unknown:
            errs.append(f"unknown module codes {sorted(unknown)}")
    extra = set(obj) - _FIELDS
    if extra:
        errs.append(f"unknown fields {sorted(extra)}")
    for k, typ in (("version", dict), ("technical_details", dict), ("params", dict)):
        if k in obj and not isinstance(obj[k], typ):
            errs.append(f"{k} must be an object")
    if obj.get("boundary") is not None and not isinstance(obj["boundary"], dict):
        errs.append("boundary must be an object or null")
    if obj.get("cause") is not None:
        errs += [f"cause: {e}" for e in validate(obj["cause"])]
    return errs


_FIELDS = {"schema", "error_code", "category", "what_happened", "completed", "pending", "effect_state", "next_action",
           "retry", "details_summary", "reported_by", "module_hints", "diagnosis_status", "boundary", "correlation_id",
           "version", "technical_details", "cause", "params"}


def from_dict(obj: dict) -> Diagnostic:
    errs = validate(obj)
    if errs:
        raise ValueError("; ".join(errs))
    d = dict(obj)
    cause = d.pop("cause", None)
    out = Diagnostic(**d)
    out.cause = from_dict(cause) if cause else None
    return out


def contract_violation(producer: str, consumer: str, contract: str, reason: str, *, reported_by: str,
                       correlation_id: str | None = None) -> Diagnostic:
    """Invalid/unknown payload on a boundary: classified as contract, origin
    open between producer, consumer and composition."""
    return make("CONTRACT-PAYLOAD", reported_by=reported_by, correlation_id=correlation_id,
                params={"reason": reason, "contract": contract},
                boundary={"producer": producer, "consumer": consumer, "contract": contract},
                extra_modules=[producer, consumer])
