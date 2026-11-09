-- RedRise v2 Core schema, version 12: a deleted account is erased (user decision of 09/11/2026, ACCOUNT-ERASURE-20261109).
-- The row stays only so the history keeps pointing to it (display name and internal user name); its e-mail,
-- password, identity link and remembered devices go, so the e-mail can open a new account, never linked to that history.
UPDATE sessions SET revoked = true WHERE user_id IN (SELECT id FROM users WHERE deleted_at IS NOT NULL);
UPDATE sessions SET device_id = NULL
 WHERE device_id IN (SELECT d.id FROM remembered_devices d JOIN identity_links l ON l.subject = d.subject
                      JOIN users u ON u.id = l.user_id WHERE u.deleted_at IS NOT NULL);
DELETE FROM remembered_devices
 WHERE subject IN (SELECT l.subject FROM identity_links l JOIN users u ON u.id = l.user_id WHERE u.deleted_at IS NOT NULL);
DELETE FROM identity_links WHERE user_id IN (SELECT id FROM users WHERE deleted_at IS NOT NULL);
UPDATE users SET email = NULL, pw_hash = '!' WHERE deleted_at IS NOT NULL;
