"""Identity provider adapter (Supabase Auth, the same project as RedRise V1).

The Core never trusts an e-mail or a role sent by a client: it asks the provider
who owns an access token and uses the stable subject. Membership and roles stay
in this server. Only the public project URL and publishable key are configured
here (identity.json beside the binaries); no privileged key exists on this side.
Adapted from V1 server/src/auth/supabase.ts (userForToken, emailPossessionVerified)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

TIMEOUT_S = 15


class ProviderUnavailable(Exception):
    pass


class TokenRefused(Exception):
    pass


class EmailUnconfirmed(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str
    full_name: str | None
    email_confirmed_at: str


class Verifier(Protocol):
    def verify(self, access_token: str) -> Identity: ...


def identity_of(user: dict) -> Identity:
    """Validated identity of a provider user record, or the reason it is refused."""
    subject, email = user.get("id"), user.get("email")
    if user.get("aud") != "authenticated" or not isinstance(subject, str) or not subject or not isinstance(email, str) or not email:
        raise TokenRefused("token without an authenticated user")
    confirmed = user.get("email_confirmed_at")
    app_meta = user.get("app_metadata") if isinstance(user.get("app_metadata"), dict) else {}
    # V1 password accounts are created administratively as confirmed: only its explicit proof counts.
    possession = app_meta.get("redrise_email_possession") is True if app_meta.get("redrise_password_account") is True else bool(confirmed)
    if not confirmed or not possession:
        raise EmailUnconfirmed()
    meta = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    name = next((meta[k].strip() for k in ("full_name", "name") if isinstance(meta.get(k), str) and meta[k].strip()), None)
    return Identity(subject, email, name, confirmed)


class SupabaseVerifier:
    def __init__(self, url: str, publishable_key: str):
        self.url, self.key = url.rstrip("/"), publishable_key

    def verify(self, access_token: str) -> Identity:
        req = urllib.request.Request(f"{self.url}/auth/v1/user",
                                     headers={"apikey": self.key, "Authorization": f"Bearer {access_token}"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 - fixed https project URL from configuration
                user = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404):
                raise TokenRefused(f"provider answered {e.code}") from None
            raise ProviderUnavailable(f"provider answered {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise ProviderUnavailable(type(e).__name__) from None
        if not isinstance(user, dict):
            raise ProviderUnavailable("unexpected provider answer")
        return identity_of(user)


def load_verifier(install_root: Path) -> SupabaseVerifier | None:
    """None when this installation has no identity configuration (honest: e-mail sign-in unavailable)."""
    try:
        cfg = json.loads((install_root / "identity.json").read_text(encoding="utf-8"))
        url, key = cfg["supabase_url"], cfg["publishable_key"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not (isinstance(url, str) and url.startswith("https://") and isinstance(key, str) and key):
        return None
    return SupabaseVerifier(url, key)
