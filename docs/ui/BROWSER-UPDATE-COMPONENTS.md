# Update Browser — componentes escolhidos e adaptações

Atualizado: 01/11/2026. Complemento da [work order](../../delivery/work-orders/DISCOVERY-20261031.md), [AS-IS/TO-BE](BROWSER-UPDATE-ASIS-TOBE.md) e [regras](../APP-RULES.md). Comandos abaixo foram **escolhidos pelo usuário, não executados** nesta elaboração. A implementação deverá conferir fonte/licença, versões e registry e fixar revisões antes de importar; `@latest` é a instrução de seleção, não um pin imutável.

## Componentes

| Comando de referência | Uso aprovado/direção | Adaptação ao RedRise |
|---|---|---|
| `npx shadcn@latest add login-05` | Tela técnica login | E-mail, Google/GitHub e confirmação inicial conforme decisões; máscara pt-BR. |
| `npx shadcn@latest add signup-05` | Tela técnica register | Cadastro manual só e-mail, alternativas sociais explícitas; sem Apple/Acme. |
| `npx shadcn@latest add sidebar-03` | Navegação principal | **Processos, Fluxos, Configurações**; sem navbar demonstrativa nem menus herdados. |
| `npx shadcn@latest add @blocks-so/dialog-11` | Algum fluxo de criação | Dialog com passos/coluna de contexto; esboço usa criação de processo. Não substituir todos os cadastros por dialog; páginas com etapas e painel lateral continuam conforme a tarefa. |
| `npx shadcn@latest add @blocks-so/table-02` | Ações das tabelas | Executar quando elegível, editar, detalhes/log conforme objeto/perfil. Não importar pausa, exclusão ou checkbox de sucesso verificado como ações já aprovadas. |
| `npx shadcn@latest add @blocks-so/table-04` | Tabela resumida/agrupada por processo no painel Processos | Grupos e rotinas relacionadas; botões de filtros obrigatórios. Adaptar colunas, removendo orçamento/prazos demonstrativos sem função no app. |
| `npx shadcn@latest add @blocks-so/stats-13` | Espaço dedicado/usado pelo app e referência ao PostgreSQL integrado | Separar bytes de armazenamento de quantidades de registros/processos. Local final da barra proposto no rodapé do conteúdo dos painéis, não da janela. Fonte/unidade/limite real ainda a definir. |
| `npx shadcn@latest add @blocks-so/stats-02` | Resumo no topo de Processos e Fluxos | Indicadores úteis a processos/rotinas/execuções; clicáveis para destino/filtro coerente. Não copiar conversão/receita ou variações temporais sem fonte. |
| `npx shadcn@latest add @blocks-so/grid-list-02` | Grade de acesso em Fluxos | Itens de processos com nome/estado e acesso a detalhes/execução; sem pessoas/cargos da demonstração. |
| `npx shadcn@latest add @blocks-so/onboarding-07` | Log de processo e visão de etapas | Rotina, status, data/hora/duração e detalhes expansíveis; leitura de eventos, não botão que produz sucesso. |
| `npx shadcn@latest add @blocks-so/onboarding-06` | Linha do tempo nos painéis principais | Evolução dos estados da execução/processo selecionado; separar futura etapa de concluída/verificada. |
| `npx shadcn@latest add @blocks-so/onboarding-05` | Atividade recente nos painéis principais | Feed derivado das mesmas mudanças de estado, com vínculo ao registro. |

## Tema e visualizações

- Regra confirmada: controle com **lua** ativa modo escuro; controle com **sol** ativa claro. Ícone alterna para a ação disponível. Trocar fundo, texto, bordas, contraste de botões/inputs/tabelas/dialogs/lateral/kanban/status, preservando legibilidade. Persistência da preferência local é direção técnica a implementar; não alterar tema de terceiros.
- O menu é **Fluxos**, substituindo Fluxos de Trabalho em todos os rótulos novos. IDs/objetos já existentes não precisam ser renomeados só para trocar máscara.
- Fluxos terá botão grande com representação de Kanban; clicar abre o quadro dos processos, com **filtro por processo**, mostrando rotinas executadas e não executadas. Esboço propõe colunas Aguardando/Em andamento/Verificada/Falhou. Falha/incerto/não verificado devem conservar sua distinção na integração real; não juntar tudo como sucesso.
- Kanban é leitura/acesso ao estado real. Arrastar cartões não foi pedido; não aprovar transições de execução ou verificação por drag-and-drop.
- Filtros de processo/status em tabela e processo no Kanban são sugestões concretas do esboço que atendem à exigência de filtros. Aplicar filtro não altera dados nem executa automação.
- Log, tabela, grade, indicadores, timeline e atividade devem observar o **mesmo modelo de estado da execução**. Não manter estados contraditórios por visualização. Estado da execução não é o estado global de uma rotina reutilizável.
- Progresso considera a sequência realmente executada; uma rotina concluída mas não verificada não deve liberar avanço ou aumentar contador de verificadas.

## Dados fictícios agora, integração depois

Usuário autorizou textos/dados fictícios para explorar e construir a interface até definir/implementar os contratos do próximo update. O esboço de 01/11 usa fixtures explícitas; nenhuma leitura de banco, disco ou conta foi feita para gerar os números.

Na engenharia, manter modo de demonstração identificado e dados isolados da persistência real. Não transformar fixture em prova de automação nem permitir fallback silencioso do backend indisponível para números de exemplo. Após conectar uma funcionalidade real, usar sua fonte real e estados carregando/vazio/erro. O indicador de espaço não autoriza reservar quota, mover arquivos, limpar dados ou alterar PostgreSQL.

No esboço, atualizar progresso é uma simulação local explicitamente indicada; isso não define botão de produção que marque rotinas verificadas. Verificação funcional futura depende de efeito observado/evidência, conforme regras do projeto.

## Referências fornecidas

| Imagem preservada | Referência |
|---|---|
| [Ações](references/blocks-table-02.png) | table-02 |
| [Criação](references/blocks-dialog-11.png) | dialog-11 |
| [Agrupamento](references/blocks-table-04.png) | table-04 |
| [Armazenamento](references/blocks-stats-13.png) | stats-13 |
| [Resumo](references/blocks-stats-02.png) | stats-02 |
| [Grade](references/blocks-grid-list-02.png) | grid-list-02 |
| [Log](references/blocks-onboarding-07.png) e [log expandido](references/blocks-onboarding-07-expanded.png) | onboarding-07, duas referências |
| [Inspiração adicional de execução/log](references/execution-log-inspiration.png) | Não identifica por si só um componente instalado ou um agente de IA a embarcar. |
| [Atividade](references/blocks-onboarding-05.png) | onboarding-05 |

Imagens preservadas byte a byte. `onboarding-06` foi escolhido pelo nome/comando do usuário e conferido na página oficial, sem atribuir incorretamente uma imagem a ele.

Fontes primárias consultadas em 01/11/2026: [dialogs](https://blocks.so/dialogs), [tables](https://blocks.so/tables), [stats](https://blocks.so/stats), [grid list](https://blocks.so/grid-list), [onboarding](https://blocks.so/onboarding). A estrutura visual escolhida não incorpora Next.js, campos, serviços ou todo o app demonstrativo como dependência de produto; o desktop continua Tauri e a migração React/shadcn será delimitada.

## Esboço atualizado e validação

Fonte de conversa: `C:/Users/raulv/.codex/visualizations/2026/10/30/01a18f30-f642-7142-aa76-2ebb6a8d2633/redrise-paineis-browser.html`. JS de autoria em `redrise-paineis-browser.js` no mesmo diretório. Não são frontend de produção nem os componentes reais instalados do registry.

Verificação de 01/11/2026 em Chromium headless: tema claro/escuro e contraste; tabela agrupada e ações; filtros e vazio; grade Fluxos; Kanban filtrado; evolução fictícia sincronizada; log; dialog de criação; confirmação sem execução; cadastro HTML condicional; rotina avulsa sem vínculo automático; Configurações; larguras 1024/736/360 sem overflow horizontal global; nenhum erro JavaScript. Capturas de claro, escuro e Kanban inspecionadas. A verificação não homologa runtime, PostgreSQL, OAuth ou o pacote instalado.
