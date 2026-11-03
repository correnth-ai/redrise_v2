# Prompt de continuidade — engenharia do update Browser

> Continuidade em 02/11/2026: o update Browser tem checkpoint/evidência de beta.14; não reiniciar I0–I8 por este prompt histórico. Para identidade, sessão, menus e Empresa, usar [AGENT-START-IDENTITY-UI](AGENT-START-IDENTITY-UI.md) e a work order correspondente. As decisões de 02/11 substituem neste escopo login/signup-05, cadastro sem senha e menus antigos, e autorizam pesquisa/reuso seletivo de identidade V1.

Use o texto abaixo como instrução para uma nova sessão. Preparado em 01/11/2026; sua existência não inicia outra sessão nem autoriza publicação.

---

Implemente localmente o próximo update do **app RedRise v2**, com novo modo de automação **somente Browser**, partindo deste checkpoint e das decisões já elaboradas. Prossiga por incrementos concretos, com validações proporcionais. Não recomece investigação/Engine/Excel já comprovados e não refaça o grill me das escolhas respondidas. Entregue o app construído/testado no escopo possível e um relatório honesto de qualquer fronteira ainda não atendida.

## 1. Root, autoridade e leitura inicial

- Root única de produto: `D:/Correnth/products/redrise-v2/repos/app`; produto `product:redrise-v2`, repo `repo:redrise-v2`. Não usar `products/redrise/repos/platform` nem o antigo pacote operation.
- Primeiro leia `D:/Correnth/company/state/current/document-authority.yaml`, routing matrix, manifesto `products/redrise-v2/product.yaml` e AGENTS aplicáveis do workspace/envelope/root. Siga as instruções locais mais próximas.
- Leia `delivery/checkpoints/BROWSER-UI-20261101.md`, esta work order `delivery/work-orders/DISCOVERY-20261031.md`, `docs/APP-RULES.md`, `docs/ui/BROWSER-UPDATE-ASIS-TOBE.md` e `docs/ui/BROWSER-UPDATE-COMPONENTS.md` integralmente. O discovery inicial é antecedente, não fonte concorrente.
- Leia baseline, Engine, roadmap, status e políticas de teste/diagnóstico conforme AGENTS. As decisões explícitas posteriores do usuário registradas na work order prevalecem nos pontos alterados: shadcn, menus novos, Browser only e acesso. Não alterar os originais históricos/hash locks para simular consistência; reconciliar documentação ativa pertinente com rastreabilidade.
- Revalide branch, HEAD e arquivos locais: na elaboração havia `main` com HEAD unborn e todo conteúdo não rastreado. Não usar reset/clean, sobrescrever trabalho alheio, inventar base commit ou criar worktree sem necessidade. Reutilize checkout adequado. Não fazer commit/push.
- Catálogo corporativo em `D:/Correnth/catalogs/skills` ou variável indicada; rode o router e resolva somente nomes exatos selecionados. Leia cada skill aplicável antes da mutação da etapa. Não adivinhar skills ou tratar recomendações irrelevantes como dependências. Skills do host aplicáveis continuam válidas.
- Memória explícita: workspace `correnth`, project `redrise-v2`. Estava indisponível; confirme se voltou sem usar histórico como autoridade. Não capturar transcrição/repositório nem criar corpus. Sem root Graphify registrada para v2 na elaboração; confirmar registry e usar código/testes/documentos se ausente, sem rebuild.

## 2. Estado real e objetivo

- Código do desktop declara `0.1.0-beta.10`; status ainda registra candidata instalada beta.6, `closed_beta_available=true`, `beta_ready=false`, `published=false`. Não declarar beta.10 instalada/homologada por isso.
- Este trabalho anterior produziu documentação, referências e protótipo interativo; **não implementou** os componentes reais, processos/orquestração novos, OAuth/confirmar e-mail ou controle genérico de browsers pessoais.
- Stack atual: Tauri/Rust, frontend TypeScript Vanilla, Core/Runner Python e PostgreSQL privado. Migrar frontend para React/TypeScript e shadcn com dependências/bundler adequados, preservando Tauri/IPC/Core/Runner/Engine; não adotar Next.js/servidor web só porque o bloco de referência contém essas pastas.
- Novo modo: cadastro de microetapa Browser manual; processo agrupa rotinas reutilizáveis, com ordem, continuação, contexto e histórico. Site usa browser escolhido; HTML local abre pelo mecanismo próprio e identifica browser/guia efetivos. Nova guia; timeout até 30 s; nenhuma reparação/kill/retry automático. Só conclusão verificada avança. Sem pausa.
- Menus: **Processos, Fluxos, Configurações**, sidebar-03, painéis admin com cards/indicadores para listas/parametrizações. A execução pode ser acessada pelos dois primeiros menus com o mesmo caso de uso/histórico.
- Máscara integral pt-BR; claro/escuro com lua/sol e contraste completo; controles de janela redondos integrados no topo direito, na ordem minimizar, maximizar/restaurar, fechar; sem barra branca/navbar demonstrativa.
- Componentes e comandos exatos estão no catálogo complementar: login-05, signup-05, sidebar-03; blocks-so dialog-11, table-02/table-04, stats-02/stats-13, grid-list-02, onboarding-05/06/07. Instale apenas o que passar a ser necessário, após revisão de fonte/versão/licença e pin. Não executar cegamente todos os `@latest`.
- Textos/estados/métricas fictícios são autorizados para construir o visual agora, identificados e isolados. Não gravar fixtures como dados de cliente nem usar fallback silencioso em produção. Componentes conectados a função real devem mostrar fonte real ou carregando/vazio/erro.

## 3. Ordem de implementação

### I0 — confirmar base e criar plano local delimitado

Verifique estado e contratos reais; escreva Work Order de implementação usando o template do projeto, com write-set, aceites, ambiente e recuperação. Faça matriz pequena: implementado / novo / proposto / dependência externa. Preserve evidências antigas. A primeira ação concreta após a leitura é inspecionar `desktop/package.json`, `desktop/src/main.ts`, comandos Tauri e o adapter Browser para definir o menor incremento de migração UI sem perder login/IPC atuais.

### I1 — fundação visual e fonte de dados demonstrativa

Prepare frontend React/shadcn dentro de Tauri, build em C: e fontes em D:, conforme projeto. Defina tema/tokens pt-BR e adapter explícito de fixtures para a UI nova. Preserve autenticação/IPC existentes enquanto a nova identidade é tratada separadamente. Não mascarar um backend não pronto com dados falsos em modo real.

Implemente shell, sidebar/menus, tema sol/lua e janela integrada. Conecte os blocos reais escolhidos, removendo funções demonstrativas não pedidas. Check de tipos/build, IPC necessário, contraste dos dois temas e redimensionamento. Não criar testes triviais de CSS ou checar textos apenas para espelhar implementação.

### I2 — painéis e navegação com fixtures identificadas

Processos: stats-02, cards de acesso, table-04 agrupada por processo, ações table-02 e filtros. Fluxos: stats-02, grid-list-02, acesso grande ao Kanban filtrável por processo. Configurações: preservar equipe/estações/app, sem incluir novas funcionalidades não definidas.

Adapte stats-13 para apresentação de espaço do app/DB/logs e contagens em unidades separadas; a capacidade/limite fictícios não viram quota real. Adapte onboarding-07 para log de execução, onboarding-06 para timeline e onboarding-05 para atividade. Todas as visualizações devem consumir o mesmo estado da mesma execução. Kanban é visualização/acesso, não verificador manual por arraste. Não importar pausa, exclusão ou “marcar verificada” só porque aparecem nas referências.

### I3 — cadastros e superfícies de interação

Página com etapas para cadastro/edição de rotina Browser: identificação/origem/isolada → destino condicional → revisão/salvar. Não pedir novamente valores cadastrados a cada execução. HTML não mostra seleção de navegador. Não vincular rotina criada a um processo automaticamente.

Use dialog-11 em um fluxo de criação conforme o esboço; preservar a flexibilidade de página/dialog/lateral por tarefa. Composição de processo deve vincular rotinas existentes, ordenar e configurar continuação por vínculo. Mesma rotina pode aparecer em processos diferentes; alterações valem nas próximas execuções e não mudam a já iniciada.

Detalhes/log em lateral e confirmação rápida de execução em dialog são direções do esboço a adaptar; pontos ainda sugeridos, como rótulos finais e política de rascunho, não se tornam novas regras corporativas. Reuse o fluxo de execução nos atalhos de Processos e Fluxos. Desmarcar isolada impede execução avulsa também na API, mas não é restrição de posição no processo.

### I4 — provar o caminho Browser mínimo antes de conectá-lo como funcional

O adapter atual inicia Chromium privado via Playwright; isso não prova controle de Chrome/Edge/Firefox pessoais já abertos. Faça um experimento mínimo delimitado com HTML/página sintética local para descoberta, nova guia, identificação do alvo e controle sem atingir guias pessoais. Avalie por browser/versão; diferencie detectado de homologado.

Não assumir que abrir uma URL entrega uma referência controlável nem que CDP se conecta a qualquer perfil aberto. Não habilitar debugging inseguro, instalar plugin do cliente, reiniciar browser, mudar perfil pessoal ou substituir o browser escolhido silenciosamente. Se um mecanismo não cumpre as regras, implemente diagnóstico honesto e prossiga nas frentes independentes; não finja suporte. Automações UI nativas exigem sessão desbloqueada, computador livre e autorização interativa aplicável; o protótipo headless não fornece essa prova.

### I5 — contratos, persistência e orquestração

Evolua somente contratos/schemas/migrações do app necessários às capacidades aprovadas, com versão/compatibilidade; não alterar contratos corporativos protegidos. Core mantém rotinas/processos/vínculos/configurações/execuções; Runner/Engine executam e verificam. PostgreSQL compartilhado continua via API; não expor credenciais DB à UI.

Fixe configuração das rotinas no início de cada execução; contexto é por execução, nunca global numa rotina reutilizada. Persistir resultado/efeito e distinguir falho, incerto, concluído não verificado e verificado. Primeiro item do processo é o início; continuação desmarcada encerra; sem pausa, pular erro ou retry automático. Não exigir checkbox isolada marcada na primeira posição. Idempotência do envio/report/encadeamento deve impedir duplicação por resposta perdida.

### I6 — integrar Browser e substituir fixtures por fontes reais

Ligue UI/Core/Runner/Engine aos contratos. Descoberta consulta registros e caminhos conhecidos na estação, sem varrer todo o disco. Salvar rotina/processo não executa. Site cria nova guia no browser escolhido; HTML abre o arquivo e identifica o browser/guia reais, inclusive quando já existirem processos. Confirmação até 30 s; falha/não verificado/incerto não avança. Transfira somente contexto válido; não selecione outra janela por coincidência de título.

Refaça somente os checks localizados e integrações afetadas, ampliando se houver impacto transversal. Métricas reais, filtros, histórico, log/timeline/feed/Kanban observam a mesma persistência. Não transformar a simulação de progresso do esboço em uma chamada que verifica efeito real.

### I7 — identidade register/login, com dependências explícitas

UI register/login com e-mail ou Google/GitHub; sem Apple. Cadastro manual só e-mail. Confirmação por mensagem com botão Confirmar; backend valida a prova da conta e registra data/hora; então redireciona para `https://redrise.app/login`. Tentativa sem confirmação é bloqueada no backend e mostra abaixo do botão em vermelho **“Confirme o e-mail para fazer o login.”** com link **“Reenviar confirmação.”**.

Usuário dispensou link/código em cada novo acesso; não reabrir essa pergunta nem acrescentar etapa recorrente à UI. Isso não especifica sozinho um protocolo de autenticação seguro: definir como sessão/identidade é provada, como se integra ao Core/equipe e como preservar usuários existentes. Não conceder sessão/admin só por um endereço confirmado digitado. Não fabricar fluxo funcional caso o contrato não esteja resolvido; manter a fronteira técnica explícita e não afetar as entregas independentes de UI/Browser.

Provedores reais, envio de e-mail, credenciais, domínio/rotas publicados, custos e escrita remota material exigem autorização específica. Não usar contas/chaves/domínio do produto anterior nem inventar callbacks publicados. Prepare implementação/contratos e fixture local dos estados que não dependam de serviço externo; antes de qualquer operação externa, apresente resultado concreto e a dependência/autorização faltante. Não marcar esse fluxo homologado usando apenas o mock.

### I8 — empacotar, validar e entregar

Execute checks proporcionais aos componentes alterados. Validador base não prova Beta. Typecheck/build frontend; testes significativos de contratos/runtime/Core e migrações em banco isolado quando alterados; checks Rust localizados se mudar bridge/Engine. Reuse scripts do projeto revisados, com caminhos de build/runtime em C: e dados sintéticos.

Gere candidato/instalador local identificado por versão/hash/inventário somente após os checks pertinentes. Não declarar nova versão instalada por inferência. Campanha prática Browser instalada deve cobrir site/HTML, browser já aberto/fechado, guia separada, referência correta, timeout/falha, isolada, processos/continuação/contexto, idempotência e status/histórico coerentes. Login/e-mail real exige a dependência autorizada; se não foi exercitado, declarar não executado. Não criar campanha Excel nem exigir máquina limpa/VM.

Registre evidência exata de cada incremento e revisão pertinente; não autoaprovar QA independente. Mantenha `beta_ready`/`published` conforme prova real. Faça checkpoint compacto antes de cada handoff, com próxima ação segura. Entregue alterações, validações, limitações e paths do candidato/documentação; sem commits, pushes ou publicação.

## 4. Limites que não podem ser perdidos

- Não implementar Excel, Notepad/Outlook, login automático em sites, catálogo de sites, pausa, retry automático, encadeamento entre processos ou drag-and-drop de estado verificado neste update.
- A regra futura de nomes `[1]`, `[2]` está preservada fora do escopo Browser; não criar funcionalidade de salvamento Excel por proximidade documental.
- Não copiar transcrição, prompts internos, skills/Graphify/memória para o instalador. Dados/configuração/evidência/cofre separados dos binários, instalação per-user em `%LOCALAPPDATA%\Programs\@redrise`.
- Não encerrar processos/documentos do usuário para reparar erros, remover proteções ou substituir executor/browser silenciosamente. Guia nova do Browser permanece aberta ao final.
- Uma implementação local pode evoluir contratos do produto necessários ao pedido; mudanças destrutivas, custos, credenciais, publicação/domínio e serviços externos não estão autorizados automaticamente.
- Se apenas uma frente estiver impedida por dependência externa, concluir as independentes e registrar o estado; não chamar entrega parcial de update inteiramente homologado.

## 5. Esboços e referências

Componentes e imagens no catálogo/`docs/ui/references/`. Esboço mais recente: `C:/Users/raulv/.codex/visualizations/2026/10/30/01a18f30-f642-7142-aa76-2ebb6a8d2633/redrise-paineis-browser.html`. Anterior: `redrise-fluxos-de-interface.html` no mesmo diretório. São protótipos locais com fixtures e controles exploratórios; não copiar como frontend de produção nem usar como prova da Engine.

Se o diretório de visualizações não existir na nova máquina, continue pelos documentos e PNGs versionáveis do repositório; não é gate. Confira os links dos fornecedores escolhidos, sem trocar por outro registry de nome parecido.

Ao receber este prompt do usuário, comece por I0 e avance nos incrementos locais autorizados. Não crie outra sessão ou agente apenas porque o prompt menciona handoff; delegação segue AGENTS e ferramentas do runtime. Preserve os checkpoints e comunique resultados concisos.
