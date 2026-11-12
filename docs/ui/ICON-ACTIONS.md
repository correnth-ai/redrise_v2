# Ações por ícone (PROCESS-ACTIONS-20261111 item 1.2)

Inventário das ações contextuais de registros e tabelas nas telas ativas. Ações de linha usam `IconAction`
(`desktop/src/components/icon-action.tsx`): nome acessível e dica iguais, foco visível no botão (e no invólucro quando
indisponível, para a dica dizer o motivo), área de 32 px, estado ocupado (girador, `aria-busy`, sem segundo clique) e
indisponível com o motivo quando a condição é realmente inválida. Decisões destrutivas abrem uma confirmação com texto;
navegação, formulários e decisões mantêm rótulo (Continuar, Voltar, Salvar, Cancelar, OK, Excluir na confirmação, Nova
Conta, Nova Rotina, Novo processo, login, etapas do instalador, Aprovar/Cancelar pedido em Marcado para mim).

| Tela | Ação | Ícone | Observação | Teste |
| --- | --- | --- | --- | --- |
| Processo › Ação, processo | Executar | Play | Abre o diálogo de estação do processo; indisponível sem etapa 1 válida. Substitui o botão Nova execução. | `process-actions.test.tsx`, `process-list-kanban.test.tsx`; nativo `actions` |
| Processo › Ação, processo | Agendar | CalendarClock | Indisponível sem etapa 1 válida. | `process-actions.test.tsx` |
| Processo › Ação, processo | Integrar rotina avulsa | Link2 | Aceita os tipos que um processo vincula, inclusive os de Boas-vindas; follow-up só depois de uma etapa. | `process-actions.test.tsx` |
| Processo › Ação, processo | Substituir etapa 1 | Replace | Indisponível sem etapa 1, com pedido pendente ou em execução. | `process-actions.test.tsx`, `step-change.test.tsx` |
| Processo › Ação, processo | Excluir | Trash2 (destrutivo) | À esquerda do lápis. Abre a confirmação digitada; indisponível em execução ou aguardando revisão (o Core confere todas). | `process-actions.test.tsx`; Core `test_process_actions.py`; nativo `delete`, `welcome` |
| Processo › Ação, processo | Editar composição | Pencil | | `usage-adjustments.test.tsx` |
| Processo › Ação, rotina do processo | Ver detalhes | Eye | | `process-list-kanban.test.tsx` |
| Processo › Ação, agendamento | Pausar / Retomar | Pause / Play | Ocupado enquanto o Core responde; falha mantém a linha com o diagnóstico. | `schedules.test.tsx`; nativo `actions` |
| Processo › Ação, agendamento | Excluir | Trash2 (destrutivo) | Abre confirmação com processo, dias, horário e estação. | `schedules.test.tsx`; nativo `actions` |
| Rotina › Lista | Executar, Ver detalhes, Editar, Excluir | Play, Eye, Pencil, Trash2 | Já eram ícones (TEAM-ACCOUNTS-20261108); Excluir abre confirmação. | `usage-adjustments.test.tsx` |
| Rotina › Atividade | Mostrar/ocultar detalhes | Eye / EyeOff | Já era ícone. | `usage-adjustments.test.tsx` |
| Configuração › Equipe | Desativar / Reativar | UserX / UserCheck | A própria conta: indisponível, com o motivo visível ligado por `aria-describedby`. | `process-list-kanban.test.tsx`, `team-accounts.test.tsx` |
| Configuração › Equipe | Excluir conta | Trash2 | Já era ícone; abre confirmação. | `team-accounts.test.tsx` |
| Configuração › Estação | Revogar | Ban (destrutivo) | Abre confirmação com texto (antes, segundo clique no mesmo botão); a estação desta sessão fica indisponível com o motivo. | `process-actions.test.tsx` |
| Configuração › Estação | Excluir estação | Trash2 | Já era ícone; abre confirmação. | `team-accounts.test.tsx` |

Mantidos com texto, por serem decisão ou navegação: Aprovar substituição / Cancelar pedido e Aprovado! (Marcado para
mim), Cancelar da execução técnica (Rotina › Atividade, detalhe), Iniciar executor (Configuração › Aplicativo), Hoje (Kanban),
Saber mais e Fechar (resumo do Kanban).
