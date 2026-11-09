# Checkpoint — agendar um processo

- 07/11/2026. Work order [SCHEDULE-PROCESS-20261107](../work-orders/SCHEDULE-PROCESS-20261107.md). Base `991ebc5`; nada commitado depois dela.
- Devolutiva incorporada na Work Order (seção "Decisões de 07/11") e decisão do usuário: estação pronta no horário, mas ocupada ou desconectada antes de iniciar, expira com "Não iniciado por desconexão."
- Ajustes documentais: AGENTS.md aponta o estado atual; a Work Order da estabilização ficou marcada como planejamento histórico.

## Incremento 1 — código (sem candidato)

- **Core 0.3.7:** migração 010 (`schedules`, `schedule_runs`, `executions.schedule_id`, aviso do tipo `schedule`), laço de 30 s no host, rotas `/api/v1/schedules`, código `SCHEDULE-NOT-STARTED`.
- **Regras:** ocorrência e execução gravadas juntas; criar/editar/retomar só no futuro; identidade pela hora local no fuso fixo do agendamento; dono relido no disparo; estação indisponível, execução anterior em andamento ou processo sem etapa 1 pulam com aviso; primeira etapa não iniciada em 15 min expira; servidor parado até 15 min executa uma vez, depois fica perdida.
- **Interface:** "Agendar" na linha do processo (administradores), lista "Agendamentos" em Processo › Ação, marca "Agendada" no Histórico, textos no sino.
- **Testes:** Core 150 testes sozinhos (OK na descoberta conjunta, 150 testes); UI 64 (6 novos); contratos 17; validate-base 346/368. Tela conferida no servidor de inspeção (prévia do Core, lista, disparo no horário com pulo e aviso).
- **Não feito:** candidato, gate e prova no app instalado (precisam do computador livre e de ordem); revisão independente.

## Incremento 2 — candidato, prova instalada, canal e instalação real (08/11)

- **Candidato 0.1.0-beta.28** (instalador `25a400e970a4e89ad3c5cec1832708ea03c848bf6693b526f09020d3649e33c3`, 3754 arquivos: a beta.27 mais a migração 010). Gate aprovado.
- **Laboratório:** contagens de base gravadas pela beta.27 antes da atualização; prova `accept_schedule.py` aprovada numa execução: migração com backup, agendamento pela tela que iniciou sozinho às 13:40 e terminou verificado, marca "Agendada" no Histórico, Empresa igual ao Core, pulo por estação indisponível com aviso no sino, permissões do operador. Rollback da beta.28 para a beta.25 numa cópia aprovado.
- **Canal local:** `latest.json` assinado para a beta.28 (antes beta.17); assinatura conferida com a chave do app.
- **Instalação real:** atualizada da beta.25 para a beta.28 por ordem do usuário; versão anterior guardada; backup antes da migração; Core respondeu 0.3.7. Ninguém entrou nem agendou na equipe real.
- Evidência: `delivery/evidence/SCHEDULE-PROCESS-20261107/increment-2.json` e `increment-2/`.

## Próxima ação segura

O usuário confere o agendamento na equipe real. Revisão independente opcional. Commit só por ordem; nada publicado.
