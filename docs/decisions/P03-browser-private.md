# P03 — private Browser (decisions)

Status: development (2026-10-27). **P03 cannot be verified before P02** (roadmap order); the user authorized P03 development while P02 awaits the clean VM.

| ID | Decision | Why |
|---|---|---|
| P03-D1 | Browser infrastructure = **Playwright for Python 1.63.0** (published 2026-09-15, Apache-2.0) + its bundled driver (`node.exe` inside the wheel) + **Chrome for Testing 153.0.8010.12** (Playwright chromium rev 1243), all inside the package. Deps: greenlet 3.5.6 (MIT AND PSF-2.0), pyee 13.0.1 (MIT), typing-extensions 4.16.0 (PSF-2.0). 1.64.x was rejected as too recent (< 2 weeks) | Roadmap requires private Playwright/Chromium, prepared at build time and never downloaded on first use. No customer Node/pip |
| P03-D2 | `PLAYWRIGHT_BROWSERS_PATH` is set **by the adapter process** to `<install>/browsers`; the global `%LOCALAPPDATA%\ms-playwright` is never used. The proof checks the launched `chrome.exe` path | B04: no global cache |
| P03-D3 | The Engine stays the owner of record → compile → run. A browser **adapter process** (`runtime/python` + `redrise_browser`) is a platform adapter, like `engine-win`. The Rust Engine starts it and talks JSON lines over stdio. Capture uses the same capture controller, manifest and integrity rules; compile produces IR actions; the executor drives the adapter | The Engine's contracts are not bypassed by a Playwright script (roadmap P03.2). Amends E01-D1: an Engine adapter may run as a managed child process in the private runtime |
| P03-D4 | Recording captures **trusted DOM events** in a headed Chromium window: `click`, `change` (value), `keydown Enter`, and navigation, each with a selector computed in-page (`data-testid` > `id` > `name` > role/text > CSS path). Untrusted (script-generated) events are ignored | Records what the user did in the UI, with stable targets |
| P03-D5 | IR **v2** = v1 plus `browser_goto`, `browser_click`, `browser_fill`, `browser_press`. v1 procedures remain valid; browser actions are only allowed with `category: browser`. Clicks and Enter presses are effectful (conservative) | Versioned, additive IR |
| P03-D6 | Effects are verified independently by reading the system of record (the synthetic page's server-side store), never from page text. Fault injection: the server can show "saved" without persisting, and the verifier must refute it | B04, B16 |
| P03-D7 | Browser runs with a fresh, run-scoped profile under the data root (no user profile, no persisted cookies) | Isolation and privacy |

Licences to carry into P10/P14: Playwright Apache-2.0 NOTICE/LICENSE, Chrome for Testing (Chromium BSD-3 plus `about:credits` third-party notices), Node.js bundled in the driver (MIT plus third-party notices in `driver/LICENSE`).
