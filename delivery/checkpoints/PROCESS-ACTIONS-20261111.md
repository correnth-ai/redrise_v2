# Checkpoint — PROCESS-ACTIONS-20261111

- **Data:** 12/11/2026. **WO:** [PROCESS-ACTIONS-20261111](../work-orders/PROCESS-ACTIONS-20261111.md). **Evidência:** [evidence.json](../evidence/PROCESS-ACTIONS-20261111/evidence.json), com o SHA-256 de cada arquivo da pasta; passo a passo do instalador em [installer-walkthrough.md](../evidence/PROCESS-ACTIONS-20261111/installer-walkthrough.md).
- **Item 1, ações:** Processo › Ação sem **Nova execução**. O Play da linha abre o diálogo de estação/parâmetros. Para administrador, todos os processos, inclusive Boas-vindas, têm seis ícones nesta ordem: Executar, Agendar, Integrar rotina avulsa, Substituir etapa 1, Excluir, Editar composição. Quando uma ação não vale, o ícone fica indisponível com o motivo. Operador vê só o Play. Core e UI deixaram de recusar Boas-vindas (`system_key`). O integrador, a substituição e o editor aceitam a etapa de bloco de notas. Em Agendamentos, Pausar, Retomar e Excluir viraram ícones; excluir pede confirmação. Em Configuração › Equipe, Desativar e Reativar são ícones e Revogar abre confirmação. Inventário em [ICON-ACTIONS](../../docs/ui/ICON-ACTIONS.md).
- **Item 2, exclusão:** a lixeira pergunta "Confirma exclusão do processo? As rotinas não serão excluídas." e mostra o nome. Excluir só habilita com **Confirmado** (sem diferenciar maiúsculas, aceitando espaços nas pontas); o envio é feito pelo formulário, com estado ocupado. O Core (`POST /api/v1/processes/{id}/archive`, administrador, palavra conferida também no contrato) faz numa só transação:
  - arquiva o processo e retira os vínculos (nenhuma rotina é arquivada);
  - desabilita os agendamentos (`process_deleted`) e cancela as trocas de etapa pendentes;
  - recusa com `PROCESS-BUSY` se houver execução em andamento ou aguardando revisão.

  Repetir o pedido responde `already` sem afetar outro processo. O histórico mantém id e nome e mostra "(excluído)". Um processo novo com o mesmo nome ganha outro id e não herda nada. Boas-vindas excluída não volta ao reiniciar (marcador arquivado).
- **Item 3:** Execuções recentes saiu de Processo › Ação; Histórico continua igual. A coluna Execução da lista mostra a última execução sob o selo.
- **Item 4.2, instalador:** a falha agora é registrada por fase e etapa (`before_swap`, `swap`, `after_swap`), com a versão realmente presente, o erro de recuperação separado, onde ficou a versão anterior e o que fazer. O assistente mostra o mesmo texto em pt-BR. A injeção de falha (`--test-fail-at`) só vale em raiz isolada. A prova nativa achou um defeito: o instalador não lia o próprio manifesto com BOM e dizia "versão ?". Foi corrigido em `6a6fbd1`, o pacote foi refeito e as provas rodaram de novo.
- **Item 4.3, Kanban:** quatro colunas, nesta ordem: No aguardo, Em andamento, Concluído, Conferido. Um dia por vez, começando em Hoje, com seletor de data e atalho Hoje. O quadro mostra "Execuções iniciadas em …". Há um card por processo, com a execução mais recente iniciada no dia, filtrada pelo dia antes de escolher (`GET /api/v1/kanban?day=AAAA-MM-DD`, no fuso do servidor). O card mostra só nome, estação e pessoa. Processos homônimos ficam em cards separados e processos excluídos continuam com o nome. Rotinas avulsas ficam fora do quadro.
- **Versões:** 0.1.0-beta.32, Core 0.3.11 (sem migração), Runner 0.3.11 e instalador 0.2.1 com InstallRS 0.1.1. O instalador `RedRise-Setup-0.1.0-beta.32.exe` tem SHA-256 `93601c73…1d64` e 311.083.974 bytes; o payload tem SHA-256 `03655794…cf78`.
- **Validações:**
  - Core 187/187, com `test_process_actions` (15 novos).
  - UI 117/117 e tsc limpo.
  - Contratos 17; validate-base 346.
  - Gate aprovado e P10 (pacote adulterado recusado, instalar, reinstalar, rollback, desinstalar).
  - Update `--quiet` de uma cópia da beta.31.
  - Prova prática nativa no laboratório: ações, exclusão com o cenário A/C de mesmo nome, Kanban do dia (1,67–1,80 s), layout claro/escuro/estreito, Boas-vindas, seis falhas do instalador em cópias, assistente servidor/cancelar/já configurado/estação/erro.
  - Rollback para a beta.31 numa cópia.

  Simulado (testes) e nativo (laboratório) estão separados na evidência.
- **Entrega:** commits `654e81c` (WO), `f871210` (feat) e `6a6fbd1` (fix e provas), integrados por fast-forward e enviados com push normal. `origin/main` = `6a6fbd1c…a86e`, conferido com `ls-remote`, seguido deste registro.
- **Canal e instalação real:**
  - Canal local assinado com a beta.32 em 12/11 às 08:55Z. A assinatura confere com a chave do app; o `latest.json` da beta.31 foi guardado.
  - Backup: cópia fria dos dados reais com o app parado (`RedRise-v2-dev/backups/real-data-before-beta32-20261112-0556`, 2.136 arquivos, 3,85 GB). A beta.31 ficou em `@redrise.previous`.
  - Update às 05:59, com o computador ocioso e sem execução, pelo instalador assinado com os argumentos do próprio update (`--quiet --relaunch`): 0.1.0-beta.32, papel mantido, dados não tocados.
  - O app reabriu no login. O Core responde 0.3.11 com a equipe inicializada e o executor está pronto, sem erro.
  - **Conferido com login (12/11; a pessoa entrou e pediu a conferência; só leitura e navegação pela UI Automation):**
    - 0.1.0-beta.32, conta Admin Lab (administrador).
    - Servidor da equipe com a estação servidor-lab-2, executor ativo e sessão do Windows disponível.
    - Dados iguais à referência anterior ao update: 3 processos, 6 rotinas, 4 execuções e 2 contas.
    - Os três processos, inclusive Boas-vindas, têm os seis ícones; não há Nova execução nem Execuções recentes; o agendamento tem os ícones.
    - O Kanban de hoje (12/11) mostra as quatro colunas vazias com a mensagem de dia sem execuções, sem herdar o Conferido de dias anteriores.
    - Nenhum ícone de ação foi usado na equipe real.
  - Antes do update, a instalação real tinha 3 processos, 6 rotinas, 4 execuções e 2 contas.
- **Pendente:**
  - Revisão independente do instalador e estação em segunda máquina física/LAN, adiadas pelo usuário.
- **Limpeza (seção 5):** inventário e remoção com `Remove-Item -LiteralPath`, um caminho por vez, dentro de `lab-test` e `stage`, sem junções nem processos em uso ([cleanup.json](../evidence/PROCESS-ACTIONS-20261111/cleanup.json)). Saíram as raízes do assistente, a cópia do rollback, as duas pastas P10 e o stage da beta.30: 3,03 GB calculados, e o C: livre passou de 36,24 para 39,08 GB. Ficaram a instalação real e sua `.previous`, o backup, `install-beta31` e `install-beta32` do laboratório, dados, ferramentas, o stage da beta.32, as releases, o canal e as evidências.
