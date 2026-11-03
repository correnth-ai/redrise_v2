# Checkpoint — implementação do update Browser

- Capturado em 01/11/2026. Task `REDRISE-BROWSER-UPDATE-20261101`; work order [BROWSER-UPDATE-20261101](../work-orders/BROWSER-UPDATE-20261101.md); evidência [evidence.json](../evidence/BROWSER-UPDATE-20261101/evidence.json). Antecessor: [BROWSER-UI-20261101](BROWSER-UI-20261101.md).
- Root `D:/Correnth/products/redrise-v2/repos/app`, `main`, HEAD unborn. Nada commitado nem publicado fora do canal local do laboratório.

## Entregue (código 0.1.0-beta.14, Runner 0.3.2)

- I0 work order; I1–I3 frontend React/shadcn (Processos/Fluxos/Configurações, wizard, dialog-11, lateral, diálogo de execução compartilhado, tema lua/sol, janela integrada), fixtures só em `npm run dev:demo`; máscara pt-BR embutida no bundle (beta.14).
- I5 Core: migração 002, rotina `browser_open` versionada, processos/vínculos, execuções com snapshot/contexto, avanço só com `verified`+continuação, isolada recusada na API, `/api/v1/storage`.
- I6 Runner: descoberta, leitura UIA, `browser_open.py` com confirmação em dois níveis (≤30 s, sem retry/kill/troca de browser), “Abrir com” → Edge, Brave identificado só para HTML.
- I7: telas TO-BE só no demo; [proposta de contrato](../../docs/identity/IDENTITY-CONTRACT-PROPOSAL.md).
- I8: candidato `C:/Users/raulv/RedRise-v2-dev/release/0.1.0-beta.14/RedRise-Setup-0.1.0-beta.14.exe` sha256 `3a121801…cbb3`; gate aprovado, assinado no canal local e **instalado pelo app** (beta.10 → beta.13 → beta.14; `@redrise.previous` mantido). Engine idêntica à beta.10.

## Decisões do usuário em 01/11 (APP-RULES B03/B05)

1. Verificado = **página carregada e pronta**; **guia aberta no endereço** sozinha falha com `BROWSER-PAGE-NOT-READY`.
2. HTML com “Abrir com”: cancelar o diálogo e abrir no Edge, sem alterar a associação.
3. Brave identificado quando a associação abre o HTML nele; nunca oferecido para site.
4. Assinar e executar a campanha (beta.13); fechar o Bloco de Notas, gate e assinar (beta.14).

## Validações

- Testes: browser_open 22, runtime 53, contratos 17, Core+PostgreSQL 30, build UI, validate-base 341.
- Real direto: sonda UIA; site carregado verificado; endereço sem servidor → `BROWSER-PAGE-NOT-READY`; HTML pela associação → Brave verificado.
- Gates: beta.13 e beta.14 `passed=true`.
- Campanha instalada (beta.14, UI Automation na janela RedRise, dados sintéticos): rotinas A/B/C e processos P1/P2 pela interface; P1 por Processos (confirmação dupla → uma execução) verificado até o fim com contexto por etapa; P2 por Fluxos interrompido em C (30 s), A não executada; isolada de B bloqueada na UI; isolada de A verificada; Histórico/Kanban coerentes. Defeito F1 (textos em inglês por CSP) corrigido na beta.14.
- Não cobertos: navegador fechado dentro de processo, “Abrir com” real, replay de request_id pelo app instalado, Chrome/Firefox/Chromium, segunda estação, identidade.

## Achados abertos (evidence.installed_campaign.findings)

F2 sessão encerrada a cada atualização e usuário não pré-preenchido; F3 painel da execução mostra só o código, diagnóstico pt-BR só no registro técnico; F4 polling ~2,7 s sem execução ativa; F5 linhas técnicas só por mouse; F6 linha do tempo “continua” na última rotina; F7 rótulos crus/“Close”/nomes truncados; F8 `tab_title` pré-carga.

## Próxima ação segura

Usuário decide a homologação formal (Edge para site, Brave identificado para HTML nesta estação) e quais achados F2–F8 corrigir; identidade segue IDENTITY-CONTRACT-PROPOSAL. Sem commit/push/publicação sem ordem.
