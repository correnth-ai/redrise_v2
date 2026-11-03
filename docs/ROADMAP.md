# RedRise v2 — passo a passo até o Beta funcional

ID: `redrise-v2-roadmap-20261024`. Versão: 4. Revisão: 27/10/2026.

Direção: Engine própria integrada ao app, escrita do zero sob SOLID, com investigação obrigatória do OpenAdapt usando o catálogo indicado. U27-PRACTICAL-TESTING mantém testes localizados durante a construção e leva campanhas completas de automação para o closed beta instalado. U27-ERROR-DIAGNOSTICS define mensagens e orientação por módulos. Não exigir PC formatado, Windows limpo ou VM.

Leia [AGENTS](../AGENTS.md), [baseline](BASELINE.md), [Engine](ENGINE.md), [testes](TESTING-STRATEGY.md), [erros](ERROR-DIAGNOSTICS.md), [requisitos](requirements.json), [aceite Beta](BETA-ACCEPTANCE.md) e [estado real](../delivery/status.json). Pxx/E/I preservam IDs. Resultados anteriores mantêm a revisão e a abrangência de suas provas; esta revisão não os apaga nem atribui ao código existente o novo tratamento de erros.

## Como um agente executa

1. Confirmar autorização, árvore/remote/HEAD real, estado e evidência existente. Não reiniciar pesquisa/Engine/Excel já verificados por suposição.
2. Abrir [Work Order](WORK-ORDER.md) para um incremento pequeno: responsabilidade, entrada/saída, efeitos, prazo, erro, arquivos e check observável.
3. Usar Harness/router, skills pertinentes com pins, memória explícita correnth/redrise-v2 e graphs apenas em roots registradas e quando pertinentes. Registrar indisponibilidade e usar fontes canônicas; sem rebuild implícito.
4. Delegar somente frentes independentes delimitadas, com objetivo, exclusões, arquivos, permissões, skills, evidência e parada; um escritor por root. Integrar achados e publicar checkpoint compacto, respeitando marker de memória.
5. Implementar e testar uma capacidade por vez. A capacidade seguinte aceita entrada fornecida diretamente/fixture, sem executar toda a cadeia anterior. Ao conectar módulos, conferir somente a fronteira pertinente. Mocks não provam efeito nativo.
6. Registrar resultado conforme [EVIDENCE](EVIDENCE.md). Distinguir check de componente, contrato e E2E prático; também simulado/nativo e manual/automatizado. Não fabricar aprovação nem apagar testes existentes.
7. Campanhas completas Excel/Browser/templates e integração de equipe pertencem a P13, depois da build de closed beta instalada. Antes disso, checks curtos necessários para desenvolver componentes e conectá-los continuam válidos.
8. Reavaliar skills e aceites ao mudar de tipo de trabalho. Ausência de máquina limpa/VM/campanha E2E não bloqueia desenvolvimento independente. Dependências reais de código, autorização e dados continuam aplicáveis.
9. Criar verificadores somente de funções reais entregues. Cloud/MCP/qualification excluídos não recebem fixtures ou gates funcionais.

| Passo | Entrega de construção | Depende de |
|---|---|---|
| P00 | Base independente e fontes | Solicitação do usuário |
| I00 | Investigação OpenAdapt com catálogo e plano próprio | P00 |
| E01 | Contratos mínimos SOLID | I00 |
| E02 | Captura/finalização própria | E01 |
| E03 | IR/compilação própria | E02 |
| E04 | Executor próprio | E03 |
| P01 | Capacidades pequenas para Excel | E04 |
| P02 | Composição privada Engine/Runner/runtime | P01 |
| P03 | Capacidades Browser e componentes privados | P02 |
| P04 | Capacidades dos templates | P03 |
| P05 | Contratos integrados e diagnóstico de erros | P04 |
| P06 | Core, equipe e persistência | P05 |
| P07 | Runner/jobs e ligações entre módulos | P06 |
| P08 | Desktop mínimo e composição pela UI | P07 |
| P09 | Catálogo conectado ao aplicativo | P08 |
| P10 | Instalador e closed beta interno disponível | P09 |
| P11 | Atualização e recuperação implementadas | P10 |
| P12 | Site/onboarding/download local isolado | P11 |
| P13 | Campanha prática manual no closed beta instalado | P12 |
| P14 | Correções fechadas e candidato pronto para release | P13 |

A sequência representa entregas; trabalho independente pode avançar quando seus contratos/insumos existirem. Não declarar passo verificado sem os checks localizados da entrega. Campanha posterior não vira dependência circular da própria construção. Disponibilidade interna, validação e publicação são estados distintos.

## P00 — Estabelecer a nova base

Confirmar IDs product:redrise-v2/repo:redrise-v2, remote `https://github.com/correnth-ai/redrise_v2.git`, manifesto separado, fontes/hash lock, memória e logos autorizados. Preservar o produto anterior. Validar base com `node scripts/validate-base.mjs --check-sources`, origin/estado e schema/hashes do manifesto. Registro original P00 não deve ser reescrito.

**Saída:** identidade e plano coerentes; próxima tarefa incompleta segundo estado. **Parar:** root/fonte divergente ou contaminação do produto anterior.

## I00 — Investigar OpenAdapt e planejar a construção da Engine

Executar [ENGINE-INVESTIGATION-PLAN](ENGINE-INVESTIGATION-PLAN.md). Usar [awesome-reverse-engineering](https://github.com/morluto/awesome-reverse-engineering) efetivamente para selecionar métodos aplicáveis às fontes OpenAdapt fixadas por revisão. Registrar pergunta → método/recurso → fonte → achado/evidência, separando hipótese de observação/reprodução. Produzir mapa de fontes, especificação independente e plano E01–E04. Não basta listar links nem importar a árvore upstream.

**Saída:** investigação revisada suficiente para construir. Se já verificada, consumir seus resultados e atualizar apenas lacunas pertinentes à nova estratégia. Checkouts/experimentos em C:, evidência sanitizada em D:.

## E01 — Especificar contratos SOLID

1. Usar I00 para definir portas pequenas de captura, finalização, IR/compiler, executor, sessão/plataforma e runtime. Domínio depende dos contratos, APIs do SO são adapters.
2. Fixar entradas/saídas, erros, efeitos, estados, deadlines e ownership de recursos. Linguagem/fronteira da Engine deve refletir a decisão já registrada, sem reabrir stack confirmada por conveniência.
3. Definir checks de conformidade e fixtures para dependências. Incorporar [diagnóstico](ERROR-DIAGNOSTICS.md) nos contratos novos/alterados pertinentes, com mapa dos códigos para símbolos reais.

**Validar:** exemplos válidos/inválidos e S/O/L/I/D concretos. **Saída:** interfaces suficientes à próxima capacidade. Não criar abstrações sem uso.

## E02 — Construir captura e finalização

Implementar iniciar/coletar/parar/cancelar em responsabilidades pequenas. Testar prazo, drenagem/erro, produtor interrompido, writer falho, liberação de recursos e estado parcial, sem busy-loop. Um teste nativo curto pode conferir captura isolada na superfície autorizada; não exige automação completa no Excel.

**Saída:** capacidade de captura com resultados/erros próprios. **Parar:** perda silenciosa, término indefinido ou captura de alvo indevido. Prova anterior permanece com seu escopo original.

## E03 — Construir representação e compilação

Implementar IR versionada e transformação da captura em procedimento. Testar diretamente com entradas pequenas/fixtures, sem regravar a cada teste. Entrada ambígua, inválida ou ação não suportada produz diagnóstico; não executar shell/Python arbitrário oriundo da gravação.

**Saída:** compilação localizada e contrato consumível pelo executor. Um mock da captura é declarado como tal.

## E04 — Construir executor próprio

Implementar ações pequenas e controle de sessão/foco/prazo. Testar uma ação/ramo de erro por vez, usando IR fornecida diretamente. Ao conectar captura/IR/executor, testar as fronteiras relevantes e propagação de falhas, sem exigir campanha E2E. Efeito incerto impede retry cego; verificador confere, não fabrica o efeito.

**Saída:** executor implementado com checks localizados. Replay completo por produto instalado será validado em P13; não embarcar OpenAdapt inteiro para completar o fluxo.

## P01 — Construir capacidades pequenas de Excel

1. Localizar Excel na máquina atual; distinguir encontrado, ausente e falha da consulta. Resultado encontrado contém descritor validado de caminho/ativação.
2. Implementar iniciar nova planilha consumindo descritor conhecido diretamente. Teste curto pode iniciar Excel e conferir prontidão, sem chamar descoberta ou gravar/reproduzir rotina inteira.
3. Implementar tratamento de ausência/falha com os quatro tópicos e códigos de módulo ao final da mensagem.
4. Testar roteamento com fixtures: encontrado → iniciar; ausente/falha → mensagem; contrato inválido → diagnóstico da fronteira. Não exigir desinstalar Excel para testar ramo ausente.

**Escrita:** módulos/contratos pertinentes, checks curtos e evidência localizada. **Saída:** capacidades reutilizáveis, sem obrigar campanha de gravação/replay completo antes de UI. Prova P01 já obtida é preservada; cenário completo Excel vai a P13 pela UI instalada. Leitura independente de XLSX continua conferindo o resultado; escrita direta não substitui automação UI.

## P02 — Compor Engine/Runner/runtime privados

1. Empacotar componentes mínimos em runtime privado, sem Python/pip/plugins/portas configurados manualmente pelo cliente.
2. Verificar resolução de executáveis/bibliotecas, versão, health e lifecycle com checks curtos no ambiente atual, registrando os paths efetivos.
3. Separar binários, dados/configuração e cofre. Padrão por usuário `%LOCALAPPDATA%\Programs\@redrise`; fontes em D:, execução de desenvolvimento em C:.
4. Registrar limites do ambiente atual. Não exigir Windows limpo, VM, remoção de toolchains globais ou repetição da campanha Excel para concluir a composição privada.

**Saída:** empacotamento/composição demonstrados por checks localizados. Instalação integrada em P10, experiência completa em P13. Pendência antiga de clean VM deixa de ser gate; nenhum resultado não executado vira aprovado.

## P03 — Construir capacidades Browser privadas

Selecionar Playwright/Chromium compatíveis e incluídos, distintos do WebView2 da UI. Testar separadamente resolução do browser privado, abertura e ações pequenas contra página local sintética, usando inputs diretos/fixtures. Detectar resposta inválida, timeout e resultado não confirmado conforme a fronteira. Evitar download inicial oculto e dependência de cache global.

**Saída:** adapter e empacotamento Browser com checks locais. Gravação/compilação/replay completo pela UI e conferência de efeito pertencem a P13. Não exigir máquina limpa nem alegar suporte a sites arbitrários por uma fixture.

## P04 — Construir capacidades dos templates

Definir metadados versão/finalidade/inputs/pré-condições/resultado/colisão. Montar capacidades pequenas de Boas-vindas, Excel, Browser, abrir Outlook e acessar Gmail. Verificar funções isoladas e tratamento de app/conta ausentes; não enviar mensagens nem criar/ler contas amplamente por inferência. Preservar literal de Boas-vindas em BASELINE e operações UI pretendidas.

**Saída:** procedimentos compostos com checks pequenos, ainda sem homologação geral. Campanha completa dos cinco templates no produto instalado em P13; não exigir repetição de todos para cada capacidade.

## P05 — Consolidar contratos, erros e decisões LAN

1. Consolidar Core Python/Runner Python/Engine/desktop, consumindo implementações existentes e contratos suficientes. Registrar API/transporte autenticado, storage, jobs e versões.
2. Implementar estrutura e propagação de [ERROR-DIAGNOSTICS](ERROR-DIAGNOSTICS.md): quatro tópicos, rodapé visível, classificação, correlação, origem, fronteira, estado de efeito e sugestões de módulos sustentadas por evidência. Registrar IDs → responsabilidades → símbolos/paths reais.
3. Testar produtores/consumidores com fixtures: formato/versão inválidos, ausência, timeout e causa preservada. Distinguir falha interna, contrato, comunicação, ambiente/pré-condição e origem desconhecida.
4. Definir equipe/LAN, sessões/capacidades, cancelamento, idempotência, migrações e recuperação. UI/Runner usam API, sem credenciais administrativas de DB.

**Saída:** contratos e diagnóstico suficientes à composição; não exigir serviço inteiro nem automação longa para cada check. Código de módulo é orientação, não certeza de atualização necessária.

## P06 — Construir Core, equipe e persistência

Construir funções pequenas de primeiro admin, login/autorização admin-operador, rotinas/versões, jobs e persistência em PostgreSQL. Verificar cada responsabilidade e fronteira pertinente; usar banco de desenvolvimento isolado quando o comportamento exigir SQL real. Testar backup/restore em destino delimitado sem afetar dados existentes.

**Saída:** componentes backend funcionais com erros/efeitos bem definidos. Piloto integrado de equipe/reinício/recuperação completa em P13. Não criar banco por estação nem herdar dados do produto anterior.

## P07 — Integrar Runner e jobs

Compor registro/capacidade, claim, sessão, execução, cancelamento, resultado e persistência via contratos P05. Checks curtos por ligação: duplicação, lease, ack, timeout, sessão indisponível e efeito incerto. Diferenciar problema de transporte de falha do módulo e preservar causa/correlação. Não repetir escrita por falta de confirmação.

**Saída:** ligação Core/Runner/Engine implementada, sem exigir campanha completa por API antes do desktop. Provas práticas de reconexão/falha pós-efeito em P13 na build instalada.

## P08 — Construir desktop e conectar capacidades

Tauri/TypeScript Vanilla/npm/Vanilla UI, Rust nativo e logos autorizados. Construir conexão/login/catálogo/ação/resultado com menus literais Rotina, Ação, Configuração. Conectar capacidades via contratos, testar roteamento e UI/IPC pontuais, inclusive os quatro tópicos de erro e rodapé de módulos. Registrar estados aguardando/em andamento/falho/incerto/verificado com verdade.

**Saída:** UI composta com serviços reais; double pode apoiar teste localizado, sem virar alegação de funcionamento completo. Não expor shell arbitrário ou acesso direto ao DB. Campanhas integradas em P13.

## P09 — Conectar catálogo e histórico ao aplicativo

Compor os cinco templates na UI com versões, inputs, pré-condições, resultados e histórico persistido. Testar pontualmente passagem de inputs, leitura de resultado, manutenção de versão e apresentação dos erros. Não exigir campanha completa Excel/Browser/templates como condição para construir o instalador.

**Saída:** composição implementada, pronta para empacotar. Efeitos reais completos são aceites P13; tela navegável não equivale a template homologado.

## P10 — Gerar instalador e disponibilizar closed beta interno

1. Gerar build/instalador identificados por versão/hash, componentes privados e inventário. Instalação por usuário no padrão definido, sem setup técnico manual.
2. Oferecer criar host de equipe ou conectar estação; decisões de serviços/portas/privilégios necessárias são explícitas, sem mudanças silenciosas no sistema/terceiros.
3. Instalar no ambiente próprio disponível, ou outro usuário local se útil e autorizado; confirmar abertura da UI/bootstrap/componentes e registrar intervenções reais. Não exigir VM/Windows limpo/PC formatado nem ausência de toolchains globais.
4. Registrar `closed_beta_available=true` e evidência apenas quando houver build instalada e aberta. Essa disponibilidade interna não declara automações homologadas, `beta_ready` ou publicação.

**Saída:** aplicativo integrado instalável disponível à experimentação. Papéis host/estações continuam no produto; validação prática da equipe no arranjo real disponível em P13. Não alegar topologia não exercitada.

## P11 — Construir atualização e recuperação

Implementar busca/manifesto/download/integridade, aviso inferior direito/indicador e botões literais Pode atualizar/Ainda não. Checks por responsabilidade, erro e fronteira, incluindo pacote inválido e efeito incerto; não exigir campanha com todas as estações para cada alteração. Preservar dados/documentos e componentes de terceiros.

**Saída:** manutenção implementada e candidata instalada atualizada quando necessário. Ensaio integrado de adiar/confirmar/falhar/recuperar em P13, depois de existir o closed beta instalado.

## P12 — Preparar site/onboarding/download local isolado

Consultar fontes específicas do site. Desenvolver telas/formulários/validações/links por responsabilidade; sem alterar domínio/autenticação/produto anterior por inferência. Preservar destinos existentes até decisão específica. Download local aponta ao instalador completo identificado; envio externo exige autorização.

**Saída:** entrega web local para candidato real; sem publicação automática. Fluxo completo baixar/instalar/conectar/usar pode ser exercitado em P13.

## P13 — Validar praticamente o closed beta instalado

1. Confirmar build instalada, `closed_beta_available` com evidência e componentes/versões. Usar [matriz Beta](BETA-ACCEPTANCE.md) no ambiente atual; outro usuário é opção, não requisito de máquina limpa.
2. Executar manualmente pela UI gravação/compilação/replay de Excel e Browser, Boas-vindas, Outlook/Gmail conforme pré-condições e demais fluxos reais. Cenário Excel preserva labels/células, B2=Cliente Teste 01 e B3 numérico 1500, saídas distintas e leitura independente após salvar/reabrir. SHA256 é informativo, não igualdade binária obrigatória.
3. Exercitar estados/falhas: Excel ausente por fixture ou ambiente apropriado, resposta incompatível, sessão bloqueada, cancelamento, timeout, efeito incerto, host indisponível e erro entre módulos. Conferir mensagem, detalhes e códigos úteis; falhas provocadas/fixtures são declaradas separadamente do uso nativo.
4. Exercitar equipe/LAN no arranjo real disponível, autorização, restart, atualização e recuperação. Registrar nós/papéis e limites; não alegar várias estações por processos numa mesma sessão.
5. Registrar bug, build, passos, esperado/observado, referência e módulos sugeridos; corrigir responsabilidade/fronteira pertinente, executar regressão localizada e repetir somente E2E afetados. Ampliar campanha se houver impacto transversal.
6. Obter revisão pertinente dos resultados e confrontar efeito observado com anunciado. Check manual vale com registro suficiente; não exigir automação de toda a matriz.

**Saída:** aceites práticos reais da versão candidata, impeditivos explicitados. **Parar o aceite afetado:** função obrigatória ainda falha/pulada ou efeito desconhecido sem tratamento; continuar correções/ações independentes. Falta de PC limpo não é bloqueio.

## P14 — Fechar candidato pronto para release

Conferir entregas, aceites obrigatórios e correções da mesma versão/build identificada. Entregar instalador/hash/inventário, release notes honestas, ambiente suportado e instruções instalar/usar/atualizar/diagnosticar/recuperar. Revisão final confirma `beta_ready=true` somente com P13 demonstrado e sem impeditivo aberto. Novas versões reabrem aceites afetados; evidência histórica não homologa automaticamente código alterado.

**Publicação separada:** commit/push/deploy/download público/domínio/release externa exigem ordem explícita. `published` permanece false até a operação autorizada e comprovada. O objetivo é closed beta funcional validado e pronto para release, sem chamar build não experimentada de versão homologada.

## Continuidade

Provas já registradas de I00/E01–E04/P01 permanecem preservadas; novos requisitos de erros e composição são trabalho pendente nos incrementos afetados. P02–P04 não ficam bloqueados por antiga exigência de clean VM. Consulte status antes de escolher a menor próxima ação.

Para outro agente executar esta direção, copie [AGENT-START-BETA](AGENT-START-BETA.md). Sua criação é atualização documental; não inicia automações nem publica produto. Mac/Linux/ARM, self-hosted remoto e parametrização avançada continuam evoluções posteriores, sem antecipação especulativa.
