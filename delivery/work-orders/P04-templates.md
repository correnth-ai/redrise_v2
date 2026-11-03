# Work Order — P04 everyday templates (development; unverifiable until P02/P03)

```text
Task ID / Run ID: TASK-REDRISE-V2-BETA-20261026 / RUN-P04-20261027-01
Human request: 2026-10-27 — start P04 template development (Boas-vindas, Excel, Browser, Outlook, Gmail candidates) while the VM is pending; P02/P03 stay unverified. Later the same day: the user required Save As to set the folder in the dialog's navigation field and only the file name in "Nome do arquivo", and asked for the corresponding skill update.
Root: D:/Correnth/products/redrise-v2/repos/app. Lab: C:/Users/<user>/RedRise-v2-dev.
Allowed write set: templates/**, runner/redrise_runner/{templates,verifiers,apps}.py (+ CLI), engine CLI flags, proofs/templates/**, proofs/* Save As steps, tests/runtime/**, docs/decisions/P04-*.md, delivery/evidence/P04/**, delivery/status.json; corporate skill catalog: skills/windows-file-dialog-navigation/** + catalog-lock.json (authorized by the user).
Boundaries on this machine: no write to the user's OneDrive Desktop, no Outlook launch (real mailbox), no credentials entered anywhere, Gmail only in a fresh RedRise profile.
Stop: a template claiming success without its verifier, overwriting existing files, or reading or sending mail.
```
