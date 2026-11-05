-- RedRise v2 Core schema, version 6: Nova Rotina (work order
-- UI-ENGINE-BOAS-VINDAS-20261103). Additive. An app_open routine opens an
-- installed application or a chosen file. Stations report what they can
-- launch. A job's mode separates the assistant's preparation and test from a
-- run: `prepare` resolves without opening, `test` opens what was resolved.
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_kind_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_kind_check
  CHECK (kind IN ('template', 'procedure', 'browser_open', 'notepad_step', 'app_open'));
ALTER TABLE routine_versions DROP CONSTRAINT routine_versions_check;
ALTER TABLE routine_versions ADD CONSTRAINT routine_versions_check
  CHECK ((kind = 'template' AND template_id IS NOT NULL) OR (kind = 'procedure' AND procedure IS NOT NULL)
         OR (kind IN ('browser_open', 'notepad_step', 'app_open') AND config IS NOT NULL));
-- NULL = not reported (older Runner); [] = reported, none found.
ALTER TABLE stations ADD COLUMN apps jsonb;
ALTER TABLE jobs ADD COLUMN mode text NOT NULL DEFAULT 'run' CHECK (mode IN ('run', 'prepare', 'test'));
