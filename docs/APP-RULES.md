# RedRise — regras do app e mapa de funcionamento

Atualizado: 02/11/2026. Produto: `product:redrise-v2`. **Detalhamento: nível 1 — visão simples.**

**Revisão de 03/11/2026 ([UI-ENGINE-BOAS-VINDAS](../delivery/work-orders/UI-ENGINE-BOAS-VINDAS-20261103.md)):** menus na ordem Empresa → Processo → Rotina → Configuração. Rotina vinculada, mesmo como única etapa, executa só pelo processo (Core recusa com ROUTINE-LINKED); a Lista executa apenas avulsas e mostra o vínculo. Processo de teste pronto **Boas-vindas** em Processo › Ação, criado uma vez por equipe e sem edição. Prevalece sobre M01, M06 e R06 nos pontos alterados.

**Revisão de 02/11/2026 (usuário):** identidade externa suspensa até as automações funcionarem. Cadastro grava só no Core, sem e-mail nem confirmação; a conta nasce inativa como operador e um administrador a ativa em Configuração › Equipe. Login no Core por e-mail ou usuário. Fora de uso por enquanto: Supabase, Resend, confirmação, reenvio, recuperação, Lembrar de mim, Estações lembradas, Google/GitHub. A01–A07 voltam quando a identidade for retomada.

**Direção vigente de identidade/UI:** [IDENTITY-UI-20261102](../delivery/work-orders/IDENTITY-UI-20261102.md), com [prompt de engenharia](AGENT-START-IDENTITY-UI.md). Implementação local em andamento (código beta.15, sem candidato); cadastro e login reais bloqueados para aceite: [estado e pendências remotas](identity/IDENTITY-N0-CONTRACT-20261102.md). Substitui as referências login/signup-05 e o cadastro sem senha: login-03/signup-03 com fundo fornecido, nome completo/e-mail/senha, mínimo 8 caracteres, mesma infraestrutura Supabase V1 seletivamente reutilizada e sessão lembrada segura. Demais fontes históricas abaixo preservam o estado anterior; esta direção prevalece nos pontos alterados.

Revisão adicional: 01/11/2026; menu **Fluxos**, temas e blocos complementares. Referências/instalação/adaptações no [catálogo de componentes](ui/BROWSER-UPDATE-COMPONENTS.md).

Objetivo: consultar uma regra e entender onde aparece, o que provoca e quais outras regras afeta. Ampliar o detalhe apenas quando solicitado. As decisões vêm da [work order do próximo update](../delivery/work-orders/DISCOVERY-20261031.md), que registra sua origem e o escopo. Este mapa não comprova implementação nem autoriza construir/publicar o update.

Legenda: **Confirmado** = decisão de produto; **Atual** = comportamento conferido no código, sem nova homologação nesta tarefa; **Proposta** = ainda não decidida; **Pendente** = falta definição/prova. Quando uma decisão mudar, atualizar sua regra e as linhas relacionadas do mapa; não manter alternativas antigas como regras ativas.

**Escopo vigente:** novo modo de automação somente Browser neste update. Nenhuma nova opção Excel/Notepad/Outlook ou login automático em sites. Requisitos posteriores de identidade incluem e-mail, Google/GitHub e confirmação, descritos em A01–A04; não são somente estilo. Preservar fluxos existentes e regressão de autenticação/contratos compartilhados. Etapa atual: [AS-IS/TO-BE de UI](ui/BROWSER-UPDATE-ASIS-TOBE.md), começando por **register** e **login**. Sugestões não aprovadas permanecem identificadas.

## 1. Regras globais

| ID | Regra confirmada | Onde influencia |
|---|---|---|
| R01 | KISS; cadastro manual como padrão; gravação opcional/avançada; poucos campos simples. Limite de cinco/seis ainda sem definição por etapa/cadastro. | Todos os cadastros; não adicionar parâmetros técnicos para resolver dúvidas de implementação. |
| R02 | Rotina é uma microetapa. Processo agrupa rotinas ordenadas e começa pela primeira. | Cadastro, composição e execução. Processo do app é distinto de processo do Windows. |
| R03 | Mesma rotina pode estar em vários processos. Alterações valem na próxima execução de todos; execução iniciada conserva sua configuração. | Salvar edição, vínculos, histórico e execução. |
| R04 | Continuação é configurada em cada vínculo do processo. Marcada + rotina concluída/verificada chama a próxima; desmarcada encerra ali. | Execução e histórico; sem pausa, salto ou retry automático. |
| R05 | Falha, resultado incerto ou não verificado impedem avanço. Mostrar o resultado real e quais rotinas não executaram. | R04, timeout, abertura, login futuro e salvamento. |
| R06 | “Esta rotina pode ser executada isoladamente” controla a execução avulsa. Não impõe posição no processo. | Disponibilidade da ação Executar e validação backend; não ignora pré-requisitos. |
| R07 | Rotinas passam contexto para a próxima na execução do processo. | Neste update: guia/browser efetivo e referências da execução; não trocar alvos nem usar janela pessoal por aproximação. |
| R08 | Valores próprios da rotina ficam no cadastro, sem perguntar novamente a cada execução. | Endereço, navegador quando aplicável, caminho, parâmetros fixos; referências dinâmicas pertencem a R07. |
| R09 | Descobrir/validar ambiente na estação executora. Usar fontes registradas/caminhos conhecidos e seletor, sem varrer todo o disco como padrão. | Listas, resolução de app/browser, compatibilidade, versão e desempenho. Lista de encontrados não equivale a browsers homologados para automação. |
| R10 | Não encerrar processos, reparar aplicativos nem reiniciar o PC para resolver falhas. | Acesso e diagnósticos; preserva documentos. Não remover proteções existentes de sessão/foco. |
| R11 | Erros seguem quatro tópicos e códigos de erro/módulos, sem inventar causa. | UI, backend e suporte; preservar correlação e resultado/efeito real. |
| R12 | Toda máscara da aplicação em **Português do Brasil**. | Títulos, campos, botões, links, loading, mensagens, estados e acessibilidade. Identificadores técnicos/URLs/provedores não são traduzidos. Texto inglês de referência não é texto final. |
| R13 | Construção visual pode usar dados/textos fictícios, identificados como demonstração. | Fixtures isoladas; fontes reais obrigatórias ao integrar. Não substituir erro do backend por métricas fictícias ou usar protótipo como evidência de automação. |

## 2. Menus, visual e acesso

| ID | Regra | Situação e relação |
|---|---|---|
| M01 | Menus no singular: **Empresa; Rotina → Lista, Atividade; Processo → Ação, Histórico, Kanban; Configuração → Equipe, Estação, Aplicativo**. | Pedido 02/11 substitui Processos/Fluxos/Configurações. Sem Gantt. Preservar funções e dados, realocando acessos. |
| M02 | **Empresa** é a primeira página após login/restauração. Dashboard inspirado na referência Productivity, com dados demonstrativos identificados. | Outras áreas mantêm fontes reais; nenhuma automação por apenas navegar. Mapa visual e realocação na work order de 02/11. |
| M03 | **register** com `signup-03`; **login** com `login-03`; ambos sobre o fundo fornecido. Shell preserva sidebar adaptada. | Pedido 02/11: nome completo/e-mail/senha; Google/GitHub compatíveis preservados, sem Apple; pt-BR por máscaras. Sem backend fictício. |
| M04 | Janela homogênea sem barra branca nativa. Controles redondos no topo direito: minimizar, maximizar/restaurar, fechar. | Confirmado, implementação/cores/fechar durante trabalho pendentes. Não adicionar navbar do template automaticamente. |
| M05 | Atualização preserva “Pode atualizar”/“Ainda não”, integridade e ponto seguro. | Base existente. Consulta periódica independente da navegação é proposta; não declarada entregue. |
| M06 | Acessos contextuais à execução em Rotina e Processo mantêm o mesmo comportamento. | Fluxo compartilhado/histórico único, mesmas permissões e bloqueio de isolada. Configuração não ganha execução pela reorganização. |
| M07 | Escolher página em etapas, dialog ou painel lateral conforme a tarefa. | Preferência por página com etapas para fluxos maiores; usos concretos do esboço ainda são propostas. Componentes shadcn e política de rascunho a definir, sem mudar regras de execução por trocar a apresentação. |
| M08 | Lua ativa modo escuro; sol ativa modo claro, com contraste aplicado em toda a interface. | Incluir backgrounds, texto, botões, inputs, tabelas, status e overlays; não afetar aplicativos de terceiros. |
| M09 | Reaproveitar tabelas/filtros e Kanban no novo mapa: Rotina › Lista; Processo › Ação, Histórico, Kanban. | Preservar composição de processos e filtros reais; não executar/verificar ao consultar nem excluir funções antigas por renomear sidebar. |
| M10 | Resumo, barra de armazenamento, timeline/log e feed acompanham o estado das execuções. | stats-02/13 e onboarding-05/06/07. Dados reais compartilham fonte; fixtures acompanham a simulação somente no modo demonstrativo. |

### Register/login: identidade e confirmação

| ID | Regra confirmada | Efeito/influência |
|---|---|---|
| A01 | Cadastro manual com **nome completo, e-mail, senha e confirmar senha**, ou Google/GitHub conforme contrato; confirmação RedRise obrigatória. | Pedido 02/11 substitui cadastro somente e-mail. Dica de senha: mínimo 8 caracteres, sem checklist extra. Nome em Configuração/perfil; conta pendente sem acesso, cadastro não concede equipe/admin. |
| A02 | Botão “Confirmar” no e-mail registra confirmação e data/hora no backend, depois direciona para `https://redrise.app/login`. | Backend valida prova da conta; redirect não é autenticação nem evento de confirmação suficiente. Destino planejado, sem publicar domínio/rota nesta tarefa. |
| A03 | Ao tentar login sem confirmação, bloquear e mostrar em vermelho sob o botão “Confirme o e-mail para fazer o login.” com link “Reenviar confirmação.” ao lado. | Backend é responsável pelo bloqueio; UI traduz o estado. Reenvio não confirma conta. |
| A04 | Usuário dispensou link/código em cada novo acesso; não acrescentar essa etapa à UI nem repetir a pergunta. | Confirmação inicial continua exigida. Definir sessão/identidade no contrato técnico sem liberar acesso por mera entrada de endereço. |
| A05 | **Lembrar de mim neste computador**, opt-in; plano adota restauração automática da sessão válida e abertura de Empresa. | Cofre por usuário Windows; sem senha salva/preenchida. Desmarcado: memória apenas. Update/reboot não devem apagar lembrança válida. Logout/esquecer revoga este dispositivo; expiração exige login. |
| A06 | Usar o **mesmo projeto Supabase do V1**; estudo/reuso seletivo autorizado para identidade, preservando V1 e Core V2. | Validar políticas/triggers/envio/callbacks reais; nenhum projeto novo ou chave privilegiada no cliente. [Estudo](identity/SUPABASE-V1-REUSE-20261102.md). |
| A07 | Configuração › Estação separa inventário conectado de **Estações lembradas** do usuário, no mesmo submenu. | Lembrança não registra/desregistra Runner. Listagem e revogação sem tokens; offline não significa esquecido. Perfil real inclui nome completo. |

Mapa do evento: **Criar conta/social → cadastro pendente + solicitação de envio → Confirmar → validação backend + timestamp → redirecionar a login → acesso conforme sessão/contrato técnico, sem etapa recorrente de link/código solicitada ao usuário**. A regra R12 traduz mensagens/botões. Provedores, callbacks, políticas de reenvio/link e vínculo com Core/equipe serão detalhados antes de implementar, sem inventar APIs ou alegar autenticação entregue.

## 3. Browser: regras e campos

| ID | Regra confirmada | Efeito |
|---|---|---|
| B01 | Escolher origem antes de navegador: **Navegar em site** ou **Abrir HTML local**, seleção única. | Controla campos, validação e mecanismo de abertura. |
| B02 | Site: escolher um navegador instalado da lista e informar endereço. | Usar a escolha persistida; não substituir por outro silenciosamente. |
| B03 | HTML local: informar caminho completo; não pedir navegador. Se o mecanismo de abertura do Windows mostrar “Abrir com” em vez de um navegador, cancelar esse diálogo e abrir o arquivo no Microsoft Edge (decisão de 01/11/2026). | Abrir o arquivo conforme seu mecanismo de abertura e identificar navegador/guia efetivos para R07. Não impor browser cadastrado nem presumir padrão quando a associação funciona; nunca alterar a associação. Contexto registra `opened_by` (`association` ou `default_browser_after_prompt`). Sem Edge, recusar com BROWSER-NOT-FOUND. Brave é identificado quando a associação abre o HTML nele, mas não é descoberto nem oferecido para site (decisão de 01/11/2026). |
| B04 | Uma abertura de página cria nova guia, mesmo com browser em execução. Próximas rotinas usam essa guia pelo contexto. | Não reutilizar guia pessoal; não abrir nova guia a cada microetapa seguinte. |
| B05 | Confirmar abertura em até **30 segundos** no total, concluindo antes se confirmada, em dois níveis (decisão de 01/11/2026): **guia aberta no endereço** (guia nova cuja barra mostra o destino) e **página carregada e pronta** (documento da guia confirmado no destino, não a página anterior nem página de erro do navegador). Só o segundo nível é verificado. | Guia aberta sem página pronta falha com BROWSER-PAGE-NOT-READY (efeito parcial: a guia fica aberta); nenhuma guia identificada falha com BROWSER-OPEN-UNCONFIRMED. Sem retry; R05 impede avanço. Contexto registra `confirmation` (`tab_open` ou `page_ready`). |
| B06 | Login é outra rotina explícita, a detalhar depois. Guia permanece aberta ao terminar o processo. | Abertura não preenche credenciais nem exige autenticação. Credenciais futuras são referências ao cofre, não senha no JSON/log da rotina. |

Campos do cadastro de abertura:

| Campo | Quando aparece | Destino/uso esperado |
|---|---|---|
| Nome da rotina | Sempre | Identificar o cadastro e o histórico. |
| Origem | Sempre, antes do navegador | Selecionar B02 ou B03; só um modo ativo é válido. |
| Navegador | Só para site | Persistir escolha; resolver/validar na execução. Para HTML, obter browser no contexto após abertura. |
| Endereço ou caminho | Conforme a origem | Persistir URL ou referência ao arquivo local; validar o modo correspondente. |
| Permitir execução isolada | Sempre | R06; backend também deve impedir execução avulsa quando desmarcado. |

Botão de atualizar a lista, busca ao entrar em Nova rotina e loading foram sugeridos; gatilho/componente finais serão escolhidos na etapa de UI. Não executar busca/disparar rotina ao simplesmente editar um campo sem uma regra aprovada.

## 4. Outros modos fora deste update

Opções e aceites novos de Excel foram retirados do escopo ativo. As decisões E01–E04/G11/G30–G32 ficam preservadas nas [regras futuras de Excel](planning/EXCEL-FUTURE-RULES.md), sem execução nesta work order. Não remover dados/código existentes por essa delimitação. Não reutilizar os IDs removidos para outra regra.

## 5. Ação da interface → backend → retorno

**Esperado no update** é um mapa funcional, sem inventar endpoints ou alegar funções já entregues. Componentes e rótulos finais dependem do grill me de UI.

| Ação/campo | Efeito esperado no backend/runtime | Retorno e regras relacionadas | Situação |
|---|---|---|---|
| Abrir menu principal | Consultar resumo permitido ao usuário, sem executar rotina ou alterar configuração. | Painel de Processos/Fluxos/Configurações; M01/M02. | Planejado |
| Clicar no card/indicador ou seu botão de acesso | Abrir o destino interno correspondente e aplicar o filtro indicado, se houver. | Lista/parametrização relacionada; sem escrita por navegar. Métricas ausentes não viram zero inventado. | Padrão confirmado; destinos propostos no complemento UI |
| Alternar lua/sol | Trocar preferência visual e cores/contrastes locais. | M08; sem requisição de automação ou mudança do estado de execução. | Confirmado |
| Filtrar tabela/Kanban | Consultar/apresentar o subconjunto correspondente. | Mesmo estado do processo/execução; não altera tarefa. | Confirmado; contratos reais a implementar |
| Atualização de status | Refletir evento persistido em tabela, grade, Kanban, etapas e feed. | R04/R05; não transformar botão visual em verificador. No protótipo, evento é apenas simulação declarada. | Planejado |
| Executar por Processos ou Fluxos | Acionar o mesmo fluxo de seleção/validação/confirmação e criação de execução, com regras iguais. | Uma execução identificada no histórico comum; atalhos não criam motores ou resultados distintos. Reenvio da mesma solicitação não duplica efeito. | Acesso contextual confirmado; controles exatos pendentes |
| Escolher origem | Ao salvar/executar, validar somente o modo ativo; não usar seleção residual de navegador para HTML. | Atualizar campos B01–B03; sem abrir alvo nessa escolha. | Planejado |
| Buscar navegadores | Consultar a estação/usuário e fontes limitadas de descoberta; deduplicar e validar candidatos. | Lista, ausência ou falha de consulta; R09/B02. | Planejado; gatilho pendente |
| Salvar rotina manual | Validar permissão, campos condicionais e configuração; persistir sem executar. | Cadastro salvo ou diagnóstico; R01/R06/R08. | Planejado; API atual já cadastra templates/procedimentos |
| Editar rotina | Salvar nova configuração usada nas próximas execuções dos processos vinculados. | Preservar configuração das execuções já iniciadas; R03. | Planejado; versão/histórico existentes devem ser preservados |
| Vincular/ordenar rotinas e marcar continuação | Persistir ordem e continuação no vínculo do processo, não globalmente na rotina. | R02–R04; sem iniciar execução por editar a sequência. | Planejado |
| Executar rotina isolada | Validar R06 e pré-requisitos; criar execução independente. | Não acionar processos que a referenciam; resultado conforme R05. | Controle de isolamento novo; jobs já existem |
| Executar processo | Usar configurações atuais fixadas no início; iniciar primeira rotina; levar contexto e aplicar continuação. | R02–R08; registrar cada resultado e motivo do término. | Planejado |
| Abertura Browser | Resolver alvo pelo modo, solicitar abertura, confirmar dentro do prazo e produzir referência da guia/browser. | B01–B06, R05/R07/R10. | Implementado na beta.14 (descoberta, guia nova, dois níveis de confirmação); provado real e na campanha instalada em Edge/Brave; homologação formal pendente de decisão |
| Rotina retorna resultado | Persistir resultado; avaliar verificação e continuação antes de iniciar a próxima. | R04/R05; falha/incerto/não verificado não avança. | Jobs existentes; orquestração nova |

## 6. Influência entre regras

| Mudança em… | Conferir também… | Motivo |
|---|---|---|
| Origem site/HTML (B01) | Campos, validação, abertura, browser efetivo e contexto (B02–B05/R07). | O mesmo campo não tem o mesmo significado nos dois modos. |
| Resultado/verificação (R05) | Timeout B05, continuação R04, contexto R07, histórico. | Sem confirmação válida, não avançar nem inventar referência para a próxima rotina. |
| Permissão isolada (R06) | Botão Executar, API e pré-requisitos. | Desabilitar apenas na UI não aplica a regra por completo; não altera posição no processo. |
| Rotina compartilhada (R03) | Todos os processos vinculados e snapshots das execuções. | Alteração afeta execuções futuras; não modificar a já iniciada. |
| Menus/componentes (M01–M04) | Permissões, ações da seção 5, campos condicionais e mensagens. | Visual deve representar o comportamento; não criar recursos só porque estão no bloco shadcn. |
| Novo atalho de execução (M06) | R02–R08, seleção do alvo, validações, criação de execução e histórico. | O local de acesso não pode mudar regras ou duplicar envio; abrir detalhes continua sendo leitura. |
| Status/fonte de dados (M09/M10/R13) | Tabela, filtros, Kanban, indicadores, log e feed. | Atualizar a mesma execução sem contradizer estados; distinguir fixture de resultado real. |
| Tema/idioma (M08/R12) | Todas as superfícies e estados de componentes. | Contraste claro/escuro e textos pt-BR se aplicam também aos blocos externos escolhidos. |
| Confirmação de e-mail (A01–A04) | Login manual/social, estado da conta, mensagem/link e timestamp backend. | Confirmar é requisito de elegibilidade; não substitui autenticação de cada acesso. |
| Idioma global (R12) | Todas as telas, erros e e-mail de confirmação voltado ao usuário. | Aplicar pt-BR à máscara, sem traduzir contratos/códigos ou importar texto inglês das referências. |

## 7. Limites atuais e como aprofundar

**Estado de implementação em 01/11/2026 (código 0.1.0-beta.14, aprovado no verify-candidate, instalado no laboratório pelo app; nenhum navegador homologado):** frontend React/shadcn com Processos/Fluxos/Configurações, tema lua/sol e janela integrada ([App.tsx](../desktop/src/App.tsx)); rotina `browser_open` versionada, processos, vínculos com continuação, execuções com snapshot/contexto e avanço só por resultado verificado no Core ([service.py](../core/redrise_core/service.py), migração 002); descoberta de navegadores e abertura com confirmação por UI Automation no Runner ([browser_open.py](../runner/redrise_runner/browser_open.py)). Checks de contrato/componente com PostgreSQL isolado e fakes passaram; abertura real provada no Edge 156 (site carregado e página de erro, B05) e no Brave (HTML pela associação, B03), inclusive na campanha pelo app instalado (processos, continuação, contexto, interrupção, isolada, histórico); achados abertos na evidência. register/login com e-mail/Google/GitHub só no build de demonstração; contrato em [IDENTITY-CONTRACT-PROPOSAL](identity/IDENTITY-CONTRACT-PROPOSAL.md). Evidência: `delivery/evidence/BROWSER-UPDATE-20261101/`.

Fontes de implementação conferidas na elaboração (31/10, antes da migração): UI e menus Vanilla (substituída), [bridge Tauri](../desktop/src-tauri/src/lib.rs), [API Core](../core/redrise_core/api.py), [resolução de apps](../runner/redrise_runner/apps.py), [Browser atual](../browser/redrise_browser/__main__.py), [templates e colisão atual](../runner/redrise_runner/templates.py). UI atual chama a bridge `api` para rotinas/jobs; gravação usa `record_start`/`record_stop`. O Browser atual inicia Chromium privado; não comprova controle de Chrome/Edge pessoais já abertos. Processos/continuação/contexto genéricos são comportamento planejado.

Preservar base beta.10 sem promover instalação/homologação; adiamentos de gravação humana Excel, segunda estação LAN, catálogo específico Browser, site/Contact Sales e Authenticode permanecem na work order. Esta tarefa mudou apenas documentos.

Detalhamento atual da UI: [register/login AS-IS/TO-BE](ui/BROWSER-UPDATE-ASIS-TOBE.md). Ao aprovar cada tela, registrar controles, links shadcn, eventos e efeitos backend. Demais telas permanecem no inventário, sem composição final por suposição; não detalhar agora algoritmos ou recursos de futuros updates.
