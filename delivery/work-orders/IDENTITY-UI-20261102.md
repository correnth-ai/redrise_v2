# Work Order — identidade funcional, sessão lembrada e navegação

Task ID: `REDRISE-IDENTITY-UI-20261102`. Data: 02/11/2026, Brasil.
Estado: **planejamento pronto para engenharia; implementação não iniciada por esta work order**.
Produto/repo: `product:redrise-v2` / `repo:redrise-v2`.
Root: `D:/Correnth/products/redrise-v2/repos/app`; remote autorizado: `https://github.com/correnth-ai/redrise_v2.git`.
Branch observada: `main`; HEAD unborn; conteúdo local não rastreado deve ser preservado.
Digest anterior à edição documental: `3af2026430e2b2f26f72c067eea248f6ce29d7fd733601177e9519efe76dfbf9` (368 arquivos).
Roadmap: incremento de identidade/UI em P08/P09/P11/P13; não encerra P13 nem homologa o produto inteiro.

## 1. Pedido, autoridade e limites

O usuário pediu nova work order e prompt de engenharia: login-03/signup-03 sobre a paisagem fornecida; cadastro real com nome completo/e-mail/senha; sessão lembrada; reaproveitamento do mesmo projeto Supabase do V1; página inicial Empresa; menus no singular; pt-BR por máscaras; SOLID e KISS; reavaliar F2–F8.

Esta rodada autoriza pesquisa read-only no V1 e documentação/assets locais no V2. **Não executa implementação, instalação, cadastro remoto ou mudança no Supabase.** O prompt associado autoriza a futura engenharia local quando submetido. Registro e login funcionais são aceite obrigatório dessa implementação, não uma alegação da documentação.

Precedência: pedido explícito de 02/11 → esta work order e APP-RULES atualizada → regras anteriores compatíveis. Substituídos neste escopo: login-05/signup-05; cadastro manual somente com e-mail/sem senha; menus Processos/Fluxos/Configurações; proibição de estudar/reutilizar seletivamente o V1 para identidade. Originais, hashes e evidências anteriores ficam preservados.

Sem novo projeto Supabase. V1 é fonte de leitura, não write-set. Compartilhar identidade não autoriza compartilhar permissões, banco operacional, sessões web ou dados de empresas.

Antecessor: `delivery/evidence/BROWSER-UPDATE-20261101/evidence.json`, SHA256 `ccdaffdb9202398b938e6542836688bbabc37ca5908145a7e215ba08b6ee6b4c`.
Último candidato registrado: `0.1.0-beta.14`, Runner `0.3.2`; campanha concluída, revisão nula/pendente; closed beta disponível, Beta completo não homologado, não publicado. Revalidar estado no início da engenharia.

## 2. Estado encontrado e escopo de entrega

| Capacidade | Encontrado | Aceite deste update |
|---|---|---|
| Login instalado | Core local, usuário/senha; token em sessionStorage | Login e-mail/senha real integrado à identidade e vínculo autorizado com Core, preservando acesso legado durante transição |
| Cadastro | Fixture de demonstração | Nome completo, e-mail, senha e confirmação da senha; persistência e confirmação reais |
| Persistência da sessão | Sem remember-me desktop | Opt-in seguro, sobrevive a fechar/reabrir, reboot e update compatível |
| Estação | Runner registrado e heartbeat | Preservar inventário; mostrar separadamente dispositivos com sessão lembrada |
| Nome | Core possui display; V1 usa full_name | Nome completo autenticado em Configuração › Equipe/perfil, sem usar nome como autorização |
| Painéis | Processos/Fluxos/Configurações reais | Nova navegação; Empresa demonstrativa explicitamente identificada; demais funções reais preservadas |
| Supabase | Código V1 implementa Auth | Mesmo projeto existente; compatibilidade remota e envio ainda precisam ser comprovados |

## 3. Login e cadastro: composição e comportamento

Referências oficiais: `https://ui.shadcn.com/blocks/login` (`login-03`) e `https://ui.shadcn.com/blocks/signup` (`signup-03`). Comandos indicados pelo usuário: `npx shadcn@latest add login-03` e `npx shadcn@latest add signup-03`. São referências de obtenção dos blocos: revisar fonte/licença, fixar versão e adaptar componentes existentes; não executar @latest indiscriminadamente nem instalar Next.js por causa da estrutura do exemplo.

- Fundo compartilhado em toda a área de login/register: `assets/auth/login-register-background.png`, cópia sem alteração da paisagem do usuário. `background-size: cover`, proporção preservada, sem distorção; recorte responsivo. Formulário sobreposto, centralizado, com marca RedRise acima, card legível e opaco ou com overlay suficiente para contraste; rodapé abaixo do card. Preservar controles nativos integrados da janela. Sem painel lateral dividido.
- Referências anexadas preservadas em `docs/ui/references/identity-20261102/`. Reproduzir hierarquia, espaçamento, bordas arredondadas e largura compacta dos cards. Empresa usa tema do shell; a paisagem fica apenas no acesso/cadastro.
- Login: título **Bem-vindo de volta**, **E-mail**, **Senha**, **Lembrar de mim neste computador**, **Entrar**, **Esqueceu a senha?**, **Não tem uma conta? Criar conta**. `autocomplete` apropriado; senha não pré-preenchida pelo app. Botões sociais previamente decididos continuam Google/GitHub, sem Apple; não copiar Apple da imagem. Social não configurado não simula sucesso; indicar indisponibilidade claramente.
- Cadastro: **Crie sua conta**, **Nome completo**, **E-mail**, **Senha**, **Confirmar senha**, **Criar conta**, **Já tem uma conta? Entrar**. Senha/confirmar lado a lado quando houver espaço, empilhadas em largura menor. Única orientação estática de composição: **A senha deve ter no mínimo 8 caracteres.** Sem checklist de número/símbolo/maiúscula. Validar mínimo também no backend; senhas divergentes e campos inválidos continuam com erro contextual. Não alterar senha antiga ou impor política de criação no login.
- Nome Unicode preservado, incluindo acentos; e-mail normalizado conforme contrato do provedor; senha nunca normalizada, aparada ou gravada em perfil/log. `full_name` é dado de apresentação, nunca role/admin/membership.
- Após cadastrar: conta pendente, envio de confirmação, instrução pt-BR. Sem acesso antes de confirmar. Preservar **Confirme o e-mail para fazer o login.** e **Reenviar confirmação.** com backend responsável pelo bloqueio. Não reutilizar o `email_confirm:true` do V1 como prova de posse. Contas legadas precisam de evidência de posse real, não só timestamp criado administrativamente.
- Confirmação registra prova/data no servidor e oferece retorno seguro ao app. `https://redrise.app/login` segue destino planejado, não callback implantado presumido. Resolver callback/deep link real e allowlist antes de envio externo; nenhum token em URL arbitrária/log. Não adicionar link/código em todo novo login.
- Recuperação real pelo provedor/serviço compatível; não deixar link morto nem fingir envio. Termos/Privacidade usam destino existente validado, sem inventar aceite/publicação jurídica.
- Todas as strings, estados, placeholders e nomes acessíveis vêm da máscara pt-BR do produto, incluída no bundle. Não traduzir códigos/contratos/provedores. Remover textos ingleses residuais também em overlays e componentes compartilhados.

## 4. Lembrar de mim: decisão de UX adotada e contrato

**Escolha de implementação recomendada nesta work order:** entrada automática, após validação/renovação de sessão, quando a pessoa marcou Lembrar de mim. É mais rápida e simples do que voltar a um formulário preenchido. O app nunca salva nem repõe a senha. Checkbox desmarcado por padrão; opt-in por conta, instalação e usuário Windows.

| Situação | Comportamento esperado |
|---|---|
| Marcado + sessão válida | Abrir diretamente Empresa após validação; sem flash de login |
| Fechar/reabrir, reiniciar PC ou atualizar app | Restaurar a mesma sessão lembrada quando válida; não duplicar dispositivo nem encerrar por trocar binários |
| Desmarcado | Credencial apenas em memória do processo; fechar de fato o app encerra o acesso local, sem restauração no próximo início |
| Apenas minimizar | Não é logout; preservar sessão em memória |
| Expirou/revogada/conta desativada | Limpar credencial inválida e pedir login; pode lembrar e-mail não secreto se consentido, nunca senha |
| Rede temporariamente indisponível | Estado recuperável pt-BR, sem autorizar acesso por fixture ou apagar sessão válida por todo erro de rede |
| Sair | Revogar sessão deste dispositivo e apagar segredo local; não logout global que derrube V1/outros dispositivos |
| Esquecer dispositivo | Revogar lembrança e sessões Core derivadas; confirmação clara; se for atual, retornar ao login |

Definir no contrato um limite V2 documentado de 30 dias absolutos por lembrança como padrão técnico proposto, respeitando qualquer expiração menor do provedor. Não modificar a política global do projeto compartilhado. Refresh rotativo não estende esse prazo indefinidamente; uma nova autenticação consentida pode criar nova lembrança. Validar sem exigir plano pago por inferência.

Persistência: cofre Windows por usuário (Credential Manager/DPAPI conforme adapter revisado), fora dos binários; refresh/credencial renovável no adapter nativo, access token efêmero. Não usar localStorage/sessionStorage/JSON de preferências para segredo persistente; nenhum service_role/admin key no desktop ou Core instalado no cliente. Uma autoridade única serializa refresh e grava rotação de forma atômica, para evitar corrida entre janelas/updates. Não levar tokens para evidências.

Separar módulos pequenos: provedor de identidade, perfil, armazenamento seguro, coordenador da sessão e autorização Core. Usar interfaces já existentes quando suficientes; não construir framework genérico. O Core verifica identidade autenticada e membership da equipe no servidor, vinculando subject estável do provedor, nunca apenas e-mail fornecido pelo frontend. Cadastro público não cria administrador nem ingressa automaticamente na equipe. Preservar bootstrap/admin/operador e contas locais até migração explícita.

## 5. Configuração › Estação e perfil

No mesmo submenu **Estação**, apresentar:

1. **Estação atual / Estações conectadas**: inventário real de Runner/host, conexão, disponibilidade da sessão Windows; independe de Lembrar de mim.
2. **Estações lembradas**: dispositivos com lembrança ativa deste usuário; nome do computador, usuário exibido, este dispositivo, última atividade e expiração/estado, ação **Esquecer dispositivo**. Um dispositivo offline pode continuar lembrado; lembrado não significa online nem apto a automatizar.

Metadados V2 mínimos: id opaco do dispositivo, subject, id da instalação/perfil Windows, referência opcional à estação Runner, id da sessão ou grant V2, criação/último uso/expiração/revogação. Secret/token não integra listagem. Não inventar fingerprint de hardware. Novos logins no mesmo perfil atualizam a entrada; múltiplos usuários não veem sessões de outros. Administrador não ganha acesso a tokens. Revogar Runner e esquecer login são operações distintas.

Configuração › Equipe mostra o nome completo do perfil autenticado e o nome no registro do membro vinculado. Operador pode ver seu próprio perfil mesmo sem acesso à administração da equipe. Nada de mudança de papel por editar nome. Cadastro/login/renovação recuperam perfil real, não fixture.

## 6. Navegação final e preservação das funções

```text
Empresa                 ← primeira página após entrar/restaurar sessão
Rotina
  Lista
  Atividade
Processo
  Ação
  Histórico
  Kanban
Configuração
  Equipe
  Estação
  Aplicativo
```

Esta é a ordem final após as correções faladas do usuário. Sem menu Gantt; o gráfico visual de Empresa pode ter barras temporais, sem criar um módulo Gantt. Singular em todos os itens da sidebar; títulos de listas dentro da página podem usar plural natural.

Mapeamento funcional para não perder entregas:
- Rotina › Lista: catálogo/cadastro/edição de rotinas e acesso contextual aos modelos e gravação existentes.
- Rotina › Atividade: atividade e registros técnicos de rotinas, com filtro/acesso ao histórico relacionado; não duplica fonte de execução nem cria novo motor.
- Processo › Ação: composição/lista de processos, ordem/continuação e diálogo compartilhado de execução, incluindo execução isolada permitida. Antigos atalhos de execução apontam ao mesmo caso de uso.
- Processo › Histórico e Kanban: reaproveitar histórico e Kanban reais de Fluxos, incluindo filtros/detalhes/contexto. Sem arraste que declare verificação manual.
- Configuração: equipe/estação/aplicativo preservados; acrescentar perfil/sessões conforme seções anteriores.
- Rota antiga/deep link interno recebe alias controlado para destino novo; não reescrever IDs de rotinas/processos ou resultados antigos para renomear menu. Retorno de login, conta trocada e sessão restaurada iniciam em Empresa; detalhes abertos dentro da sessão continuam navegáveis.

## 7. Empresa — referência visual observada

URL visitada no navegador em 02/11/2026: `https://shadcn-nextjs-admincn-admin-template.vercel.app/dashboard/productivity`. Observação direta de screenshot e árvore acessível, não apenas descrição por nome.

- Sidebar esquerda de aproximadamente 250 px e conteúdo à direita; header horizontal arredondado acima do conteúdo; espaços de aproximadamente 24 px entre cards; cards escuros com borda/sombra discreta, títulos no topo esquerdo.
- Primeira faixa: card largo dividido em aproximadamente 2/3 para linha do tempo horizontal com barras coloridas e 1/3 para lista de quatro projetos com ícones coloridos e subtítulo de progresso.
- Segunda faixa: dois cards de tamanho semelhante: gráfico de visão semanal e taxa/indicador com minigráfico.
- Abaixo, a página contém card de plano/pagamento, card de desempenho com abas e uma tabela com filtros e paginação. Reproduzir composição, densidade e posicionamento, adaptando o conteúdo a Empresa: visão de recursos/armazenamento no lugar de cobrança/cartão, desempenho da empresa e tabela de atividades/equipe. Não adicionar Stripe, coleta de cartão, compra de plano ou um catálogo de menus do template por referência visual.
- Cabeçalho pode preservar pesquisa/ações existentes; não inserir botões de notificação/pesquisa sem comportamento ou apresentação honesta. Manter controles da janela do app.
- Dados numéricos e séries fictícias estão autorizados **nesta página**, com selo persistente **Dados demonstrativos** e fonte de fixtures própria. Sem gravar no Core nem confundir com a campanha Browser. Demais telas e autenticação usam dados reais. Gráficos/barra temporal em Empresa não comprovam integração ou execução real.
- Em larguras menores, empilhar os cards preservando a ordem; tabela tem rolagem localizada. Claro/escuro e zoom/teclado legíveis. Não copiar código de template comercial sem licença verificada; reconstruir visual com componentes já licenciados do projeto quando necessário.

## 8. Reuso do Supabase e dependências verificadas

Estudo técnico: [SUPABASE-V1-REUSE-20261102](../../docs/identity/SUPABASE-V1-REUSE-20261102.md).

Direção: **mesmo projeto Supabase e emissor Auth**, dados operacionais V2 continuam no Core/PostgreSQL da equipe. Reutilizar contratos/padrões e somente trechos necessários com proveniência, não importar o runtime Paperclip/V1. O estudo local não comprova projeto remoto/configuração implantada.

Antes de cadastro real: confirmar identidade do projeto existente por configuração segura, política de senha, guard triggers efetivamente aplicados, envio/confirmar e-mail, providers/callbacks e isolamento de dados. Não revelar chave/URL com segredo na work order. Se cadastro público suportar o contrato, preferir SDK/Auth padrão. Se guard V1 exigir criação administrativa, preparar endpoint V2 mínimo em serviço confiável hospedado e confirmação real; esse serviço nunca é o Core instalado no PC do cliente. Definir e revisar o contrato/diff antes de qualquer alteração externa.

Sem diminuir proteção global do V1, remover trigger, recriar conta ou usar auto-confirmação para contornar incompatibilidade. O mínimo de 8 do V2 não pode virar número/símbolo exigidos silenciosamente pelo backend. Se configuração compartilhada impedir, registrar incompatibilidade concreta, preparar solução compatível isolada e obter a autorização externa necessária. Conta existente V1 não recebe acesso V2 por existir ou por e-mail coincidir; entrada e vínculo exigem prova e membership. Não ligar identidades sociais automaticamente por e-mail.

## 9. Reavaliação dos achados F2–F8

Nenhum achado é fechado por planejamento ou renomeação. IDs originais e evidência preservados.

| ID | Decisão de escopo | Aceite / prioridade |
|---|---|---|
| F2 | Absorvido por identidade/sessão lembrada; ainda aberto | P1: marcada restaura após fechamento/reboot/update; desmarcada não restaura; logout/revogação e cofre comprovados |
| F3 | Continua válido | P1: detalhes de falha exibem os quatro tópicos pt-BR e códigos, reaproveitando o mesmo diagnóstico do registro |
| F4 | Continua válido, independente do redesign | P2: consultas conforme visibilidade/atividade; sem loop ocioso global de ~2,7 s; registrar antes/depois e manter atualização de execução ativa |
| F5 | Continua válido em Atividade/Histórico | P1 de acessibilidade: registro abre por teclado/foco visível, Enter/Espaço, sem depender do mouse |
| F6 | Continua válido | P2: último item mostra fim; continuação só quando existe próxima etapa e vínculo aplicável |
| F7 | Absorvido pela revisão global pt-BR e menus | P1: máscara para rótulos/fechar acessível; nome completo disponível por layout/expansão acessível sem truncamento irrecuperável |
| F8 | Continua válido no contexto Browser | P2: título final coerente com documento confirmado, sem mudar critério de verificação ou trocar guia |

Executar F2/F3/F5/F7 nos incrementos tocados; F4/F6/F8 como correções delimitadas depois da identidade/navegação, com regressão Browser proporcional. F1 continua corrigido e vira regressão da máscara embutida. Homologação formal Edge/Brave continua pendente; este pedido não a concede.

## 10. Incrementos, verificação e conclusão

| Inc. | Entrega e dependência | Prova mínima |
|---|---|---|
| N0 | Revalidar árvore/status/evidência, decidir contrato Auth/Core e configuração reutilizável; sem segredo | Matriz de contratos, impacto V1 e diff externo separado; fontes e skills fixadas |
| N1 | Login-03/signup-03 reais no bundle, fundo e máscaras; depende de N0 para adapter | Typecheck/build; inspeção visual em temas/larguras; navegação e validação de campos; sem fingir backend |
| N2 | Adapter Supabase, cadastro/confirmação/login/recuperação/perfil e membership; depende da compatibilidade remota de N0 | Contratos locais negativos/positivos; cadastro sintético autorizado no mesmo projeto, recebimento/confirmar, login, perfil; confirmar que V1 não regrediu |
| N3 | Cofre + coordenador de sessão + lembranças/listagem/revogação; depende N2 | Isolamento entre contas/usuários Windows, refresh concorrente/rotação, expiração/revogação, offline recuperável; sem segredo em bundle/log |
| N4 | Empresa e nova árvore; realocar funções sem alterar resultados | Inspeção de Empresa com selo e fixtures; rotas antigas/novas; autorização, fontes reais e mesmo diálogo de execução |
| N5 | F3/F5/F7 e depois F4/F6/F8 | Checks focados e inspeção de teclado/pt-BR; métricas de polling; teste de último item/contexto |
| N6 | Candidato local identificado e campanha instalada | Gate; login/cadastro reais, fechar/reabrir, reboot coordenado pelo usuário, update compatível, esquecer/logout; smoke P1/P2 Browser, Histórico/Kanban; revisão independente |

Usar `npm run typecheck`/`npm run build:ui` no espelho de build em C:, testes pertinentes em `tests/contracts`, `tests/core`, `tests/runtime` e testes novos de identidade/sessão com entradas significativas. Banco local de teste isolado em C:. Executar `node scripts/validate-base.mjs` para integridade documental; não é prova de identidade nem Beta. Cobrir senha de 7 recusada/8 sem número-símbolo aceita; divergência; conta pendente/reenvio; duplicação/retorno perdido; assinatura/audiência/subject inválidos; conta sem membership; nome acentuado; refresh expirado/revogado; logout de V2 sem derrubar V1.

Campanha real só em contas sintéticas de destino autorizado. Envio real, alteração de Supabase/serviço hospedado/callback e uso de credenciais privilegiadas exigem revisão/aprovação concreta aplicável. Preparar primeiro implementação e diff de configuração/migração, impactos/reversão e validações locais; não pedir permissão abstrata antes de ter algo revisável. Não criar projeto substituto se houver bloqueio. Reinício do PC fica coordenado pelo usuário, sem reiniciar à força ou fechar documentos.

Conclusão exige distinguir `implemented`, `locally-tested`, `remote-configured`, `installed-tested`, `reviewed`; não substituir prova remota por fake. Se falta acesso remoto, terminar o independente e registrar registro/login real como **bloqueado para aceite**, não entregue. `beta_ready` e `published` não mudam por esta work order.

## 11. Write-set, recuperação e evidência

Engenharia autorizada pelo prompt: `desktop/**`, `core/redrise_core/**`, migrações V2 aditivas, `contracts/**`, `tests/**`, assets autorizados e documentação/evidência desta tarefa. Runner/Engine só nos pontos diretamente afetados por F8/compatibilidade e preservação de sessão; não reconstruir Engine/Excel. V1 permanece read-only; qualquer write-set remoto/V1 é diff proposto separado, sem aplicar implicitamente.

Fora: originais/hash locks, provas históricas, dados reais/credenciais, produto antigo em escrita, canal/site públicos, novo projeto Supabase, dependências cloud da automação, preços/Stripe/Gantt. Assets/background e documentos não viram instalação da feature.

Build/runtime/cache/dependências em `C:/Users/raulv/RedRise-v2-dev`; fonte em D:. Dados/config/cofre fora de binários. Updater mantém **Pode atualizar / Ainda não** e preserva estado seguro. Sem commit/push/publicação/assinatura/instalação implícitos pela elaboração do plano; futura campanha/assinatura segue autorização específica.

Recuperação: preservar beta.14 e evidência; migrações aditivas com backup de teste; manter conta local existente acessível durante transição; nenhum reset/clean, remoção de usuários, logout global ou downgrade que ignore schema. Falha externa não autoriza trocar projeto/provedor nem burlar confirmação. Stop em efeito remoto incerto, segredo exigido no cliente, mudança protegida ou regressão no V1; concluir incrementos independentes.

Evidência futura: `delivery/evidence/IDENTITY-UI-20261102/`, com comandos/resultados, origem/hash do código adaptado, build/hash/inventário, screenshots sintéticos, limitações e revisão independente (revisor ainda não designado; não autoaprovar). Registrar causa conhecida vs hipótese; quatro tópicos e códigos conforme ERROR-DIAGNOSTICS.

## 12. Skills, memória, grafo e próxima ação

Router executado em 02/11, run `REDRISE-IDENTITY-UI-20261102`: selecionou `scope-planning`, `task-context-checkpoint`, `better-auth-setup`. Aplicada somente `scope-planning` (`fd7b13af53a7853d7cbd43ac9f72e801d602c7fb4e592981ac4842e4ded58bfa`) nesta elaboração. `better-auth-setup` rejeitada por adequação: V1 usa Supabase Auth, não há decisão de introduzir Better Auth. Checkpoint de continuidade não necessário para esta entrega de documentação. Skill do host computer-use lida para inspeção visual da referência pública.

Antes de mutação de código, reexecutar router para a capacidade real, resolver os nomes exatos pelo catálogo e ler as skills pertinentes (frontend/localização/identidade/cofre/contratos conforme selecionadas), sem pré-carregar catálogo. Reavaliar em nova dependência, mismatch de schema/plataforma, falha inesperada ou ampliação de escopo.

Memória consultada com workspace `correnth`, project `redrise-v2`: serviço local indisponível (conexão recusada); fallback canônico. Grafo sem contexto válido no router; fontes locais e código usados, sem extração/rebuild. Pesquisa V1 delegada read-only delimitada; sem subdelegação/escrita ou segredo. Principal conferiu os pontos críticos na fonte.

Próxima ação: submeter [AGENT-START-IDENTITY-UI](../../docs/AGENT-START-IDENTITY-UI.md) ao engenheiro, começar N0 e seguir os incrementos até os aceites possíveis, reportando precisamente as dependências externas.
