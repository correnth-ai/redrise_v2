# Work Order — estabilização, interface funcional e estado canônico

- **ID:** STABILIZATION-REAL-UI-20261107.
- **Data:** 07/11/2026. **Estado:** proposta documentada; implementação não iniciada por esta Work Order.
- **Solicitação:** após a revisão do app, segurança e documentação, o usuário pediu uma Work Order com a sequência proposta. Confirmou KISS em todo o projeto, a abertura confirmada pela janela como simplificação deliberada e a necessidade de indicadores e botões funcionais, sem dados fictícios no uso normal.
- **Produto / repositório:** `product:redrise-v2` / `repo:redrise-v2`.
- **Root / remote / branch:** `D:/Correnth/products/redrise-v2/repos/app` / `https://github.com/correnth-ai/redrise_v2.git` / `main`.
- **HEAD observado:** `f78d229f4c7149bc4d3599ff794a7942353a4d29`. Árvore limpa antes desta redação; revalidar antes da engenharia. HEAD identifica a base; não foi calculado um novo digest de árvore.
- **Autorização atual:** criar este documento. A sequência descreve trabalho proposto e não comprova execução, homologação, instalação ou publicação. Não modifica `delivery/status.json` nesta entrega.

## Objetivo e decisões preservadas

Tornar as funções já entregues confiáveis, ligar a interface aos dados persistidos e consolidar uma descrição inequívoca do estado vigente. Cada incremento deve entregar um resultado pequeno e observável, aproveitando Core, Runner, componentes e atualização de tabelas existentes.

**KISS é critério transversal:** preferir a menor solução suficiente; não criar plataforma de métricas, framework de automação, nova camada de serviços ou parametrização genérica para resolver uma necessidade localizada. Revisitar somente diante de uma limitação concreta.

**Abertura de destino:** manter o critério atual de confirmação pela janela do aplicativo. Identificação do documento exato não é defeito a corrigir nem requisito adicional desta Work Order. Documentar esse alcance no aceite. A decisão não relaxa os verificadores específicos já existentes de salvamento, conteúdo, PDF ou resultado das demais ações.

**Interface funcional:** números representam fatos consultados; controles habilitados executam a ação indicada ou navegam para o destino correto. Ausência de informação não vira zero, sucesso ou gráfico inventado. Recursos adiados continuam explicitamente indisponíveis; não precisam ser implementados apenas para habilitar um botão.

## Fontes e ponto de partida

- Autoridade organizacional: `D:/Correnth/company/state/current/document-authority.yaml`, manifesto `D:/Correnth/products/redrise-v2/product.yaml` e decisões vigentes do v2; seguir os AGENTS aplicáveis.
- Fontes locais: [regras do app](../../docs/APP-RULES.md), [roadmap](../../docs/ROADMAP.md), [estado](../status.json), [aceite Beta](../../docs/BETA-ACCEPTANCE.md), [testes](../../docs/TESTING-STRATEGY.md), [diagnósticos](../../docs/ERROR-DIAGNOSTICS.md), [tabelas em tempo real](../../docs/ui/LIVE-TABLES.md) e [modelo de Work Order](../../docs/WORK-ORDER.md).
- Predecessor: [UI-ENGINE-BOAS-VINDAS-20261103](UI-ENGINE-BOAS-VINDAS-20261103.md) e sua [evidência](../evidence/UI-ENGINE-BOAS-VINDAS-20261103/evidence.json), SHA256 `b4c0906eaab57ca517270508745744b47ef097046f0b8d9748b3bdbE7fb3e354` (comparar sem distinção de maiúsculas). Registra aceite instalado da beta.25, com limites próprios; não é homologação geral.
- Revisão desta conversa, 06/11/2026: cancelamento seguido de continuação reproduzido com Core/PostgreSQL isolados e Runner simulado; Empresa usa fixtures mesmo no app normal; autenticação sem limitação de tentativas; concorrência HTTP/banco sem teto explícito. Estes achados devem receber regressões reproduzíveis no incremento correspondente; a conversa não substitui um relatório de execução versionado.
- Divergências documentais observadas: candidato estruturado beta.14 versus instalação beta.25; identidade externa suspensa versus texto que ainda a chama vigente; stack antiga; aceites não reconciliados com adiamentos; dois hashes normativos divergentes. Revalidar antes de corrigir, sem promover todos os passos para `verified`.
- Validação anterior: 342 checks de base; typecheck e 47 testes UI; 108 testes Runner aprovados e um skip por falta de `pdftotext`; npm audit sem vulnerabilidades conhecidas. Descoberta global do Core: 221 testes, 14 falhas e 74 erros; identificado reuso de token entre bancos de classes repetidas. Core básico isolado: 14 aprovados. Não atribuir todas as falhas à mesma causa sem individualizá-las.

## Mapeamento e ordem

Os IDs abaixo são incrementos desta Work Order, não novas fases nem substitutos de Pxx. O passo global observado continua P13; os incrementos corrigem componentes anteriores e alimentam seu aceite. Nenhum gate é avançado pela criação deste plano.

| Ordem | Incremento | Relação com roadmap | Dependência / saída para o próximo |
|---|---|---|---|
| 1 | S1 — cancelamento e estado canônico | P07/P08, documentação de P13 | Base e evidência beta.25; regressão do cancelamento e aceite vigente reconciliado |
| 2 | S2 — indicadores e controles reais | P08/P09 | S1 define estados e alcance; interface consulta as mesmas fontes dos detalhes |
| 3 | S3 — segurança básica e testes confiáveis | P06/P07/P08 | S1/S2 integrados; controles limitados, testes isolados e falhas individualizadas |
| 4 | S4 — validação instalada e recuperação | P10/P11/P13 | S1–S3 com checks pertinentes aprovados; candidato identificado e ambiente disponível |
| 5 | S5 — próxima capacidade de automação | Planejamento após S4, sem novo gate presumido | Escolha de uma necessidade real da equipe e Work Order própria delimitada |

### S1 — cancelamento e estado canônico

**Fronteira:** intenção de cancelar → estado persistido → resultado do Runner → decisão de continuar.

- Quando o cancelamento for aceito antes de enfileirar a próxima etapa, impedir a continuação. Propagar cancelamento aos adaptadores onde for seguro interromper; não prometer desfazer um efeito já ocorrido.
- Preservar resultado e efeitos reais da etapa em curso, distinguindo cancelamento solicitado, parada e conclusão. Resolver explicitamente a corrida entre resultado e cancelamento, sem retry automático.
- Consolidar versão de código, candidato, instalação e publicação com suas evidências. Atualizar regras vigentes, stack, matriz de aceites obrigatórios/adiados/superados e pendências já resolvidas; preservar histórico e IDs.
- Conferir hashes normativos após revisar as mudanças intencionais. A atualização do manifesto organizacional é um subescopo documental explícito, não permissão para editar outros produtos ou policies.

**Aceite:** teste de contrato com processo de duas etapas e Runner simulado demonstra que cancelar não libera a segunda; cobrir cancelamento na fila, em execução e corrida com resultado. Estado documental aponta para evidências existentes sem declarar homologação. Manter a confirmação pela janela como aceite de abertura.

**Write-set proposto:** `core/redrise_core/service.py`, `runner/redrise_runner/agent.py` e adaptadores diretamente envolvidos; testes correspondentes em `tests/core` e `tests/runtime`; `delivery/status.json`, README/AGENTS e documentos diretamente conflitantes; `D:/Correnth/products/redrise-v2/product.yaml` apenas para reconciliação comprovada. Delimitar os arquivos exatos antes de editar.

### S2 — indicadores e controles reais

**Fronteira:** registro persistido → consulta/autorização → indicador/lista → ação do usuário → retorno observável.

- Inventariar cada card, gráfico, botão e filtro: fonte, fórmula/recorte, permissão, destino/efeito, estados vazio/carregando/erro e forma de atualização. Estender o inventário existente, sem manter dois mapas concorrentes.
- Substituir fixtures de Empresa por dados do Core. Primeira fatia: processos cadastrados, execuções por situação, revisões pendentes, estações disponíveis e atividades recentes. Armazenamento usa medições existentes, sem capacidade fictícia.
- Um clique em indicador abre a lista correspondente com o mesmo filtro. Período e contagem do card devem coincidir com os detalhes.
- Não apresentar as últimas 100 execuções como total global. Escolher a solução menor adequada: rotular explicitamente o recorte ou agregar no Core quando a tela realmente precisar do total/período. Evitar baixar todo o histórico para contar no cliente.
- Definir a fórmula antes de exibir taxa/comparação. Período sem observações não equivale a 0% de sucesso. Horas economizadas, produtividade e métricas sem base suficiente permanecem ausentes ou indisponíveis.
- Aproveitar as notificações de mudança e leituras existentes. Falha de consulta mostra diagnóstico; nunca troca silenciosamente para demonstração.
- Botões de salvar, executar, cancelar, aprovar, abrir relatório e navegar devem ter efeito real, retorno e estado ocupado conforme o fluxo. Evitar duplo envio. Operações indisponíveis explicam o motivo; Kanban continua somente leitura.
- Fixtures continuam permitidas nos testes e no modo de demonstração explicitamente separado, sem alimentar a sessão normal.

**Aceite:** dados sintéticos persistidos produzem contagens e filtros coerentes; uma alteração real atualiza card e lista; usuário sem permissão não obtém dados por clique/API; erro, vazio e indisponível não aparecem como sucesso ou zero inventado. Cobrir mais de 100 execuções se a métrica depender desse limite. Verificar nomes acessíveis dos controles modificados, incluindo rádios do assistente.

**Write-set proposto:** `desktop/src/features`, `desktop/src/data`, componentes/estado diretamente envolvidos e testes UI; endpoints/consultas em `core` e testes de contrato somente quando necessários; `docs/ui/LIVE-TABLES.md` e regras afetadas. Sem redesenho global, novos menus ou sistema de analytics.

### S3 — segurança básica e testes confiáveis

- Limitar tentativas de login/cadastro com política pequena e explícita, espera e resposta adequada; evitar bloqueio permanente que terceiros possam provocar. Testar recusa e recuperação com relógio controlado e contas sintéticas.
- Limitar requisições/conexões simultâneas e espera, mantendo margem para heartbeat/cancelamento. O tamanho do cache de conexões ociosas não é um limite de concorrência.
- Corrigir o ciclo de fechamento de sockets TLS indicado pelos warnings. Testar conexões concluídas, interrompidas e handshake incompleto em servidor isolado, sem teste de carga contra a instalação real.
- Corrigir descoberta repetida de classes e limpeza de estado/token entre bancos dos testes. Individualizar todas as falhas da execução anterior; não suprimir testes, warnings ou casos para obter aprovação.
- Preservar TLS/pinning, tokens em hash, permissões no Core e assinatura/verificação de updates. Levantar dependências Rust/Python com ferramentas já disponíveis; registrar cobertura e limitações, sem instalar scanners ou atualizar versões em massa por inferência.

**Aceite:** regressões localizadas de limites e recuperação passam; suíte Core agregada e suítes isoladas têm resultados consistentes, sem token de outro banco. Falhas remanescentes têm causa/evidência e continuam abertas. Não converter npm audit limpo em declaração de segurança integral.

**Write-set proposto:** `core/redrise_core/{api,auth,db,service}.py`, testes pertinentes e dependências somente se uma correção específica for justificada. Nenhuma troca de provedor de identidade.

### S4 — validação instalada e recuperação

- Identificar candidato por versão, hash do instalador, fonte e dependências. Incluir a licença Playfair já corrigida no fonte e conferir sua presença no pacote.
- No ambiente disponível e com janela de uso do desktop combinada, provar um fluxo curto: cadastrar rotina → preparar → executar processo → solicitar/aprovar revisão → consultar histórico e relatório. Conferir indicadores, filtros e botões com os mesmos registros.
- Exercitar cancelamento sem avanço, falha de conexão, permissões administrador/operador e preservação de dados. Repetir somente os cenários afetados, incluindo a regressão Boas-vindas pertinente.
- Distinguir rollback do binário e recuperação de dados migrados. Testar em cópia isolada com dados sintéticos; documentar backup/restauração e limites reais antes de afirmar reversibilidade.
- Manter rascunho real de e-mail/webmail pendente: pode autosalvar em conta real e foi recusado anteriormente. Não enviar mensagens.

**Aceite:** evidência manual/prática vinculada ao candidato e às regras vigentes, com limites e intervenções declarados. Nenhum dado pessoal ou token nos artefatos. `closed_beta_available`, `beta_ready` e `published` continuam distintos. Não fixar número de versão futuro por suposição.

**Write-set proposto:** empacotamento e testes estritamente relacionados, evidência sanitizada e documentos de recuperação/aceite. Instalação, interação e qualquer escrita externa seguem autorização aplicável; o plano não as executa.

### S5 — evolução das automações

Escolher uma única microetapa útil a partir do uso da equipe, definir entrada, resultado, erro e aceite e abrir Work Order específica. Reutilizar contexto de processo e mecanismos existentes. Este incremento entrega a escolha e o plano da próxima capacidade; não autoriza um catálogo amplo ou implementação indefinida.

Permanecem adiados conforme decisões atuais: gravação humana Excel, segunda estação LAN, identidade externa, envio automático, site/Contact Sales completo e Authenticode. Antes de reativar gravação, revisar limites de captura e campos sensíveis. Não reabrir esses itens para cumprir botões de demonstração.

## Verificação, evidência e conclusão

**Comandos conhecidos para execução futura, conforme o incremento:**

- Base documental: `node scripts/validate-base.mjs` na root. É foundation-only; conferir separadamente links e hashes do manifesto, que esse comando não garante.
- Core básico: `<Python do laboratório> -B -m unittest test_core.CoreTest -q` em `tests/core`.
- Core agregado após corrigir isolamento: `<Python do laboratório> -B -m unittest discover -s . -p 'test_*.py' -q` em `tests/core`.
- Runner: selecionar apenas módulos afetados, por exemplo `<Python do laboratório> -B -m unittest test_app_open test_browser_open test_notify_draft -q` em `tests/runtime`; esses componentes simulados não provam efeito nativo.
- UI: `npm run typecheck` e `npm test -- --reporter=dot` em build C: cujos fontes/configuração/lockfile correspondam ao checkout. Não executar contra cópia stale nem instalar dependências na root D: por conveniência.
- Gate de candidato existente: `packaging/release/verify-candidate.ps1`, somente em S4 sob a autorização pertinente, pois instala e opera aplicativos. Seu smoke não substitui os novos aceites de interface/cancelamento.

Cada incremento registra comando, entrada sintética, esperado, observado, tipo de check (componente/contrato/E2E; simulado/nativo), versão/hash, erros e módulos, falhas/skips e próxima ação. Usar [EVIDENCE.md](../../docs/EVIDENCE.md). Artefatos futuros: `delivery/evidence/STABILIZATION-REAL-UI-20261107/`, com resultados separados por S1–S4; não criar relatórios de sucesso antecipados. Runtimes/provas ficam em C:; repositório recebe somente evidência sanitizada. Esta redação não gerou nova prova funcional.

**Revisão:** revisão independente antes de marcar aceite de engenharia; revisor ainda não designado. Um escritor por Git root. Esta tarefa documental não exige delegação. Se útil na implementação, delegar somente revisão independente delimitada/read-only, sem recursão, com fontes, skill, evidência e parada explícitas.

**Skills e continuidade:** router executado como `normative`, memória explícita `correnth/redrise-v2` indisponível; fallback canônico. Graphify não usado; v2 não tem root registrada na revisão. Aplicadas `scope-planning` (SHA256 `fd7b13af53a7853d7cbd43ac9f72e801d602c7fb4e592981ac4842e4ded58bfa`), `documentation-decision-log` (`94d7404269c6b354a8ba5e1cd0704769b7bdd648e3379f5ddc296a1696bd2d3b`) e `phase-identity-reconciliation` (`6ae32e783ae16f93c1e30efed32ade0b69e0c869016e2e255af129b40c9fd143`), resolvidas pelo catálogo corporativo e congeladas pelo Harness. Reexecutar seleção/resolução no checkpoint de engenharia e antes de nova dependência, falha inesperada, mudança de schema, interação nativa ou ampliação de escopo; não pré-carregar skills de fases futuras.

## Parada e recuperação

- Encerrar cada incremento no aceite delimitado ou registrar seu bloqueio real. Não ampliar automaticamente para recursos adiados.
- Uma repetição nativa só ocorre após diagnosticar a falha e conferir efeitos anteriores. Efeito incerto interrompe a execução; nunca repetir escrita ou aprovação cegamente.
- Se autoridade/aceite permanecer ambíguo, resolver a decisão antes de mudar comportamento. Divergência de teste exige diagnóstico, não remoção de teste.
- Recuperar alterações locais por diff específico, preservando mudanças alheias; sem reset destrutivo. Dados migrados exigem backup e recuperação ensaiada, não apenas restauração de binários.
- Fora do escopo: commits, pushes, publicação, produção, gastos, credenciais, alterações V1 e escrita remota material. Aplicar HITL quando uma ação efetiva atravessar essas fronteiras.

**Entrega atual:** esta Work Order. **Próxima ação proposta:** iniciar S1 em tarefa de implementação autorizada, revalidando HEAD, árvore, estado e evidência; manter S2 como a próxima fatia de produto para retirar dados demonstrativos do uso normal.
