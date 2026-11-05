# Checkpoint — Boas-vindas

- 04/11/2026. Work order [UI-ENGINE-BOAS-VINDAS-20261103](../work-orders/UI-ENGINE-BOAS-VINDAS-20261103.md); [evidência](../evidence/UI-ENGINE-BOAS-VINDAS-20261103/evidence.json).
- Instalada: 0.1.0-beta.25 (05/11/2026, por ordem do usuário), gate aprovado, sem assinatura no canal. Engine `b4f13d23…7ca9`.

## Estado

- **Aceite do Boas-vindas:** 7 de 7 cenários no app instalado, com equipe sintética isolada e revisão independente.
- **Entregue:** processo pronto em Processo › Ação, três etapas com contexto na mesma execução, rotina vinculada só pelo processo, ordem dos menus, vínculo na Lista.
- **Fora desta fatia:** demais pontos da work order, listados em `not_done` na evidência.

## Andamento dos incrementos (04/11/2026)

Incrementos 1 a 4 aceitos na 0.1.0-beta.24 instalada no laboratório, gate aprovado, com equipe sintética criada por versão anterior, sem assinatura no canal. A instalação real e a equipe real não foram tocadas. Nada commitado. Detalhes em `candidate_increments_1_to_4` na evidência. Correções feitas depois da beta.24 entram no próximo candidato.

Incrementos 5 a 7 aceitos na 0.1.0-beta.25 instalada no laboratório, gate aprovado, 9 de 9 cenários e Boas-vindas completo, sem assinatura no canal. Só o rascunho real de mensagem não foi exercitado: pode salvar na conta real, e o usuário optou por não testar por enquanto (2026-11-05). Detalhes em `candidate_increments_5_to_7` na evidência.

## Próxima ação segura

Instalação real atualizada para a 0.1.0-beta.25 em 05/11/2026, com backup `pre-migration-20261105-044430.dump`; detalhes em `real_install` na evidência. Falta o usuário conferir as telas com a equipe real: ninguém entrou nela depois da atualização. Sem rascunho real por enquanto. Ainda em aberto: se editar a rotina da etapa 1 também exige aprovação. A licença da Playfair Display entra no próximo candidato. Provas com o computador livre: `proofs/nova-rotina/accept_increments.py` e `proofs/boas-vindas/accept_boas_vindas.py`.
