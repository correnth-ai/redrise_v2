# Checkpoint — Estabilização e interface funcional

- 07/11/2026. Work order [STABILIZATION-REAL-UI-20261107](../work-orders/STABILIZATION-REAL-UI-20261107.md). Evidência por incremento em `delivery/evidence/STABILIZATION-REAL-UI-20261107/`.
- Base: `main` em `f78d229`; nada commitado; o checkout é compartilhado.
- Decisões do usuário (07/11): parar ao fim de cada incremento; S1 só no Core, sem botão novo de cancelar execução; S2 com resumo no Core para os últimos 30 dias; S3 com 5 falhas em 5 minutos → espera de 60 s, dobrando até 15 min, em memória.

## S1 — cancelamento e estado canônico (feito no código, sem candidato)

- **Defeito reproduzido:** cancelamento aceito com a etapa 1 em execução era ignorado quando o Runner informava `verified`; a etapa 2 entrava na fila. O novo teste falha 2 de 7 casos no código de `f78d229` e passa 7 de 7 com a correção.
- **Correção:** `core/redrise_core/service.py` (Core 0.3.6). Cancelamento aceito antes de a próxima etapa entrar na fila impede essa etapa; a etapa em curso guarda o resultado real; a execução termina `cancelled`. Resultado antes do cancelamento: o cancelamento é recusado para a etapa concluída e a etapa na fila ainda pode ser cancelada. Última etapa concluída não vira cancelada.
- **Runner:** sem mudança; o cancelamento já chega pelo heartbeat ao Engine nas etapas que o aceitam. Abrir aplicativo, site, relatório e rascunho não são interrompidos no meio.
- **Estado canônico:** `status.json` aponta a 0.1.0-beta.25 instalada (laboratório e instalação real), sem assinatura no canal, publicação ou homologação; beta.14 ficou em `earlier_candidates`. AGENTS, README e APP-RULES dizem identidade externa suspensa, menus e stack vigentes. BETA-ACCEPTANCE tem a matriz de reconciliação com os adiamentos. Hashes de ENGINE.md e ERROR-DIAGNOSTICS.md atualizados no manifesto `products/redrise-v2/product.yaml`.
- **Tela:** Processo › Histórico com dados persistidos no laboratório mostra a execução cancelada, etapa 1 verificada e as demais não executadas.
- **Não feito:** revisão independente; prova instalada (S4); candidato beta.26.

## Próxima ação segura

S2 iniciado por ordem do usuário em 07/11; ver abaixo.

## S2 — indicadores e controles reais (feito no código, sem candidato)

- **Core:** `GET /api/v1/executions/summary` conta no banco as execuções dos últimos 30 dias por situação; `GET /api/v1/executions?days=30` devolve as mesmas linhas, até 500. Mesmos predicados das abas do Histórico. `days` fora de 1 a 366 é recusado.
- **Empresa:** sem fixtures na sessão normal (`empresa-demo.ts` removido). Processos, execuções do período, marcados para mim, estações disponíveis, situação das execuções, atividade recente e tamanho do banco; cada indicador abre a lista com o mesmo filtro. Erro mostra diagnóstico e "—". Taxa só com execuções finalizadas.
- **Histórico:** aceita o período vindo da Empresa e diz quantas linhas mostra.
- **Controles:** `useAction` evita duplo envio e mostra falhas em Equipe, Estação, Aplicativo, cancelar verificação, cancelar execução técnica e criar rotina por modelo. Rádios do assistente com nome e descrição acessíveis no navegador; UIA da WebView2 instalada fica para S4.
- **Linha do tempo:** etapa concluída antes de uma parada diz "execução encerrada aqui" em vez de "continua para a próxima".
- **Tela:** inspecionada com dados persistidos no laboratório: contagens iguais às abas, clique levou à lista com 3 de 3 linhas, execução nova pela tela atualizou os cards sem navegar.
- **Não feito:** revisão independente; prova instalada (S4).

## Próxima ação segura

S3 iniciado por ordem do usuário em 07/11; ver abaixo.

## S3 — segurança básica e testes confiáveis (feito no código, sem candidato)

- **Tentativas:** 5 falhas em 5 min por conta (usuário e e-mail contam juntos) ou por endereço → 429 `AUTH-RATE-LIMITED` com espera de 60 s, dobrando até 15 min; na espera a senha não é conferida e novas tentativas não aumentam o tempo; sucesso zera a conta; reinício zera tudo. Cadastro: todo pedido conta por endereço. Em memória, como decidido.
- **Concorrência:** 64 conexões (16 por endereço), 30 s de timeout; 16 vagas de pedido + 4 reservadas para o executor e cancelar, espera de 5 s, depois 503 `CORE-BUSY`; feed de mudanças sem vaga; banco com no máximo 32 conexões em uso (o cache de 8 não é limite). Números em P05-D14.
- **TLS:** o servidor fecha o socket TLS ao fim de cada conexão; antes ficava para o coletor (1.332 avisos na linha de base). Testado: concluída, interrompida, handshake nunca enviado, não TLS, fechada na hora.
- **Testes:** as 88 falhas da descoberta global (14 + 74) individualizadas: `CoreTest` coletado 9 vezes e token de admin guardado na classe, reutilizado em outro banco. Agora `Harness` não é TestCase e cada classe descarta caches ao iniciar seu cluster. Descoberta global e módulos isolados: 136 testes, todos OK, 0 avisos de recurso.
- **Dependências:** inventário Rust (9 diretas, 440 no lock) e Python (Core, navegador, runtimes) com ferramentas existentes; nenhum scanner instalado nem consulta a base de vulnerabilidades.
- **Tela:** login no laboratório mostrou "Aguarde 60 segundos" na 6ª tentativa e voltou a conferir a senha após a espera.
- **Riscos abertos:** quem conhece um usuário na LAN pode fazê-lo esperar (nunca permanente); usuários no próprio servidor compartilham 127.0.0.1; margem do executor só no nível do pedido; números não medidos sob carga real.
- **Não feito:** revisão independente; prova instalada (S4).

## Próxima ação segura

S4 iniciado por ordem do usuário em 07/11; ver abaixo.

## S4 — validação instalada e recuperação (aceito no candidato do laboratório, revisão pendente)

- **Candidato:** 0.1.0-beta.26, instalador `8cee8c98376eca5ea29eea8c5fa0eb6cdd1d61d8814e07ac775ea33edd7dc81e`, Core 0.3.6, Runner 0.3.11; Engine e ferramenta do instalador iguais aos da beta.25. Única diferença de arquivos para a beta.25: a licença Playfair (`licenses/playfair-display-OFL.txt`).
- **Gate:** `verify-candidate.ps1` aprovado (Boas-vindas 3 vezes ocioso e 3 sob carga). Instalado só na pasta do laboratório; a instalação real continua na beta.25.
- **Prova prática** (`proofs/stabilization/accept_s4.py`, equipe sintética): dados da beta.25 preservados; Empresa igual ao Core (25 processos; 49 execuções = 0 + 0 + 6 + 43; estações 1 de 1) e o card abre o Histórico com as mesmas 6 linhas; rádios com nome na árvore do Windows; cadastrar → preparar → testar; revisão com sino e Aprovado!; relatório em PDF e pasta; cancelamento com a etapa 1 em execução no Runner real sem iniciar a etapa 2; permissões de operador; limite de login 429/60 s e recuperação. Nenhum clique perdido.
- **Intervenções:** a prova foi corrigida duas vezes (menu Empresa é botão; faixa do Histórico chega em partes). Nenhum código do app mudou depois do build.
- **Rollback × recuperação** (`rollback_check.py`, cópia isolada): o Core 0.3.5 abriu os dados gravados pelo 0.3.6 com as mesmas contagens; backup e restauração em banco separado reproduziram todas as tabelas. Só é reversível porque S1–S3 não criaram migração.
- **Não exercitado:** falha de conexão do app com o Core instalado (exigiria mudar firewall/sistema); rascunho real de e-mail; carga real.
- **Não feito:** revisão independente; assinatura no canal, publicação e atualização da instalação real (dependem de ordem explícita).

## Revisão independente (07/11, dois revisores somente leitura)

- Sem bloqueios. Quatro correções recomendadas, todas confirmadas na fonte: R1 limite de login ultrapassável por pedidos simultâneos; R2 blocos de Processo › Ação contam a lista limitada a 100 sem rótulo; R3 a prova da Empresa não confere a aba e as linhas de "Precisam de atenção"; R4 a prova de dados preservados só verifica histórico não vazio. Dez itens menores. Detalhes em `delivery/evidence/STABILIZATION-REAL-UI-20261107/review.json`.

## Correções da revisão (07/11, por ordem do usuário)

- **Corrigido:** R1 (tentativa contada antes da senha, sob um único bloqueio), R2 (blocos de Processo › Ação contados no Core, 30 dias, como a Empresa), R3/R4/R14 (provas mais estritas: linhas da aba, contagens antes e depois da atualização, atualização ao vivo), R5 (estado em APP-RULES), R6 (asserção de teste), R8/R9 (erros na tela), R10 (hash da licença), R11 (limpeza do rollback). Mantidos com motivo: R7, R12, R13.
- **Testes:** Core 139 sozinhos e juntos, sem avisos; UI 58; contratos 17; validate-base 346/368.
- **Candidato 0.1.0-beta.27** (instalador `f9956ea325df51d2f193eaede56fb6f2fd46b54f284bd97928d8444998426510`): gate aprovado; contagens de base gravadas pela beta.26 antes da atualização; instalado só no laboratório; prova completa aprovada numa única execução (10 cenários, nenhum clique perdido); rollback da beta.27 para a beta.25 numa cópia aprovado. Evidência: `s4-fixes.json` e `s4b/`.
- **Finais de linha:** arquivos que meus scripts gravaram com CRLF voltaram a LF, como o índice guarda; sem mudança de conteúdo para o git.
- A instalação real continua na beta.25; nada assinado, publicado ou commitado.

## S5 — próxima capacidade (somente plano)

- Quatro necessidades apresentadas a partir do que já existe; o usuário escolheu **agendar um processo** (07/11).
- Work Order própria: [SCHEDULE-PROCESS-20261107](../work-orders/SCHEDULE-PROCESS-20261107.md). Um horário e dias da semana por agendamento, numa estação; cada ocorrência é uma execução comum com `request_id` por ocorrência (sem duplicar); estação indisponível pula e avisa, sem fila; ocorrência perdida só até 15 min. Sem cron, intervalos ou nova tentativa.
- A confirmar antes de implementar: operador pode agendar? (proposta: só administrador); janela de 15 min para ocorrência perdida.
- Nenhum código, candidato ou instalação nesta etapa. Evidência: `s5.json`.

## Próxima ação segura

A Work Order STABILIZATION-REAL-UI-20261107 está concluída (S1–S5), com revisão independente fechada e candidato 0.1.0-beta.27 aceito só no laboratório. Próximo: o usuário confirma os dois pontos e ordena a SCHEDULE-PROCESS-20261107. Commit, assinatura no canal, publicação e atualização da instalação real só por ordem explícita.
