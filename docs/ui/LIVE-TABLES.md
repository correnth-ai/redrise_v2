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
| Processo › Ação, contagens | `executions/summary` (30 dias, contado no Core, como a Empresa), `processes`, `reviews` | executions, jobs, reviews | Lê de novo quando a loja lê as execuções; cada bloco abre o Histórico com o mesmo período e situação. Falha mostra o diagnóstico e "—". |
| Processo › Ação, agendamentos | `schedules` | schedules | Lê de novo a cada mudança anunciada e depois de cada ação; falha mostra o diagnóstico, nunca lista vazia. Próxima ocorrência sempre vinda do Core. |
| Processo › Ação, execuções recentes | `executions` (as 100 mais recentes) | executions, jobs, reviews | Mesmas regras da tabela; a lista é rotulada como recentes e não serve de total. |
| Processo › Histórico | `executions` | executions, jobs, reviews | Detalhe aberto segue a mesma execução. |
| Processo › Histórico com período (aberto por um indicador da Empresa) | `executions?days=30` | executions, jobs, reviews | Lê de novo quando a loja lê as execuções. Mostra o período e a quantidade; acima de 500 avisa que lista as mais recentes. |
| Processo › Kanban | `executions` | executions, jobs, reviews | Somente leitura. |
| Marcado para mim | `reviews`, `step-changes` | reviews, step_changes, executions | Pedido aberto muda de estado na tela; o Core decide quem aprova. |
| Sino | `notifications` | notifications | Contagem e lista. |
| Rotina › Atividade, linha do tempo e feed | `executions` | executions, jobs | Derivados da mesma execução. |
| Rotina › Atividade, execuções técnicas | `jobs` | jobs | Lê de novo com o aviso e mantém a leitura periódica própria. |
| Configuração › Equipe | `users` | users | Lê de novo com o aviso e depois de cada ação; só administrador lê. Linha excluída sai só depois da confirmação do Core; falha mantém a linha e mostra o diagnóstico. |
| Configuração › Estação | `stations` | stations | Lê de novo com o aviso e a cada 10 s enquanto visível (TEAM-ACCOUNTS-20261108): ficar offline é falta de sinal, que não gera aviso, então Online→Offline aparece em até ~55 s (45 s do Core + 10 s). Leitura que falha mostra Status "Desconhecido" e o diagnóstico, nunca Offline. |
| Configuração › Aplicativo, espaço usado | `storage` | nenhum | Medida cara: lida ao abrir. |
| Empresa, indicadores | `executions/summary`, `processes`, `stations`, `reviews` | executions, jobs, reviews, processes, stations | O resumo lê de novo sempre que a loja lê as execuções. Falha mostra o diagnóstico e "—". |
| Empresa, atividade recente | `executions` | executions, jobs | Mesmo feed de Rotina › Atividade. |
| Empresa, armazenamento | `storage` | nenhum | Medida lida ao abrir a página. |
| Nova Rotina, checks | `jobs/{id}` | nenhum | Consulta o próprio job a cada 800 ms enquanto ele não termina. |

## Empresa: indicadores e controles (STABILIZATION-REAL-UI S2, 07/11/2026)

Todos os números vêm do Core. Os dados demonstrativos saíram da sessão normal; o modo de demonstração (`vite --mode demo`) calcula os mesmos indicadores sobre as próprias fixtures, identificado na tela.

| Indicador | Fonte e fórmula | Permissão | Ao clicar | Vazio / carregando / erro |
|---|---|---|---|---|
| Processos cadastrados | `processes`: quantidade de processos não arquivados | Qualquer pessoa ativa da equipe | Processo › Ação | "—" até ler; erro geral da loja no topo |
| Execuções nos últimos 30 dias | `executions/summary`: `total`, contado no banco por `created_at` nos últimos 30 dias | Qualquer pessoa ativa | Histórico com o mesmo período | "—" e diagnóstico; 0 só quando o Core contou zero |
| Marcados para mim | `reviews`: pedidos pendentes com a pessoa | A própria pessoa | Processo › Ação, Marcado para mim | "—" até ler |
| Estações disponíveis | `stations`: não revogadas, com sinal nos últimos 45 s e sessão pronta, sobre as não revogadas | Qualquer pessoa ativa | Configuração › Estação | "—" até ler |
| Em andamento, Aguardando revisão, Precisam de atenção, Verificadas | `executions/summary`: grupos `running`, `waiting`, `attention` (finalizada e não verificada), `verified`; os mesmos predicados das abas do Histórico (`groupOf`) | Qualquer pessoa ativa | Histórico com o mesmo período e a aba do grupo | "—" e diagnóstico |
| % das finalizadas | verificadas ÷ (verificadas + precisam de atenção) do período | — | — | Sem finalizadas: "Nenhuma finalizada no período", nunca 0% |
| Armazenamento | `storage.db_bytes`: tamanho do banco medido no servidor | Qualquer pessoa ativa | Configuração › Aplicativo | "—" e diagnóstico; sem capacidade inventada |

Fora desta fatia, mantidos ausentes: horas economizadas, produtividade, comparação com período anterior e gráficos sem base.

Controles com efeito no Core ou no desktop usam `useAction` (`desktop/src/hooks/use-action.ts`): ficam desabilitados enquanto a chamada corre, uma de cada vez, e a falha aparece na tela. Aplicado em Equipe (ativar/desativar, adicionar), Estação (revogar), Aplicativo (iniciar executor e abrir navegador, cada um com o próprio erro), Nova Rotina (cancelar verificação), execuções técnicas (cancelar) e criar rotina a partir de modelo. Conferidos em 07/11 e já com estado ocupado: Nova Rotina (salvar, preparar, testar), execução de processo e de rotina, aprovar revisão, pedidos de substituição, composição de processo e execução legada. A tela de gravação segue fora do menu, como recurso adiado, e não foi alterada. Operações adiadas seguem desabilitadas com "(em breve)"; o Kanban continua somente leitura.

## O que não gera aviso

- Heartbeat sem mudança visível e renovação de lease: escrevem a cada poucos segundos.
- Checks de preparação: quem precisa deles é a tela que criou o job.
- Estação passar a offline: é ausência de escrita.
