# Checkpoint — ACCOUNT-ERASURE-20261109

- **Data:** 09/11/2026. **WO:** [ACCOUNT-ERASURE-20261109](../work-orders/ACCOUNT-ERASURE-20261109.md). **Evidência:** [evidence.json](../evidence/ACCOUNT-ERASURE-20261109/evidence.json).
- **Entregue:** excluir conta apaga e-mail, senha, vínculo de identidade e dispositivos lembrados; fica só nome e usuário interno para o histórico; o e-mail volta a abrir conta nova, nunca ligada ao histórico antigo. Migração 012 aplica isso às contas já excluídas. `ACCOUNT-EMAIL-RESERVED` retirado. Decisão P05-D17.
- **Versões:** 0.1.0-beta.30 (Core 0.3.9, Runner 0.3.11), instalador `2a9ecac2…`, fonte `237f015` (código idêntico em `fd3ba8d`).
- **Validações:** testes do Core (15 módulos, todos OK; `test_team_accounts` 15), UI 81/81, contratos 17, validate-base 346/368; gate aprovado; prova prática no laboratório (migração 012 apagando a conta já excluída; o caso do usuário pela tela; contas e exclusão da TEAM-ACCOUNTS); rollback para a beta.29 numa cópia aprovado.
- **Canal e instalação real:** canal local assinado com a beta.30; app real atualizado pelo próprio update em 09/11 às 09:00, reaberto às 09:01 na tela de login; Core 0.3.9, backup antes da migração, executor pronto e sem erro.
- **Usuário:** entrar na equipe real e criar de novo a conta com o e-mail da conta excluída (o caso da captura); esta sessão não usa as credenciais da equipe.
- Revisão independente não designada. Nada publicado (MediaFire segue adiado); commits enviados ao `origin/main`.
