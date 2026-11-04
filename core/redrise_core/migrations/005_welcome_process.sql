-- RedRise v2 Core schema, version 5: Boas-vindas test process (work order
-- UI-ENGINE-BOAS-VINDAS-20261103). Additive. A notepad_step routine is one of
-- the three steps the Runner performs on the Windows Notepad; `system_key`
-- marks the ready-made process, which the Core creates once per team.
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_kind_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_kind_check
  CHECK (kind IN ('template', 'procedure', 'browser_open', 'notepad_step'));
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_check
  CHECK ((kind = 'template' AND template_id IS NOT NULL) OR (kind = 'procedure' AND procedure IS NOT NULL)
         OR (kind IN ('browser_open', 'notepad_step') AND config IS NOT NULL));
ALTER TABLE processes ADD COLUMN system_key text UNIQUE;
