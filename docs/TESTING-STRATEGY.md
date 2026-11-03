# Testes localizados e validação prática do closed beta

Direção de 27/10/2026: U27-PRACTICAL-TESTING. Este documento atualiza a sequência de desenvolvimento e aceites; não remove testes existentes nem resultados já obtidos. Consulte [roadmap](ROADMAP.md), [diagnóstico de erros](ERROR-DIAGNOSTICS.md) e [estado](../delivery/status.json).

## Construção por capacidades pequenas

Desenvolver uma responsabilidade observável por vez, sob SOLID. O teste de uma capacidade deve poder executar sem completar todas as capacidades anteriores, subir o produto inteiro ou repetir uma automação longa. Não criar um processo/serviço/classe para cada clique: separar responsabilidades com utilidade real.

Cada incremento define entrada, saída, pré-condições, efeitos, prazo, erro e prova curta. Usar fixtures/doubles para dependências não exercitadas e identificar explicitamente o que foi simulado. Quando a capacidade interage com o SO/app, um teste nativo curto e delimitado pode validar somente essa operação; não precisa virar gravação/compilação/replay completo.

Exemplo de construção para Excel, com nomes ilustrativos de contratos ainda a reconciliar com o código:

| Capacidade | Entrada e saída | Teste localizado |
|---|---|---|
| Localizar Excel | Consulta → Found(descritor validado de instalação/ativação), NotFound ou DiscoveryFailed | Descoberta no ambiente atual; testes determinísticos de encontrado/ausente/consulta falha sem desinstalar Excel |
| Iniciar nova planilha | Descritor validado fornecido diretamente → sessão/documento pronto ou erro | Um descritor conhecido/fixture permite testar inicialização sem chamar a descoberta; teste nativo curto abre uma planilha sintética e confere prontidão |
| Apresentar ausência/erro | Resultado estruturado → mensagem e códigos | Fornecer NotFound ou falha e conferir os quatro tópicos, a orientação e o rodapé de diagnóstico |
| Compor o fluxo | Found → iniciar; NotFound/DiscoveryFailed → apresentar; resultado inválido → erro de contrato | Testar roteamento com doubles; não exige executar Excel real para cada ramo |

O descritor pode conter caminho do executável ou identificador de ativação suportado, versão e método de descoberta. Fixar a forma no contrato pertinente. Não aceitar caminho arbitrário como comando nem exigir que toda instalação tenha o mesmo formato. NotFound não é prova de defeito no localizador; falha ao consultar não pode ser convertida silenciosamente em NotFound.

## Conectar módulos sem perder o diagnóstico

Conectar automaticamente os resultados pelos contratos do aplicativo. O usuário não concatena scripts. Uma capacidade consome um valor/resultado validado, em vez de repetir o trabalho do produtor para conseguir ser testada.

Na ligação de duas capacidades, executar apenas os checks de fronteira pertinentes: entrada/saída e versão, roteamento encontrado/ausente, propagação de erro/correlation ID, timeout, resposta inválida e confirmação de efeito incerto. Não exigir uma suíte global ou campanha de automações para concluir cada módulo.

Separar o módulo que reportou a falha, a fronteira onde ela apareceu e os módulos sugeridos para investigação. Uma resposta inválida pode ter origem no produtor, no consumidor ou na transformação; timeout pode ser lentidão ou indisponibilidade, não prova de bug de transporte. Preservar causa conhecida e incerteza conforme [ERROR-DIAGNOSTICS.md](ERROR-DIAGNOSTICS.md).

## Sequência de entrega e aceite

1. **Componentes:** pesquisa existente, capacidades pequenas, módulos, contratos e checks localizados. P01–P04 preparam Excel/runtime/Browser/templates; não bloqueiam o restante por falta de campanha E2E ou máquina limpa.
2. **Composição:** Core, Runner, desktop e catálogo consomem contratos; checks curtos de integração necessários ao fluxo. A capacidade central precisa estar implementada; UI que simula sucesso não a substitui.
3. **Closed beta interno disponível:** gerar e instalar o aplicativo integrado pelo instalador, abrir a UI e confirmar bootstrap dos componentes no ambiente atual. Registrar build/versão/hash e evidência de disponibilidade; esse estado não declara automações homologadas.
4. **Validação prática:** após existir essa build instalada, executar manualmente os cenários completos de Excel, Browser e demais templates pela UI, além de equipe/LAN, atualização e recuperação quando disponíveis. Registrar versão, ações, esperado, observado e erro/módulos. Corrigir e repetir os cenários afetados.
5. **Pronto para release:** aceites obrigatórios do Beta demonstrados e impeditivos resolvidos. Disponibilidade interna, validação e publicação são estados separados.

As campanhas completas de P01/P03/P04/P09 anteriormente exigidas antes de integrar o app passam para P13. P01/P03/P04/P09 mantêm entregas de implementação e checks pequenos de suas responsabilidades. Não executar toda a matriz a cada alteração: repetir somente os cenários atingidos e ampliar quando houver evidência de impacto transversal.

## Ambiente de validação

Usar o ambiente próprio disponível. Outro usuário local, caso útil e autorizado, pode exercitar perfil, configurações e instalação por usuário; não é obrigatório. Não exigir Windows recém-formatado, máquina limpa, VM ou ausência global de Python/Node/Rust como gate desta abordagem. Não desinstalar ferramentas do ambiente para fabricar esse cenário.

Registrar o contexto real: SO, versão do app/Excel, usuário/perfil pertinente sem dados pessoais, runtime/browser efetivamente usados e intervenções. Outro usuário compartilha componentes instalados para a máquina; sua utilização não comprova ambiente limpo. Assegurar dependências privadas pelo empacotamento, paths e diagnóstico observados, com limites de cobertura explícitos. O compromisso de não exigir setup técnico do cliente continua válido.

Equipe/LAN permanece função do produto. Validar no arranjo disponível e registrar nós/papéis reais; não simular três processos na mesma sessão e alegar três estações. Falta de topologia necessária limita esse aceite e não impede desenvolver componentes independentes. Nenhum PC formatado é requisito.

## Evidência e preservação do trabalho existente

Uma verificação localizada comprova sua capacidade, não homologação geral. Distinguir component_check, contract_check e practical_e2e no relatório, inclusive nativo versus simulado e manual versus automatizado. O objetivo é evidência suficiente para saber o que aconteceu; sem quantidade mínima de testes, cobertura arbitrária ou burocracia por operação trivial.

Evidências anteriores permanecem com sua revisão e escopo originais. As provas já realizadas de Engine/Excel podem informar o desenvolvimento; não precisam ser repetidas por mudança documental. Elas não satisfazem automaticamente a aceitação da UI instalada nem o novo tratamento de erros. Novas exigências de erros/contratos são implementadas nos incrementos afetados e verificadas em P05/P07/P08/P13, sem alegação de que código antigo já as atende.

`closed_beta_available` exige instalador/build identificados e abertura/bootstrap no ambiente registrado. `beta_ready` exige os critérios de [BETA-ACCEPTANCE.md](BETA-ACCEPTANCE.md) demonstrados na versão candidata. `published` exige operação externa autorizada e evidência distinta. As provas práticas ocorrem depois do closed beta disponível e antes da conclusão de prontidão para release; não exigem publicação pública prévia.
