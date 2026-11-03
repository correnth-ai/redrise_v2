# Checkpoint — identidade, sessão e navegação

- 02/11/2026. Task `REDRISE-IDENTITY-UI-20261102`; [evidência](../evidence/IDENTITY-UI-20261102/evidence.json); [registro para retomar a identidade](../../docs/identity/IDENTITY-N0-CONTRACT-20261102.md).
- `main`, HEAD unborn. Nada commitado nem publicado fora do canal local. Instalada: beta.17 (`daeb7842…7fff`, gate aprovado, assinada no canal local). Código com isolamento de teste após a beta.17, fora de commit.

## Estado

- **Decisão do usuário:** identidade externa suspensa até as automações funcionarem.
- **Cadastro:** grava só no Core, sem e-mail nem confirmação. Conta inativa, operador; administrador ativa em Configuração › Equipe. Padrão escolhido pelo agente, a revisar.
- **Login:** Core, por e-mail ou usuário. Sessão não lembrada; F2 segue aberto.
- **Mantido:** Empresa, navegação, F3–F8, módulo de identidade no Core sem cliente, migração 003.
- **Removido do repositório, com cópia em `C:/Users/raulv/RedRise-v2-dev/research/identity-supabase-backup-20261102`:** função de cadastro, `identity.rs`, `vault.rs`, `lib/identity.ts`.
- **Remoto:** nada alterado no Supabase nem no Resend.
- **Testado em instância isolada (`C:/Users/raulv/RedRise-v2-dev/lab-test`):** cadastro, recusa antes da ativação, ativação, login como operador, saída. Conta sintética própria do agente; contas do usuário não são usadas.
- **Incidente:** a primeira instância de teste parou o PostgreSQL instalado por cerca de um minuto; restaurado e causa corrigida (ver evidência).

## Próxima ação segura

Automações, conforme a direção do usuário. A instância de teste só roda com `REDRISE_TEST_VAULT` e `REDRISE_DATA_ROOT` juntos.
