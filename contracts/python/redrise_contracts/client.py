"""Core API client with certificate pinning (P05-D5), stdlib only.

The peer certificate's SHA-256 is compared with the fingerprint from the join
code *before* any request bytes (tokens, passwords) are sent. Transport
failures become CORE-UNREACHABLE / CORE-CERT-MISMATCH diagnostics; a Core
error body is returned as the producer's diagnostic (never replaced)."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import socket
import ssl

from . import diagnostics as dg


class CoreError(Exception):
    def __init__(self, status: int, diagnostic: dg.Diagnostic):
        super().__init__(diagnostic.error_code)
        self.status, self.diagnostic = status, diagnostic


class CoreClient:
    def __init__(self, host: str, port: int, fingerprint: str, token: str | None = None, timeout_s: float = 15.0,
                 reported_by: str = "RR-UI"):
        self.host, self.port, self.fp = host, port, fingerprint.lower()
        self.token, self.timeout_s, self.by = token, timeout_s, reported_by
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE  # identity is the pinned fingerprint below
        self._ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    def _unreachable(self, reason: str, cid: str | None, sent: bool) -> CoreError:
        d = dg.make("CORE-UNREACHABLE", reported_by=self.by, correlation_id=cid, params={"reason": reason},
                    effect_state="unknown" if sent else "none", technical_details={"host": self.host, "port": self.port})
        return CoreError(0, d)

    def call(self, method: str, path: str, body: dict | None = None, correlation_id: str | None = None,
             timeout_s: float | None = None) -> dict | list:
        cid = correlation_id or dg.new_correlation_id()
        conn = http.client.HTTPSConnection(self.host, self.port, context=self._ctx, timeout=timeout_s or self.timeout_s)
        sent = False
        try:
            try:
                conn.connect()
            except (OSError, ssl.SSLError) as e:
                raise self._unreachable(type(e).__name__, cid, False) from None
            der = conn.sock.getpeercert(binary_form=True) or b""
            if not hmac.compare_digest(hashlib.sha256(der).hexdigest(), self.fp):
                raise CoreError(0, dg.make("CORE-CERT-MISMATCH", reported_by=self.by, correlation_id=cid))
            headers = {"Content-Type": "application/json", "X-Correlation-Id": cid}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            data = json.dumps(body or {}).encode("utf-8") if method != "GET" else None
            try:
                conn.request(method, path, body=data, headers=headers)
                sent = method != "GET"
                resp = conn.getresponse()
                raw = resp.read()
            except (OSError, http.client.HTTPException, socket.timeout) as e:
                raise self._unreachable(type(e).__name__, cid, sent) from None
        finally:
            conn.close()
        try:
            obj = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            raise CoreError(resp.status, dg.contract_violation("RR-CORE", self.by, "api/v1 JSON", "response is not JSON",
                                                               reported_by=self.by, correlation_id=cid)) from None
        if 200 <= resp.status < 300:
            return obj
        diag = obj.get("diagnostic") if isinstance(obj, dict) else None
        if diag is None or dg.validate(diag):
            raise CoreError(resp.status, dg.contract_violation("RR-CORE", self.by, "redrise.diagnostic/1",
                                                               f"HTTP {resp.status} without a valid diagnostic",
                                                               reported_by=self.by, correlation_id=cid))
        raise CoreError(resp.status, dg.from_dict(diag))
