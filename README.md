# RedRise v2

Nova base independente para o produto comercial **RedRise**, estabelecida em 24/10/2026. App B2B de automações verificáveis, começando por Excel desktop real no Windows 11.

**Direção vigente (27/10/2026):** Engine própria/SOLID; preservar investigação e provas já registradas. Construir capacidades pequenas com testes localizados, conectar por contratos e validar fluxos completos no closed beta instalado, no ambiente disponível. Estado real em delivery/status.json; disponibilidade interna não equivale a Beta homologado.

| Identificador | Valor |
|---|---|
| Produto / repositório | `product:redrise-v2` / `repo:redrise-v2` |
| Remote | `https://github.com/correnth-ai/redrise_v2.git` |
| Root local | `D:/Correnth/products/redrise-v2/repos/app` |
| Manifesto organizacional | `D:/Correnth/products/redrise-v2/product.yaml` |
| Memória | `correnth` / `redrise-v2` |
| Primeiro alvo | Windows 11 x64 + Excel Microsoft 365 desktop |

Leia nesta ordem:

1. [AGENTS.md](AGENTS.md) — limites e execução pelos agentes.
2. [Baseline](docs/BASELINE.md) — decisões confirmadas e pendências.
   Consulte também [Engine](docs/ENGINE.md) — direção atual, fronteiras SOLID e métodos de estudo.
3. [Roadmap passo a passo](docs/ROADMAP.md) — provas, desenvolvimento, integração e Beta.
4. [Estado das entregas](delivery/status.json) — execução e pendências atuais.
5. [Work Order](docs/WORK-ORDER.md) e [evidência](docs/EVIDENCE.md) — como executar e concluir cada incremento.

Rastreabilidade: [requisitos D01–D51](docs/requirements.json), [fontes com hashes](docs/sources.lock.json) e [critérios Beta](docs/BETA-ACCEPTANCE.md). Os originais permanecem no pacote indicado pelo usuário; não foram copiados em massa.

Stack mantida: Tauri, TypeScript Vanilla, npm, Vanilla UI, Rust nativo, Core/Runner Python e PostgreSQL compartilhado. A Engine própria integra o app; linguagem/integração concreta seguem a decisão E01 registrada. Windows instala por usuário em `%LOCALAPPDATA%\Programs\@redrise`, com Engine/runtime/componentes gerenciados; sem instalar plugins ou configurar portas manualmente. Dados e cofre ficam separados dos binários.

O produto anterior permanece separado. Reaproveitamento não é requisito. Os [logos existentes](assets/brand/redrise/README.md) foram especificamente autorizados pelo usuário, com integridade/proveniência verificáveis.

Validação da base, sem instalar dependências:

```powershell
node scripts/validate-base.mjs
node scripts/validate-base.mjs --check-sources
```

Próximo incremento conforme estado atual e roadmap revisão 4; não reiniciar etapas verificadas. Verificação de resultados se limita às funções previstas/entregues, sem verificadores funcionais de cloud/MCP/qualification excluídos. Os comandos acima não iniciam automação. Commits, pushes, publicação e operações externas exigem ordem explícita.

Antes de construir a Engine, execute o [plano preparatório de investigação](docs/ENGINE-INVESTIGATION-PLAN.md). Para outro agente conduzir pesquisa e desenvolvimento local até o Beta pronto para release, copie o [prompt de execução](docs/AGENT-START-BETA.md).


Procedimentos vigentes: [testes e validação prática](docs/TESTING-STRATEGY.md) e [mensagens de erro e códigos de módulos](docs/ERROR-DIAGNOSTICS.md). Prompt atualizado em [AGENT-START-BETA.md](docs/AGENT-START-BETA.md).

