# Identity contract and remote proposal (N0)

> **Suspended on 02/11/2026 by the user** until automations work. Sign-up now only records the account in the Core. This document is the record to resume from. Removed code is kept outside the repository at `C:/Users/raulv/RedRise-v2-dev/research/identity-supabase-backup-20261102`.

02/11/2026. Task `REDRISE-IDENTITY-UI-20261102`. Implemented locally; **nothing was applied to Supabase, V1, SMTP or callbacks, and no remote call was made.** Real sign-up and login are **blocked for acceptance** until section 3 is resolved.

## 1. Contract implemented

| Boundary | Contract | Where |
|---|---|---|
| Configuration | `identity.json` beside the binaries: `supabase_url` (https), `publishable_key`, optional `redirect_to`. Public values only, kept out of the repository. Lab source: `C:/Users/raulv/RedRise-v2-dev/config/identity.json`, packaged by `build-release.ps1`. Absent: `IDENTITY-NOT-CONFIGURED`, and the team user sign-in remains | `packaging/`, `identity.rs`, `identity.py` |
| Provider calls | Native layer only, REST: `signup`, `token?grant_type=password\|refresh_token`, `resend`, `recover`, `logout?scope=local`. The window CSP stays closed; the web view never holds provider tokens | `desktop/src-tauri/src/identity.rs` |
| Identity check | Core asks the configured project who owns the token (`/auth/v1/user`), requires `aud=authenticated` and proof of e-mail, and keys on the stable subject. Mirrors V1 `emailPossessionVerified`: an account with `redrise_password_account` needs `redrise_email_possession=true` | `core/redrise_core/identity.py` |
| Membership | `identity_links` (subject to one team user). No link: `IDENTITY-NO-MEMBERSHIP`. E-mail and metadata never grant anything; role stays in `users` | `service.py`, migration 003 |
| Joining a team | One explicit link: verified account plus the team user and password (`POST /api/v1/identity/link`). No automatic join, no admin by sign-up | `service.py`, `auth.tsx` |
| Remembered session | Opt-in. Refresh token in Windows Credential Manager, rotated under a per-user lock and written before use. Unchecked: process memory only. Absolute 30 days per device, enforced by the Core; restoring does not extend it | `vault.rs`, `identity.rs`, `service.py` |
| Devices | `remembered_devices` per subject and installation; list and revoke only your own, no tokens. Sign-out revokes this device and its Core sessions, provider `scope=local`, never global | `service.py`, `configuracoes.tsx` |

Decision taken in this increment, to review: the explicit link above is the smallest membership path that keeps "no automatic join". Invitations are not implemented.

## 2. Reuse from V1 (read-only, with provenance)

Adapted, not copied as a runtime: token check and possession rule from `server/src/auth/supabase.ts` (lines 15-27 and 125-129). Deliberately not reused: `admin.createUser(email_confirm:true)`, the number/symbol password rule, cookies, Paperclip runtime, service role.

## 3. Unknowns that block real sign-up

Only local sources were read. V1's project URL and key exist as environment bindings; `.env` files were not opened. Each row needs the remote state.

| # | Question | Local evidence | If it fails | Who |
|---|---|---|---|---|
| R1 | Is `redrise_guard_password_write` applied? | `supabase-password-guards.sql` raises on any password write without server metadata | Public sign-up cannot work: the app shows `IDENTITY-SIGNUP-BLOCKED`. Needs a hosted V2 endpoint (R6); do not remove the guard | Dashboard or read-only SQL |
| R2 | Are password accounts allowed in the project? | `identity-supabase-auth.yaml`: `no-password-authentication-in-beta`, providers `[github]` | Same as R1; changing it is a V1 policy decision | User |
| R3 | Password policy allows 8 characters with no number or symbol? | V1 app rule is 8 + number + symbol; the remote value is unknown | `IDENTITY-PASSWORD-WEAK` on V2. Global setting, must not change silently | Dashboard |
| R4 | Confirm e-mail is on, SMTP works, rate limits? | Not provable locally | With auto-confirm the app refuses the session (`IDENTITY-SIGNUP-BLOCKED`) | Dashboard, one synthetic test |
| R5 | Where do confirmation and recovery links land? | `https://redrise.app/login` is planned, not deployed. Without an allowlisted `redirect_to` the project's Site URL (V1) is used | Confirmation may land on V1. **Recovery has no V2 page to set the password**, and the V1 guard requires a nonce for password changes. Recovery is therefore only requested, not proven end to end | User decision |
| R6 | V1 impact of V2 accounts | Manifest: `direct_signup: new-company-onboarding` | A V2 sign-up may be able to enter V1 onboarding in the shared project. Must be checked before real accounts | User, V1 test |

## 4. Proposed remote changes (not applied)

Nothing below happens without concrete approval. Order: read-only first.

1. **Read-only:** `GET <project>/auth/v1/settings` with the publishable key (shows `disable_signup`, `mailer_autoconfirm`, providers), and the dashboard or SQL checks for R1-R3. Impact: none.
2. **One synthetic sign-up** to a mailbox you name: confirm, sign in, profile, sign-out. Impact: one row in the shared `auth.users` and one real e-mail. Rollback: delete that account in the dashboard (you do it).
3. **If R1/R2 block public sign-up:** a minimal hosted V2 endpoint in the existing trusted service that validates the 8-character rule and creates the account *with a real confirmation e-mail*, holding the privileged key server-side. The Core and the desktop never hold it. Needs a separate diff and approval.
4. **Allowlist** `redirect_to` for the agreed confirmation page, and decide the recovery page. Rollback: remove the entry.
5. **Social:** Google/GitHub need a desktop return path (PKCE and a loopback or deep link) and the allowlist. They are shown as unavailable until then.

No new project, trigger removal, auto-confirm or global policy change is proposed.

## 5. Remote results (02/11/2026)

- Public settings (read-only): sign-up enabled, auto-confirm off, providers `email` and `github`; Google off.
- One real sign-up, made by the user in the installed beta.15: refused with `IDENTITY-SIGNUP-BLOCKED`, provider code `unexpected_failure`.
- **Hypothesis, not proven:** R1, the V1 password guard. To confirm, read-only, in the Supabase SQL editor:

```sql
select tgname from pg_trigger where tgrelid = 'auth.users'::regclass and not tgisinternal;
```

Expect `redrise_password_write_guard` if R1 holds. The Auth log for that request should show the database message. Also check whether the e-mail now exists in `auth.users`.

If confirmed, public sign-up cannot work and item 3 of section 4 applies. A hosted endpoint in the same project must set `redrise_password_account` server-side, send a real confirmation and record `redrise_email_possession`, because the Core requires that proof for such accounts. Recovery needs the same treatment, since the guard requires a nonce for password changes.

## 6. Proposal after the trigger was confirmed (not applied)

The user confirmed that the trigger exists on the project, so public sign-up cannot work and is not worth retrying. Sources read: V1 `server/src/auth/password-provider.ts` and `routes/password-auth.ts`.

**Service.** One Supabase Edge Function in the same project, so no new project and no V1 code change. The service role stays in the function; the app and the Core only call its public URL.

| Action | Behavior |
|---|---|
| `signup` | Validates 8 characters and the name; `admin.createUser` with `email_confirm: true` and `app_metadata { redrise_password_account: true, redrise_email_possession: false }`, the same contract V1 uses to pass the guard. Same answer for a new or an existing e-mail. Sends the confirmation |
| `confirm` | Proves the e-mail, then sets `redrise_email_possession: true` with a timestamp |
| `resend` | Sends the confirmation again; same answer for any e-mail; rate limited |
| `recover` + `recover/finish` | E-mail code plus new password; `updateUserById` with `redrise_email_possession: true` and a new `redrise_password_change_nonce`, as V1 does |

Sign-in stays on the provider. It succeeds before confirmation because the account is created as confirmed, so **the Core is what blocks it**, with `IDENTITY-UNCONFIRMED`; that rule is already implemented and tested. The app must map this refusal to the "Confirme o e-mail" message, as it does now.

**Decision needed: how the e-mail is confirmed.**

| Option | For | Against |
|---|---|---|
| A. 6-digit code typed in the app (recommended) | Needs no web page, callback or domain; also solves recovery; a mail scanner cannot confirm by opening a link | Changes A02, which asks for a "Confirmar" button |
| B. "Confirmar" button in the e-mail, as A02 says | Keeps the decision | Edge Functions serve HTML as plain text, so a GET must confirm and redirect. A mail scanner can then confirm an account registered by someone else, with that person's password, and V1 trusts the same flag. `https://redrise.app/login` is not deployed for V2 |

**Risks to accept or test.**
- V2 accounts satisfy V1's `hasRedrisePassword`, so they can sign in to V1 and reach its onboarding (R6). V1 is not changed by this proposal.
- A V2 password of 8 letters is below V1's number and symbol rule. V1 checks that rule when a password is created, not at sign-in.
- Whether `admin.createUser` applies the project's password policy (R3) is unknown until the first test.

**Needed to deploy, done by the user.** Deploy the function, and set the Resend key and sender as function secrets. Rollback: delete the function; accounts already created stay until removed by hand.

## 7. Decision and implementation (02/11/2026)

The user chose the link in the e-mail, through the Resend `onboarding` template; A02 stands. Implemented, not deployed: [services/identity-function](../../services/identity-function/README.md). It differs from section 6 in three points:

- The confirmation link is signed by the function itself, so no provider OTP is used and no account can be created by asking for a link.
- `resend` needs the account's password, so an e-mail address alone cannot locate an account or send mail to it.
- **Recovery is not in the function.** The app still calls the provider's `recover`, and the guard refuses a password change made that way. Recovery remains unproven until a path is decided.

Accepted risk from section 6, option B: a mail scanner opening the link confirms the account. The Resend Events API cited by the user manages event schemas and does not record clicks, so the function records the click.
