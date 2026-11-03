-- Sign-up recorded in the Core (user decision of 02/11/2026): an e-mail for team
-- users. Additive; existing users keep their username and have no e-mail.
ALTER TABLE users ADD COLUMN email text UNIQUE;
