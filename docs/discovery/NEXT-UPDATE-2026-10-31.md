# Discovery — próximo update do app RedRise

Data: 31/10/2026. Produto: `product:redrise-v2`. Estado: aberto, em discussão.
Fonte das decisões: solicitação do usuário nesta conversa em 31/10/2026.
Referência de partida: código `0.1.0-beta.10`; não representa versão instalada ou homologada.

Este documento registra a direção do próximo update. Não inicia implementação, instalação, atualização, gravação ou publicação. Decisões confirmadas abaixo prevalecem, no seu escopo, sobre a direção anterior; hipóteses e propostas continuam identificadas como tais. Não altera retroativamente provas ou versões históricas.

## 1. Resultado esperado

O usuário cadastra uma rotina por um fluxo manual simples, sem precisar gravar ações ou conhecer detalhes da Engine. A gravação permanece como alternativa avançada e opcional. As duas entradas devem produzir processos compatíveis com o ambiente real da estação executora, com resultados verificáveis e sem atingir documentos alheios.

O app adota shadcn/ui, adaptando os blocos selecionados às funcionalidades atuais. A janela terá aparência homogênea, sem a barra branca nativa do Windows.

## 2. Decisões confirmadas

| ID | Decisão | Consequência |
|---|---|---|
| D01 | Cadastro manual é o caminho padrão para criar rotinas. | O usuário pode definir o processo sem gravá-lo. Não confundir com executar manualmente uma rotina já cadastrada. |
| D02 | Gravação é uma alternativa avançada e opcional. | Preservar o recurso existente e melhorar sua usabilidade; não obrigar seu uso no cadastro. |
| D03 | Os formulários devem usar poucos campos simples, no máximo cinco ou seis. | Aplicar também à gravação; alcance do limite por rotina/etapa ainda em discussão. |
| D04 | A automação deve considerar diferenças entre versões do Windows e do aplicativo. | A Engine precisa reconhecer o ambiente e escolher um comportamento compatível; não transferir seleção técnica de versão ao usuário. |
| D05 | O trabalho documental deve se alinhar à base `0.1.0-beta.10`. | Reconciliar código, estado da candidata e documentação sem inventar instalação ou homologação. |
| D06 | O catálogo Browser específico fica para depois. | Relacionar sua evolução ao cadastro manual e à gravação simplificada, sem escolher um site alvo agora. |
| D07 | Substituir a direção Vanilla UI por shadcn/ui no frontend. | Registrar e planejar a migração necessária; manter o backend e as funções atuais. |
| D08 | Usar `login-03`, `signup-03` e `sidebar-04`, adaptados ao app atual. | Não importar menus, serviços ou funcionalidades demonstrativas dos blocos. |
| D09 | Remover a decoração branca nativa da janela e integrar os controles ao visual. | Sem navbar ou faixa adicional do template; manter movimentação e redimensionamento da janela. |
| D10 | Três botões redondos no canto superior direito. | Ordem da esquerda para a direita: minimizar, maximizar/restaurar, fechar. Estilo inspirado no Mac, com a ordem e a posição especificadas pelo usuário. |
| D11 | Preservar os adiamentos já registrados. | Não reabrir gravação humana Excel, LAN ou outros itens por consequência indireta deste discovery. |
| D12 | O cadastro manual será uma sequência de ações, inicialmente somente para Excel. | Confirmado na resposta do usuário à pergunta sobre o modelo. Definir o passo a passo Excel antes de ampliar para Browser ou outros aplicativos. |

## 3. Engine: reconhecer ambiente, capacidades e estado

### Problema

O Bloco de Notas é o caso inicial: versões com guias e restauração de sessão podem abrir várias janelas/guias. Abrir o processo não prova que existe um editor vazio pronto para receber texto. Uma guia é um documento, que pode ter seu próprio arquivo; várias guias não são partes de um único arquivo.

O comportamento não deve depender apenas de um ramo “Windows 10” versus “Windows 11”. A Microsoft documenta guias como atualização do próprio Notepad, incluindo preferência por guia ou nova janela. Versão do app, configuração e estado observado também importam [S1].

### Direção técnica proposta, ainda não implementada

1. O Runner coleta o ambiente na estação que executará, não no computador que cadastrou a rotina: versão/build do SO, arquitetura, idioma relevante, aplicativo efetivamente resolvido e versão/pacote quando disponível.
2. Um adapter identifica capacidades e estado: janela clássica ou com guias, documento ativo, restauração de sessão, diálogos e condições de prontidão. Identificação por versão ajuda a selecionar um perfil, mas não substitui a confirmação da interface real.
3. A Engine escolhe um perfil de comportamento versionado e testado, com pré-condições explícitas. Ambiente desconhecido ou ambíguo produz recusa explicada antes de digitar; não adivinhar o alvo.
4. Antes de gravar e antes de executar, validar janela e documento/guia de destino. Antes de ações relevantes e após retomada, conferir novamente sessão, foco e estado necessário.
5. Rotinas manuais e gravadas usam as mesmas fronteiras de compatibilidade, execução e verificação. Reutilizar contratos/IR existentes quando adequados, após conferir sua cobertura; gravar num ambiente não garante reprodução em outro.
6. Guardar referências técnicas mínimas de compatibilidade e perfil junto da versão da rotina e da execução, sem capturar conteúdo de outros documentos. Definir contrato e retenção durante implementação.

Não prometer suporte Windows 10 neste discovery: o alvo atual é Windows 11 x64. Projetar a identificação para distinguir variantes não equivale a homologar todas elas. A ampliação do suporte continua uma decisão aberta.

### Preparação do Bloco de Notas

Necessidade expressa pelo usuário: começar a automação com apenas uma guia de trabalho, evitando interferência de guias restauradas.

Restrição existente a preservar: documentos e janelas já abertos pelo usuário não podem ser descartados. Fechar todas as guias ou limpar a sessão global não é uma solução segura por padrão.

Proposta para discussão: obter uma nova janela isolada e um documento/guia pertencente à execução, confirmar que é o alvo correto e deixar as guias anteriores intactas. Se isso não for possível naquela variante, explicar a condição e interromper a preparação. O mecanismo concreto de isolamento precisa de prova; não assumir que um argumento de linha de comando ou atalho funciona em todas as versões.

Critérios propostos:

- Diferenciar perfis de editor clássico/com guias sem depender apenas do nome do SO.
- Com várias janelas/guias restauradas e documentos não salvos, escrever somente no destino da rotina e preservar todos os demais.
- Interferência de teclado/mouse, mudança indevida de alvo ou efeito desconhecido interrompe o fluxo com estado honesto; não retentar escrita automaticamente.
- Mudança de versão do aplicativo entre cadastro e execução exige revalidar compatibilidade.
- Aplicar a regra de encerramento já registrada: app previamente aberto permanece aberto; resultado não verificado preserva o alvo para conferência; fechar apenas recursos comprovadamente pertencentes à execução quando cabível.
- Homologação inclui efeitos persistidos conferidos independentemente; um arquivo criado diretamente por código não substitui a automação UI exigida.

## 4. Cadastro manual e gravação opcional

Confirmado: linguagem simples, poucos campos e entrada manual por padrão. O cadastro deve gerar uma rotina persistida e versionada, consumível pela execução existente, em vez de uma configuração descartável.

Modelo confirmado pelo usuário: **sequência de ações simples, inicialmente somente para Excel**. Operação pronta deixa de ser a alternativa em aberto para o modelo inicial. A gravação continua opcional e seu adiamento de homologação humana Excel permanece preservado.

### Passo a passo Excel para discussão

Proposta exploratória, ainda não aprovada como sequência obrigatória ou lista completa de ações:

1. **Identificar a rotina:** informar um nome simples.
2. **Abrir a planilha:** escolher um arquivo existente ou criar uma pasta de trabalho nova, se essa opção fizer parte do primeiro processo escolhido.
3. **Escolher onde trabalhar:** selecionar a aba da planilha.
4. **Adicionar ações de preenchimento:** indicar a célula e o valor; adicionar outras ações conforme necessário. Exemplo: preencher B2 com o nome do cliente e B3 com o valor do pedido. Esse exemplo não restringe o editor ao template atual.
5. **Salvar o resultado:** escolher pasta e nome do arquivo; confirmar tratamento de destino já existente, preservando a recusa de sobrescrita atual até decisão explícita.
6. **Revisar e cadastrar:** mostrar a sequência em linguagem simples e salvar a rotina. Cadastrar não executa automaticamente a automação.

Proposta de interação: botão “Adicionar ação”, ordem visível e possibilidade de editar, remover e reordenar os passos antes de cadastrar. Cada ação mostra apenas seus campos relevantes. Os cinco/seis campos **por etapa** são proposta, não interpretação confirmada do limite original. Nomes finais, ações iniciais e forma de selecionar aba/célula dependem do primeiro processo real a definir.

Decidir também quais valores ficam fixos na rotina e quais serão solicitados a cada execução. Não pedir campos sem uso nem expor executável, classe de janela, seletor, JSON, flags ou sintaxe de compilação.

Usar seletores de arquivos/pastas quando aplicáveis, rótulos do negócio, validação próxima ao campo e resumo antes de salvar. Não pressupor que todos os processos cabem em seis campos universais. Precisamos definir se o limite inclui nome/operação e se vale por etapa ou pelo cadastro completo.

Gravação: oferecer uma escolha explícita como “Criar por gravação”, mantendo-a opcional. Simplificar seleção de alvo e parâmetros; não exigir que o usuário entenda IR ou declarações técnicas. Rótulo final e posição ainda abertos. Preservar rotinas já cadastradas e suas versões.

A Engine existente reduz parte do trabalho de execução, mas não prova que o editor manual será simples de implementar. É necessário definir as operações suportadas, a conversão para procedimento, pré-condições, edição/versionamento e critérios de verificação. Não prometer automação arbitrária ou inferência automática a partir de poucos campos.

## 5. Frontend shadcn/ui e janela

### Blocos selecionados pelo usuário

```text
Signin: npx shadcn@latest add login-03
Signup: npx shadcn@latest add signup-03
Sidebar/layout: npx shadcn@latest add sidebar-04
```

Comandos registrados como referências, não executados. Antes da implementação, fixar versões, preset e origem dos blocos para reprodução; `@latest` não identifica uma versão imutável.

As fontes oficiais usam componentes React/TSX; o guia Vite usa React + TypeScript e Tailwind [S2–S4]. O app atual usa TypeScript Vanilla, sem React/bundler, em `desktop/package.json`. Portanto, não é uma troca de CSS. Proposta: migrar o frontend dentro de Tauri para React/TypeScript com ferramentas compatíveis, reaproveitando contratos IPC/API e regras do produto. Versões, bundler, tokens e plano de migração serão decididos antes de implementar. Next.js, servidor web ou rotas do exemplo não são requisitos do desktop.

Mapeamento obrigatório:

- `login-03`: login da equipe com usuário/senha existentes; não impor email, login social ou serviços externos do bloco.
- `signup-03`: adaptar ao fluxo atual de criar equipe/primeiro administrador. Não criar cadastro público ou mudar permissões por inferência; confirmar a divisão visual com conectar equipe.
- `sidebar-04`: preservar somente **Rotina, Ação, Configuração** e os controles existentes pertinentes ao perfil. Remover menus de convite, projetos, billing, equipes demonstrativas, dashboards vazios e demais recursos ausentes. Não adicionar header/navbar/breadcrumb do exemplo sem necessidade aprovada.
- Preservar logos, permissões, histórico, catálogo, execução e mensagens úteis. Aplicar os novos formulários simples às duas entradas de criação de rotina.

Controles da janela: retirar decoração nativa por mecanismo suportado do Tauri e criar os controles integrados [S5]. Manter ações reais de minimizar, alternar maximização/restauração e fechar; área arrastável sem sobrepor inputs/botões, resize, foco por teclado e rótulos acessíveis. Definir o que fechar significa durante gravação/execução sem interromper efeitos ou perder dados silenciosamente.

Cores ainda abertas: o usuário pediu referência Mac e círculos, mas demonstrou dúvida sobre as cores. Proposta visual: amarelo para minimizar, verde para maximizar/restaurar e vermelho para fechar, preservando a ordem funcional solicitada. Não tratar essa proposta como escolha já confirmada. Mac como referência visual não amplia suporte para macOS.

## 6. Versão de referência e atualização assistida

Estado observado na abertura do discovery:

- `desktop/package.json` e `desktop/src-tauri/tauri.conf.json`: `0.1.0-beta.10`.
- `delivery/status.json`: candidata registrada `0.1.0-beta.6`, `closed_beta_available=true`, `beta_ready=false`, `published=false`; próxima ação cita verificação de beta.10.
- `project.json` contém descrições anteriores de runtime não implementado e Engine não empacotada.

Alinhar a documentação com beta.10 significa separar versão do código, build gerada, instalada, candidata e homologada. Não substituir o número em evidências de beta.2/beta.6 nem alegar que beta.10 foi instalada. A reconciliação factual é tarefa futura; este discovery não modifica registros operacionais.

Explicação do ponto 6 da revisão: em `desktop/src/main.ts`, o temporizador de seis horas apenas redefine `updateChecked=false`; a consulta ocorre numa renderização posterior do shell. Assim, permanecer na mesma tela não dispara por si só a nova busca. Já existem assinatura/integridade, aviso, adiamento e caminho de instalação/recuperação; a observação não significa ausência de updater.

Proposta ainda a confirmar: consulta periódica independente da navegação, consulta ao iniciar, opção manual em Configuração e estado distinguindo sem atualização, atualização disponível e falha da consulta. Manter “Pode atualizar”/“Ainda não”, integridade, ponto seguro e recuperação. Frequência final, comportamento offline e critérios do pacote ficam abertos; não instalar automaticamente.

## 7. Escopo preservado

Conforme `delivery/status.json#/scope_decisions`:

- Gravação humana Excel e segunda estação LAN/decisão de firewall continuam adiadas para depois do Beta.
- Authenticode continua fora por decisão de custo; não confundir com assinatura do manifesto de atualização já implementada.
- Site completo e Contact Sales real permanecem posteriores ao roadmap e fora deste trabalho no app.
- Catálogo Browser/site alvo específico segue adiado conforme esta conversa; o modelo de cadastro pode prever Browser sem anunciar template funcional.
- Sem commits, pushes, publicação, custos, credenciais ou alterações em serviços de terceiros.

## 8. Perguntas abertas e próxima conversa

1. Modelo resolvido: sequência de ações, começando por Excel. Qual primeiro processo real será detalhado — que planilha usa, o que faz e qual resultado deve produzir?
2. O limite de cinco/seis campos vale pelo cadastro inteiro ou por etapa, incluindo nome/operação?
3. A área isolada para a rotina atende ao objetivo de uma única guia de trabalho, preservando as demais? Não implementar limpeza de guias pessoais por suposição.
4. Windows 10 passa a ser plataforma suportada ou apenas variante a reconhecer e informar incompatibilidade? Qual matriz inicial de app/versão/idioma será homologada?
5. Quais preset, tema/tokens e cores finais dos controles? O signup adapta somente criar equipe/primeiro administrador?
6. Como deve se comportar fechar durante gravação ou execução? Qual frequência e apresentação da consulta de update?
7. Qual será a versão do próximo update? beta.10 é referência de partida, não versão automaticamente atribuída a mudanças futuras.

Sequência proposta de refinamento: detalhar o primeiro processo Excel, suas ações e campos; definir preparação/compatibilidade; fechar fluxo de cadastro/gravação; aprovar visual adaptado; definir aceites da build e reconciliar documentação. Só depois derivar tarefas de implementação delimitadas.

## 9. Fontes e limites da evidência

Fontes locais: [baseline](../BASELINE.md), [Engine](../ENGINE.md), [roadmap](../ROADMAP.md), [status](../../delivery/status.json), [campanha histórica](../../delivery/evidence/P13/campaign.json), [UI](../../desktop/src/main.ts), [Runner/templates](../../runner/redrise_runner/templates.py), [guard de entrada](../../engine/crates/engine-win/src/guard.rs), [updater](../../desktop/src-tauri/src/update.rs).

Fontes externas oficiais consultadas em 31/10/2026:

- S1: [Microsoft — guias no Notepad](https://blogs.windows.com/windows-insider/2023/01/19/tabs-in-notepad-begins-rolling-out-to-windows-insiders/).
- S2: [shadcn/ui — blocos de autenticação](https://ui.shadcn.com/blocks/authentication).
- S3: [shadcn/ui — blocos de sidebar](https://ui.shadcn.com/blocks/sidebar).
- S4: [shadcn/ui — instalação Vite](https://ui.shadcn.com/docs/installation/vite).
- S5: [Tauri — personalização de janela](https://v2.tauri.app/learn/window-customization/).

O mecanismo de isolamento, a compatibilidade entre versões e a migração visual são propostas a provar, não capacidades verificadas nesta tarefa. Memória operacional indisponível no router (`correnth`/`redrise-v2`); usadas fontes primárias. Nenhum grafo foi consultado ou reconstruído. Checks da revisão de 30/10 são históricos e não homologam este update. Reavaliar este discovery após respostas do usuário, novos presets ou prova que altere uma hipótese técnica.
