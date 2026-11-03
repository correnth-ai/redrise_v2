# Identidade register/login — proposta de contrato técnico (I7)

> Atualização 02/11/2026: este documento registra a proposta anterior. O pedido posterior definiu **nome completo/e-mail/senha**, login-03/signup-03, mesma infraestrutura Supabase do V1 e remember-me. Os pontos sobre ausência de senha, proibição de reuso de identidade V1 e opções de fator ainda abertas estão substituídos pela [nova work order](../../delivery/work-orders/IDENTITY-UI-20261102.md) e pelo [estudo Supabase](SUPABASE-V1-REUSE-20261102.md). Confirmação, prova de identidade e membership continuam necessários. A implementação real permanece pendente.

01/11/2026. Estado: **proposta, não implementada no backend nem homologada**. Decisões de produto vigentes: A01–A04 em [APP-RULES](../APP-RULES.md) e G38–G43 na [work order de discovery](../../delivery/work-orders/DISCOVERY-20261031.md). Este documento só organiza o que falta para o fluxo ser seguro; não reabre a dispensa de link/código em cada acesso (G43).

## O que existe no candidato 0.1.0-beta.11

| Item | Situação |
|---|---|
| Telas `register` (signup-05) e `login` (login-05) em pt-BR, com E-mail, Google, GitHub, sem Apple | Construídas apenas no build de demonstração (`npm run dev:demo`), com estados fictícios: conta pendente, literal vermelho **“Confirme o e-mail para fazer o login.”** com link **“Reenviar confirmação.”**, mensagem pós-cadastro. Nenhum envio, provedor ou backend é chamado. |
| Login do app instalado | Inalterado: usuário + senha da equipe em `/api/v1/login` (Core local), agora com layout login-05. Usuários, sessões e perfis existentes preservados. |
| Bootstrap criar/conectar equipe | Inalterado, em “Boas-vindas à RedRise”. |

## Por que não há fluxo funcional ainda

1. **Prova de sessão sem senha e sem link/código recorrente.** Só e-mail digitado não prova identidade; conceder sessão por ele permitiria a qualquer pessoa entrar como outra. Sem senha (G38) e sem link/código por acesso (G43), a prova precisa vir de um fator que a RedRise ainda não tem: provedor OAuth (Google/GitHub) a cada login, credencial do dispositivo (passkey/WebAuthn) registrada após a confirmação, ou sessão persistente vinculada ao dispositivo emitida na confirmação. Cada opção muda a UX ou exige serviço externo — decisão do usuário.
2. **Fronteira web × desktop.** O destino `https://redrise.app/login` é web; o app desktop autentica no Core da equipe (servidor local/LAN). Falta definir quem emite e valida a identidade (serviço web RedRise vs Core da equipe) e como uma conta confirmada vira membro de uma equipe com perfil.
3. **Serviços externos.** Envio de e-mail, OAuth Google/GitHub (client id/secret, callbacks) e o domínio/rota publicados exigem autorização específica, credenciais e possivelmente custos. Nada disso foi configurado; não usar contas/chaves/domínio do produto anterior.

## Contrato proposto (para decisão)

Entidades no serviço de identidade (onde quer que fique hospedado):

- `account`: id, e-mail normalizado (único), `status` `pending|confirmed|disabled`, `confirmed_at` (UTC, gerado pelo servidor), provedores vinculados (`google`/`github` com subject id, nunca só o e-mail do provedor).
- `confirmation`: hash do token aleatório (≥ 128 bits), account_id, `expires_at`, `used_at`; o e-mail leva o token no botão **Confirmar**; o servidor valida token+conta, grava `confirmed_at` e só então redireciona para `/login`. Repetir o clique após uso: mensagem idempotente “e-mail já confirmado”, sem novo timestamp. Endereço em query nunca é prova.
- `resend`: limitado por conta e por IP; invalida tokens anteriores; responde igual para e-mail existente ou não (sem enumeração).
- Login: backend recusa `pending` com código `IDENTITY-UNCONFIRMED` (a criar nos dois contratos: `contracts/errors.json` + máscara pt-BR, com o literal aprovado e a ação de reenvio). Social: retorno OAuth válido de conta `pending` também é recusado.
- Vínculo com o Core: membro da equipe passa a referenciar `account_id`; migração dos usuários atuais (usuário+senha) é opt-in e explícita — nenhuma conversão silenciosa, nenhum usuário removido.

Abertas para o usuário: (a) fator de prova por acesso entre as opções do item 1; (b) onde roda o serviço de identidade; (c) política de validade/reenvio; (d) posição de criar/conectar equipe no onboarding.

## Fora deste candidato

Envio real de e-mail, OAuth, publicação de rota/domínio, migração de contas, código `IDENTITY-UNCONFIRMED` no backend. Não marcar register/login como homologado pelo mock.
