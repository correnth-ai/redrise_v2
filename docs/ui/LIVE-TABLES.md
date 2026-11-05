# Tabelas em tempo real: inventário e regras

Work order [UI-ENGINE-BOAS-VINDAS-20261103](../../delivery/work-orders/UI-ENGINE-BOAS-VINDAS-20261103.md). Levantado no código em 05/11/2026, antes de ligar a atualização.

## Como funciona

1. **Aviso:** o PostgreSQL avisa o Core a cada mudança confirmada, por domínio (migração 009, `NOTIFY`). Rollback não avisa.
2. **Espera:** o desktop pergunta `POST /api/v1/changes` e fica aguardando até 20 s. A resposta só diz o que mudou, nunca os dados.
3. **Leitura:** com aviso, a tela lê de novo pelos endpoints de sempre, com as mesmas permissões. Vários avisos seguidos viram uma leitura (`SETTLE_MS`).
4. **Rede de segurança:** a leitura periódica continua (3 s com execução em andamento, 30 s parado). Se o aviso falhar, a tela segue certa, só mais lenta. Janela oculta não inicia novas perguntas nem leituras; o que já estava a caminho termina.

## Inventário

| Tela | Fonte | Domínios que atualizam | Regra |
|---|---|---|---|
| Rotina › Lista | `routines`, `processes` | routines, processes | Mantém busca, aba, ordenação, página e seleção. Linha excluída sai da seleção. |
| Processo › Ação, processos | `processes`, `routines` | processes, routines, executions | Composição aberta não é sobrescrita: trabalha na própria cópia até salvar. |
| Processo › Ação, contagens e execuções recentes | `executions`, `reviews` | executions, jobs, reviews | Mesmas regras da tabela. |
| Processo › Histórico | `executions` | executions, jobs, reviews | Detalhe aberto segue a mesma execução. |
| Processo › Kanban | `executions` | executions, jobs, reviews | Somente leitura. |
| Marcado para mim | `reviews`, `step-changes` | reviews, step_changes, executions | Pedido aberto muda de estado na tela; o Core decide quem aprova. |
| Sino | `notifications` | notifications | Contagem e lista. |
| Rotina › Atividade, linha do tempo e feed | `executions` | executions, jobs | Derivados da mesma execução. |
| Rotina › Atividade, execuções técnicas | `jobs` | jobs | Lê de novo com o aviso e mantém a leitura periódica própria. |
| Configuração › Equipe | `users` | users | Lê de novo com o aviso; só administrador lê. |
| Configuração › Estação | `stations` | stations | Fica offline pelo tempo sem sinal, que não gera aviso: quem mostra é a leitura periódica de 30 s. |
| Configuração › Aplicativo, espaço usado | `storage` | nenhum | Medida cara: lida ao abrir. |
| Empresa, atividades | dados demonstrativos | nenhum | Não é dado real: não atualiza. |
| Nova Rotina, checks | `jobs/{id}` | nenhum | Consulta o próprio job a cada 800 ms enquanto ele não termina. |

## O que não gera aviso

- Heartbeat sem mudança visível e renovação de lease: escrevem a cada poucos segundos.
- Checks de preparação: quem precisa deles é a tela que criou o job.
- Estação passar a offline: é ausência de escrita.
