# Checkpoint — contas da equipe, estações e ajustes de uso

- 08–09/11/2026. Work order [TEAM-ACCOUNTS-20261108](../work-orders/TEAM-ACCOUNTS-20261108.md). Base `991ebc5`, com a S5 (agendamento) encontrada sem commit e registrada no próprio commit `ddd42e2`. Evidência: [evidence.json](../evidence/TEAM-ACCOUNTS-20261108/evidence.json).
- Decisões técnicas registradas antes de implementar (WO, seção 9). Item 8 (MediaFire) adiado por ordem do usuário, fora do gate.

## Entregue (Core 0.3.8, migração 011, desktop 0.1.0-beta.29, Runner 0.3.11 inalterado)

- **Item 1:** "+ Nova Conta" no canto de Meu perfil; assistente em quatro etapas (nome, e-mail, senha, confirmar); `POST /api/v1/accounts` cria Operador ativo que entra na hora. Lixeira em conta inativa; exclusão lógica (`DELETE /api/v1/users/{id}`), relida sob trava, sessões encerradas, histórico preservado, e-mail reservado.
- **Item 4:** Status (Online/Offline/Desconhecido) separado de Estado; a sessão sabe sua estação pela credencial da estação enviada no login; "Esta estação" não é revogada nem excluída; estação revogada pode ser excluída (lógica).
- **Itens 5 e 6:** qualquer vínculo removível, processo vazio salvo; composição sem início válido não executa (`PROCESS-START-INVALID`, agendamento pausa); excluir rotina vinculada a retira de todos os processos na mesma transação.
- **Itens 2, 3, 7, 9, 11:** coluna Ações com o fundo da linha; olho nas execuções técnicas; Aplicativo sem Navegador e com Sobre no card do servidor; hierarquia da sidebar; controles verde/amarelo/vermelho.

## Testes e provas

- Core: `test_team_accounts` 13 OK e os demais módulos OK (seis expectativas antigas atualizadas porque a WO mudou a regra). UI: 81/81, typecheck limpo. Contratos 17 OK. validate-base 346/368.
- Gate da 0.1.0-beta.29 aprovado. Prova prática no laboratório: os 11 cenários aprovados no mesmo candidato instalado, em sete rodadas (as repetições corrigiram só o script de prova e o driver de UI; um clique fora da tela abriu o Pesquisar do Windows, e o driver agora recusa cliques fora da janela). Rollback beta.29 → beta.28 numa cópia aprovado, inclusive com conta excluída.

## Entrega

- Commits na `main` local: `ddd42e2` (S5), `880662e` (esta WO, fonte do instalador), `d8682b8` e `fa9347b` (prova). Sem push.
- Instalador `C:\Users\raulv\RedRise-v2-dev\release\0.1.0-beta.29\RedRise-Setup-0.1.0-beta.29.exe`, SHA256 `6dedaf96867d6b67066743a74fab54e47683cb7d69e9475e75626d78405aa6e7`, assinado no canal local (antes beta.28).
- Instalação real atualizada pelo update do próprio app em 09/11 01:35: 0.1.0-beta.28 → 0.1.0-beta.29, anterior guardada, backup `pre-migration-20261109-013602.dump`, Core 0.3.8, sem erros nos logs; app reaberto na tela de login.

## Pendências

- **Usuário:** entrar no app real e conferir a equipe (esta sessão não usa as credenciais da equipe real).
- **Encontrado antes do update:** a estação do próprio servidor real já estava revogada (heartbeats recusados desde antes). A WO manda não recuperar automaticamente; enquanto ela estiver revogada, a sessão não fica ligada a uma estação e não há estação conectada para executar na equipe real, até este computador entrar de novo na equipe.
- **Estação do servidor religada (09/11, por ordem do usuário):** este computador entrou de novo na equipe como a estação 2 `servidor-lab-2` pelo `redrise_runner join` (mesmo mecanismo do setup; usuário e senha digitados pelo próprio usuário). Depois de reabrir o app, os heartbeats voltaram a ser aceitos (200) e o executor está sem erro. A estação revogada 1 `servidor-lab` continua no inventário até um administrador excluí-la pela lixeira ([evidência](../evidence/TEAM-ACCOUNTS-20261108/real-station-rejoin.json)).
- Revisão independente não designada. Item 8 adiado. Nada publicado.
