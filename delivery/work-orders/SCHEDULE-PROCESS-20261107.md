# Work Order — agendar um processo

- **ID:** SCHEDULE-PROCESS-20261107.
- **Data:** 07/11/2026. **Estado atual:** concluída em 08/11/2026: candidato 0.1.0-beta.28 aceito no laboratório (gate, prova prática, rollback numa cópia), assinado no canal local e instalado na instalação real por ordem do usuário ([incremento 1](../evidence/SCHEDULE-PROCESS-20261107/increment-1.json), [incremento 2](../evidence/SCHEDULE-PROCESS-20261107/increment-2.json)); sem publicação nem commit. **Estado na implementação (histórico):** em implementação desde 07/11/2026, por ordem do usuário ("devemos fazê-los e depois iniciar a S5"), depois de incorporar a devolutiva sobre esta proposta (seção "Decisões de 07/11").
- **Origem:** S5 da [STABILIZATION-REAL-UI-20261107](STABILIZATION-REAL-UI-20261107.md). Escolha do usuário em 07/11 entre quatro necessidades apresentadas (agendar processo, ler valor de planilha, relatório numa pasta da equipe, conferir texto no site): **agendar um processo**.
- **Produto / repositório:** `product:redrise-v2` / `repo:redrise-v2`, `D:/Correnth/products/redrise-v2/repos/app`, `main`.
- **Base:** commit `991ebc5` (STABILIZATION concluída; Core 0.3.6; candidato 0.1.0-beta.27 aceito só no laboratório).
- **Autorização:** implementar e testar no código. Candidato, instalação no laboratório (com o computador livre), instalação real, assinatura, publicação e commit seguem ordens próprias.

## Microetapa

Executar um processo já cadastrado automaticamente, num horário e em dias da semana escolhidos, numa estação escolhida, sem ninguém clicar em "Executar". Cada ocorrência que inicia é uma execução comum: mesmo contexto entre etapas, mesmas revisões, relatório, cancelamento, histórico e indicadores.

**KISS:** um horário por agendamento, dias da semana marcados. Um laço no Core, uma ocorrência identificável e a execução existente. Sem cron, intervalos, feriados, exceções de calendário, várias estações, nova tentativa automática, agendamento de rotina avulsa, novo serviço ou framework de agendamento.

## Decisões de 07/11 (devolutiva e usuário)

1. **Ocorrência e execução gravadas juntas.** Na mesma transação e conexão: travar o agendamento (`FOR UPDATE SKIP LOCKED`), inserir a ocorrência, criar a execução, gravar o vínculo nos dois sentidos (`schedule_runs.execution_id` e `executions.schedule_id`) e avançar a próxima ocorrência. Uma queda antes do commit não deixa nada; depois do commit deixa tudo. O `request_id` continua impedindo uma segunda execução da mesma ocorrência.
2. **Criar, editar ou retomar calcula a próxima ocorrência futura.** Nunca executa retroativamente o que estava pausado ou o horário que acabou de ser alterado. Recuperar um horário perdido vale só quando o agendamento ficou habilitado e o Core estava parado.
3. **Identidade da ocorrência = data e hora local no fuso do agendamento** (`AAAA-MM-DDTHH:MM`). Ela é a chave única no banco (`schedule_id + slot_local`) e a base do `request_id` (`agenda-<id>-<AAAAMMDDHHMM>`): as duas sempre coincidem. Numa hora repetida, executa uma vez; numa hora que não existe, aquele dia é pulado. **O fuso é gravado no agendamento e fica fixo**: não acompanha mudanças do servidor; só muda quando um administrador edita o agendamento (vale o fuso do computador de quem editou).
4. **Permissão relida no disparo.** O laço não passa pela API: relê o dono e exige pessoa ativa e administradora. Se o dono foi desativado ou rebaixado a operador, a ocorrência é pulada (`owner_not_allowed`), o agendamento fica pausado e os administradores ativos recebem aviso. Um administrador que editar ou retomar o agendamento passa a ser o dono.
5. **Estação pronta no horário, mas ocupada ou desconectada antes de iniciar:** a ocorrência espera no máximo 15 min a partir do horário; depois **expira**. O passo é cancelado sem efeito, a ocorrência fica `expired` e o dono recebe "Não iniciado por desconexão." (decisão do usuário).
6. **Só administradores criam, editam, pausam, retomam e excluem.** Operadores veem os agendamentos e as ocorrências. **Tolerância de 15 min** para horário perdido e para início.

## Comportamento

| Situação no horário | Resultado |
|---|---|
| Dono ativo e administrador; estação conectada (últimos 45 s), compatível e com sessão pronta; nenhuma ocorrência anterior em andamento | Cria a execução em nome do dono, marcada "Agendada"; ocorrência `started` com o vínculo. |
| Estação desconectada, revogada, incompatível ou com sessão indisponível | Não enfileira. Ocorrência `skipped` com o motivo; aviso ao dono. Sem fila e sem nova tentativa. |
| Execução anterior do mesmo agendamento em andamento ou aguardando revisão | `skipped` (`previous_still_running`); aviso ao dono. |
| Iniciou a execução, mas a etapa 1 não começou em 15 min (estação ocupada ou desconectada) | `expired`: etapa cancelada sem efeito; aviso "Não iniciado por desconexão." |
| Core parado no horário, agendamento habilitado | Ao voltar, até 15 min de atraso: executa uma vez; mais que isso: `missed` com aviso e nenhuma execução. Nunca recupera várias ocorrências seguidas: a próxima passa a ser a primeira futura. |
| Agendamento pausado | Não executa nem acumula. Retomar calcula a próxima futura. |
| Processo arquivado ou sem etapa 1 | `skipped`, agendamento pausado, aviso ao dono. |
| Dono desativado ou rebaixado | `skipped` (`owner_not_allowed`), agendamento pausado, aviso aos administradores ativos. |

## Dados e API (Core)

- Migração `010_schedules.sql`: `schedules` (processo, estação, dias da semana em máscara, hora, minuto, fuso, habilitado, motivo da pausa, dono, próxima ocorrência local e seu instante) e `schedule_runs` (ocorrência local, instante, estado `started|skipped|missed|expired`, motivo, execução, diagnóstico; única por agendamento + ocorrência local). `executions.schedule_id` e notificação do tipo `schedule`. Mudanças entram no feed com o domínio `schedules`.
- Laço no host do Core a cada 30 s (`Core.schedule_tick`), dentro do processo único do Core; os testes chamam o mesmo método com relógio controlado.
- Rotas: `GET /api/v1/schedules`, `POST /api/v1/schedules`, `POST /api/v1/schedules/preview`, `PATCH /api/v1/schedules/{id}`, `DELETE /api/v1/schedules/{id}`, `GET /api/v1/schedules/{id}/runs`. Diagnósticos `redrise.diagnostic/1`; textos do backend em inglês ASCII, pt-BR só na máscara e na interface.

## Interface

- Processo › Ação, linha do processo: "Agendar…" (só administradores) abre um diálogo com dias da semana, horário e estação. Mostra a próxima ocorrência calculada pelo Core antes de salvar.
- Lista "Agendamentos" na mesma página: processo, dias e horário, estação, próxima ocorrência, última ocorrência (iniciada, pulada com motivo, perdida, expirada) e Pausar/Retomar/Excluir com `useAction`.
- Histórico: execuções agendadas com a marca "Agendada". Ocorrências que não iniciaram aparecem só na lista e no sino.

## Aceite

1. **Contrato (Core, PostgreSQL isolado, relógio controlado, Runner simulado):**
   - Uma ocorrência vencida cria exatamente uma execução, com o vínculo nos dois sentidos.
   - Repetir o laço ou reiniciar não duplica.
   - A falha ao criar a execução não deixa ocorrência solta.
   - Estação indisponível e execução anterior em andamento dão `skipped` com aviso.
   - A etapa 1 não iniciada em 15 min dá `expired` com aviso.
   - Core parado: 10 min executa; 2 h dá `missed` e a próxima é futura.
   - Pausar, editar e retomar nunca executam retroativamente.
   - Hora repetida executa uma vez e hora inexistente pula, num fuso com horário de verão.
   - Dono rebaixado ou desativado: pausa e aviso.
   - Permissões: administrador, operador e sem token.
2. **Componente (UI):** o diálogo mostra a próxima ocorrência vinda do Core; a lista mostra o estado real, inclusive falha de leitura com diagnóstico, sem zero inventado; botões com estado ocupado; marca "Agendada" no Histórico.
3. **Prática (candidato instalado no laboratório, computador livre, equipe sintética):**
   - O processo de teste com a Calculadora, agendado para 2 min adiante, começa sem clique e aparece no Histórico como agendado e na Empresa.
   - Com a estação indisponível, a ocorrência é pulada e o aviso chega ao sino.
4. **Gate e recuperação:** `verify-candidate.ps1`, contagens antes e depois da atualização e rollback numa cópia, como na S4. A migração 010 faz o rollback para versões anteriores depender do backup feito antes da migração; documentar. **Resultado (08/11):** o Core 0.3.5 abre a base migrada com as mesmas contagens e ignora os agendamentos; voltar o esquema exige o backup anterior à migração ([evidência](../evidence/SCHEDULE-PROCESS-20261107/increment-2.json)).

## Fora do escopo

Intervalos, cron, feriados, várias estações por agendamento, nova tentativa automática, agendar rotina avulsa, disparo por e-mail ou arquivo, execução na instalação real sem ordem explícita, publicação. Os itens adiados da STABILIZATION continuam adiados.

## Write-set

- Core: `core/redrise_core/{service,api,host}.py` e `core/redrise_core/migrations/010_schedules.sql`.
- Contratos e máscara: `contracts/errors.json`, `contracts/modules.json`, `desktop/locale/pt-BR.json`.
- Interface: `desktop/src/features/processos.tsx`, `desktop/src/features/fluxos.tsx` (marca), `desktop/src/components/notifications-bell.tsx`, um componente de agendamento, `desktop/src/data/{source,types,demo}.ts`.
- Testes e prova: `tests/core/test_schedules.py`, `desktop/tests/schedules.test.tsx`, `proofs/schedules/`.
- Documentos: `docs/APP-RULES.md`, `docs/ui/LIVE-TABLES.md`, `docs/decisions/P05-contracts-lan.md`, evidência e checkpoint próprios.

## Riscos

- O computador servidor precisa estar ligado e com o RedRise aberto no horário: o agendamento não acorda o Windows nem inicia o app.
- A estação precisa de sessão do Windows desbloqueada; com a tela bloqueada, a ocorrência é pulada (comportamento atual do Runner).
- O fuso fixo não acompanha uma mudança de fuso do servidor até que um administrador edite o agendamento.
