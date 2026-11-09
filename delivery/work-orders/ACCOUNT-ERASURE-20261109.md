# ACCOUNT-ERASURE-20261109 — conta excluída é apagada e o e-mail volta a ficar livre

- **Data:** 09/11/2026. **Produto:** `product:redrise-v2`. **Repositório:** `D:\Correnth\products\redrise-v2\repos\app` (`main`, base `4245527`).
- **Pedido do usuário (09/11, no chat, com a captura da recusa `ACCOUNT-EMAIL-RESERVED` em + Nova Conta):** "Quando excluímos uma conta, ela deve ser de fato excluída dos registros, constando apenas no log/histórico... mas deve ser possível criar uma nova conta com o e-mail de uma que foi excluída". Autorizou atualizar, gerar o update, fazer commit e push e atualizar tudo.
- **Substitui:** a decisão 4 da seção 9 da [TEAM-ACCOUNTS-20261108](TEAM-ACCOUNTS-20261108.md) (e-mail de conta excluída reservado) e a parte correspondente de P05-D16. O restante daquela WO continua valendo.

## 1. Regra

1. Excluir conta continua exigindo conta inativa, relida sob trava, com confirmação, e continua sem Reativar.
2. A conta excluída é **apagada**: e-mail, senha, vínculo de identidade externa e dispositivos lembrados são removidos; todas as sessões terminam.
3. Fica só o que o **histórico** mostra: o nome de exibição e o usuário interno, na mesma linha, para execuções, revisões, agendamentos e rotinas continuarem dizendo quem fez o quê. Não há exclusão em cascata do histórico.
4. O **e-mail fica livre**: + Nova Conta (e o cadastro público) com ele cria uma conta nova, com outro id e outro usuário interno (`.2`, `.3`…), nunca ligada ao histórico da excluída.
5. A senha antiga não abre nada. Uma conta viva continua recusando outra com o mesmo e-mail (`ACCOUNT-EXISTS`).

## 2. Implementação

- **Migração 012** (`core/redrise_core/migrations/012_account_erasure.sql`): aplica a regra às contas já excluídas (pela 0.1.0-beta.29): revoga sessões, desliga e remove dispositivos lembrados e vínculos de identidade, zera e-mail e senha (`pw_hash = '!'`, que não confere com nenhuma senha). Sem mudança de esquema.
- **Core 0.3.9** (`service.py`): `delete_user` faz o mesmo na exclusão; `create_account` deixa de consultar contas excluídas (o código `ACCOUNT-EMAIL-RESERVED` sai do catálogo e da máscara pt-BR); login e vínculo de identidade ignoram contas excluídas (mesmo tempo de resposta de usuário inexistente).
- **Desktop 0.1.0-beta.30:** o diálogo Excluir conta diz que o e-mail e a senha são removidos, que o e-mail fica livre para uma conta nova e que o nome continua só no histórico; o assistente volta à etapa E-mail só em `ACCOUNT-EXISTS`.
- **Voltar à 0.1.0-beta.29:** o Core 0.3.8 lê a base migrada; contas apagadas continuam fora da lista e sem acesso. Contas excluídas depois disso por ele voltariam a reservar o e-mail até a próxima atualização. Reverter a migração 012 não recupera e-mails e senhas apagados (só o backup feito antes de migrar).

## 3. Aceite

- **Core:** `tests/core/test_team_accounts.py` (test_03 com a linha apagada; test_03b e-mail reutilizado em conta nova, senha antiga recusada, usuário interno diferente; test_03c migração 012 sobre conta excluída pela regra antiga).
- **UI:** `desktop/tests/team-accounts.test.tsx` (texto do diálogo; recusa de e-mail volta à etapa).
- **Prática no laboratório:** `proofs/account-erasure/accept_erasure.py` (migração 012 sobre a base da beta.29, apagando as contas já excluídas; o caso do usuário pela tela: excluir e criar de novo com o mesmo e-mail); `proofs/team-accounts/accept_team.py` cenário delete atualizado.
- Gate `verify-candidate.ps1`, rollback numa cópia, canal local assinado, update real pelo app.

## 4. Registro de execução

Ver o checkpoint [ACCOUNT-ERASURE-20261109](../checkpoints/ACCOUNT-ERASURE-20261109.md) e a evidência `delivery/evidence/ACCOUNT-ERASURE-20261109/evidence.json`.
