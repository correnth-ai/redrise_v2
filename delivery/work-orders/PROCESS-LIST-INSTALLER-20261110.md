# Work Order — listagem de processos e instalação Windows

- **ID:** PROCESS-LIST-INSTALLER-20261110.
- **Estado:** planejamento concluído em 11/11/2026, por solicitação do usuário; pronta para execução pelo agente engenheiro. Quatro itens no escopo. Implementação ainda não iniciada; planejamento concluído não significa funcionalidades entregues.
- **Produto / repositório:** `product:redrise-v2` / `repo:redrise-v2`.
- **Root / remote:** `D:/Correnth/products/redrise-v2/repos/app` / `https://github.com/correnth-ai/redrise_v2.git`.
- **Base observada:** branch `main`, HEAD `9cef3cb99f8ba2c2832d5b401fbc1cbb97a76479`; árvore limpa antes deste documento. Revalidar no início da construção.
- **Estado documental:** beta.30, Core 0.3.9, Runner 0.3.11; fonte `AGENTS.md` e `delivery/status.json`. A imagem do usuário também mostra beta.30. Não constitui nova prova de instalação.
- **Contexto:** nova WO, sem reabrir TEAM-ACCOUNTS ou ACCOUNT-ERASURE. Escopo de UI em P13 e instalação/update nas fronteiras existentes de P10/P11.
- **Autorização atual:** por instrução explícita do usuário em 11/11/2026, o engenheiro deve implementar, testar e, após validar a alteração, fazer commit, integrar à main, fazer push ao remote autorizado, gerar a nova versão Beta, atualizar o canal local e realizar o update da instalação real, verificando o resultado e reconciliando a documentação. Essas operações não exigem repetir a pergunta de autorização. **InstallRS aprovado explicitamente como tecnologia escolhida**. MediaFire e distribuição pública permanecem adiados. Esta sessão apenas finaliza o documento/prompt; a execução cabe ao agente engenheiro.

## 1. Processo › Ação: lista navegável e rotinas recolhíveis

### Estado observado

`ProcessTable` em `desktop/src/features/processos.tsx` renderiza todos os processos recebidos e todas as rotinas filhas. Existem filtros de processo e última execução, mas não paginação nem expansão individual. `Core.list_processes` em `core/redrise_core/service.py` consulta todos os processos não arquivados, sem LIMIT nessa consulta. Não há teto explícito de quantidade nesses pontos; isso não comprova capacidade ilimitada ou desempenho para grandes volumes.

### Comportamento solicitado e definição KISS para execução

1. Antes do nome de cada processo, na posição azul da imagem, exibir botão de expandir/recolher com chevron, tooltip e `aria-expanded`. Só esse botão alterna a lista de rotinas; clicar em Executar, Agendar, Editar ou demais ações não alterna expansão.
2. Padrão de implementação: processos recolhidos ao entrar. Expandir mostra as rotinas na ordem existente; recolher deixa apenas a linha-resumo do processo, com nome, contagem, estado, datas e ações. Sem apagar ou alterar vínculos.
3. Paginar **processos**, não linhas de rotina: 10 por página por padrão, opções 10/25/50, anterior/próxima, primeira/última e total filtrado. Um processo e suas rotinas expandidas ficam na mesma página. A expansão não muda a contagem paginada.
4. Reutilizar o padrão e helpers de Rotina › Lista (`data-table.tsx`, `table-state.ts`), adicionando apenas suporte delimitado a linhas filhas se necessário. Evitar um segundo framework de tabelas.
5. Busca por nome de processo; preservar filtros por processo e estado da última execução, com Limpar filtros. Filtrar e ordenar antes de paginar. Ordenação inicial estável; oferecer nome e última execução com sucesso. Ao mudar filtro/tamanho, ajustar a página; nunca deixar página vazia indevida depois de remover/filtrar dados.
6. Manter expansão por ID durante atualização de dados na mesma visita à página. Não exigir persistência permanente. Preservar ações/permissões, indicadores e a variante `compact` onde for usada.
7. Primeira implementação: paginação local sobre a coleção existente, como na tabela de rotinas. Isso limita a renderização, não o volume transferido pelo Core. Medir um conjunto sintético de 100 processos com rotinas; registrar dados e comportamento, sem alegar limite homologado. Paginação no servidor só entra se houver gargalo demonstrado e contrato revisado; sem truncamento silencioso.

### Última execução com sucesso

- Na região amarela, entre Estado/Execução e Ações, adicionar coluna **Último sucesso**, na linha do processo. Exibir data e hora locais (`dd/MM/aaaa HH:mm`), com instante completo/fuso em tooltip quando útil.
- Sucesso = execução do processo encerrada com o resultado canônico `verified`. Usar o horário de conclusão (`finished_at`), não a criação da execução nem o resultado isolado de uma rotina.
- Core retorna campo específico, por exemplo `last_success_at`, calculado sobre todo o histórico aplicável. Não derivar de `last_execution`, de uma página de histórico ou apenas dos últimos 30 dias. Uma falha posterior não apaga o sucesso anterior.
- Processo sem sucesso: “Nunca”. Falha de carregamento: “—” e diagnóstico, sem confundir ausência com erro. Linha de rotina não herda uma data fictícia do processo.
- Preservar a informação da última tentativa e seus estados; “Último sucesso” é informação adicional. Empates de ordenação têm desempate estável por ID.

### Aceite do item 1

- 0, 1, 10, 11, 25, 51 e 100 processos sintéticos: total/páginas corretos, sem perder ou repetir processos; busca/filtros/ordenação operam sobre toda a coleção.
- Expandir/recolher por mouse e teclado, sem alterar dados nem disparar execução; ações independentes; estado mantido durante refresh da mesma visita.
- Processo com sucesso antigo e falha recente mantém a data do sucesso; sucesso fora de 30 dias também aparece; execução em andamento/cancelada/não verificada não conta como sucesso.
- Temas claro/escuro e janela estreita: alinhamento, cabeçalho, coluna de ações e datas legíveis. Testes de componente/contrato e prova visual local; nenhuma automação real é necessária para fabricar o histórico de teste.

## 2. Assistente de instalação Windows com InstallRS

### Decisões e fontes

- **InstallRS é a escolha aprovada**, não uma alternativa em comparação. Não substituir por NSIS/Inno Setup ou reabrir seleção por preferência do executor. Se houver incompatibilidade comprovada, apresentar a evidência e uma solução delimitada antes de trocar tecnologia.
- Sessão consultada via `read_thread`: `thread://01a1b90e-ee33-7100-ba69-094cb5262f74?hostId=local`, quatro turnos finais. O usuário pediu wizard direto e escolha servidor/estação na instalação. As sugestões de macOS/hospedagem dessa conversa não entram neste escopo.
- Fonte primária: [InstallRS](https://github.com/merlinz01/InstallRS). Documenta licença MIT, wizard nativo Windows, páginas personalizadas, progresso e cancelamento. Isso é capacidade declarada upstream, não prova de compatibilidade com RedRise. Fixar versão/revisão e lockfile na implementação; revisar somente dependências efetivamente embarcadas e preservar avisos de licença.
- Hoje `installer/src/main.rs` usa confirmação MessageBox, valida payload/manifesto, extrai em staging e faz troca atômica com recuperação; mantém dados separados, atalho e registro de desinstalação. `desktop/src/features/auth.tsx` oferece a escolha criar equipe/conectar apenas na primeira abertura.

### Experiência proposta

1. Abrir o EXE inicia diretamente o wizard **Instalar RedRise**, sem a pergunta preliminar “Deseja instalar?”. Não contornar avisos legítimos do Windows.
2. **Boas-vindas:** apresentar RedRise e Continuar.
3. **Como este computador será usado?** Escolha obrigatória, sem seleção silenciosa:
   - **Servidor da equipe:** mantém dados da equipe e também pode executar rotinas; precisa ficar ligado com o RedRise aberto para atender estações/agendamentos.
   - **Estação de operação:** conecta-se ao servidor de uma equipe existente; não cria outro banco/equipe local.
4. **Pronto para instalar:** mostrar papel escolhido e destino por usuário `%LOCALAPPDATA%\Programs\@redrise`; Voltar/Instalar/Cancelar. Sem exigir senha administrativa do Windows no fluxo normal por usuário.
5. **Instalação:** progresso real por etapa, erro compreensível e cancelamento seguro. Não simular progresso concluído antes da validação.
6. **Concluído:** oferecer Abrir RedRise. A primeira abertura segue o papel escolhido sem repetir a escolha:
   - servidor: configurar equipe e primeiro administrador usando o fluxo local existente;
   - estação: informar código da equipe e registrar a máquina com administrador, seguindo contrato existente; depois login individual de quem vai operar.

### Integração e limites

- KISS: um instalador Windows x64 com InstallRS, reaproveitando o payload e as garantias atuais. Escolher papel determina o fluxo/configuração; não exige criar dois instaladores nem otimizar o tamanho do pacote nesta entrega.
- Persistir apenas intenção não secreta `server|station`, com contrato de versão claro, fora de binários substituíveis. Senhas, tokens e código de conexão não são argumentos de linha de comando, logs ou conteúdo do instalador.
- A intenção não concede acesso, não cria administrador nem comprova conexão. O app valida e consome a escolha ao concluir a configuração. Definir cancelamento/retomada e evitar setup duplicado se fechar e reabrir antes de finalizar.
- Instalação existente: detectar configuração válida e preservar papel, banco, estações e credenciais. Update/reinstalação não pergunta novamente nem converte servidor em estação. Mudança de papel de uma instalação configurada fica fora desta WO.
- Compatibilidade com updater é obrigatória: inspecionar flags/contratos atuais de instalação silenciosa, retorno de erro e rollback antes de ligar InstallRS. Não substituir silenciosamente argumentos que o updater usa; adaptar com testes do produtor e consumidor.
- Manter hash/manifesto, staging, troca atômica, proteção quando o app está aberto, desinstalação por usuário e preservação de dados. Cancelar antes do commit mantém a instalação anterior; durante etapa atômica, completar ou recuperar a operação antes de sair, sem terminar com diretório parcial.
- O framework pode trazer operações de instalação próprias; não executar dois mecanismos concorrentes sobre o mesmo destino. Definir um único responsável por extração, swap, registro e rollback.
- Estação sem servidor acessível: instalação dos binários pode concluir, mas configuração deve indicar conexão pendente e permitir tentar novamente, sem criar servidor local como fallback.
- Não criar serviço Windows, liberar firewall automaticamente, configurar VPN, baixar dependências inesperadas ou instalar ferramentas corporativas no cliente. Componentes necessários continuam gerenciados pelo pacote.

### Aceite do item 2

- Prova inicial com InstallRS fixado: wizard abre no Windows, página de papel funciona e a intenção chega corretamente à primeira abertura do RedRise. Registrar dependências, licença e integração escolhida.
- Instalação nova sintética como servidor e como estação: fluxo correto, sem pergunta duplicada, sem privilégios implícitos; estação não inicia banco local.
- Cancelar em telas anteriores não instala; falha/cancelamento durante instalação não destrói instalação anterior ou dados. Payload adulterado é recusado; processo do app aberto respeita proteção vigente.
- Atualizar cópia de beta existente preserva papel/dados/login; updater continua compatível; rollback comprovado numa cópia e desinstalação preserva dados conforme contrato.
- Prova de conexão a Core de teste separado para o ramo estação; distinguir teste integrado local de homologação em segunda máquina física/LAN/VPN. Não declarar homologação remota com mocks ou duas instâncias no mesmo host.
- Provas nativas no laboratório C:, sem exigir máquina limpa/VM. Registrar explicitamente qualquer prova prática não executada.

## 3. Configuração › Equipe: impedir desativação da própria conta

- Manter o botão **Desativar** visível, porém desabilitado na linha cuja conta corresponde ao usuário autenticado. Usar ID canônico da sessão (`me.id`), nunca nome de exibição, e-mail ou texto `admin.lab` fixo.
- Mostrar motivo simples, acessível, como “Você não pode desativar sua própria conta”. Clique, Enter/Espaço ou eventos programáticos da UI não enviam PATCH para esse caso; não gerar o painel vermelho por uma ação previsivelmente indisponível.
- Preservar estado ocupado e permissões das demais linhas. Outro administrador autorizado continua podendo gerenciar contas conforme o contrato vigente; a proteção do último administrador ativo continua valendo.
- Verificar e garantir também no Core a recusa de autodesativação por chamada direta, inclusive quando há outro administrador ativo. A UI evita o erro no uso normal; não remover validações ou ocultar erros reais de outras ações.
- **Fonte:** `TeamAdmin` em `desktop/src/features/configuracoes.tsx` hoje desabilita o botão apenas durante `action.busy`. O erro CONFLICT da imagem não prova qual precondição falhou; não atribuí-lo automaticamente à proteção de autodesativação já implementada.
- **Aceite:** própria linha desabilitada sem requisição nem alerta; outra conta continua gerenciável; troca de usuário muda a linha protegida; chamada direta não desativa o ator; proteção testada com dois administradores e também com último administrador. Nenhuma conta real é desativada como teste.

## 4. Processo › Kanban: layout, resumo e atualização automática

### 4.1 Colunas responsivas, ordem e nome

- Ordem fixa da esquerda para a direita: **Aguardando → Em andamento → Atenção → Não executada → Conferida**.
- Trocar “Verificada” por **“Conferida”** no Kanban e no seu resumo para o estado correspondente. Manter o valor canônico `verified`; não renomear enums, banco ou outros menus por inferência.
- Fazer as cinco colunas dividirem igualmente a largura disponível, crescendo/reduzindo quando a janela ou a sidebar mudarem. Remover a largura fixa `w-60` como único dimensionamento.
- Em janela estreita, preservar largura mínima legível e oferecer rolagem horizontal local do quadro, sem cortar cards ou alterar a ordem. Evitar empilhar colunas de modo a perder a leitura esquerda→direita. Títulos longos quebram linha sem ultrapassar o card.
- **Aceite:** janela maximizada, restaurada e redimensionada; sidebar expandida/recolhida; temas claro/escuro; cinco colunas usam o espaço disponível quando couberem e têm rolagem acessível quando não couberem.

### 4.2 Resumo ao clicar; Histórico somente por Saber mais

- Clicar no card abre diálogo de resumo sobre o Kanban, sem navegar imediatamente. Reutilizar o padrão de diálogo existente, com X, fechamento por clique fora e Escape; devolver foco ao card ao fechar quando ele ainda existir.
- O quadro atual representa **etapas/rotinas da execução mais recente de cada processo**, e não um único card por processo. Preservar essa granularidade e as rotinas avulsas atuais. Identificar o resumo pelo ID da execução + identificador/posição estável da etapa.
- Resumo de consulta, sem formulário editável: nome do processo/rotina, etapa e posição, situação atual, estação, pessoa solicitante, horários disponíveis e motivo de espera/falha/não execução quando conhecido. Mostrar informação real; ausência não vira data, usuário ou causa inventada. Não despejar contexto técnico bruto ou segredos.
- Botão **Saber mais** navega a **Processo › Histórico**, abrindo a execução exata do card. Fechar por X, clique fora ou Escape mantém a rota, filtro e posição do Kanban.
- Enquanto aberto, o resumo acompanha os dados atuais da **mesma execução/etapa**. Se uma execução mais nova substituir os cards do processo no quadro, não trocar silenciosamente o resumo para ela; manter o original identificado e consultá-lo pelo ID quando necessário. Se ficar indisponível, indicar isso e permitir fechar.
- **Aceite:** clique e teclado abrem resumo correto; somente Saber mais navega; todos os fechamentos mantêm Kanban/filtro; card em atualização não fecha o diálogo nem muda sua identidade; nenhuma execução ou alteração de status é disparada por abrir o resumo.

### 4.3 Atualização do servidor e de outras pessoas/estações

- Cards, contadores e resumo aberto devem refletir mudanças confirmadas pelo Core sem F5, troca de página ou interação do observador. O movimento entre colunas representa estado real, sem drag-and-drop nem avanço manual.
- Reutilizar o store compartilhado (`desktop/src/state.tsx`), feed `/api/v1/changes` e polling de recuperação existentes. Hoje o store já faz leituras periódicas e reage a mudanças; conferir que início, avanço, revisão, falha, cancelamento e conclusão das execuções emitem/consomem os eventos pertinentes. Não adicionar WebSocket ou segundo loop global sem necessidade comprovada.
- A atualização cobre execuções visíveis ao usuário nessa equipe/servidor, mesmo iniciadas por outra pessoa ou estação; não filtrar implicitamente pelo solicitante atual. Preservar autorização no Core.
- Manter o mapeamento canônico: etapa ainda pendente/na fila/em revisão → Aguardando; preparação/execução → Em andamento; resultado `verified` → Conferida; falhas/incertezas/demais situações que exigem atenção → Atenção; etapa que não chegou a executar ao terminar a execução → Não executada. Não forçar toda execução a passar por todas as colunas.
- Identidade estável evita cards duplicados ou movimentação da etapa errada. Respostas antigas não podem sobrescrever novas. Eventos rápidos podem aparecer já no estado mais recente; não fabricar estados intermediários apenas para animar o quadro.
- Meta de aceite em ambiente saudável: alteração confirmada no Core aparece no quadro e resumo em até **5 segundos**, com a janela visível e feed operacional. Medir tempo de detecção e atualização; documentar separadamente o limite do polling de recuperação quando o feed falhar. Não prometer latência instantânea ou garantia de rede.
- Ao voltar de janela oculta ou recuperar conexão, reler o estado atual. Durante indisponibilidade, mostrar que os dados podem estar desatualizados e o diagnóstico; não zerar contadores, remover cards ou declarar conclusão artificialmente. Cancelar assinaturas/leitura de detalhe ao fechar/sair.
- Revisar a abrangência da fonte: a lista geral de execuções pode ser limitada. Não declarar “todos os processos” se o Kanban omitir silenciosamente a execução mais recente de processos fora dessa janela. Se necessário, prover consulta delimitada de última execução por processo para o quadro, sem baixar todo o histórico e sem aumentar um limite arbitrariamente.
- **Aceite:** dois clientes/sessões de teste no mesmo Core, um observando o Kanban e outro iniciando/avançando execução sintética; conferir cards, contadores, pessoa/estação e resumo aberto. Cobrir sucesso, atenção, cancelamento com etapas não executadas e revisão, conforme os caminhos válidos. Cobrir queda/retorno do feed, perda de conexão, retorno de janela oculta, nova execução do mesmo processo e histórico maior que o limite da lista geral. Diferenciar clientes simulados de prova em duas máquinas; VPN continua fora do escopo.

## 5. Sequência, write-set e evidências

1. Ler instruções, estado e evidências atuais; registrar HEAD/dirty files e dependências, fixar versão de InstallRS e iniciar os quatro itens sem aguardar novos pontos. Defaults técnicos deste documento orientam a execução; não são pendências de aprovação.
2. Implementar campo de último sucesso/contrato e lista paginada/expansível; verificar item 1.
3. Integrar InstallRS com o mecanismo de instalação existente e contrato de intenção; verificar item 2 em incrementos pequenos, sem migração ampla do app.
4. Implementar proteção da própria conta e Kanban (itens 3 e 4), com testes localizados e prova de atualização entre clientes.
5. Integrar os quatro itens num candidato de laboratório, validar instalação/update/rollback em cópias e reconciliar documentos dos comportamentos entregues.
6. Executar a entrega autorizada abaixo até verificar a instalação real e a documentação final, preservando registros históricos.

### Entrega autorizada após testes aprovados

1. Determinar a próxima versão Beta disponível pelo estado real e sincronizar os manifests/lockfiles pertinentes antes do commit e da build final. Não presumir beta.31 nem aumentar versões de componentes não alterados sem necessidade.
2. Fazer commit somente das mudanças revisadas desta WO e dependências necessárias identificadas. Integrar à `main`, resolver conflitos preservando trabalho alheio e repetir os checks afetados. Se já estiver em main, não criar merge artificial. Registrar SHA da fonte integrada.
3. Fazer push normal para `origin/main` após conferir que o remote corresponde a `https://github.com/correnth-ai/redrise_v2.git`; sem force-push, reset destrutivo ou alterações de proteção. Se o remoto avançou, integrar com cuidado e revalidar antes de enviar. Confirmar o SHA remoto.
4. Gerar instalador e artefatos finais de update rastreáveis ao commit integrado. Executar gates de integridade, instalação e update/rollback em laboratório; artefato que difere do candidato testado exige revalidar os checks afetados. Registrar versão, tamanho e SHA256.
5. Preparar o canal local de atualização e assinatura exigida pelo mecanismo vigente, mantendo chaves no cofre e fora de logs. Preservar backup recuperável de dados/configuração antes de migrações. Não enviar instalador para MediaFire ou outro serviço público.
6. Atualizar o app instalado pelo mecanismo de update, em janela segura de interação. Não encerrar automações ou trabalho do usuário à força. Verificar o app reaberto: versão efetiva, login, papel servidor/estação, preservação de dados e os quatro itens aplicáveis. Falta de acesso/sessão necessária é bloqueio concreto a registrar, não motivo para declarar update concluído.
7. Atualizar documentação canônica afetada, `AGENTS.md`, `delivery/status.json`, regras do app, contratos/UI/instalação pertinentes e evidências/checkpoint. Distinguir build, instalação real e distribuição pública; versão oficial Beta deste canal local não implica publicação pública nem homologação VPN/macOS.
8. Fazer commit e push complementar dos registros finais de update/documentação, se surgirem após o commit da build. Preservar a relação entre SHA da build, hash do instalador e SHA documental. Confirmar consistência local/remota e reportar quaisquer arquivos não relacionados preservados.

- **Write-set atual:** somente este documento.
- **Write-set de entrega autorizado para o engenheiro:** manifests/lockfiles de versão realmente afetados, scripts existentes de build/update quando necessário, `AGENTS.md`, `delivery/status.json`, documentação canônica pertinente e evidências/checkpoint desta WO. Artefatos, dados e segredos não entram no Git por inferência.
- **Write-set complementar dos itens 3/4:** `desktop/src/features/{configuracoes,fluxos}.tsx`, `desktop/src/data/status.ts`, `desktop/src/state.tsx`, contratos de dados e testes associados; `core/redrise_core/{service,api}.py` somente para proteção/autorização, abrangência da consulta e eventos necessários. Reutilizar componentes existentes de diálogo; reconciliar `docs/APP-RULES.md` e `docs/ui/LIVE-TABLES.md` com o comportamento entregue.
- **Write-set de construção proposto:** `desktop/src/features/processos.tsx`, `desktop/src/components/data-table.tsx`, `desktop/src/lib/table-state.ts`, `desktop/src/data/{types,source,demo}.ts`, `core/redrise_core/service.py` e API se contrato exigir, testes de UI/Core; `installer/`, scripts atuais de packaging e provas de instalação/update afetados; `desktop/src/features/auth.tsx`, integração Tauri de setup/configuração e testes relacionados; documentação/contratos/avisos de licença afetados. Delimitar arquivos exatos após leitura das instruções locais vigentes.
- **Verificações:** `node scripts/validate-base.mjs`; scripts efetivos de typecheck/testes em `desktop/package.json`; testes Core em PostgreSQL isolado; checks Rust do instalador e `proofs/installer/p10-installer-checks.ps1` adaptados ao contrato real. Registrar comandos e resultados na execução; validação documental não prova comportamento do app.
- **Artefatos futuros:** `delivery/evidence/PROCESS-LIST-INSTALLER-20261110/` e `delivery/checkpoints/PROCESS-LIST-INSTALLER-20261110.md`, dados sintéticos, hashes do candidato e relação com commit. Antes da execução registrar hash da evidência predecessora `delivery/evidence/ACCOUNT-ERASURE-20261109/evidence.json`.
- **Recuperação:** manter versão anterior e backups das bases sintéticas; preservar mudanças de outros autores; nenhuma exclusão de dados reais para testar. Não repetir escrita de resultado incerto.
- **Fora de escopo:** macOS, VPN, hospedagem/download público/MediaFire, identidade externa, mudança dos papéis de usuários, reconversão de instalação existente, revisão ampla de automações ou WOs anteriores.
- **Parada atual:** planejamento encerrado, próximo passo é executar pelo prompt. Na construção, incompatibilidade material de InstallRS exige diagnóstico, não troca silenciosa de tecnologia; continuar frentes independentes possíveis. Revisão de integração do instalador antes de aceitar candidato; revisor ainda não designado. Não ultrapassar a fronteira de liberação definida acima.

### Gate de conclusão da entrega

- Itens 1–4 implementados com respectivos aceites demonstrados; falhas e provas não executadas explicitadas, sem declarar sucesso parcial como total.
- InstallRS fixado, licenças registradas e instalador Windows rastreável ao commit integrado e enviado; registrar versão real e SHA256, sem presumir beta.31.
- Instalação servidor/estação, preservação de configuração e compatibilidade de update/rollback provadas em laboratório. Testes nativos e simulados identificados separadamente.
- Testes de dados históricos, permissões, Kanban entre clientes e layouts realizados; tempo de atualização medido.
- Commit integrado e push confirmados; canal local atualizado; update da instalação real concluído e verificado; documentação/evidências reconciliadas e enviadas. Versão instalada só avança com evidência e publicação pública permanece adiada.
- Relatório final com arquivos alterados, comandos/resultados, commits local/remoto, versão efetivamente instalada, caminho/hash do instalador e limitações. Não encerrar como entrega completa apenas porque o laboratório passou. Distribuição pública, VPN e macOS permanecem fora do escopo.

## Registro de execução (11/11/2026)

- Itens 1–4 implementados e provados (laboratório nativo, Core e UI); 0.1.0-beta.31, instalador `52bcd0f1…b615`, fonte `2bb2b02`; `main` local integrada; canal local assinado; app real atualizado pelo update do app (Core 0.3.10, papel mantido).
- Push: `9cef3cb..f836683` em `origin/main` (11/11/2026, SHA remoto conferido), seguido do commit documental.
- Instalação real conferida com login em 11/11/2026 (versão, papel servidor, dados, itens 1, 3 e 4); ver checkpoint.
- Pendente: revisão independente do instalador. A prova nativa do Kanban no caminho de revisão, servidor perdido e de volta e histórico além da lista geral passou em 11/11/2026 (`accept-wo-20261111-185040.json`).
- Checkpoint: [PROCESS-LIST-INSTALLER-20261110](../checkpoints/PROCESS-LIST-INSTALLER-20261110.md); evidência: `delivery/evidence/PROCESS-LIST-INSTALLER-20261110/evidence.json`.

## 6. Prompt de execução para o agente engenheiro

```text
Execute a Work Order D:\Correnth\products\redrise-v2\repos\app\delivery\work-orders\PROCESS-LIST-INSTALLER-20261110.md.

Root exclusiva: D:\Correnth\products\redrise-v2\repos\app.
Leia a WO integralmente, os AGENTS.md aplicáveis e as fontes canônicas pertinentes. Confirme branch, HEAD, alterações locais, estado atual e evidências; preserve trabalho existente e não reinicie WOs concluídas.

Esta mensagem autoriza implementar os quatro itens, testar, gerar o candidato e realizar provas em laboratório com dados sintéticos; após os testes aprovados, fazer commit, integrar à main, fazer push ao remote autorizado, gerar a nova versão Beta e concluir o update da instalação real e a documentação. Não peça novamente autorização para essas operações já aprovadas. Siga KISS e os defaults documentados. InstallRS está escolhido e aprovado: fixe a versão, integre e valide; não reabra comparação de tecnologias nem substitua silenciosamente.

Entregue: processos paginados e expansíveis com último sucesso real; assistente Windows servidor/estação; proteção da própria conta contra desativação; Kanban responsivo com resumo, Saber mais e atualização automática entre clientes. Preserve contratos, permissões, histórico, dados e garantias de instalação/update/rollback.

Use as skills aplicáveis conforme o router e registre evidências reais. Prove cada item com os testes e cenários da WO, inclusive UI nativa e instalação em laboratório. Simulação não comprova instalação real nem homologação LAN/VPN. Não altere dados reais para testar.

Após validar os itens, siga a sequência de entrega da seção 5:
1. Defina a próxima versão Beta disponível e sincronize manifests/lockfiles antes do commit/build.
2. Faça commit, integre à main, revalide mudanças de integração e faça push normal para origin/main, conferindo remote e SHA. Preserve alterações alheias; não use force-push.
3. Gere os artefatos finais a partir do commit integrado; valide integridade, instalação, update e rollback em laboratório. Registre hashes.
4. Atualize o canal local com os artefatos e assinatura exigidos, preservando backup recuperável e segredos no cofre.
5. Faça o update da instalação real pelo mecanismo do app, sem interromper trabalho ou automações em curso. Verifique versão, login, dados, papel da instalação e funcionalidades após reabrir.
6. Reconcilie toda a documentação afetada e evidências/checkpoint. Faça commit/push documental complementar quando necessário e confirme consistência com a versão instalada.

Continue até o gate de conclusão da entrega, não somente até a build ou os testes. Resolva decisões rotineiras sem pedir confirmação; diante de bloqueio material, registre evidência e conclua o trabalho independente possível. Não fabrique testes ou declare conclusão com aceites obrigatórios pendentes. Não presuma o número da próxima versão.

MediaFire e distribuição pública permanecem adiados. VPN e macOS estão fora do escopo. Push do código para o repositório autorizado está incluído; publicação pública de instalador não está.

Ao finalizar, informe itens entregues, testes/provas, commits e confirmação do push, versão efetivamente instalada, caminho e SHA256 do instalador, documentação atualizada e pendências. Não confunda candidato de laboratório com versão oficial instalada.
```

## 7. Rastreabilidade do planejamento

- Classe: normativa/planejamento, com leitura pontual de código e sessão referenciada. Fontes canônicas diretas; nenhum grafo/rebuild necessário para este plano delimitado.
- Skill `scope-planning` já lida e resolvida nesta conversa: SHA256 `fd7b13af53a7853d7cbd43ac9f72e801d602c7fb4e592981ac4842e4ded58bfa`. Seleção reconfirmada pelo seletor do router nesta rodada; reavaliar skills antes de instalar dependências/implementar UI nativa.
- Memória consultada: `workspace=correnth`, `project=redrise-v2`; indisponível (`MEMORY_UNAVAILABLE`). Continuidade pelas fontes e este documento; sem captura automática.
- O plano não altera o estado canônico para “implementado”, “publicado” ou “homologado”. Nenhum código, instalador ou instalação real foi modificado.
