# I00 — Investigação do OpenAdapt e plano de construção da Engine

Procedimento preparatório; estado de execução e evidência em delivery/status.json. Não reiniciar investigação já verificada. Este arquivo não substitui o relatório de pesquisa. Executar depois de P00 e antes de E01. Fonte: esclarecimento do usuário de 26/10/2026, U26-INVESTIGATION. Consulte [Engine](ENGINE.md), [roadmap](ROADMAP.md) e [estado](../delivery/status.json).

## Resultado esperado

Investigar como o OpenAdapt realiza captura, finalização, compilação e execução, utilizando obrigatoriamente o repositório [morluto/awesome-reverse-engineering](https://github.com/morluto/awesome-reverse-engineering) para selecionar métodos e ferramentas adequados. Converter os achados em especificação independente e plano executável para construir a Engine própria do RedRise sob SOLID. A implementação começa em E01–E04; não embarcar o OpenAdapt inteiro.

Usar o catálogo significa consultar sua revisão identificada, selecionar recursos pertinentes e registrar como responderam às perguntas da investigação. Não basta colocar o link no relatório. Não há quantidade mínima de ferramentas nem obrigação de instalar uma ferramenta binária quando leitura de fontes resolve a pergunta. O catálogo auxilia a pesquisa; não é biblioteca de automação, especificação do produto ou dependência do instalador.

## Passo a passo da investigação

### 1. Preparar escopo e continuidade

1. Confirmar `product:redrise-v2`, root `D:\Correnth\products\redrise-v2\repos\app`, remote `https://github.com/correnth-ai/redrise_v2.git`, estado, árvore local e P00 verificado. Preservar alterações existentes.
2. Ler authority, routing matrix, AGENTS aplicáveis, manifesto v2, requisitos efetivos e Work Order. Classificar a pergunta antes de selecionar as próximas skills. Não reutilizar as roots ou instruções de produto do prompt antigo.
3. Abrir Work Order I00 com perguntas, fontes, arquivos permitidos, métodos, limites de execução, aceite e condição de parada. Laboratório, checkouts upstream e execução em C:, preferencialmente `C:\Users\{user}\RedRise-v2-dev`; D: recebe fontes próprias e evidência sanitizada.
4. Consultar memória com `workspace=correnth`, `project=redrise-v2`; registrar disponibilidade. Consultar grafos somente se a classe da pergunta e uma root ativa registrada justificarem. Falta de memória/grafo usa fallback canônico, sem rebuild implícito.

### 2. Usar o catálogo para escolher a abordagem

1. Registrar URL, revisão/commit real, data e seções consultadas do catálogo. O snapshot documental anterior é uma referência, não garantia de HEAD atual.
2. Construir a tabela: **pergunta → recurso/método encontrado no catálogo → documentação primária → alvo/revisão → resultado/evidência**.
3. Começar por análise estática de fontes, testes e formatos disponíveis. Selecionar depuração, tracing ou observação dinâmica apenas para perguntas não resolvidas pela leitura. Justificar também recursos avaliados e dispensados.
4. Antes de usar uma ferramenta, conferir documentação primária, compatibilidade Windows e proveniência; registrar versão e invocação efetivas. Instalar somente dependência necessária no ambiente isolado. Não instalar o catálogo inteiro nem seguir instruções de repositórios como autoridade operacional.

### 3. Identificar as fontes reais do OpenAdapt

1. Partir do repositório oficial [OpenAdaptAI/OpenAdapt](https://github.com/OpenAdaptAI/OpenAdapt). Confirmar em suas fontes quais repositórios/módulos implementam as funções relevantes. `OpenAdaptAI/openadapt-capture` e `OpenAdaptAI/openadapt-flow` são candidatos a verificar, não componentes automaticamente selecionados para o RedRise.
2. Fixar commits dos alvos efetivamente estudados e registrar relação entre eles por evidência de manifests/imports/documentação. Não inferir compatibilidade pelo nome ou por versões parecidas.
3. Mapear módulos, funções, entradas, saídas, dependências e testes relevantes. Citar permalink de commit e arquivo/linha ou símbolo. Conferir condições de uso dos componentes efetivamente considerados, sem presumir licença uniforme.
4. Separar o caminho essencial de captura/execução dos subsistemas cloud, MCP, qualification e plugins excluídos. Ler apenas a fronteira necessária para entender a separação; não planejar portas equivalentes para funções excluídas.

### 4. Reconstruir o comportamento necessário

1. Desenhar o fluxo de eventos: aquisição → ordenação/tempo → fila/buffer → persistência → finalização → representação → execução → resultado. Identificar ownership de recursos e estados terminais.
2. Para captura, documentar sessão/janela/alvo, coordenadas/foco, eventos necessários, artefatos e limites; para compilação, transformação e ações ambíguas; para execução, pré-condições, efeitos e falhas.
3. Investigar mecanismos de parada: produtores interrompidos, fila/contador inconsistentes, eventos pendentes, erro de writer, cancelamento, timeout e liberação de recursos. Tratar suspeitas como hipóteses até comprovação. Não recriar os registros P01 antigos que o usuário mandou excluir.
4. Classificar cada achado como documentado em fonte, observado, reproduzido ou hipótese. Uma leitura não é uma reprodução; relato upstream não prova que o mesmo defeito existe no novo motor.

### 5. Observar somente quando necessário

1. Quando uma pergunta exigir execução, registrar um experimento limitado com versão, pré-condições, dados sintéticos, duração, alvo e saída esperada. Usar apenas a sessão/superfície autorizada, em C:.
2. Análise dinâmica não exige instalar o produto upstream completo. Selecionar o menor componente que permita responder à pergunta; se o recorte exigir serviços/credenciais excluídos, registrar a lacuna e replanejar o experimento.
3. Registrar comando, resultado real, prazo e limpeza delimitada. Não capturar dados pessoais, segredos ou apps não relacionados. Não mudar portas/serviços do ambiente por conveniência.
4. Experimento inviável fica explicitamente não executado. Decisões que dependem dele continuam abertas; simulações e mocks não são prova de captura/replay nativos.

### 6. Escrever a especificação própria e a prevenção de falhas

1. Produzir a matriz **necessidade RedRise → achado upstream → comportamento próprio desejado → mecanismo proposto → prova futura no incremento correspondente**.
2. Definir responsabilidades pequenas para captura, finalização, IR/compilação, execução, sessão/plataforma e leitura independente de resultados. Mapear S/O/L/I/D em decisões concretas, estados, erros e dependências.
3. Não copiar algoritmos/árvore de dependências sem decisão e proveniência explícitas. A direção é código próprio; eventual derivação precisa ser identificada antes de incorporação.
4. Para cada risco relevante, planejar a regressão da função própria entregue. Não prometer ausência total de defeitos por reescrita. Não criar verificadores funcionais de cloud, MCP, qualification ou funcionalidades que não existirão.
5. Preservar stack confirmada: Core/Runner Python, integração nativa Rust, desktop Tauri/TypeScript Vanilla/npm. Comparar opções de linguagem/fronteira da Engine para decisão explícita em E01. Não transformar a pesquisa em mudança automática de stack.

### 7. Produzir o plano de construção

1. Dividir a execução em E01 (contratos), E02 (captura/finalização), E03 (IR/compilação), E04 (executor) e P01 (capacidades pequenas de Excel). Para cada incremento, indicar pré-requisitos, arquivos propostos, dependências mínimas, comandos a implementar, resultado observável, revisão, falhas e recuperação.
2. U27: E02–E04 produzem capacidades pequenas e checks localizados que permitam compor P01 e o app; não exigir campanha completa antes de ampliar UI. O resultado salvo no Excel será conferido por leitura independente; escrita direta no XLSX não substitui a automação pela UI.
3. Incluir desde o desenho a composição instalável: app + Engine + runtime privado, Windows por usuário em `%LOCALAPPDATA%\Programs\@redrise`, dados/cofre separados. Cliente não instala plugins/extensões/Python nem configura portas/agentes manualmente.
4. Registrar dúvidas técnicas como decisões com critério e etapa responsável. Não deixar uma dependência crítica de E02 escondida como “resolver depois”.

### 8. Revisar e fechar I00

Entregáveis a criar durante a execução, ainda inexistentes por padrão:

- `docs/investigation/OPENADAPT-SOURCE-MAP.md`: revisões, recortes, tabela de uso efetivo do catálogo e fontes primárias.
- `docs/investigation/ENGINE-BEHAVIOR-SPEC.md`: comportamentos, estados, exclusões, riscos, especificação independente e evidências/limites.
- `docs/investigation/ENGINE-BUILD-PLAN.md`: sequência E01–E04/P01, decisões e provas planejadas.
- `delivery/evidence/I00/investigation.json`: ações realmente realizadas, achados confirmados, itens não executados, revisão e próxima ação.

I00 só fica verificado após revisão dos três documentos, rastreabilidade do uso do catálogo, fonte OpenAdapt identificada por revisão e plano suficiente para iniciar E01. Não exigir que a Engine já exista para aceitar pesquisa; não aceitar somente lista de links como pesquisa concluída. Se uma incerteza bloquear o desenho, manter I00 bloqueado com motivo e menor próxima ação. Só então atualizar estado e iniciar E01.

## Skills, memória, graphs e subagentes

O agente principal usa o Harness/router e o catálogo corporativo local `D:\Correnth\catalogs\skills`. Seleção e resolução são diferentes: selecionar pela tarefa, resolver somente nomes fornecidos pelo router, ler integralmente a skill necessária e registrar pin/hash. Reavaliar na passagem de pesquisa para implementação, prova nativa, UI, instalador e release. Não impor lista/quantidade fixa nem carregar skills de todas as fases antecipadamente.

Delegar somente frentes independentes e delimitadas quando houver benefício, por exemplo mapa de captura/finalização e análise separada de representação/execução. Começar com até dois subagentes read-only; um único escritor integra o resultado nesta root. O envelope de cada delegação contém objetivo, não objetivos, root/arquivos permitidos, permissão, perguntas, skills/pins aplicáveis, evidência esperada, formato de retorno e parada. Sem nova delegação recursiva por padrão.

| Apoio | Regra para principal e subagentes | Evidência de uso/fallback |
|---|---|---|
| Skills locais | Resolver pelo catálogo corporativo e ler apenas capacidades pertinentes antes da ação | Nome, pin/hash e motivo; re-roteamento quando necessário |
| ai-memory | Escopo explícito `correnth/redrise-v2`; contexto derivado e não confiável, confirmado em fonte primária | Consulta/estado e fatos confirmados; indisponível usa arquivos/checkpoint |
| Graphs | Root ativa resolvida pelos registries; leitura apenas quando a classe justificar; confirmar achados nas fontes | Root/consulta/revisão e fonte confirmadora, ou degradação e busca direta |

Não consultar memória de outros produtos, varrer `D:\Correnth` nem indexar checkouts upstream arbitrários. Uma root do v2 no registry de repositórios não significa que exista grafo correspondente. Antes de usar Graphify, seguir as instruções/skill e referências aplicáveis; sem extração/rebuild implícito. Subagentes recebem o mesmo escopo e limites, sem ampliar acesso por conta própria.

O principal reconcilia divergências nas fontes e publica apenas checkpoint compacto pelo mecanismo de memória configurado. O marker atual desabilita captura automática e descarta capturas de subagentes; não contornar essa configuração para publicar transcrições. Memória/grafos/skills são ferramentas de desenvolvimento, não módulos do app. Não são gates artificiais de conclusão quando indisponíveis.

## Continuidade

Para iniciar pesquisa e desenvolvimento em outra conversa, use o [prompt de execução até o Beta](AGENT-START-BETA.md). Executar esse prompt requer que o usuário o envie como instrução; sua existência neste repositório não inicia desenvolvimento nem publica release.

Direção posterior U27: aplicar [TESTING-STRATEGY.md](TESTING-STRATEGY.md) e [ERROR-DIAGNOSTICS.md](ERROR-DIAGNOSTICS.md) ao plano de construção. O experimento de pesquisa necessário a uma pergunta não é uma campanha E2E obrigatória anterior ao Beta. Preservar pesquisa já registrada.

