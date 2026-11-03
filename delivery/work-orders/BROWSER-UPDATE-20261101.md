# Work Order — implementação do update Browser (I0–I8)

```text
Task ID / Run ID: REDRISE-BROWSER-UPDATE-20261101 / run 2026-11-01-a (sessão iniciada por outra sessão Claude Code a pedido do usuário)
Roadmap step: refinamento P08/P09/P11/P13 (update por recurso: Browser); não conclui etapa do roadmap por si.
Human request and authorized scope: implementar localmente o update Browser seguindo docs/AGENT-START-BROWSER-UPDATE.md, I0–I8; sem commit, push, publicação, assinatura de canal, serviços externos, credenciais ou custos.
Product: product:redrise-v2
Repository: repo:redrise-v2
Root / remote / branch: D:/Correnth/products/redrise-v2/repos/app / origin https://github.com/correnth-ai/redrise_v2.git / main
Actual HEAD (or unborn) and source-tree digest: unborn (nenhum commit); scripts/source-digest.mjs antes da primeira mudança = 5273770adc4bb0c05875dbe7b477e790db9c8709826f8a97ba97db4edfc89a99 (323 arquivos).
Existing dirty files to preserve: todo o conteúdo é não rastreado; nada é removido. Evidências históricas e hash locks intocados.
```

## Objetivo e aceite observável

| Inc. | Aceite | Tipo de check |
|---|---|---|
| I1 | Desktop em React/TypeScript + Tailwind + primitivas shadcn (fonte revisada e fixada) dentro do Tauri; tema claro/escuro (lua/sol) com tokens; janela sem decoração nativa com controles redondos minimizar/maximizar-restaurar/fechar; sidebar-03 com Processos/Fluxos/Configurações; login atual (usuário/senha → `/api/v1/login`) e bootstrap (criar/conectar equipe) preservados; update “Pode atualizar/Ainda não” preservado. | typecheck + build (C:), inspeção em navegador local das larguras/temas |
| I2 | Painéis com stats-02, table-04 agrupada + ações table-02 + filtros, grid-list-02, Kanban por processo, stats-13 (bytes separados de contagens, sem quota inventada), onboarding-05/06/07 lendo o mesmo estado de execução; fixtures só no modo demonstração identificado. | build + inspeção |
| I3 | Cadastro de rotina Browser em página com etapas (identificação/origem/isolada → destino → revisão); HTML sem navegador; composição de processo (vincular rotinas existentes, ordenar, continuação por vínculo) em dialog-11; detalhes em lateral; confirmação de execução em dialog compartilhado por Processos e Fluxos. | build + inspeção; contratos no I5 |
| I4 | Experimento delimitado do mecanismo de abertura/identificação por browser (descoberta somente leitura; abertura real apenas com autorização interativa). Detectado ≠ homologado. | component_check nativo (quando autorizado) |
| I5 | Migração 002 (rotina `browser_open` versionada, processos, vínculos, execuções com snapshot, contexto por execução, encadeamento idempotente); isolada recusada no backend; só `verified` + continuação avança. | contract_check com PostgreSQL isolado em C: |
| I6 | Runner executa `browser_open` (site no browser escolhido, HTML pelo mecanismo de abertura do Windows), confirma em ≤30 s via UI Automation somente leitura, sem retry/kill/substituição; heartbeat publica browsers detectados; UI usa fontes reais. | component/contract checks; prático instalado depende de I4 |
| I7 | register/login (signup-05/login-05) e-mail + Google/GitHub em pt-BR, estados de confirmação (inclusive o literal vermelho e “Reenviar confirmação.”) apenas como fixture identificada; contrato técnico pendente documentado; nenhum serviço externo. | build + inspeção; não homologado |
| I8 | Checks proporcionais, candidato local identificado (versão/hash/inventário) sem assinar/publicar; campanha prática conforme autorização; checkpoint atualizado. | conforme TESTING-STRATEGY |

## Matriz implementado / novo / proposto / dependência externa

| Item | Estado no início | Destino neste update |
|---|---|---|
| Login usuário/senha, sessões, perfis admin/operador | Implementado (Core) | Preservado; nova máscara |
| Criar/conectar equipe, estações, Runner, jobs idempotentes | Implementado | Preservado; acesso via Configurações |
| Templates/gravação Windows/Browser privado (Playwright) | Implementado | Preservado (sem novas opções Excel) |
| Updater (Pode atualizar/Ainda não) | Implementado | Preservado |
| Frontend React/shadcn, tema, janela integrada | Novo | I1–I3 |
| Rotina Browser manual (site/HTML), isolada, processos, vínculos, execução com snapshot/contexto | Novo | I3/I5/I6 |
| Descoberta de browsers na estação | Novo | I6 (registro + caminhos conhecidos) |
| Abertura em browser pessoal + identificação da guia | Novo, sem prova | I4/I6; homologação exige campanha autorizada |
| Indicadores de armazenamento | Novo | Bytes reais (dados/logs/DB) sem quota; capacidade fictícia só em demonstração |
| Identidade e-mail/Google/GitHub + confirmação | Proposto/decidido sem contrato técnico | I7: UI+fixture e contrato pendente; serviços reais = dependência externa |
| OAuth, envio de e-mail, domínio redrise.app | Dependência externa | Não operado |

## Write set

- `desktop/**` (exceto `src-tauri/icons`, gerado): migração React; `src-tauri/src/*.rs`, `tauri.conf.json`, `capabilities/*` para janela/IPC/armazenamento.
- `core/redrise_core/{service.py,api.py,migrations/002_*.sql}`; `runner/redrise_runner/{agent.py,browsers.py,uia.py,browser_open.py,__main__.py,diagnose.py}`.
- `contracts/errors.json`, `desktop/locale/pt-BR.json` (novos códigos nos dois); `tests/**` significativos.
- Versão `0.1.0-beta.11` em `desktop/package.json`, `Cargo.toml`, `tauri.conf.json`, pacotes Python quando o candidato for gerado.
- Documentação ativa: este Work Order, checkpoint novo, `docs/APP-RULES.md`/AS-IS-TO-BE quando o estado mudar, evidência `delivery/evidence/BROWSER-UPDATE-20261101/`.
- Fora do write set: originais/hashes de requisitos, evidências históricas, `products/redrise/**`, control plane, canal/site publicados.

Build, `node_modules`, caches e runtimes: somente `C:\Users\raulv\RedRise-v2-dev` (cópia por `packaging/desktop/build-desktop.ps1`; lockfile volta como fonte).

## Dependências e decisões técnicas

- Fonte shadcn/blocks.so obtida dos registries oficiais (`ui.shadcn.com/r/styles/new-york-v4/*.json`, `blocks.so/r/*.json`), ambos MIT, revisada e copiada para `desktop/src/components`; sem executar `npx shadcn@latest`. Pins npm: versão mais recente publicada antes de 2026-10-18 (≥ 2 semanas), registrada no lockfile.
- Sem Next.js nem servidor web; Vite apenas como bundler de build. `@tabler/icons-react` substituído por `lucide-react` (um conjunto de ícones).
- UI Automation via ctypes no Runner (stdlib only), somente leitura (endereço da guia selecionada, guias por janela); nenhum input sintético.
- Navegador escolhido é um id (`chrome`, `msedge`, `firefox`, `chromium`), resolvido na estação executora; ausente → falha explícita, sem substituição.

## Skills, memória, grafo

- Skills (catálogo `D:/Correnth/catalogs/skills`, resolvidas por nome exato): `react-frontend-setup` 1f8efa29…b9d2, `frontend-localization-contract` cf62e05e…a16a2, `browser-automation-integration` 087fbab3…fd3, `task-context-checkpoint` 88c25b1e…7bc (pins completos no checkpoint).
- Memória `correnth/redrise-v2`: CLI `ai-memory` não disponível no PATH desta sessão; fallback em fontes canônicas. Graphify: nenhuma root registrada para v2; não consultado.

## Parada, recuperação e limites

- Parar e registrar se: abertura real de browser exigir interação na sessão do usuário sem autorização; contrato de identidade exigir serviço externo; mudança afetar contrato protegido corporativo.
- Recuperação: arquivos novos podem ser removidos; edições em arquivos existentes são locais e rastreadas pelo digest; banco de teste é temporário em C:. Nunca reset/clean.
- Sem commit/push/publicação/assinatura sem ordem explícita do usuário. Revisão independente não autoaprovada.
