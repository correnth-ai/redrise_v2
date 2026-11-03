# Reutilização do Supabase V1 para identidade V2

02/11/2026. Pesquisa local read-only; não comprova configuração implantada. Relacionada à [work order](../../delivery/work-orders/IDENTITY-UI-20261102.md).

## Conclusão

É viável manter **o mesmo projeto Supabase e emissor de identidade**. O V1 já implementa Supabase Auth; não é apenas PostgreSQL com Better Auth. O reuso não está pronto para copiar integralmente: confirmação, política de senha, guard triggers, armazenamento desktop e vínculo com equipe precisam de adaptação. Não criar outro projeto; não levar o runtime Paperclip nem service_role ao cliente.

## Evidências locais

Root V1: `D:/Correnth/products/redrise/repos/platform`.

| Fonte | Comportamento observado |
|---|---|
| `server/src/auth/supabase.ts:15–27` | Cliente Auth valida token com `getUser`, audiência e estado de confirmação |
| `server/src/auth/supabase.ts:69–113` | Associação de subject Supabase à identidade local; não confiar apenas em e-mail |
| `ui/src/lib/supabase.ts:1–8` | SDK, PKCE, persistência e auto-refresh web |
| `server/src/routes/password-auth.ts:57–111` | Rotas reais de cadastro/login/recuperação |
| `server/src/auth/password-provider.ts:18–39` | Serviço exige configuração privilegiada/flags e templates; cadastro administrativo com `email_confirm:true`, `full_name`, `redrise_email_possession:false`, seguido de login |
| `server/src/routes/auth.ts:96–140` | GET/PATCH de perfil |
| `packages/shared/src/password-policy.ts:5–15` | Mínimo 8 + número + símbolo; diverge do pedido V2 |
| `server/src/auth/supabase-password-guards.sql:7–26` | Trigger proposta exige metadado administrativo no cadastro com senha e nonce em alteração |
| Mesmo SQL, linhas 30–41 | Bloqueio de vínculo entre provedores distintos |
| `ui/src/api/auth.ts:387–400` | Fluxo GitHub OAuth |
| `server/src/__tests__/supabase-auth.test.ts`, `password-auth-routes.test.ts` | Testes existentes como referência; não executados nesta pesquisa |

O SQL tem instrução de aplicação condicionada. Existência do arquivo **não prova aplicação no Supabase remoto**. Código também não prova que SMTP, providers, callbacks ou flags estejam ativos hoje.

## Decisão arquitetural para o plano

1. Mesmo emissor/projeto Auth, sujeito estável (`sub`) como chave de identidade; perfil `full_name` como apresentação.
2. Core V2 continua autoritativo para equipe/role, processos e estações, no PostgreSQL já existente da equipe. Conta Supabase não equivale a membership e jamais cria admin por simples cadastro.
3. Adapter de identidade verifica credencial pelo mecanismo documentado e seguro; adapter de sessão guarda segredo renovável no cofre do SO, não storage web padrão; perfil é validado e retornado por endpoint autenticado.
4. Registro de dispositivos lembrados pertence ao V2 e à conta; não reutilizar cookie V1 ou inventário de Runner como se fosse sessão humana. Logout/revogação por dispositivo, sem logout global V1.
5. Identidades locais V2 existentes preservadas, com migração/vinculação explícita e prova de titularidade; nada de associação automática por e-mail.

Se public signUp estiver liberado e compatível, usar o fluxo normal Supabase. Se o guard V1 estiver ativo, projetar endpoint V2 no serviço hospedado confiável existente/adaptado, com confirmação verdadeira. Não instalar uma chave administrativa no Core da equipe para fazer cadastro. Não remover guard ou habilitar auto-confirmação para fazer a UI parecer funcional.

## Compatibilidades que precisam de verificação autorizada

- Projeto/ref e ambiente efetivos, chaves públicas corretas, sem ler/expor segredo em artefato.
- Política remota de senha: V2 deve aceitar oito caracteres sem impor número/símbolo; não alterar V1 globalmente. Caso configuração global impossibilite coexistência, apresentar conflito e solução delimitada antes de aplicar.
- Guard triggers instalados, fluxos admin/public permitidos, separação de metadados controlados pelo servidor e pelo usuário.
- Posse de e-mail: `email_confirm:true` legado não substitui confirmação real. Verificar `redrise_email_possession` ou prova equivalente; preservar timestamp auditável.
- SMTP/Resend efetivamente configurado, templates, limites, callbacks allowlisted e retorno desktop; nenhuma suposição de e-mail entregue por resposta HTTP.
- Google/GitHub disponíveis e fluxo PKCE/retorno correto; não ligar contas por coincidência de e-mail nem inserir Apple por causa do layout.
- Isolamento e autorização do V2, políticas de leitura e revogação de dispositivo; testes de não regressão V1 em ambiente autorizado.

Mudanças em serviço/SQL/policy/callback remotos precisam de diff, impacto, rollback e aprovação concreta. Esta pesquisa não leu `.env`, não acessou credenciais/usuários e não executou chamadas no Supabase. Nenhum novo projeto foi criado.

## Fontes primárias externas consultadas

- [Supabase: sessões](https://supabase.com/docs/guides/auth/sessions): access/refresh, renovação e identificador de sessão. O plano deve respeitar rotação e não presumir logout global adequado para V2.
- [Supabase: autenticação por senha](https://supabase.com/docs/guides/auth/passwords): signup/login, confirmação, callbacks e recuperação. Recursos documentados não comprovam configuração no projeto existente.

## Limite da implementação atual V2

`desktop/src/lib/api.ts:51–54` usa sessionStorage para token Core, sem opção de lembrança; `core/redrise_core/service.py:124–148` emite sessão local e revoga por token. Nenhum dos dois implementa, por si só, identidade Supabase, cofre persistente ou listagem de dispositivos humanos. Isso explica o escopo técnico de F2 sem afirmar que toda perda de sessão tenha uma única causa demonstrada.
