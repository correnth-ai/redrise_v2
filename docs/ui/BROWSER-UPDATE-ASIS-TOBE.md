# UI — AS-IS / TO-BE do update Browser

31/10/2026. Complemento da [work order](../../delivery/work-orders/DISCOVERY-20261031.md) e do [mapa de regras](../APP-RULES.md). Começar por **register** e **login**, nomes confirmados pelo usuário.

Atualização 01/11/2026: usuário escolheu os [blocos complementares e adaptações](BROWSER-UPDATE-COMPONENTS.md). Referência ativa do esboço: `redrise-paineis-browser.html` no diretório de visualizações da conversa, com claro/escuro, Processos/Fluxos/Configurações, filtros, tabela, grade, Kanban, criação e logs. O esboço anterior fica como antecedente, não especificação concorrente.

**AS-IS**: conferido no código, sem nova inspeção visual do app instalado. **TO-BE aprovado**: decisão explícita do usuário. **TO-BE proposto**: sugestão a discutir, sem autorização automática de implementação. Browser é o novo modo de automação; register/login agora incluem os requisitos explícitos de identidade/confirmar e-mail descritos abaixo. Não tratar autenticação nova como migração apenas visual. Nenhum serviço externo foi configurado.

**Regra global confirmada:** toda a máscara da UI em Português do Brasil, incluindo títulos, campos, botões, links, erros, carregamentos, estados e acessibilidade. Identificadores `register`/`login`, nomes de provedores, códigos técnicos e URLs não são traduzidos. Textos ingleses das imagens são referências de layout, não cópia final.

## 1. Inventário de telas

| ID | AS-IS | TO-BE / situação |
|---|---|---|
| UI01 | Primeira abertura: criar equipe e conectar a equipe, em formulários lado a lado. | **register**, `signup-05`: e-mail ou Google/GitHub, confirmação obrigatória por e-mail. Equipe/onboarding ainda a definir. |
| UI02 | Logo, usuário, senha e Entrar, quando há conexão mas não sessão válida. | **login**, `login-05`, pt-BR e confirmação inicial obrigatória; sem novo link/código a cada acesso, conforme resposta do usuário. |
| UI03 | Sidebar recolhível: Rotina/Ação/Configuração, usuário/perfil, Sair; decoração nativa. | **`sidebar-03`**; menus **Processos, Fluxos, Configurações**, com painéis admin e controles integrados. |
| UI04 | Rotina: tabela, criar por modelo/gravação, versões e Executar. | Divisão aprovada: gestão em Processos, acompanhamento em Fluxos; execução acessível contextualmente nos dois. Controles/cards ainda a detalhar. |
| UI05 | Gravação: Windows/Browser, alvo Excel/Notepad, endereço, iniciar/parar, parâmetros e compilar/salvar. | Nova experiência Browser; decidir apresentação de recursos legados sem apagar dados. Não criar opções Excel novas. |
| UI06 | Executar: estação e inputs; cria job. | Valores cadastrados; permissão isolada e execução de processo; layout pendente. |
| UI07 | Ação: histórico atualizado a cada 3 s; detalhe com diagnóstico, timeline, resultado técnico e Cancelar quando aplicável. | Proposta: painel Fluxos leva ao acompanhamento/histórico com contexto e motivo do término. |
| UI08 | Configuração: estação/executor, servidor, browser privado, usuários, estações e Sobre. | Painel **Configurações**, com acesso às telas internas por cards/indicadores/botões; preservar funções. |
| UI09 | Update: indicador/toast e Pode atualizar/Ainda não; diagnósticos em quatro tópicos e cópia. | Preservar ao migrar UI; não adicionar melhorias funcionais do updater por suposição. |

Fontes: [main.ts](../../desktop/src/main.ts), [styles.css](../../desktop/styles.css), [dom.ts](../../desktop/src/dom.ts), [configuração Tauri](../../desktop/src-tauri/tauri.conf.json). Telas após acesso ainda não revisadas em detalhe com o usuário.

## 2. register — AS-IS

Hoje o equivalente é `renderWelcome()`, sem cadastro público de conta.

| Área | Campos atuais | Botão / efeito atual |
|---|---|---|
| Criar equipe neste computador | Nome da equipe; nome desta estação (`servidor`); usuário administrador; nome de exibição; senha; confirmar senha; porta local (`47800`). | **Criar equipe** valida senha/confirmar e chama `host_create`. |
| Conectar a uma equipe | Código da equipe; nome desta estação; usuário administrador; senha. | **Conectar** chama `station_join`. |

`host_create` inicia Core, cria equipe/primeiro administrador via `/api/v1/setup`, registra a estação host e inicia Runner. A UI faz login via `/api/v1/login`, guarda a sessão e abre Configuração com mensagem/código da equipe. `station_join` conecta/registra a estação e inicia Runner; a UI reavalia estado pelo `boot()` e apresenta login se não houver sessão. Não afirmar que Conectar já autentica a sessão da UI.

## 3. register — TO-BE atualizado

**Aprovados:** nome técnico `register`, referência `npx shadcn@latest add signup-05`, imagens fornecidas e máscara pt-BR. Registro manual tem somente **E-mail**; o usuário acrescentou expressamente as alternativas **Google** e **GitHub**, substituindo a exclusão anterior de login social. Sem Apple, apesar de aparecer na imagem de referência.

- Campo manual: **E-mail**. Não pedir usuário, nome de exibição, senha, confirmação, equipe, estação ou porta na register.
- Botão principal **Criar conta** (tradução do Create Account indicado pelo usuário). Alternativas **Continuar com Google** e **Continuar com GitHub**. Links entre telas em pt-BR; redação complementar proposta: “Já tem uma conta? Entrar”.
- Marca RedRise em lugar de Acme. Cabeçalho proposto: “Boas-vindas à RedRise”. Rodapé de termos/privacidade, se mantido da referência, precisa de texto pt-BR e destinos reais a definir; não inventar links ou termos.
- Equipe/primeiro administrador/conectar estação continuam capacidades existentes, mas sua posição no novo onboarding é pendente. Não removê-las do backend ou inventar equipe/credenciais automáticas para preencher lacunas.

| Controle | Ao acionar | Backend / retorno | Decisão |
|---|---|---|---|
| E-mail | Informar endereço do cadastro manual. | Validar obrigatoriedade/formato; digitar não confirma identidade. | Confirmado |
| Criar conta | Solicitar cadastro pendente e envio da confirmação ao endereço informado. | Conta fica não confirmada; não liberar sessão por aceitar e-mail. Contrato/serviço de envio ainda a definir. | Fluxo confirmado; não implementado |
| Continuar com Google/GitHub | Iniciar autenticação no provedor escolhido; após retorno válido, solicitar confirmação ao e-mail obtido. | Exigir confirmação RedRise também no social; não marcar confirmado só porque o provedor respondeu. Resolver ausência de e-mail/colisão de contas sem inventar identidade. | Provedores e confirmação aprovados; contratos pendentes |
| Entrar | Navegar para login. | Não criar conta/equipe por navegação. | Referência aprovada; adaptação pt-BR |

Estados: entrada, e-mail inválido, enviando, aguardando confirmação, falha de envio/provedor. Mensagem pós-envio proposta: “Enviamos um e-mail de confirmação. Abra a mensagem e clique em Confirmar.” Envio solicitado não equivale a entrega comprovada. Nenhum e-mail real, integração OAuth, provedor de envio, credencial ou domínio foi operado nesta elaboração.

## 4. login — AS-IS

`renderLogin()` tem logo, título “Entrar”, **Usuário**, **Senha** e botão **Entrar**. Foco inicial em Usuário. Submit chama `/api/v1/login`, guarda token de sessão e executa `boot()`; identidade é conferida em `/api/v1/me`. Com sessão válida, abre shell/menu atual, inicialmente Rotina. Erros ficam no formulário; diagnósticos estruturados usam quatro tópicos e códigos.

## 5. login — TO-BE para discutir

**Aprovados:** nome `login` e referência `npx shadcn@latest add login-05`, substituindo `login-03`.

- Referência fornecida: campo **E-mail**, botão **Entrar**, alternativas **Continuar com Google**/**Continuar com GitHub**, marca RedRise; sem Apple. Nenhum campo de senha foi solicitado.
- Confirmação prévia do e-mail é obrigatória, inclusive no social. Usuário dispensou link/código em cada acesso posterior: não criar esse passo no fluxo nem repetir a pergunta. Sessão/identidade continuam responsabilidade do contrato técnico; não presumir que somente informar e-mail concede sessão válida.
- Quando tentar entrar sem confirmação, exibir abaixo do botão, em vermelho, o literal **“Confirme o e-mail para fazer o login.”**, acompanhado do hyperlink **“Reenviar confirmação.”**
- Loading e impedimento de envio duplicado propostos; preservar e-mail digitado após falha. Link complementar proposto: “Não tem uma conta? Criar conta”.
- Não acrescentar lembrar-me/recuperação de senha. Perfil e permissões continuam decididos no backend, não pela entrada de e-mail.

| Controle sugerido | Ao acionar | Backend / retorno | Decisão |
|---|---|---|---|
| Entrar | Solicitar autenticação e consultar elegibilidade de confirmação. | Backend deve bloquear não confirmado; retornar estado que produz o literal vermelho e link. Método de autenticação manual confirmado ainda pendente. | Botão e bloqueio aprovados |
| Continuar com Google/GitHub | Executar fluxo do provedor escolhido. | Não emitir sessão utilizável sem confirmação exigida pela RedRise. | Provedores aprovados; fluxo técnico pendente |
| Reenviar confirmação. | Solicitar novo envio da confirmação. | Não confirma conta nem libera login por clicar; informar andamento/resultado em pt-BR. Política de reenvio e validade do link a definir. | Ação/literal aprovados |
| Criar conta | Navegar para register. | Sem criação de conta/equipe por navegação. | Referência aprovada; adaptação pt-BR |

Migração de usuários existentes, vínculo com equipe e fronteira identidade web/desktop são pendências explícitas; não excluir contas nem converter identificadores silenciosamente. Senha do Core local existente e login da conta descrita nestas telas não se tornam equivalentes sem contrato explícito.

### Confirmação por e-mail — evento e redirecionamento

1. Cadastro manual ou retorno social válido obtém o endereço e solicita a confirmação; permanece pendente.
2. O e-mail enviado contém botão **Confirmar**.
3. Ao clicar, o backend valida a prova vinculada àquela conta e registra a confirmação, com data e hora. Não aceitar somente um endereço em query como prova.
4. Após registrar a confirmação com sucesso, redirecionar para **`https://redrise.app/login`**, destino solicitado pelo usuário. O clique visa os dois efeitos, mas a liberação depende do registro backend, não do carregamento da página ou de um evento enviado pelo frontend.
5. Conta confirmada fica elegível para acesso. A confirmação não cria por si só equipe ou privilégios. Conforme decisão posterior, não solicitar novo link/código em cada acesso; preservar essa UX no contrato técnico de autenticação/sessão.

Contrato técnico futuro: estado pendente/confirmado e timestamp de confirmação da conta, gerado pelo servidor, com fuso/formato definidos na implementação. Validade/uso do link, repetição do clique, falha no envio e tentativa de reenvio ainda precisam de detalhe. Não alegar que rota/domínio ou disparo de e-mail estão publicados.

## 6. Componentes e aprovações

| Item | Origem | Situação |
|---|---|---|
| Nome UI01/UI02 | `register` / `login` | Confirmado pelo usuário em 31/10/2026 |
| register | `npx shadcn@latest add signup-05`: [referência oficial](https://ui.shadcn.com/blocks/authentication) | E-mail manual ou Google/GitHub; confirmação obrigatória; pt-BR |
| login | `npx shadcn@latest add login-05`: [referência oficial](https://ui.shadcn.com/blocks/authentication) | E-mail e Google/GitHub; bloqueio sem confirmação; autenticação manual posterior ainda a definir |
| Shell | `npx shadcn@latest add sidebar-03`: [referência oficial](https://ui.shadcn.com/blocks/sidebar) | Substitui sidebar-04; menus/painéis descritos abaixo |
| Imagem register | [Referência fornecida](references/register-reference.png) | Layout aprovado como referência; texto pt-BR, marca RedRise, GitHub substitui Apple |
| Imagem login | [Referência fornecida](references/login-reference.png) | Layout aprovado como referência; mensagem/verificação adicionadas sob o botão |
| Imagem sidebar | [Referência fornecida](references/sidebar-03-reference.png) | Base de sidebar, sem importar rótulos/menus de documentação |
| Imagem painel admin | [Referência fornecida](references/admin-dashboard-reference.png) | Estrutura de cards/indicadores; dados fictícios agora permitidos no esboço identificado, sem importar receita/vendas/planos como funções reais |

As quatro imagens foram preservadas byte a byte dos anexos fornecidos em 31/10/2026. São referências visuais, não instruções para importar Apple, Acme, termos/URLs de exemplo, métricas financeiras, navegação superior ou recursos ausentes da solicitação. Inputs/ações só são confirmados conforme decisões explícitas; estados/cópias propostos permanecem identificados.

Comandos dos blocos não executados. Versões/preset serão fixados antes da implementação. Aprovação de um bloco não aprova serviços/links fictícios contidos no exemplo. Nomes de tela não exigem renomear comandos internos ou endpoints existentes.

Ao aprovar um item, registrar tela/controle, decisão, componente/link, evento, efeito backend, estados e regra impactada. Atualizar work order/mapa quando houver mudança funcional. Cada aprovação será registrada, sem promover automaticamente as sugestões vizinhas.

## 7. Menus e painéis admin — padrão confirmado

**Decisão do usuário:** sidebar `sidebar-03` com **Processos**, **Fluxos**, **Configurações**. Cada menu principal abre sua página admin em formato de dashboard. Gestão, listas e parametrizações internas são acessadas por cards/indicadores e botões alinhados aos cards; o indicador também pode abrir o destino relacionado. Não abrir direto uma lista ao clicar no menu principal sem passar pelo painel acordado.

Os nomes antigos Rotina/Ação/Configuração são AS-IS, não rótulos TO-BE. “Admin” descreve o padrão de página solicitado; não introduz por si só um novo perfil, superadmin ou alteração das permissões atuais. O que cada perfil vê/aciona será mapeado junto aos destinos.

Fluxo de navegação: **sidebar → painel do menu → card/indicador/botão → lista ou parametrização interna → detalhe/cadastro**. Consultar um painel ou clicar em indicador não executa automação nem grava alterações. Executar/salvar permanece ação explícita na tela correspondente.

Não copiar barras de navegação superior ou breadcrumbs automaticamente. Mantém-se janela homogênea sem navbar adicional e controles integrados. Tema agora definido: lua para escuro, sol para claro, alterando cores/contrastes de toda a UI. Dimensões e composição fina continuam ajustáveis. Blocos/posições especificados no catálogo complementar prevalecem sobre sugestões genéricas anteriores.

### Conteúdo dos painéis — divisão aprovada, cards/componentes ainda propostos

| Menu | Card/indicador proposto | Botão/destino proposto | O que ocorre no backend |
|---|---|---|---|
| Processos | Processos cadastrados | **Gerenciar processos** → lista/composição de processos | Consultar registros permitidos; criação/ordenação só ao salvar na tela interna. |
| Processos | Rotinas Browser | **Gerenciar rotinas** → biblioteca/cadastro de microetapas | Consultar rotinas; manter manual como padrão e gravação como alternativa. |
| Fluxos | Execuções em andamento | **Acompanhar execuções** → lista filtrada | Consultar execuções/estado; não iniciar ou cancelar por clicar no indicador. |
| Fluxos | Execuções que precisam de atenção | **Ver ocorrências** → falhas/incertas/não verificadas | Consultar resultados e motivo de interrupção; sem retry automático. |
| Fluxos | Histórico de execuções | **Abrir histórico** → lista/detalhe de processo e rotinas | Ler resultados/evidência já persistidos. |
| Configurações | Equipe e usuários | **Gerenciar equipe** → membros/perfis | Consultar conforme permissão; alteração de usuário só em ação explícita autorizada. |
| Configurações | Estações | **Gerenciar estações** → lista/status/configuração | Consultar estado; revogação/registro não ocorre por navegação. |
| Configurações | Aplicativo e ambiente | **Ver configurações** → dados do app/ambiente e funções existentes pertinentes | Consultar versão/conexão/status; não aplicar update ou mudar ambiente ao abrir o card. |

A divisão funcional foi aprovada: Processos gerencia processos/rotinas; Fluxos acompanha execuções/histórico; Configurações reúne equipe/estações/app. Isso não restringe o início de uma execução a um só menu. Não criar um novo tipo de objeto chamado Fluxos por inferência. Cards exatos, componentes, contagens/filtros e botões ainda serão detalhados.

Indicador clicável e botão do mesmo card devem levar a destinos coerentes; filtro visível. Usuário autorizou dados fictícios para construir a UI agora; identificá-los e isolá-los. Na integração real, usar fonte real e estados carregando/vazio/erro, sem fallback fictício ou falha representada por zero. Stats/armazenamento, timeline, atividade e Kanban escolhidos são mapeados no catálogo; não adicionar gráficos extras sem finalidade definida.

### Execução acessível pelos dois menus

Decisão: não fechar um caminho exclusivo para iniciar automações. O usuário deve poder acionar as tarefas (rotinas/processos, sem criar uma terceira entidade “task” por suposição) de Processos ou Fluxos quando o contexto permitir. A mesma ação tem as mesmas regras e retorno; posição de acesso não altera significado.

| Contexto | Acesso proposto | Comportamento comum |
|---|---|---|
| Processos: processo ou rotina selecionado na lista/detalhe | **Executar**, já com o item identificado. | Abrir o fluxo comum com o alvo preenchido e as validações pertinentes. |
| Fluxos: painel de execuções | **Nova execução**, escolhendo processo ou rotina elegível. | Abrir o mesmo fluxo após selecionar o alvo; não duplicar campos/regras num formulário independente. |
| Histórico/resultado de uma execução | **Ver detalhes** | Ler o registro único; não repetir uma automação só por abrir ou clicar no indicador. |

Os rótulos e pontos exatos da tabela são propostas; o acesso por ambos os menus está confirmado. Preferência posterior do usuário (01/11/2026): página própria com etapas para tarefas maiores, dialog e lateral conforme a tarefa; não escolher um único formato universal. A ação de executar deve continuar compartilhada entre seus pontos de acesso. Proposta: confirmação final sem pedir novamente valores já cadastrados; se não houver alvo, selecioná-lo antes.

No backend, ambos os acessos devem usar o mesmo caso de uso de execução, persistência e aplicação de permissões/continuação/contexto. Mesma execução aparece no histórico comum, independentemente do menu de origem. A rotina avulsa desabilitada não pode ficar executável pelo outro menu. Cada processo continua começando pela primeira rotina e não avança sem verificação. Não abrir várias guias por reenvio duplicado da mesma solicitação; uma nova execução intencional terá identidade própria.

Base atual a preservar: `runForm()` já bloqueia duplo clique e usa `request_id` para criação idempotente de job em `main.ts`; isso não comprova que orquestração de processos/atalhos novos já exista. Documentar e testar a fronteira nova sem duplicar o executor ou inventar endpoints separados só por menu.

### Regras de interação a detalhar por card

- Registrar título, explicação, fonte do indicador, destino, filtro e permissões.
- Registrar se clicar no corpo/valor também navega e para onde; garantir acionamento por teclado/rótulo acessível em pt-BR.
- Escolher links dos componentes shadcn de card, botão, indicador e listas com o usuário. A imagem não seleciona sozinha uma biblioteca admin externa, autenticação Clerk ou serviços pagos.
- Preservar visualização/gestão de recursos existentes conforme o escopo, sem adicionar menus financeiros, clientes, chats ou documentação por estarem nas imagens.

## 8. Esboço visual — página, painel lateral e dialog

Solicitado em 01/11/2026; representa interação proposta, não implementação nem aprovação dos componentes finais. Dados e navegadores da demonstração são ilustrativos, sem consulta à máquina/conta. Nenhuma ação do esboço salva no app ou executa automação.

| Tarefa | Formato proposto | Sequência / conteúdo |
|---|---|---|
| Cadastrar/editar rotina Browser | Página própria com etapas | Identificação (nome, origem e permissão isolada) → Destino (site com browser/endereço; HTML somente caminho) → Revisão e cadastro. Distribui os campos existentes sem inventar nova configuração. |
| Compor processo | Página própria com etapas | Proposta a detalhar depois, sem inventar agora os passos ou validações adicionais. |
| Consultar detalhes de rotina/execução | Painel lateral | Contexto da lista preservado; resumo e acesso a ações explícitas. Detalhes não iniciam execução. |
| Confirmar execução de item já definido | Dialog | Nome do alvo, estação e valores cadastrados; confirmar/voltar. Não redigitar os parâmetros. |
| Execução sem item definido | Selecionar alvo antes da confirmação | Formato a detalhar; o dialog de exemplo usa uma rotina já identificada. |

Esboço navegável de referência da conversa: `C:/Users/raulv/.codex/visualizations/2026/10/30/01a18f30-f642-7142-aa76-2ebb6a8d2633/redrise-fluxos-de-interface.html`. Não é asset de runtime nem novo frontend de produção. Protótipo usa controles locais para explorar comportamento, não a implementação final shadcn. Seus componentes/links serão escolhidos pelo usuário.

Limites: cancelar/voltar do cadastro no esboço não decide ainda a política de rascunho ou perda de alterações; foco é comparar formatos. Os cards não aprovam métricas ou novos submenus. Não adicionar fluxo de pausa, execução real, novos modos ou autenticação pelo protótipo.

Verificação do esboço em 01/11/2026: navegação em três etapas, campos condicionais site/HTML, painel lateral, confirmação em dialog, retorno/Escape e menus conferidos em navegador headless; sem erros JavaScript e sem overflow horizontal nos tamanhos 1024/736/360. Capturas de painel e cadastro inspecionadas. Verificação exclusiva do protótipo, não da Engine ou do aplicativo instalado; nenhuma execução real de automação.

## 9. Próxima conversa

1. Escolher cards/indicadores do painel Processos e pontos de acesso às listas/detalhes/execução. Divisão dos menus já aprovada; não repetir essa pergunta.
2. Explorar o esboço e aprovar/ajustar página em etapas para cadastro, lateral para consulta e dialog para execução rápida; então escolher os links shadcn correspondentes. Não restringir execução a um só caminho.

Seleções posteriores já registradas: `@blocks-so/dialog-11` para um fluxo de criação; tabela de ações/grupos com filtros; stats/armazenamento; grade/Kanban; log/timeline/feed; claro/escuro e fixtures. Não repetir perguntas de seleção desses blocos. O engenheiro pode refinar texto/posição ainda propostos sem importar funções demonstrativas não escolhidas.

## 10. Continuidade para engenharia

Consultar o [checkpoint](../../delivery/checkpoints/BROWSER-UI-20261101.md) e o [prompt de implementação](../AGENT-START-BROWSER-UPDATE.md). Handoff manual, sem agente/sessão sucessora criada. O próximo agente deve revalidar estado volátil, aplicar instruções do projeto, resolver skills por etapa, construir UI com os blocos reais e provar a integração Browser separadamente do esboço. Não copiar simulação como runtime.

Pendência posterior de onboarding: onde criar/conectar equipe e definir primeiro administrador. Pergunta de link/código por acesso foi encerrada pelo usuário e não deve ser reaberta.

Referência oficial consultada em 31/10/2026: blocos base são adaptados pelas imagens e instruções explícitas do usuário; provedores confirmados são Google/GitHub. Comandos registrados, não executados.

Fonte backend: [bridge Tauri](../../desktop/src-tauri/src/lib.rs) e [API Core](../../core/redrise_core/api.py). Sem inspeção visual instalada, alteração de código, novos testes funcionais ou criação real de usuário/equipe nesta elaboração.
