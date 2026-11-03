# Checkpoint — definição e UI do update Browser

- Capturado em: 01/11/2026, America/Sao_Paulo.
- Fronteira: definição funcional, seleção de componentes e esboço interativo concluídos para handoff manual à engenharia; refinamentos visuais ainda propostos estão identificados.
- Task key: `REDRISE-BROWSER-UPDATE-20261101`; Work Order de origem `DISCOVERY-20261031`.
- Owner: nenhuma execução de engenharia iniciada; nova sessão humana deve assumir explicitamente pelo prompt.
- Objetivo seguinte: implementar/testar localmente o update Browser, preservando padrões, capacidades existentes e limites externos.
- Entrada exata: [AGENT-START-BROWSER-UPDATE.md](../../docs/AGENT-START-BROWSER-UPDATE.md).
- Autoridade: documento de autoridade do workspace → fontes canônicas aplicáveis → AGENTS → decisões explícitas na [work order](../work-orders/DISCOVERY-20261031.md); ler manifesto v2 e instruções antes de mutar.

## Fontes duráveis

1. [Work order e decisões G01–G54](../work-orders/DISCOVERY-20261031.md), com exclusões/adiamentos explícitos; IDs retirados não reutilizados.
2. [Mapa de regras](../../docs/APP-RULES.md): campos, menus, eventos, backend e influência entre regras.
3. [AS-IS/TO-BE](../../docs/ui/BROWSER-UPDATE-ASIS-TOBE.md): código atual versus decisões/propostas.
4. [Componentes selecionados e adaptações](../../docs/ui/BROWSER-UPDATE-COMPONENTS.md), com links e referências PNG.
5. [Excel futuro](../../docs/planning/EXCEL-FUTURE-RULES.md): preservar, não implementar agora.

## Último estado verificado

- Root `D:/Correnth/products/redrise-v2/repos/app`, branch `main`; nenhum commit de base (HEAD unborn); conteúdo existente não rastreado. Preservar tudo. Revalidar no início seguinte.
- `desktop/package.json`: `0.1.0-beta.10`, TypeScript Vanilla; nova UI React/shadcn ainda não implementada. Core/Runner Python, Engine/bridge Rust existentes.
- `delivery/status.json` ainda diferencia candidata instalada beta.6 e código beta.10; `beta_ready=false`, `published=false`. Não mudou nesta tarefa.
- Adapter Browser atual inicia Chromium privado; suporte genérico aos browsers pessoais/identificação da guia do HTML não foi entregue por esta elaboração.
- Mudanças desta fase: documentos, 14 referências PNG preservadas byte a byte (4 anteriores + 10 novas), esboços/QA no diretório da conversa. Sem alteração de código funcional, dependências, banco, contas, instalação, deploy, commits ou pushes.

## Verificação e evidência

- Esboço atualizado `redrise-paineis-browser.html` e fonte JS no diretório `C:/Users/raulv/.codex/visualizations/2026/10/30/01a18f30-f642-7142-aa76-2ebb6a8d2633/`.
- `check-redrise-panels.py` nesse diretório: PASS em Chromium headless, temas/contraste, tabela/ações, filtros/vazio, grade, Kanban por processo, progresso/log/atividade sincronizados, criação em dialog, confirmação demonstrativa, cadastro HTML e rotina avulsa, Configurações e larguras 1024/736/360; sem erros JavaScript.
- Capturas `redrise-panels-light.png`, `redrise-panels-dark.png`, `redrise-panels-kanban.png` inspecionadas; `redrise-panels-create.png` também gerada. Ícones no esboço são inicializados pelo runtime de visualização; o renderer de teste sem esse runtime não é captura do app instalado.
- Conferência documental final e validator base registrados em `delivery/evidence/UI-DESIGN-20261101/verification.json`; validador é foundation-only, não prova Beta/Engine.
- Checks antigos 53 runtime/17 contratos/typecheck da revisão de 30/10 são históricos, não validação funcional nova de 01/11.

## Decisões que não devem ser reabertas

- Menus Processos/**Fluxos**/Configurações; sidebar-03; máscara pt-BR; lua/sol; criação/cadastro por páginas/diálogos/lateral conforme tarefa; catálogo blocks-so escolhido.
- Rotina=microetapa reutilizável; processo=sequência; começa na primeira; continuação por vínculo; sem pausa/retry; só resultado verificado avança; contexto por execução; permissão isolada não impõe posição.
- Browser site escolhe instalado; HTML não pede browser e identifica após abrir; nova guia; até 30 s; guia permanece ao fim; não matar processo/reparar usuário.
- Register/login com e-mail e Google/GitHub; confirmação inicial obrigatória com timestamp/backend e destino redrise.app/login. Mensagem/link literais no TO-BE. Usuário dispensou link/código em cada acesso; não repetir a pergunta.
- Fixtures/textos fictícios autorizados na UI de demonstração, sem virar prova real. Excel e salvamento com sufixo estão fora deste update.

## Pendências técnicas e limites

- Construir frontend real com componentes escolhidos e contratos/processos ainda novos; o esboço aproxima visual/ações, não contém a instalação real dos blocos.
- Provar por browser o mecanismo de abertura/controle/guia, respeitando perfis e interação existente. Detectado não significa homologado.
- Definir identidade/sessão sem introduzir passo recorrente de código/link e sem conceder acesso só pelo endereço digitado. Vínculo da identidade web ao Core/equipe, migração das contas e onboarding ainda precisam de solução técnica.
- OAuth/envio real/credenciais/domínio/publicação dependem de autorização e serviços concretos. Não operar o domínio antigo por inferência. Não fabricar essa entrega; continuar UI/Browser independentes.
- Dimensões, textos fictícios finais, política de rascunho e posições específicas não aprovadas podem ser refinados com o usuário; não transformar exemplos em novo escopo.
- Capacidade dedicada real/quotas e fonte dos indicadores de armazenamento precisam de contrato; números exibidos são fictícios e não medição local.

## Continuidade

- Skills lidas: `documentation-decision-log`, `powershell-shell`, `task-context-checkpoint` (SHA256 `88c25b1e0dd233056be4b9f6dfa7ff8c1543d3844f6827f90efc97ec315a3437`) e host `visualize`. Reload the full visualize skill before creating or updating a visualization.
- Memória: workspace `correnth`, project `redrise-v2`; router de 01/11 retornou `MEMORY_UNAVAILABLE`; fallback fontes canônicas. Sem publicação de transcrição/memória e sem rebuild de grafo.
- Operações ativas desta tarefa: nenhuma instalação/automação interativa/serviço de produto. QA headless final terminou com sucesso; nenhum helper servidor foi iniciado. Revalidar processos se outra sessão tiver operado depois.
- Política sucessora: somente prompt manual solicitado; nenhuma thread, subagente ou nova sessão criada. Arquivos do app continuam sob um escritor por root.
- Próxima ação segura: ler prompt e fontes, revalidar root/HEAD/dirty state e criar o Work Order delimitado I0 antes da primeira mudança de implementação.
