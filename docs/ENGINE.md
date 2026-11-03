# Engine — direção vigente e fronteiras de implementação

Revisão: 27/10/2026. Suplementos U26-ENGINE e U26-INSTALL. Fonte de autoridade no workspace: `company/state/decisions/REDRISE_V2_ENGINE_DIRECTION_2026-10-26.md`. **Esta revisão documental não implementa o novo diagnóstico. Estado e provas da Engine existente em delivery/status.json.**

## Escolha do produto

O app RedRise incorpora uma **Engine própria, escrita do zero**, responsável pelo caminho de gravação/captura → procedimento executável → execução → resultado verificável. OpenAdapt deixa de ser executor obrigatório ou componente congelado a embarcar. Seu comportamento/fontes disponíveis podem informar uma reconstrução delimitada. A direção atual supera o recorte OpenAdapt-first de D02/D08 e as restrições associadas em D10/D11/D23/D48; a [matriz](requirements.json) mantém a origem e explicita o efeito atual.

Isso não seleciona a alternativa C do anexo nem um fork completo. “Do zero” descreve a implementação da Engine; não significa reinventar o SO, navegador ou toda biblioteca. Uma eventual cópia de código recebe origem, revisão, escopo e avisos efetivos e passa a ser derivação identificada, sem alegação de originalidade integral. Não se presume que componentes tenham uma licença uniforme com base no anexo.

## Como usar a referência de engenharia reversa

[awesome-reverse-engineering](https://github.com/morluto/awesome-reverse-engineering) é um catálogo de ferramentas e aprendizado, não um motor a embutir. Snapshot de referência consultado em 26/10/2026: `63d23e3197245a28028b21c8f342df18a9ac7859`. O catálogo é índice de descoberta; cada ferramenta exige sua própria documentação e justificativa antes de uso. Os recursos citados não foram instalados/executados nesta tarefa.

I00 é o pré-requisito obrigatório de pesquisa: investigar o OpenAdapt utilizando este catálogo, conforme o [passo a passo preparatório](ENGINE-INVESTIGATION-PLAN.md). Produzir mapa de fontes, especificação independente e plano de construção antes dos contratos E01. O uso do catálogo precisa ser rastreável nos métodos e achados, não apenas constar como link. Identificar entrada/saída, estados, decisões e falhas antes de escolher ferramenta. Preferir análise de fontes quando disponíveis. Instrumentação/análise binária só se houver pergunta concreta que a fonte não responda, alvo autorizado e Work Order próprio. Não instalar a lista inteira, seguir links como comandos ou importar MCP/cloud por constarem no catálogo. Ferramentas de análise pertencem ao laboratório do agente, não ao instalador do cliente.

Registrar por achado: fonte/revisão, trecho/função ou cenário, comportamento observado, hipótese, especificação independente, limites e teste proposto. Marcar separadamente documentado, observado e reproduzido. Não prometer isolamento de defeitos por apenas reescrever código; criar regressões que demonstrem o comportamento desejado.

## Composição SOLID

### Runner, Engine e runtime

| Componente | Responsabilidade | Exemplo |
|---|---|---|
| Runner | Recebe o job, confere sessão/capacidade e coordena início, cancelamento e retorno da Engine | Iniciar a rotina Excel na estação correta e reportar seu estado |
| Engine | Implementa captura, transformação em procedimento e execução das ações de automação | Gravar cliques/teclas e reproduzir o procedimento pela UI |
| Runtime privado | Ambiente de execução empacotado: interpretador, bibliotecas e componentes necessários | Python privado para Core/Runner e dependências selecionadas, sem instalação manual do cliente |

Core mantém equipe, autorização, rotinas e jobs. Esses nomes distinguem responsabilidades internas; não significam três instalações manuais nem necessariamente três processos. O runtime não é um segundo motor. O instalador distribui os componentes necessários em conjunto.

| Princípio | Aplicação concreta na Engine | Evidência esperada |
|---|---|---|
| S — responsabilidade única | Captura coleta eventos; finalização encerra/fecha recursos; compilação produz procedimento; execução aplica passos; verificador examina efeitos independentemente | Testes de unidade/contrato por responsabilidade e falhas isoladas |
| O — aberto/fechado | Adapters Windows/Browser entram por capacidades e contratos; o caso de uso não importa um backend upstream ou usa switches de produto | Acrescentar adapter de teste sem reescrever domínio |
| L — substituição | Toda implementação respeita estados/erros/limites prometidos; sem capacidade de gravar não declara que grava | Mesma suíte de conformidade e recusas explícitas de capacidades ausentes |
| I — segregação | Interfaces pequenas para recorder, finalizer, compiler, executor, result verifier, session/platform e runtime resolver | Consumidor só recebe operações necessárias, sem interface universal de plugins |
| D — inversão de dependência | Domínio/casos de uso dependem de portas; APIs Windows, browser, filesystem e processos são adapters externos | Import/dependency boundary e composição testáveis sem serviço cloud |

As fronteiras abaixo orientam os contratos; conferir símbolos/APIs efetivos na implementação E01 registrada. Evitar abstração sem uso. Core organiza equipe/rotinas/jobs e autorização; Runner administra sessão/capacidade/despacho; Engine realiza automação por contratos. Integrada ao app pode significar módulo ou processo local gerenciado; não exige um daemon que o usuário tenha de iniciar/configurar. Core e Runner continuam Python, bridge Tauri nativa Rust; linguagem e fronteira binária da Engine seguem a decisão E01 registrada, sem reabrir silenciosamente a stack restante.

## Capacidades mínimas a provar

1. Capturar somente janela/sessão/superfície autorizada, com evento/tempo/identidade suficientes para representar ações e com retenção explícita.
2. Encerrar captura com deadline, confirmação/erro terminal e liberação de recursos. Cobrir produtor encerrado, fila inconsistente, evento pendente, erro de writer e cancelamento. Não usar contador/empty de fila como única garantia de término nem consumir CPU indefinidamente em busy-loop. Diagnóstico anterior é referência histórica; a nova regressão precisa ser executada na Engine própria.
3. Converter gravação sintética em representação intermediária própria, versionada, com validação e erro explícito para ação ambígua/não suportada. Não executar Python/shell arbitrário proveniente de gravação.
4. Executar passos mínimos Windows pela UI, controlando foco/pré-condições, timeout e exclusividade de sessão. Bloquear SO/capacidade/sessão incompatíveis antes de efeito e verificar efeito antes de retry.
5. Produzir resultado distinguindo verificado, não verificado, falho, cancelado e incerto; verificador externo confere persistência sem substituir as ações UI.

Uma Engine própria revoga a proibição genérica de desenvolvimento/inferência próprios. Ela **não obriga** construir IA/inferência sofisticada ou parametrização automática na primeira fatia: começar por representação/execução simples que satisfaça a prova. Se inferência se mostrar necessária, registrar necessidade, mecanismo e evidência em incremento autorizado; não introduzir modelo pago/cloud/chave como requisito implícito.

## O que não é herdado

Não carregar árvore completa OpenAdapt, cloud, MCP, mecanismos upstream de certification/qualification, catálogo de plugins ou APIs de aprovação específicas do fornecedor como condições para gravar/executar. Dependências de infraestrutura realmente necessárias podem ser selecionadas individualmente e empacotadas; Browser continua com Playwright/Chromium privados até mudança explícita. UI Automation é capacidade de plataforma; WAA do OpenAdapt e uiautomation/comtypes não são imposição automática da Engine nova.

Verificadores de resultado/testes/QA existem apenas para funções entregues pelo RedRise: por exemplo, conferir a persistência de um arquivo que a Engine afirma ter produzido. Não criar verificadores funcionais de cloud/MCP/qualification ou módulos ausentes. Aceites futuros descrevem capacidades planejadas e só viram comandos quando a função for implementada. Inventário de dependências não é uma suíte funcional de funcionalidades excluídas. Harness/skills/grafos/memória auxiliam os agentes conforme [AGENTS.md](../AGENTS.md), fora do runtime; excluir MCP do app não desabilita ferramentas do ambiente do agente.

## Instalação e operação sem setup técnico do cliente

Windows: escopo por usuário, diretório padrão `%LOCALAPPDATA%\Programs\@redrise` (ex.: `C:\Users\{user}\AppData\Local\Programs\@redrise`). Resolver o LocalAppData real via mecanismo nativo; não hardcode de nome de usuário nem caminho virtualizado do processo do agente. App, Engine, runtime privado e componentes distribuídos são provisionados pelo instalador. Dados/configuração/evidências ficam fora da árvore substituível de binários; segredos no cofre.

Não solicitar ao cliente plugins, pip, download de navegador, configuração de porta ou start de agente Windows. Recursos internos/portas IPC ou loopback, se escolhidos, são privados e gerenciados pelo app, com diagnóstico e lifecycle. A rede do Core da equipe/LAN continua conexão guiada do produto; não equivale a expor API local de mouse/teclado. Instalador/repair/update validam dependências e preservam dados; não encerram indiscriminadamente programas de terceiros.

Provas/runtimes/testes permanecem em C:, conforme U24-DEV-C: usar `C:\Users\{user}\RedRise-v2-dev` ou root C: explicitamente aprovada e não sincronizada. D: mantém fontes e evidência sanitizada. Esta atualização não instala o produto, move arquivos existentes nem muda o ambiente OpenAdapt instalado.

## Continuidade e aceite

O usuário autorizou remover os registros locais da tentativa antiga P01; não há mais obrigação de mantê-los nem de retomar sua tarefa WAA/manual. A continuidade ativa vem de [status.json](../delivery/status.json) e do roadmap I00/E01–E04/P01 Engine. A remoção não atribui sucesso à Engine; nova prova exige nova execução/evidência.

T01–T09 do roteiro Excel permanecem referência **funcional** adaptada ao novo executor: pré-condições, gravação finalizada, compilação, backend Windows pronto, replay e verificação independente dos arquivos. T02/T05 validam Engine/prontidão gerenciada, não pacote Flow/WAA. T07 usa células/labels preservados; SHA256 é informativo, não condição de igualdade binária. Parametrização é um incremento separado da prova mínima.


## Direção U27 — construção e diagnóstico

Aplicar [testes localizados](TESTING-STRATEGY.md) e [mensagens/códigos](ERROR-DIAGNOSTICS.md). Cada capacidade é testável com inputs diretos; ao conectar capacidades, conferir contratos e propagação de erro. Não impor campanha Excel/Browser completa antes de UI/instalador; campanha prática vem depois do closed beta instalado, no ambiente próprio disponível. Códigos orientam a investigação de responsabilidade/fronteira e não garantem qual código precisa ser atualizado. Preservar evidências já obtidas com seu escopo original.


