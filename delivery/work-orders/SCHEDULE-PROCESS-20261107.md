# Work Order — agendar um processo

- **ID:** SCHEDULE-PROCESS-20261107.
- **Data:** 07/11/2026. **Estado:** proposta documentada; implementação não iniciada.
- **Origem:** S5 da [STABILIZATION-REAL-UI-20261107](STABILIZATION-REAL-UI-20261107.md). Escolha do usuário em 07/11 entre quatro necessidades apresentadas (agendar processo, ler valor de planilha, relatório numa pasta da equipe, conferir texto no site): **agendar um processo**.
- **Produto / repositório:** `product:redrise-v2` / `repo:redrise-v2`, `D:/Correnth/products/redrise-v2/repos/app`, `main`.
- **Base:** `f78d229` mais a árvore não commitada da STABILIZATION (Core 0.3.6, candidato 0.1.0-beta.27 aceito só no laboratório). Revalidar HEAD e árvore antes da engenharia.
- **Autorização atual:** criar este documento. Implementação, candidato, instalação e qualquer escrita externa exigem ordem própria.

## Microetapa

Executar um processo já cadastrado automaticamente, num horário e em dias da semana escolhidos, numa estação escolhida, sem ninguém clicar em "Executar". Cada ocorrência é uma execução comum: mesmo contexto entre etapas, mesmas revisões, relatório, cancelamento, histórico e indicadores.

**KISS:** um horário por agendamento, dias da semana marcados, hora local do computador servidor. Sem expressões cron, intervalos ("a cada N minutos"), feriados, exceções de calendário, várias estações, nova tentativa automática ou agendamento de rotina avulsa.

## Reaproveitamento

- **Execução:** `Core.create_execution(actor, request_id, station_id, process_id, …)` já é idempotente por `request_id`. Cada ocorrência usa `request_id = "agenda-<id>-<AAAAMMDDHHMM local>"`: reiniciar o Core ou checar duas vezes nunca cria duas execuções da mesma ocorrência.
- **Fila e Runner:** sem mudança. A compatibilidade da estação é conferida antes de enfileirar (P05-D8); o Runner só reivindica com a sessão do Windows pronta (P05-D9).
- **Avisos:** notificações existentes (sino) para o dono do agendamento quando uma ocorrência é pulada ou termina sem verificação.
- **Telas:** Processo › Ação (ação na linha do processo) e Histórico/Empresa como hoje; feed de mudanças com um domínio novo `schedules`.

## Comportamento

| Situação no horário | Resultado |
|---|---|
| Estação conectada, compatível e com sessão pronta | Cria a execução (pedida pelo dono do agendamento, marcada "agendada") e grava a ocorrência como `started` com o id da execução. |
| Estação desconectada, revogada, incompatível ou com sessão indisponível | Não enfileira. Grava a ocorrência como `skipped` com o diagnóstico e avisa o dono. Sem fila esperando e sem nova tentativa. |
| Uma execução anterior do mesmo agendamento ainda em andamento ou aguardando revisão | Pula (`skipped`, motivo `previous_still_running`): nunca duas ocorrências do mesmo agendamento ao mesmo tempo. |
| Core parado no horário | Ao voltar, uma ocorrência perdida há no máximo 15 min ainda executa; mais antiga fica `missed`, sem executar. Nunca recupera várias ocorrências seguidas. |
| Agendamento pausado, processo arquivado ou sem etapa 1 | Não executa; os dois últimos casos pausam o agendamento e avisam o dono. |

Hora local do servidor, gravada com fuso (`America/Sao_Paulo` hoje). Mudança de fuso ou horário de verão: a próxima ocorrência é recalculada a partir do relógio local; uma hora inexistente pula e uma hora repetida executa uma vez (mesmo `request_id`).

## Dados e API (Core)

- Migração `010_schedules.sql`: `schedules` (id, process_id, station_id, hour, minute, weekdays smallint bitmask, timezone, enabled, created_by, created_at, updated_at) e `schedule_runs` (schedule_id, slot timestamptz, state `started|skipped|missed`, execution_id, diagnostic, created_at; único por schedule_id + slot).
- Laço no host do Core a cada 30 s, num único processo (o Core é único por equipe): procura ocorrências vencidas com `FOR UPDATE SKIP LOCKED` e cria as execuções como acima. Usa as vagas e o teto de conexões de S3 como qualquer pedido.
- Rotas: `GET/POST /api/v1/schedules`, `PATCH /api/v1/schedules/{id}` (pausar, horário, dias, estação), `DELETE /api/v1/schedules/{id}`, `GET /api/v1/schedules/{id}/runs` (últimas 50). Erros com diagnóstico `redrise.diagnostic/1`; textos em inglês ASCII no backend e pt-BR só na máscara.
- **Permissões (padrão proposto, confirmar na engenharia):** administrador cria, altera e apaga qualquer agendamento; operador vê os agendamentos e as ocorrências. A execução fica em nome de quem criou o agendamento; desativar essa pessoa pausa os agendamentos dela.

## Interface

- Processo › Ação, linha do processo: "Agendar…" abre um diálogo com dias da semana, horário, estação (só as compatíveis) e a próxima ocorrência calculada pelo Core antes de salvar.
- Lista "Agendamentos" na mesma página: processo, dias e horário, estação, próxima ocorrência, última ocorrência (iniciada, pulada com motivo, perdida) e ações Pausar/Retomar/Excluir com `useAction`.
- Histórico: execuções agendadas marcadas "Agendada"; ocorrências puladas aparecem só na lista de agendamentos e no sino, não como execução.

## Aceite

1. **Contrato (Core, PostgreSQL isolado, relógio controlado, Runner simulado):** a ocorrência vencida cria exatamente uma execução; verificar duas vezes e reiniciar o Core não duplicam; estação desconectada, incompatível ou com sessão indisponível gera `skipped` com diagnóstico e aviso, sem fila; execução anterior em andamento gera `skipped`; Core parado 10 min executa a perdida e parado 2 h gera `missed`; pausar, alterar e excluir; permissões administrador/operador e sem token; processo arquivado pausa.
2. **Componente (UI):** diálogo mostra a próxima ocorrência vinda do Core; lista mostra o estado real, inclusive falha de leitura com diagnóstico, sem zero inventado; botões com estado ocupado.
3. **Prática (candidato instalado no laboratório, computador livre, equipe sintética):** agendar o processo de teste com a Calculadora para 2 min adiante; a execução começa sem clique, aparece no Histórico como agendada e na Empresa; agendar com a estação bloqueada gera ocorrência pulada e aviso no sino; o executor é encerrado só pela prova.
4. Gate `verify-candidate.ps1`, contagens antes e depois da atualização e rollback numa cópia, como na S4 (a migração 010 torna o rollback para versões anteriores dependente do backup antes da migração; documentar).

## Fora do escopo

Intervalos, cron, feriados, várias estações por agendamento, nova tentativa automática, agendar rotina avulsa, disparo por e-mail ou arquivo, execução na instalação real sem ordem explícita, publicação. Itens adiados da STABILIZATION continuam adiados.

## Write-set proposto

`core/redrise_core/{service,api}.py`, `core/redrise_core/migrations/010_schedules.sql`, `core/redrise_core/host.py` (laço), `contracts/errors.json`, `contracts/modules.json`, `desktop/locale/pt-BR.json`, `desktop/src/features/processos.tsx` e um componente de agendamento, `desktop/src/data/{source,types,demo}.ts`, testes `tests/core/test_schedules.py` e `desktop/tests/schedules.test.tsx`, prova `proofs/schedules/`, `docs/APP-RULES.md`, `docs/ui/LIVE-TABLES.md`, evidência e checkpoint próprios.

## Riscos e pontos a confirmar

- O computador servidor precisa estar ligado e com o RedRise aberto no horário; o agendamento não acorda o Windows nem inicia o app.
- A estação precisa de sessão do Windows desbloqueada; com a tela bloqueada a ocorrência é pulada (comportamento atual do Runner).
- Permissão de operador para agendar e o limite de 15 min para ocorrência perdida são propostas; confirmar com o usuário antes da implementação.
