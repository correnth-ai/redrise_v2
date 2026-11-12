# Work Order — ações de processos, instalador e limpeza do laboratório

- **ID:** PROCESS-ACTIONS-20261111. **Data:** 11/11/2026. **Estado:** executada em 11–12/11/2026 (registro na seção 8). Planejamento fechado em 11/11.
- **Produto/root:** `product:redrise-v2`, `repo:redrise-v2`, `D:/Correnth/products/redrise-v2/repos/app`.
- **Base inspecionada:** `main`, `5f40ecbc32c32b594094a9988ac4a0a24ca53bbf`; SHA remoto de `origin/main` igual, árvore limpa antes destes documentos. Remote autorizado: `https://github.com/correnth-ai/redrise_v2.git`.
- **Predecessora:** PROCESS-LIST-INSTALLER-20261110, beta.31/Core 0.3.10/Runner 0.3.11. Revisão nesta sessão em `delivery/reviews/PROCESS-LIST-INSTALLER-20261111.md`. Não repetir implementação já entregue.
- **Pedido:** revisar entrega anterior, preparar esta WO e um prompt completo para o próximo engenheiro. A submissão do prompt final pelo usuário autoriza a execução e a entrega nele descritas; esta sessão só revisa e documenta.
- **Princípio:** KISS, dados reais, autorização no Core, histórico preservado. MediaFire/publicação pública, VPN e macOS continuam fora do escopo.
- **Revisão de escopo (11/11):** o pedido mais recente substitui integralmente a exclusão em duas modalidades por exclusão somente do processo com palavra digitada; também substitui o Kanban de etapas/cinco colunas por cards de processos, quatro colunas e filtro obrigatório de um único dia. As regras abaixo prevalecem sobre a WO predecessora nesses pontos.

## 1. Processo › Ação e padronização de ícones

### 1.1 Execução e conjunto de ações

- Remover o botão destacado **Nova execução** de Processo › Ação. Iniciar execução pelo ícone Play da linha do processo, preservando o diálogo necessário para estação/parâmetros e os controles de permissão. Não remover APIs de execução, agendamentos nem execução de rotina avulsa em seu próprio contexto.
- Para administrador, todas as linhas de processos, inclusive **Boas-vindas**, apresentam o mesmo conjunto de ações: **Executar, Agendar, Integrar rotina avulsa, Substituir etapa 1, Excluir, Editar composição**, nessa ordem. Lixeira imediatamente à esquerda do lápis.
- A ausência atual de ações em Boas-vindas é uma regra `system_key` tanto na UI quanto no Core. Este pedido altera essa regra para gestão dos processos: corrigir ambos, não apenas mostrar botões que retornam erro. Revisar também a aceitação de seus tipos de rotina no editor/integrador.
- Todos os ícones precisam ter ação real e nome acessível/tooltip, foco visível, área clicável e estado ocupado. Condição realmente inválida pode desabilitar a ação com motivo: processo vazio não executa, substituição concorrente precisa ser resolvida, etc. Não fingir que toda ação é executável em qualquer estado.
- Preservar controle por perfil: disponibilizar todas as ações de gestão ao administrador não autoriza concedê-las a operadores. APIs continuam validando permissões.
- Não recriar Boas-vindas automaticamente a cada início após sua exclusão intencional. Manter marcador/tombstone ou solução mínima compatível com o seed atual e sua chave única. Exclusão/edição não podem quebrar setup, health checks ou updates.

### 1.2 Padrão de ações por ícone

- Converter ações contextuais de registros/tabelas para o padrão `IconAction` da lista de processos. Em **Agendamentos**, Pausar/Retomar e Excluir viram ícones funcionais, mantendo confirmações e estados.
- Inventariar ações contextuais nas telas ativas do app e aplicar o mesmo padrão onde houver equivalentes (executar, editar, visualizar, pausar, retomar, excluir, desativar/reativar). Registrar tabela curta tela/ação/ícone/teste; não se limitar a trocar aparência de Agendamentos.
- Preservar clareza de navegação e formulários: Continuar, Voltar, Salvar, Cancelar, OK, escolhas de exclusão, Nova Conta/Nova Rotina/Novo processo, login e etapas do instalador podem manter texto. Não transformar avisos/decisões destrutivas em ícones ambíguos. Isso concretiza a preferência do usuário por ícones nas ações sem eliminar rótulos necessários às decisões.
- A terceira imagem mostra quebra de linha da última execução em janela estreita, sem instrução textual adicional de remoção. Preservar a informação e verificar legibilidade/layout responsivo; não suprimi-la por inferência.

## 2. Exclusão somente do processo, com confirmação digitada

### Fluxo solicitado

1. Lixeira abre caixa com a mensagem literal **“Confirma exclusão do processo? As rotinas não serão excluídas.”**, identificando separadamente o nome do processo alvo.
2. Solicitar que a pessoa digite **Confirmado**. Habilitar Excluir somente quando `trim().toLowerCase()` for exatamente `confirmado`: aceitar caixa alta/baixa/mista e espaços externos; rejeitar vazio, outra palavra, texto adicional e correspondência parcial.
3. Digitar não exclui sozinho. Confirmar pelo botão Excluir ou Enter no formulário válido; impedir submissão dupla e mostrar estado ocupado. Cancelar/X/Escape antes do envio não altera nada; reabrir limpa o campo. Não transportar a confirmação digitada entre processos.
4. Excluir **apenas o processo** e retirar seus vínculos ativos. Nenhuma rotina é arquivada/apagada: as que só tinham esse vínculo tornam-se avulsas; as compartilhadas mantêm os demais vínculos e apenas deixam de listar o processo excluído. Não converter automaticamente a configuração de uma rotina dependente de contexto em rotina executável isoladamente; preservar a rotina e suas validações de execução.
5. Remover desta entrega o seletor das duas modalidades e qualquer caminho de exclusão combinada de processo+rotinas. Exclusão de rotina por sua própria tela permanece um fluxo separado.

### Contrato e integridade

- Reutilizar arquivamento persistente quando compatível; exclusão retira itens do catálogo ativo, não apaga histórico de execuções, revisões, evidências ou arquivos externos produzidos.
- Core recebe o **ID imutável** do processo e valida administrador, existência e conflitos dentro da transação. Arquivamento e retirada dos vínculos ativos desse processo são atômicos. Nenhuma rotina nem vínculo de outro processo é apagado; serializar alterações concorrentes da composição com a exclusão.
- A confirmação digitada é prevenção de erro humano, não autorização. Validá-la também no contrato de exclusão que a UI usa; a API continua exigindo sessão/perfil e nunca identifica o alvo pelo texto de confirmação ou nome.
- Não excluir enquanto houver execução em andamento/aguardando revisão do processo alvo. Retornar motivo real e orientar concluir/cancelar pelo fluxo existente; não matar execução por efeito colateral da exclusão. Execuções de outros processos que compartilham rotinas não são afetadas.
- Resolver pedidos de substituição pendentes: não deixar aprovação futura alterar processo arquivado. Cancelar/inutilizar explicitamente os pedidos associados com registro, sem aprová-los automaticamente.
- Agendamentos do processo excluído ficam desabilitados/arquivados na mesma operação de forma que nenhum novo disparo seja possível; preservar histórico de ocorrências. Garantir comportamento concorrente com o scheduler.
- UI só remove registros após confirmação; falha mantém dados e apresenta diagnóstico. Repetir requisição não deve excluir outra entidade ou duplicar efeitos. Atualizar listas, totais, opções de filtros e estado de seleção sem página vazia incorreta.
- Preservar processos vazios quando não excluídos e permitir excluir um processo vazio pelo mesmo fluxo.
- **Identidade e nomes repetidos:** criar posteriormente outro processo com o mesmo nome deve gerar **novo ID**, sem ressuscitar o anterior, herdar seus vínculos, execuções, agendamentos, pedidos ou última execução/sucesso. Não fazer upsert, associação, agrupamento, seleção ou exclusão por nome. Se houver unicidade de nome, permitir reutilização após arquivamento sem reutilizar a identidade.
- **Histórico:** manter ID e nome do processo antigo em execuções, ocorrências e revisões. Usar registro arquivado retido e/ou snapshot histórico compatível com o modelo; nunca substituir por nome vazio, nome do novo processo ou inferência pelo nome atual. Alterar o nome do processo novo não modifica os registros antigos.
- Filtros/opções de Histórico identificam processos por ID; se nomes coincidirem, desambiguar na consulta/detalhe com indicação de excluído e referência curta/data, sem renomear arbitrariamente o processo. Cards/listas/contadores nunca misturam entidades homônimas.

### Aceite

- Play funciona; botão Nova execução removido; todos os processos administrativos têm os seis ícones, inclusive Boas-vindas, e ações reais funcionam quando válidas.
- Confirmar/cancelar, digitar confirmado/CONFIRMADO/CoNfIrMaDo e rejeitar palavras incorretas; Enter só submete campo válido; processo exclusivo/compartilhado/vazio/sistema; reabrir o app após excluir Boas-vindas sem recriação.
- Rotinas exclusivas tornam-se avulsas; compartilhadas perdem só o vínculo excluído; nenhuma rotina é arquivada. Histórico continua consultável e snapshots intactos.
- Cenário obrigatório: criar processo A com nome X, rotina exclusiva e outra compartilhada com B; gerar histórico/agendamento sintéticos; excluir A; criar C com o mesmo nome X. Confirmar IDs distintos, C sem vínculos/histórico herdados, B intacto, rotina exclusiva avulsa, histórico de A com nome X preservado; renomear C e conferir A novamente. Repetir consulta após reiniciar e testar requisição atrasada para A sem atingir C.
- Operador/API sem autorização são recusados; concorrência, execução/revisão pendente e scheduler não produzem execução em entidade excluída nem exclusão parcial.
- Agendamentos e demais ações contextuais funcionam por ícones, com tooltips, teclado, estado ocupado e testes de sucesso/falha nos dois temas.

## 3. Histórico somente no submenu próprio

- Remover todo o bloco **Execuções recentes** de **Processo › Ação**, incluindo título, busca, tabela e paginação desse bloco.
- Preservar **Processo › Histórico**, filtros e navegação dos indicadores para o histórico. Não apagar execuções, APIs ou componentes usados por Histórico/Atividade/Kanban.
- Aceite: Ação termina com os componentes pertinentes de processo/agendamento; Histórico continua mostrando execuções recentes e antigas e abre a execução correta pelos atalhos existentes.

## 4. Instalador: capturas passo a passo e correção encontrada na revisão

### 4.1 Evidência visual

- Existem capturas da beta.31 em `delivery/evidence/PROCESS-LIST-INSTALLER-20261110/shots/wizard-*.png`. Não alegar que a etapa nunca foi fotografada.
- Capturar **a versão final desta entrega**, em laboratório sintético: boas-vindas, escolha de papel, servidor escolhido, pronto, progresso realmente em andamento, conclusão, primeira abertura de servidor; repetir estação/pronto/primeira abertura/conexão pendente e conexão de teste; registrar instalação já configurada sem nova escolha de papel, cancelamento e erro controlado.
- Criar `installer-walkthrough.md` com miniaturas/links locais relativos, ordem, legenda, versão, papel, ação executada e resultado observado. Incluir hashes no índice de evidências. Capturas são imagens reais de UI, sem mockups; não capturar senhas, tokens, códigos de conexão reais ou dados pessoais desnecessários.
- Não executar novo setup sobre a instalação real só para tirar prints. Provas nativas exigem ambiente disponível; seguir a skill de computer-use aplicável quando interagir com a UI.

### 4.2 Diagnóstico fiel a falhas após a troca de versão

- Achado P2: `installer/src/wizard.rs:90–91` afirma genericamente que a versão anterior continua intacta mesmo se o erro acontece após o swap, durante atalho/registro/intenção (`installer/src/main.rs:347–370`). Corrigir para informar fase, versão efetivamente presente, dados preservados quando verificado e próxima ação. Não declarar rollback sem executá-lo e confirmá-lo.
- Corrigir também o caminho que ignora erro de restauração (`main.rs:349–352`) e afirma “previous version restored”. Registrar separadamente falha original e falha de recuperação; não apresentar sucesso de recuperação incerto.
- Não é necessário reinventar transações do instalador: usar resultado estruturado por fase ou rollback verificável, mantendo um único dono do destino. Preservar modo quiet/update e seu resultado de erro.
- Aceite: falhas injetadas antes do swap, depois do swap (inclusive gravação da intenção) e na restauração, somente em cópias. Mensagem/JSON e arquivos concordam; usuário não recebe instrução baseada em versão equivocada. Revalidar cancelamento, update e rollback afetados.
- A inconsistência de nomenclatura do resumo do Kanban é absorvida pela seção 4.3: usar os novos rótulos do quadro/resumo, mantendo enums canônicos e rótulos de outros menus fora do escopo.

### 4.3 Kanban por processo e dia selecionado

**Esta definição substitui a anterior de cinco colunas e cards por etapa.**

#### Colunas e significado

- Exibir apenas, nesta ordem: **No aguardo → Em andamento → Concluído → Conferido**. Preservar layout responsivo, usando quatro colunas para toda a largura disponível e rolagem local quando necessário.
- **No aguardo:** execuções/etapas antes em Aguardando, Atenção ou Não executada, incluindo falha, recusa, incerteza, cancelamento e espera por revisão. Não reiniciar nem reenfileirar execução por mudança de coluna. No resumo, manter o estado técnico e motivo reais (ex.: Falhou); a coluna não deve insinuar que haverá nova tentativa automática.
- **Em andamento:** execução efetivamente em andamento/preparação, sem situação bloqueante de espera/revisão/falha.
- **Concluído:** execução encerrada com resultado canônico de conclusão sem conferência (`completed_unverified`), sem falha/incerteza/cancelamento. Não usar como degrau fictício para toda execução.
- **Conferido:** execução encerrada com resultado canônico `verified`. Não promover só porque uma etapa isolada foi verificada; preservar o critério de resultado do processo. Se o Core não distingue algum caso, estender contrato/testes com resultado real, nunca inventar conferência na UI.
- Mapear explicitamente e testar todos os estados atuais do Core com precedência coerente. O estado agregado do processo/executação determina a coluna; não usar a pior situação de uma etapa ainda não iniciada para esconder uma execução que segue normalmente.

#### Dia único, obrigatório

- Filtro sempre preenchido com **Hoje** inicialmente; oferecer seletor de **uma data de calendário** e atalho Hoje. Sem intervalo, multisseleção, Todos os períodos ou botão que deixe a data vazia. Exibir claramente a data selecionada.
- Definição KISS de recorte: execuções cujo **início (`created_at`) pertence ao dia escolhido**, no fuso da equipe/servidor explicitado no contrato. Consultar `[início do dia, início do dia seguinte)` convertido corretamente para instantes; não calcular simplesmente 24 horas em dias de mudança de fuso. Clientes da mesma equipe devem interpretar o mesmo dia da mesma forma.
- Explicitar no filtro/ajuda “Execuções iniciadas em [data]”. Uma execução que atravessa a meia-noite continua pertencendo ao dia em que começou; não aparece duplicada no dia seguinte. O resultado mostrado é o atual dessa execução, não uma reconstrução de seu estado à meia-noite.
- Enquanto o atalho Hoje estiver ativo, acompanhar a virada do dia no fuso da equipe e atualizar a seleção/consulta; uma data escolhida explicitamente permanece fixa. Não reaproveitar seleção antiga ao abrir a página de modo a contrariar o padrão Hoje.
- Processo conferido em outro dia não aparece Conferido no dia selecionado por herança do último resultado geral. Dia sem execuções corresponde a quadro vazio com mensagem apropriada, sem criar cards fictícios para todo processo cadastrado.

#### Unidade do card, conteúdo e atualização

- **Um card por processo no dia**, representando sua execução mais recente iniciada nesse dia. Filtrar pelo dia **antes** de escolher a mais recente por `process_id`; desempatar de forma determinística por ID da execução. Não consultar só a última execução global e então filtrar, nem depender da janela limitada do Histórico.
- Várias execuções do mesmo processo no dia não criam inúmeros cards; o resumo pode indicar a representação da mais recente e levar ao Histórico da execução exata. Processos distintos de mesmo nome permanecem cards separados por ID. Rotinas avulsas não entram no quadro de processos por associação de nome; permanecem no Histórico/Atividade.
- Card mostra **somente três informações:** título com **nome do processo**, **estação** e **usuário que solicitou/executou** conforme autoria canônica. Remover título de etapa, número de etapa, badges, datas e mensagens do card; detalhes continuam no resumo. Nome e usuário exibidos não são chaves de identidade.
- Preservar resumo ao clicar, fechar por X/clique fora/Escape mantendo Kanban, e Saber mais para a execução exata no Histórico. Resumo usa os novos rótulos e explica falhas/esperas reais.
- Cards, contadores e resumo acompanham o servidor e outras pessoas/estações pelo mecanismo existente. Meta saudável: até 5 s com janela visível/feed funcionando; preservar diagnóstico de dados desatualizados e testes de reconexão. Troca de data cancela/descarta respostas anteriores; nenhum card de outra data aparece por corrida de requisições.
- Trocar filtro de data fecha o resumo antigo; atualização automática não troca silenciosamente a execução de um resumo já aberto por uma mais nova. Identificadores e fetch por ID preservam a identidade do resumo.
- Para processos excluídos, execuções históricas do dia continuam consultáveis e mantêm seu nome/ID; exclusão não elimina registro histórico do quadro. Processo recriado com mesmo nome não herda o card anterior.

#### Aceite adicional obrigatório

- Hoje inicial/obrigatório, escolha de dia único sem intervalo, virada do dia, limites de meia-noite/fuso e execução atravessando dias; data sem execução dá vazio.
- Sucesso ontem e falha hoje: ontem → Conferido; hoje → No aguardo com falha explícita no resumo. Sem herdar sucesso. Várias execuções no dia representam só a mais recente.
- Exercitar as quatro colunas e todos os estados agregados, incluindo conclusão sem conferência, revisão e falha, sem mudar estados reais nem fazer retry.
- Cards têm apenas nome do processo, estação e usuário; resumo/Histórico correto; quatro colunas responsivas nos dois temas.
- Dados além do limite do Histórico, duas sessões, refresh, corrida na troca de dia, reconexão e processos homônimos (inclusive antigo excluído e novo) não perdem nem misturam registros.

## 5. Limpeza de pastas defasadas em C:

- Pedido autorizado: o engenheiro deve apagar sobras defasadas da própria operação/laboratório, com inventário e critérios abaixo. A alegação de 40 pastas/25,8 GB vem do usuário e não deve ser apresentada como nova medição desta revisão.
- Escopo inicial permitido: subpastas comprovadamente descartáveis de `C:/Users/raulv/RedRise-v2-dev/lab-test` e `C:/Users/raulv/RedRise-v2-dev/stage`. Outros diretórios só entram com evidência de propriedade/uso desta entrega e escopo explícito; não fazer varredura destrutiva de C:, Temp, perfil ou todo RedRise-v2-dev.
- Antes de apagar: gerar inventário com path absoluto resolvido, versão/finalidade, tamanho, motivo, último uso conhecido e classificação manter/remover. Comparar com instalação atual, processos ativos, canal, rollback e referências necessárias das provas. Data antiga por si só não torna uma pasta descartável.
- Preservar instalação real, dados/configuração/cofres, `.previous` necessário à recuperação, candidato atual, versão anterior recuperável e seus artefatos/backups compatíveis, dependências/toolchains em uso e evidências finais. Não apagar screenshots/relatórios por estarem dentro de uma pasta velha: consolidar antes o que deve ser retido.
- Validar cada caminho absoluto dentro das roots permitidas e rejeitar root em si, junctions/reparse points e alvos ambíguos. Não seguir links. Confirmar que nenhum processo está executando do alvo; não matar processos para viabilizar limpeza.
- Executar em PowerShell ponta a ponta, `Remove-Item -LiteralPath` para cada alvo aprovado pelo inventário. Sem `cmd /c`, caminhos concatenados inseguros ou wildcard amplo. Não reinstalar dependências porque a limpeza as apagou.
- Efetuar limpeza ao fim de uma ação atômica ou após entrega validada; se faltar disco antes, remover apenas sobras já classificadas. Falha/incerteza preserva a pasta e é relatada. Não apagar backups antes de comprovar update e recuperação.
- Registrar inventário, exclusões/falhas, bytes calculados e espaço livre observado antes/depois. Não prometer recuperar exatamente o tamanho calculado. Atualizar checkpoints que mencionem stages pendentes já removidos, preservando o fato histórico e acrescentando estado atual.

## 6. Execução, entrega e completion gate

1. Ler AGENTS/autoridade, estado atual e revisão predecessora; resolver skills e verificar memória no escopo `correnth/redrise-v2`. Registrar HEAD/dirty files e preservar trabalho alheio.
2. Implementar ações/exclusão com contratos e testes de integridade; padronizar ícones e remover Execuções recentes.
3. Implementar o Kanban diário de processos da seção 4.3 e seus contratos/testes. Corrigir diagnóstico do instalador; realizar testes e capturas organizadas. Usar dados sintéticos, provas nativas em C: e checks localizados.
4. Conferir a próxima versão Beta disponível, sincronizar manifests, testar e produzir candidato. Não presumir beta.32.
5. Sob o prompt de execução submetido pelo usuário: commit, integração à main, push normal ao remote autorizado, build rastreável, gate/instalação/update/rollback em laboratório, canal local assinado e update da instalação real. Não repetir autorização já dada por esse prompt. Sem force-push, publicação pública ou interrupção forçada de trabalho/automação.
6. Verificar app reaberto, login, papel, dados e funções; atualizar documentação/status/evidências e fazer commit/push documental complementar. Realizar limpeza delimitada, registrar resultado e manter recuperação disponível.

**Gate:** aceites das seções 1–4 aprovados; screenshots reais indexados; limpeza executada nos alvos seguros ou exceções justificadas; commit/main/remoto identificados; candidato com hash e origem; update real comprovado; documentos coerentes. Nenhum sucesso fictício se faltar prova obrigatória. Revisão de código não substitui prova nativa do instalador.

### Fontes, write-set e recuperação

- Agora: esta WO e relatório de revisão. Implementação futura: `desktop/src/features/{processos,schedules,fluxos,configuracoes}.tsx` e demais telas/componentes identificados no inventário de ações, `icon-action.tsx`, contratos/data source/types/tests; `core/redrise_core/{service,api}.py`, migração nova somente se necessária, testes/diagnósticos; `installer/src/{main,wizard}.rs` e testes; scripts de prova/limpeza delimitados, manifests de versão e docs/status/evidências. Um escritor por root; sem mudanças não relacionadas.
- Revalidar regras canônicas de Boas-vindas/seed e reconciliar docs/contratos em vez de suprimir testes contraditórios. Nova autorização altera as restrições indicadas nesta WO, não as proteções de acesso.
- Skills: planejamento por `scope-planning`, já lida, pin `fd7b13af53a7853d7cbd43ac9f72e801d602c7fb4e592981ac4842e4ded58bfa`; reavaliar no início da implementação/UI nativa/limpeza. Memória anterior indisponível; fontes diretas e checkpoint são o fallback. Grafo não consultado; não reconstruir para esta tarefa.
- Validar com scripts reais de UI/typecheck, testes Core isolados, contratos, base validator, testes do instalador e gate de candidato. Recuperação por backups/versão anterior compatível, sem destruir dados nem repetir operação incerta.
- Evidências próprias: `delivery/evidence/PROCESS-ACTIONS-20261111/`; checkpoint de mesmo ID. Dados sintéticos, sem segredos. Interromper somente a ação bloqueada e concluir trabalho independente possível.

## 7. Prompt completo para o próximo engenheiro

```text
Implemente e conclua a Work Order:
D:\Correnth\products\redrise-v2\repos\app\delivery\work-orders\PROCESS-ACTIONS-20261111.md

Root exclusiva de código: D:\Correnth\products\redrise-v2\repos\app.
Leia a WO inteira, os AGENTS.md aplicáveis e a revisão delivery/reviews/PROCESS-LIST-INSTALLER-20261111.md. Confira HEAD, branch, alterações locais, estado e evidências. Preserve trabalho de outros autores e não reinicie a entrega beta.31.

Esta mensagem autoriza implementar e testar os itens da WO e, após os testes aprovados, fazer commit, integrar à main, fazer push para origin/main no remote https://github.com/correnth-ai/redrise_v2.git, gerar a próxima versão Beta, atualizar o canal local, fazer update da instalação real e reconciliar a documentação. Não peça novamente autorização para essas operações. Não use force-push.

Entregue a execução pelo Play da lista; ações funcionais por ícones inclusive em Boas-vindas e Agendamentos; exclusão SOMENTE do processo pela mensagem “Confirma exclusão do processo? As rotinas não serão excluídas.” e confirmação digitada “Confirmado”, sem distinguir maiúsculas/minúsculas. Nenhuma rotina é excluída: exclusivas ficam avulsas e compartilhadas perdem só aquele vínculo. Preserve histórico com nome/ID antigo e teste recriar outro processo de mesmo nome sem herdar vínculos ou registros. Não implementar as antigas duas modalidades. Remova Execuções recentes de Ação.

Implemente o Kanban com No aguardo, Em andamento, Concluído e Conferido; situações antes em Atenção/Não executada ficam em No aguardo sem alterar estado real ou gerar retry. Filtro obrigatório de um único dia, Hoje por padrão, sem intervalos. Aplique a semântica temporal e de estados da seção 4.3: uma execução mais recente por processo dentro do dia, não a última global. Cards mostram só nome do processo, estação e usuário. Preserve resumo, Saber mais, atualização automática e identidades de processos homônimos. Corrija também os diagnósticos do instalador apontados na revisão.

Use KISS e contratos validados no Core. Não habilite ícones que apenas disparam erros por proteções antigas de system_key. Preserve permissões, execuções em andamento, dados e recuperação. Teste concorrência com vínculos e agendamentos. Use dados sintéticos, nunca exclusão de dados reais como prova.

Tire screenshots reais, passo a passo, do assistente InstallRS da versão final, incluindo servidor, estação, progresso ativo, conclusão, primeira abertura e cenários de erro/cancelamento. Organize um installer-walkthrough.md com imagens, legendas, versão e hashes, sem segredos. Não altere a tecnologia aprovada.

Após testes aprovados: sincronize a próxima versão disponível, faça commit/integração/push, gere artefatos rastreáveis e valide gate, instalação, update e rollback em laboratório. Atualize o canal local com a assinatura exigida. Faça o update real em janela segura, sem interromper trabalho/automação; reabra e verifique versão, login, papel, dados e funcionalidades. Atualize docs/status/evidências/checkpoint e faça commit/push documental complementar.

Apague pastas de laboratório/staging que ficarem defasadas, seguindo integralmente a seção 5: inventário prévio, paths absolutos verificados nas roots permitidas, sem junctions, sem processos em uso e sem wildcard amplo. Preserve instalação atual, dados, cofres, evidências, dependências ativas e recuperação da versão anterior. Use PowerShell com Remove-Item -LiteralPath; registre removidos, preservados, falhas e espaço antes/depois. Autorização de limpeza não permite apagar pastas pessoais ou o laboratório inteiro.

Continue até o completion gate, não pare no código/build. Se houver bloqueio concreto, registre evidência e conclua as partes independentes possíveis. Não invente resultados. MediaFire/distribuição pública, VPN e macOS permanecem fora de escopo.

Ao finalizar: itens entregues, testes/provas, commits e SHA remoto, versão realmente instalada, caminho/hash do instalador, walkthrough visual, documentação, resultado da limpeza e pendências.
```

## 8. Registro de execução (12/11/2026)

- **Decisões do usuário no chat (11/11):** exclusão "Seguir a WO" (só o processo, palavra Confirmado); Kanban "Redesenho da WO" (quatro colunas, um dia, um card por processo).
- **Entregue:**
  - Itens 1–3 e 4.2–4.3 em `f871210`; correção do instalador achada pela prova nativa (manifesto com BOM) e provas em `6a6fbd1`.
  - Push normal: `origin/main` = `6a6fbd1c40eaaf5fd8ead3f6ff646fdd3a95a86e`.
  - Versão livre conferida: 0.1.0-beta.32 (Core 0.3.11, instalador 0.2.1).
- **Provas:**
  - Simuladas: Core 187/187 (15 novos), UI 117/117, contratos 17, validate-base 346.
  - Nativas no laboratório: gate, P10, update de cópia, prova prática de todos os cenários, seis falhas do instalador em cópias, rollback numa cópia.
  - Detalhe na [evidência](../evidence/PROCESS-ACTIONS-20261111/evidence.json); passo a passo em [installer-walkthrough.md](../evidence/PROCESS-ACTIONS-20261111/installer-walkthrough.md).
- **Instalação real:**
  - Canal local assinado; cópia fria dos dados.
  - Instalador `93601c73…1d64` com os argumentos do update.
  - 0.1.0-beta.32, papel mantido, Core e executor prontos, reaberta no login.
  - Conferida com login em 12/11: versão, papel, dados iguais à referência, seis ícones em todos os processos e Kanban de hoje.
- **Limpeza:** cinco pastas em `lab-test`/`stage` (3,03 GB calculados; C: livre de 36,24 para 39,08 GB), em [cleanup.json](../evidence/PROCESS-ACTIONS-20261111/cleanup.json).
- **Pendente:** revisão independente do instalador e estação em segunda máquina (adiadas pelo usuário). Checkpoint: [PROCESS-ACTIONS-20261111](../checkpoints/PROCESS-ACTIONS-20261111.md).
