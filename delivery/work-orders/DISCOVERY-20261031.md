# Work Order — próximo update do app RedRise

Estado: em elaboração no grill me de UI; funcionalidades deste incremento delimitadas a Browser. Não inicia implementação nesta tarefa. Fonte: decisões do usuário nesta conversa em 31/10/2026. Produto: `product:redrise-v2`.

Atualização de 01/11/2026: componentes complementares, temas, menu Fluxos, filtros/Kanban/logs e fixtures em [BROWSER-UPDATE-COMPONENTS.md](../../docs/ui/BROWSER-UPDATE-COMPONENTS.md). Continuidade e ordem de engenharia em [AGENT-START-BROWSER-UPDATE.md](../../docs/AGENT-START-BROWSER-UPDATE.md), a partir do [checkpoint](../checkpoints/BROWSER-UI-20261101.md). A criação do prompt não inicia execução nem cria outro agente/sessão.

## Escopo vigente — update por recurso: somente Browser

Decisão mais recente: implementar e testar somente o modo Browser neste update, com as regras aprovadas de cadastro de abertura site/HTML, navegadores, nova guia, timeout, execução isolada, processos/continuação/contexto e histórico. Realizar agora o grill me de UI antes de implementar. O [AS-IS/TO-BE de UI](../../docs/ui/BROWSER-UPDATE-ASIS-TOBE.md) complementa esta ordem; somente detalhes de UI explicitamente aprovados são requisitos, os demais continuam propostas.

**Excluídos deste incremento:** novas opções/rotinas Excel, seleção de aba, preenchimento/salvamento/sufixos de arquivos; execução nativa Notepad/Outlook; login automático em sites; catálogo de sites específicos; novas funções LAN; publicação; melhorias adicionais do updater ainda não aprovadas. As [decisões futuras de Excel](../../docs/planning/EXCEL-FUTURE-RULES.md) ficam preservadas fora do escopo implementável/testável desta ordem. Não remover código, rotinas, dados ou provas de recursos existentes por essa delimitação; a apresentação de opções antigas na UI será decidida no TO-BE, não por exclusão silenciosa.

A migração shadcn e a janela integrada permanecem na revisão visual acordada, com regressão dos fluxos existentes que forem afetados. “Testar somente Browser” delimita a campanha funcional do novo recurso, não autoriza ignorar regressões de autenticação, permissões, persistência ou contratos compartilhados alterados. Aceite novo: cadastro Browser persistido; site/HTML conforme origem; nova guia com referência identificada; confirmação até 30 s; execução isolada conforme permissão; processo encadeia só resultados verificados e carrega contexto; erro/resultado não verificado para sem retry; guia permanece aberta. Registrar efeitos reais e limitações da build, sem alegar homologação de browsers externos apenas por detecção.

Complemento explícito posterior para acesso: register/login com e-mail ou Google/GitHub, confirmação por e-mail obrigatória, timestamp backend e destino `https://redrise.app/login`, conforme G39–G42. Usuário dispensou solicitar link/código em cada novo acesso (G43); não repetir essa pergunta nem acrescentar esse passo à UI. Contrato técnico de sessão/identidade e integração com Core/equipe serão resolvidos sem presumir sessão autenticada por mera entrada de e-mail. Não configurar serviços, OAuth, envio real ou domínio/publicação nesta etapa documental.

Esta work order concentra as decisões e o escopo do próximo update. O [mapa de regras do app](../../docs/APP-RULES.md) apresenta sua visão consolidada e as relações entre regras, campos, menus e backend, começando em nível simples. Manter os dois coerentes: decisões/escopo aqui, mapa de comportamento e impacto lá. O arquivo `docs/discovery/NEXT-UPDATE-2026-10-31.md` é antecedente preservado, sem evolução paralela. Decisões posteriores prevalecem sobre propostas anteriores. O registro operacional ao final descreve a criação documental, não uma autorização para construir o update.

## Direção consolidada

- KISS: começar pela menor capacidade útil; reaproveitar verificações existentes quando aplicáveis, sem exigir mecanismos gerais novos por antecipação.
- Cadastro manual é o padrão: cada microetapa é uma rotina independente; um processo agrupa as rotinas e define sua sequência e continuação. Este incremento implementará apenas Browser/HTML; demais modos ficam para outros updates. A tarefa atual prepara documentação/UI, sem iniciar implementação.
- Gravação permanece opcional e avançada. Poucos campos simples, no máximo cinco/seis; alcance por etapa ou cadastro completo ainda aberto.
- Separar abertura de Browser/HTML de futuras rotinas de trabalho/login. Não ampliar a abertura para preencher páginas ou documentos neste update.
- Reconhecer SO/build, aplicativo/versão e capacidades na estação executora; adaptar os caminhos atômicos sem exigir escolha técnica de versão pelo usuário. Matriz suportada, suporte Windows 10 e mecanismo geral de perfis ainda não definidos.
- Preservar proteção de documentos, tratamento de efeito incerto e controles de foco/sessão já usados durante ações UI. Verificação de processo tem escopo limitado e não prova resultado de preenchimento/salvamento.
- Migrar para shadcn/ui: `login-05`, `signup-05`, **`sidebar-03`**. Menus TO-BE: **Processos, Fluxos, Configurações**, substituindo os nomes anteriores. Register com e-mail manual ou Google/GitHub. Preservar permissões; máscara pt-BR, marca RedRise e sem Apple. Identidade/bootstrap e organização funcional não são simples troca de campos.
- Blocos React/TSX exigem planejamento da migração do frontend Vanilla. Stack/versões/preset/tokens finais pendentes; manter Tauri e contratos com Core/Runner/Engine. Não executar os comandos `npx shadcn@latest add ...` nesta fase; fixar versões antes da implementação.
- Janela homogênea, sem decoração branca nativa/navbar adicional. Três controles redondos no canto superior direito, da esquerda para a direita: minimizar, maximizar/restaurar, fechar. Preservar arraste, resize e acessibilidade. Cores e comportamento de fechar durante trabalho ainda abertos.
- Base de código de referência `0.1.0-beta.10`. Reconciliar descrições e estados sem mudar evidências históricas: status ainda registra candidata instalada beta.6, `beta_ready=false`, `published=false`. Documentação alinhada não comprova instalação de beta.10.
- Updater: a revisão identificou que o temporizador apenas libera consulta na próxima renderização. Consulta independente de navegação, acionamento manual e apresentação do estado continuam propostas a confirmar. Preservar “Pode atualizar”/“Ainda não”, integridade, ponto seguro e recuperação.
- Preservar adiamentos: gravação humana Excel; segunda estação LAN/firewall; catálogo Browser/site alvo; site completo/Contact Sales. Authenticode segue fora por custo. Sem publicação, custos, credenciais, commit ou push.

## Bloco 1 — rotina de iniciação: acessar aplicativo

### Decisões confirmadas no grill me

| ID | Decisão | Limite |
|---|---|---|
| G01 | Pronto/verificado nesta ação significa observar que o processo do software está iniciado. | Não exigir nova solução geral de janela interativa para concluir a capacidade inicial. Não confundir processo com serviço Windows, que é um recurso distinto. |
| G02 | Se o processo correto já existe, aproveitar e concluir a ação de acesso; se não existe, solicitar abertura e conferir sua presença. | Não abrir duplicata por padrão. Identidade exata do processo/handler é questão técnica abaixo. |
| G03 | Não encerrar processos, reiniciar computador nem reparar aplicativo travado. | Processo residual pode satisfazer a verificação simples; preparação posterior pode falhar. Diagnosticar sem alegar que o aplicativo está utilizável; resolução do ambiente cabe ao usuário/TI. |
| G04 | Se identificação/vinculação de janela já estiver implementada e for aplicável, pode ser reaproveitada. | Não remover proteções existentes nem apresentar os mecanismos específicos como solução universal já entregue. |
| G05 | Lista pesquisável de aplicativos identificados, com “Não encontrou? Selecionar aplicativo”. | Seleção manual deve permitir qualquer tipo de arquivo, sem filtro obrigatório `.exe`. Selecionabilidade não equivale a garantia de abertura/automação. |
| G06 | Escolha feita uma vez no cadastro da rotina e persistida para as próximas execuções. | A cada execução resolver/validar o alvo salvo; não repetir descoberta ampla nem exigir nova escolha quando continuar válido. |
| G07 | Localização deve ser prática e rápida, inclusive em máquinas/servidores com discos grandes. | Não usar varredura completa do disco como caminho normal. Método e metas de tempo ainda precisam ser definidos e medidos. |
| G09 | Distinguir acessar aplicativo de abrir um arquivo. | Aplicativo já iniciado pode ser reutilizado. Arquivo solicitado deve ser aberto mesmo com seu aplicativo associado já em execução. Chrome aberto não satisfaz uma abertura destinada ao Edge. |
| G10 | Documento será referenciado por caminho completo, incluindo nome e extensão. | Não copiar/anexar automaticamente o conteúdo à rotina. O usuário pode colar o caminho; seleção assistida pode complementar sem mudar a referência. |
| G12 | Após o grill me funcional, realizar outro grill me dedicado à UI. | Agente sugere telas, controles e botões; usuário escolhe os componentes shadcn e fornece seus links. Não fechar composição visual agora. |
| G13 | Oferecer lista de navegadores instalados e disponíveis na estação, para escolha no cadastro. | Pesquisar locais de instalação e incorporá-los à estratégia de descoberta. Não substituir a escolha pelo Chromium privado silenciosamente. Lista final de browsers homologados ainda aberta. |
| G14 | Abrir uma nova guia para a automação Browser. | Não reutilizar uma guia pessoal que já esteja naquele endereço nem substituir sua navegação. Mecanismo de controle da nova guia precisa de prova. |
| G15 | Login será uma microetapa explícita, separada de abrir aplicativo/arquivo/endereço. | Uma futura etapa reconhecerá a tela específica e preencherá usuário/senha vinculados à pessoa/rotina. Não implementar login genérico, pausa ou credenciais como parte da abertura. |
| G16 | Cada microetapa é uma rotina diferente; processo agrupa as rotinas. | Separar identidade de rotina, composição do processo e execução concreta. Não confundir com processo do sistema operacional. |
| G17 | A continuação automática para a próxima rotina vinculada é opcional por vínculo dentro do processo. | Marcado chama a próxima somente após conclusão verificada; desmarcado executa a rotina atual e encerra a execução ali. Sem pausa ou continuação manual dessa execução neste incremento. |
| G18 | Abertura Browser tem duas opções mutuamente exclusivas: navegar em site ou abrir HTML local. | Escolher a origem antes de navegador. Site: escolher navegador. HTML local: não informar navegador; abrir o arquivo conforme seu mecanismo de abertura e identificar o navegador efetivo. Esta decisão posterior substitui a precedência de browser escolhido para HTML. |
| G19 | Falha de uma rotina interrompe o processo naquele ponto. | Não executar as seguintes nem repetir automaticamente a rotina falha. Resultado incerto ou concluído não verificado também impede avanço (G21). Sem pausa neste incremento. |
| G20 | A mesma rotina pode participar de vários processos. | Ordem e continuação pertencem a cada vínculo no processo, sem duplicação obrigatória da rotina. |
| G21 | Avanço exige resultado concluído e verificado da rotina atual. | Decisão final do usuário substitui a hipótese intermediária de avançar com ressalva amarela. Não há opção de ignorar verificação para continuar neste incremento. |
| G22 | Executar um processo começa sempre pela primeira rotina vinculada. | Sem seleção de início intermediário neste incremento; não retomar execução anterior por suposição. |
| G23 | Uma rotina pode ser executada isoladamente, fora de um processo. | Execução independente para uso/teste; não dispara processos que a referenciam. Pré-requisitos de contexto ainda devem ser satisfeitos. |
| G24 | As rotinas de um processo carregam contexto para a próxima como referência. | Neste update: browser/guia da mesma execução; não selecionar outra janela nem criar outra guia em cada microetapa subsequente que apenas consome contexto. |
| G25 | Cadastro terá a opção “Esta rotina pode ser executada isoladamente”. | Marcada permite execução isolada, sujeita aos pré-requisitos. Desmarcada exige contexto anterior e desabilita execução isolada. Componente visual final será escolhido no grill me de UI. |
| G26 | Valores como endereço e caminho serão definidos e salvos no cadastro da rotina. | Não solicitar novamente a cada execução neste incremento. Não oferecer “Perguntar ao executar” por suposição. |
| G27 | Alteração de rotina compartilhada vale para todos os processos vinculados na próxima execução. | Execução iniciada conserva sua configuração inicial. Se a mudança tornar um processo inadequado, revisar esse processo e cadastrar outra rotina específica quando necessário. Não exigir atualização manual de versão em cada processo. |
| G28 | Ao terminar o processo, a guia permanece aberta para conferência. | Não fechar automaticamente nesse fluxo novo. Uma eventual rotina explícita de fechamento será tratada separadamente; não encerrar processos do navegador. Conferir impacto nos templates atuais antes de alterar sua regra anterior. |
| G29 | A checkbox de execução isolada não impõe posição no processo. | Vale para qualquer rotina, inclusive a primeira. Retirada a proposta de exigir checkbox marcada na primeira posição; não criar esse gate ou perguntar novamente o que ela já controla. |
| G33 | Abertura Browser tem prazo de até 30 segundos para confirmação. | Concluir antes se confirmada; se não confirmar no prazo, falhar e encerrar o avanço, sem nova tentativa automática. Critério exato de confirmação de guia/browser ainda precisa de prova técnica. |
| G34 | Criar mapa simples das regras globais, menus, campos, ações e backend. | `docs/APP-RULES.md` inicia em nível 1; ampliar detalhe sob solicitação. Distinguir regra confirmada, proposta e comportamento atual. |
| G35 | Entregar updates por recurso; este somente Browser. | Excel e demais modos fora de implementação/aceite novos; UI detalhada no AS-IS/TO-BE, com sugestões diferenciadas de aprovações. |
| G36 | Começar a revisão de UI pelas telas `register` e `login`. | Nomes confirmados substituem sign up/sign in na documentação de telas. Referências visuais atualizadas por G37; não renomear endpoints por nome de tela. |
| G37 | Referências: `npx shadcn@latest add login-05` e `npx shadcn@latest add signup-05`. | Substituem login-03/signup-03; imagens fornecidas complementam layout. Provedores autorizados por G39, sem Apple. Comandos não executados. |
| G38 | Register manual pede somente e-mail. | Sem senha/usuário/equipe/estação/porta. G39 acrescenta alternativas sociais; equipe/Core e login manual posterior à confirmação ainda a definir. |
| G39 | Cadastro/acesso por e-mail ou Google/GitHub. | Enviar confirmação ao endereço informado/obtido em ambos os casos. Confirmação do provedor não substitui o evento RedRise exigido. Não presumir merge de contas ou e-mail inexistente. |
| G40 | E-mail de confirmação contém “Confirmar”; clique registra confirmação com data/hora no backend e redireciona a `https://redrise.app/login`. | Validar a prova da conta e persistir confirmação antes de tratá-la como liberada. Redirect sozinho não confirma identidade nem autentica automaticamente. Não implica publicação autorizada. |
| G41 | Login não confirmado bloqueado; mensagem vermelha abaixo do botão: “Confirme o e-mail para fazer o login.” e link “Reenviar confirmação.” ao lado. | Aplicar no backend também, inclusive em login social. Reenvio não libera acesso por si só. |
| G42 | Toda máscara da aplicação deve estar em Português do Brasil. | Inclui campos, títulos, botões, links, erros, carregamentos, estados e rótulos acessíveis. Manter identificadores técnicos/URLs/provedores. Regra global, não só register/login. |
| G43 | Não solicitar link/código por e-mail em cada novo acesso. | Pergunta encerrada pelo usuário. Preservar confirmação inicial e bloqueio de não confirmado; não interpretar a dispensa como autorização para conceder sessão somente pelo endereço digitado. Detalhe técnico de autenticação sem novo passo de UI será tratado nos contratos. |
| G44 | Menus principais: **Processos, Fluxos, Configurações**. Sidebar: `npx shadcn@latest add sidebar-03`. | Substitui Rotina/Ação/Configuração e sidebar-04 no TO-BE. Nomes antigos permanecem somente como AS-IS; organização dos recursos existentes será mapeada sem perda de função/dados. |
| G45 | Cada menu principal abre painel de administração com cards/indicadores e botões de acesso a telas internas. | Listas, parametrizações e gestão de submenus são acessadas pelo painel; indicador pode servir de acesso ao destino relacionado. Não copiar métricas financeiras, menus ou recursos demonstrativos das imagens. |
| G46 | Divisão dos menus aprovada: Processos gerencia processos/rotinas; Fluxos acompanha execuções/histórico; Configurações reúne equipe/estações/app. | Pode haver acesso à execução em Processos e em Fluxos conforme o contexto; não obrigar um único caminho de navegação. Não aprova automaticamente todos os cards/componentes sugeridos. |
| G47 | Acessos à execução devem conservar o mesmo comportamento e regras. | Direção técnica: ação/fluxo de execução compartilhado entre os atalhos, mesmas permissões, valores cadastrados, isolamento/contexto/continuação, resultado e histórico. Distinguir navegação de iniciar uma execução. Layout exato de formulário/modal ainda a aprovar. |
| G48 | Formato de interação depende da tarefa: preferência por página própria com etapas para fluxos maiores, admitindo dialog e painel lateral quando adequados. | Solicitado esboço visual em 01/11/2026. Não há escolha global de drawer para todas as ações. As associações concretas propostas no esboço ainda aguardam aprovação. |
| G49 | Controle de tema com lua para escurecer e sol para clarear. | Aplicar cores/contrastes a toda a máscara, incluindo overlays, inputs/tabelas e painéis. Não apenas trocar ícone/fundo. |
| G50 | Menu antes chamado Fluxos de Trabalho passa a **Fluxos**. | Substituição na máscara e documentação ativa; demais nomes permanecem Processos e Configurações. |
| G51 | Usar referências blocks-so indicadas no catálogo de componentes complementar. | dialog-11, table-02/table-04 com filtros, stats-13/stats-02, grid-list-02 e onboarding-05/06/07. Adaptar ao produto; não importar ações/menus demonstrativos que contrariem regras. |
| G52 | Textos/dados fictícios permitidos na construção visual até integrar as funcionalidades. | Identificar demonstração e isolar fixtures; não alegar telemetria real, sucesso de automação ou fallback de produção com esses dados. |
| G53 | Fluxos inclui acesso grande ao Kanban e filtro por processo, mostrando tarefas/rotinas executadas ou não. | Visualizações de estado sincronizadas; sem drag-and-drop que force verificação, pausa ou retry automático. |
| G54 | Gerar prompt para próximo agente engenheiro com checkpoint, ordem e padrões do projeto. | Handoff manual em arquivo; não inicia implementação agora nem autoriza commit/push, publicação, custos ou operação externa. |

### Implementação atual conferida, sem mudança

- `runner/redrise_runner/apps.py`: `resolve()` atende Notepad, Excel e Outlook por caminhos/convenções específicos; `is_running()` enumera processos pelo nome da imagem; `launch()` inicia executável. Ainda não é catálogo genérico de todos os aplicativos/arquivos.
- O mesmo arquivo contém `launched_window()`: identifica nova janela por imagem/classe, aguarda estabilização e prefere a nova janela em primeiro plano. `templates.py` usa essa identificação e passa `--bound-window` para procedimentos nativos pertinentes.
- A Engine já possui suporte de vinculação de janela e checagens de foco/sessão no executor. `excel.py` possui verificação específica de janela/planilha pronta. Esses mecanismos atendem caminhos existentes; não comprovam uma ação genérica de acessar qualquer aplicativo.
- Portanto, preservar e reaproveitar esses recursos onde fizer sentido; a exigência mínima nova de processo não implica enfraquecer a execução UI existente.

### Proposta técnica para localização rápida, ainda não aprovada/implementada

Montar a lista a partir de aplicativos registrados e entradas de lançamento do Windows para usuário/máquina, incluindo os cenários de arquitetura pertinentes; pesquisar os nomes dessa lista, não cada arquivo do disco. App Paths e inventário de apps do usuário são fontes complementares, não prova de completude. Aplicativos portáteis/não registrados podem ser escolhidos pelo seletor. Manter dados de resolução reutilizáveis, validar o item salvo e atualizar o inventário quando solicitado ou quando ficar inválido, sem percorrer o disco em toda execução.

Windows registra aplicativos e caminhos independentemente de estarem em Program Files ou em uma pasta por usuário. Fontes oficiais: [Application Registration](https://learn.microsoft.com/en-us/windows/win32/shell/app-registration) e [Get-StartApps](https://learn.microsoft.com/en-us/powershell/module/startlayout/get-startapps?view=windowsserver2025-ps). A cobertura real e o desempenho serão medidos no alvo suportado; não anunciar “todos os softwares do PC” sem comprovação.

### Qualquer arquivo: seleção e abertura

Executável, atalho, documento e HTML podem exigir mecanismos de abertura diferentes. Proposta: usar o mecanismo de abertura apropriado do Windows para o item selecionado e resolver o aplicativo responsável, em vez de tratar qualquer arquivo como binário executável. Não fornecer shell/comando arbitrário como campo de cadastro.

Para um HTML, o processo observado pode ser o navegador já existente. Decisão G09: sempre solicitar a abertura do arquivo, inclusive nesse caso. Refinamento final de G18: **não pedir nem impor navegador no cadastro de HTML local**. O usuário descreveu que a abertura pode seguir a configuração do software/projeto ou a associação padrão do Windows; o mecanismo efetivo deve ser investigado, não presumido apenas pela extensão. Abrir o item selecionado e identificar em qual navegador efetivamente abriu. Não considerar um navegador qualquer em execução como prova dessa identificação. Se abrir no Edge já em uso, usar a nova guia desse acesso; Chrome aberto não é referência equivalente. G14 permanece: nova guia, sem reutilizar guia pessoal. Não alterar associações/configuração para forçar a abertura. Fonte oficial sobre associações: [Default Programs](https://learn.microsoft.com/en-us/windows/win32/shell/default-programs).

Consequência técnica a provar: relacionar a abertura à guia/browser efetivos, mesmo quando há vários navegadores abertos ou um launcher intermediário. A presença de um processo não identifica sozinha a página de destino. Se a abertura não produzir alvo identificável, usar diagnóstico explícito conforme os critérios de avanço, sem fingir contexto válido e sem repetir a abertura automaticamente. Não tratar esse mecanismo geral como já implementado.

### Intenção explícita e suporte Browser atual

Proposta de contrato: diferenciar acessar aplicativo, abrir arquivo e acessar endereço. A Engine não precisa inferir intenção apenas do processo ou extensão: o tipo da ação e seu alvo persistido determinam se abrir o item é obrigatório. Detectar o estado e resolver o alvo continua necessário. Campo/controle visível correspondente será definido no grill me de UI.

Verificação em `browser/redrise_browser/__main__.py`: o adapter atual usa Playwright para iniciar Chromium privado com perfil persistente; possui navegação, clique, preenchimento e consulta de URL/título dentro do contexto gerenciado. Não foi encontrado nesse adapter um fluxo de conexão a Chrome/Edge arbitrários já abertos pelo usuário. Reutilizar o que existe é possível no contexto gerenciado, mas “processo do navegador já existe” não prova controle sobre suas guias. G13 define escolha entre instalados para navegar em site; G18 define identificação após abertura para HTML local. Investigar integração apropriada por browser, sem alegar que o adapter atual já atende isso e sem instalar plugins, alterar perfil pessoal ou reiniciar o navegador por suposição.

Para acessar um site, navegador já aberto pode dispensar novo processo, mas não dispensa solicitar navegação ao endereço escolhido em nova guia (G14), mesmo que outra guia já esteja no mesmo endereço. Login/autenticação é uma etapa futura separada (G15), não parte da prova de abertura.

### Pesquisa solicitada — locais de instalação dos browsers no Windows

Pesquisa em fontes primárias em 31/10/2026. Caminhos abaixo são candidatos conhecidos de descoberta, não diretórios cuja existência garante instalação utilizável. Resolver as pastas reais do usuário/sistema e as arquiteturas pertinentes; não fixar `C:` nem nome de usuário. Não confundir diretório de perfil `User Data` com executável instalado.

| Browser | Caminhos candidatos para executável | Evidência |
|---|---|---|
| Google Chrome estável | `%ProgramFiles%\Google\Chrome\Application\chrome.exe`; `%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe`; `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe` | B1/B2 |
| Microsoft Edge estável | `%ProgramFiles%\Microsoft\Edge\Application\msedge.exe`; `%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe`; `%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe` | B1 enumera essas raízes como candidatos; não afirma que todas as modalidades são padrões do instalador em todas as versões. |
| Mozilla Firefox | `%ProgramFiles%\Mozilla Firefox\firefox.exe`; `%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe` | B3 documenta pastas padrão e instalação personalizada; validar arquivo e identidade. |
| Chromium | `%LOCALAPPDATA%\Chromium\Application\chrome.exe`; para instalação por máquina, candidato sob `%ProgramFiles%\Chromium\Application\chrome.exe` | B2 documenta instalação por usuário e por máquina. Não confundir com Chromium privado empacotado pelo RedRise. |

Não limitar a descoberta a esta tabela: complementar com registros/entradas de lançamento do Windows e seleção manual já acordada. Instalações personalizadas, portáteis, Store e outros browsers não podem ser excluídos apenas por estarem fora de Program Files. B4 documenta, por exemplo, instalação standalone Vivaldi em pasta escolhida que pode não se registrar no sistema. Brave/Opera/Vivaldi e canais Beta/Dev/Canary exigem seus próprios perfis/fontes antes de incluir novos caminhos como comprovados; o conjunto inicial suportado precisa ser definido, sem expandir automaticamente os aceites funcionais para todos os produtos detectados.

Fluxo proposto de descoberta limitada:

1. Executar na estação/usuário que realizará a automação, não inferir a lista de uma estação a partir do host.
2. Consultar referências registradas, resolver caminhos e testar apenas candidatos conhecidos e itens escolhidos; não fazer busca recursiva no disco.
3. Conferir presença, acesso e identidade/versão quando consultável; deduplicar o mesmo alvo. Distinguir ausente, consulta falhou, permissão negada e encontrado. Não iniciar cada navegador apenas para montar a lista.
4. Exibir candidatos encontrados com identidade suficiente para escolha; um browser localizado não está automaticamente homologado para automação. Disponibilidade em execução continua sujeita a política/permissão real.
5. Persistir a seleção e validar novamente antes de executar; descoberta pode ser atualizada sem perder seleção ainda válida. Sem fallback automático para outro navegador.

Gatilhos sugeridos pelo usuário, ainda sem escolha final: botão de atualizar/buscar; busca ao entrar em Nova rotina com estado de carregamento; ou combinação. O controle redondo, componente shadcn, loading e posição serão fechados na etapa de UI. Evitar bloquear o app inteiro durante a descoberta; limite de tempo/cache ainda a definir.

Fontes da pesquisa, sem copiar código ou instalar ferramentas:

- B1: [Microsoft Playwright — registro dos canais e raízes de busca Windows](https://raw.githubusercontent.com/microsoft/playwright/main/packages/playwright-core/src/server/registry/index.ts), entradas `chrome`/`msedge` e `_createChromiumChannel`.
- B2: [Chromium — documentação do mini_installer](https://chromium.googlesource.com/chromium/src/+/main/chrome/installer/mini_installer/README.md), instalações por usuário/máquina e canais.
- B3: [Mozilla — instalação personalizada do Firefox](https://support.mozilla.org/en-US/kb/custom-installation-firefox-on-windows).
- B4: [Vivaldi — instalação e modalidades](https://help.vivaldi.com/desktop/install-update/install-the-vivaldi-browser/).

As fontes de código em `main` são referências consultadas nesta data, não pins de dependência nem prova de compatibilidade com a versão embarcada no app. Antes da implementação, fixar a revisão pertinente e conferir as APIs/limitações do adapter escolhido. Pesquisa de diretórios não instala, executa ou homologa browsers.

### Microetapa futura de login

Intenção confirmada: a rotina pode incluir uma etapa específica para identificar uma tela de login e preencher seus campos com credenciais vinculadas à pessoa. Esta etapa será discutida depois; não presumir login automático apenas porque uma página foi aberta nem escolher agora comportamento para CAPTCHA/MFA.

Compatibilizar com a separação de segredos já existente: guardar na rotina a referência da credencial, mantendo o segredo no cofre do sistema; não persistir senha em texto no JSON da rotina, capturas ou logs. `contracts/python/redrise_contracts/vault.py` já fornece cofre Windows para segredos do host, mas credenciais pessoais de sites, autorização e vínculo usuário/rotina ainda precisam de desenho próprio. Não alegar que esse novo fluxo está implementado. O usuário não deve fornecer credenciais nesta conversa.

Arquivo ausente, sem associação ou falha/permissão de abertura devem produzir diagnóstico explícito; não declarar sucesso por selecionar qualquer arquivo. Tipo de alvo, identidade resolvida e dados persistidos serão definidos nos contratos, sem expor essas distinções técnicas como campos obrigatórios ao usuário.

### Critérios de aceite propostos

- Ação acessar aplicativo, processo correto já presente: reutilizar e registrar evidência limitada à presença do processo; não matar nem relançar por reparação. Para abrir arquivo, enviar a solicitação de abertura mesmo com processo existente; não pular esse efeito.
- Processo ausente: solicitar abertura e observar confirmação. G33 define até 30 segundos para abertura Browser; intervalo e critério técnico completo ainda a definir. Não expandir esse prazo para todas as futuras rotinas por inferência.
- Falha de consulta não significa processo ausente; processo desconhecido não significa confirmado. Não usar apenas um PID de launcher temporário como prova do aplicativo final.
- Seleção não restringe extensão; itens que não podem ser abertos têm mensagem específica, sem fallback silencioso.
- Persistir seleção e reaproveitar em nova execução, validando que ainda resolve corretamente. Mudança de pasta/associação ou múltiplas versões precisa de política explícita.
- Separar “aplicativo acessado: processo confirmado” de “documento preparado” e de “resultado da rotina verificado”. Não certificar login, janela ou página com uma prova apenas de processo.
- Não encerrar processos do alvo nem reiniciar o sistema para resolver falhas. A relação com a regra anterior de fechar janelas próprias ao final do template será esclarecida antes de alterar esse comportamento existente.

## Decisões retiradas do escopo ativo

G08/G11/G30/G31/G32, referentes a preparação/Excel/salvamento, foram preservadas em [EXCEL-FUTURE-RULES.md](../../docs/planning/EXCEL-FUTURE-RULES.md). Não compõem formulários novos, endpoints novos nem aceites deste update Browser. IDs não serão reutilizados.

## Bloco 3 — processos e encadeamento de rotinas

Modelo confirmado: **processo → rotinas vinculadas em sequência → execução das microetapas**. Exemplo descritivo: processo “Cadastrar pedido” contém rotina “Abrir sistema”, rotina “Entrar no sistema” e rotina “Preencher pedido”. Os nomes são exemplos, não catálogo aprovado.

O controle de continuar automaticamente pertence ao vínculo/posição da rotina no processo. A mesma rotina pode participar de vários processos (G20), sem codificar globalmente qual é a próxima. Cada processo mantém sua ordem e configuração de continuação. G27 define que todos usam a alteração na próxima execução; guardar a configuração usada por cada execução para rastreabilidade não implica exigir seleção de versão no cadastro do processo.

Regra final: somente resultado **concluído e verificado**, combinado com continuação marcada e próxima rotina vinculada, permite avançar. Falha, conclusão não verificada ou efeito incerto encerram o avanço; não há retry automático ou salto. Continuação desmarcada encerra a execução após a rotina atual; não há pausa. Registrar quais rotinas não executaram e o motivo, distinguindo término configurado de falha ou falta de verificação; não anunciar que todas foram executadas quando isso não ocorreu. A hipótese de avançar com alerta amarelo foi descartada explicitamente na resposta final do usuário.

| Resultado atual | Continuar marcado | Efeito na sequência |
|---|---|---|
| Concluído e verificado | Sim, há próxima | Iniciar a próxima rotina vinculada. |
| Concluído e verificado | Não | Encerrar aqui por configuração, sem pausa. |
| Concluído e verificado | Sim, sem próxima | Encerrar por fim da sequência. |
| Concluído não verificado, incerto ou falho | Qualquer valor | Encerrar o avanço, preservar resultado e evidência; não executar a próxima nem repetir automaticamente. |

A menção inicial a um processo chamar outro é ambígua diante da explicação subsequente de checkbox por rotina dentro do processo. Não introduzir encadeamento entre processos, recursão ou ciclos como funcionalidade confirmada; esclarecer depois se necessário.

### Início, execução isolada e contexto

G22: ao executar um processo, iniciar pela primeira rotina. Aplicar os vínculos e critérios de continuação já confirmados. G23: execução isolada de uma rotina não inicia automaticamente nenhum processo que a use. G25 controla sua disponibilidade: se “Esta rotina pode ser executada isoladamente” estiver desmarcada, a execução isolada fica desabilitada e deve ser recusada também no backend/API, não apenas ocultada na interface. Nesse caso a rotina necessita do contexto anterior do processo. Exemplo confirmado: “Fazer login” depende da(s) rotina(s) predecessora(s).

A opção marcada não fabrica contexto nem ignora pré-requisitos; ainda pode haver falha de ambiente ou alvo indisponível. Não escolher janela pessoal por conta própria e não executar predecessoras silenciosamente. G29: a permissão é da rotina, em qualquer posição; não exigir que a primeira rotina esteja marcada para cadastrar ou executar o processo. Validações de pré-requisitos reais continuam distintas dessa permissão. Valor padrão da opção ainda não definido.

G26: endereço, caminho e demais valores próprios da rotina são salvos no cadastro, sem nova pergunta a cada execução. Distinguir esses valores estáveis das referências de guia/documento produzidas em tempo de execução e dos segredos mantidos no cofre. G27: ao iniciar uma execução, resolver e fixar as configurações atuais das rotinas vinculadas para aquela execução; alterações posteriores só valem em novas execuções. O mecanismo técnico de snapshot/versionamento será definido na implementação, preservando histórico existente.

G24: o contexto do processo passa entre suas rotinas como referência. Exemplo conceitual: “Abrir sistema” cria a guia; uma futura rotina “Fazer login” receberia essa referência. Login ainda não está incluído no incremento. Uma rotina explícita de abertura cria o alvo novo; a exigência de nova guia não significa uma guia adicional para cada rotina subsequente que apenas consome contexto. Não anunciar rotinas consumidoras não implementadas como entregues.

Direção técnica derivada, a detalhar nos contratos: contexto pertence a **uma execução** do processo e não à definição global de uma rotina reutilizável. Duas execuções/processos não podem trocar referências por coincidência de nome do aplicativo, URL ou arquivo. Revalidar a referência antes do próximo efeito; não adivinhar outro alvo quando a guia/documento desaparecer. A política de exclusividade de sessão existente deve ser preservada; isolamento de contexto não autoriza automações simultâneas disputando mouse/teclado.

Persistir resultado/evidência histórica não torna uma referência de janela/guia reutilizável em execução futura. O conjunto de dados do contexto e sua duração ainda serão definidos. Credenciais permanecem referências ao cofre, sem transportar senhas em logs/contexto exposto. A elegibilidade de execução isolada obedece G25; não introduzir fluxo de fornecimento manual de contexto como função já aprovada.

Critérios propostos para implementação futura: preservar ordem; executar somente a próxima vinculada quando continuação autorizada e resultado elegível; interromper na falha; registrar qual rotina executou/parou e quais não executaram; não usar checkbox para ignorar falhas; não disparar a próxima duas vezes por confirmação duplicada; aplicar alterações compartilhadas somente em novas execuções; recusar execução isolada não permitida também fora da UI. Representação das versões/configurações fica para o refinamento dos contratos, conforme G27.

## Duas etapas de grill me

1. **Funcional:** fechar comportamento das ações, condições, efeitos, verificação e falhas; começar pelas lógicas Browser/HTML, depois Excel e demais incrementos definidos.
2. **UI:** somente após encerrar o funcional, percorrer cada funcionalidade/tela. O agente sugere organização, campos, botões e estados; o usuário indica os links dos componentes shadcn escolhidos. Registrar mapeamento funcionalidade → tela → componente/link → adaptação → estados/aceite. Os blocos login/signup/sidebar já escolhidos permanecem referências, sem completar por suposição os demais componentes.

## Cadastro funcional confirmado — abrir página

Ordem e campos condicionais, com composição shadcn a definir no grill me de UI:

1. Nome da rotina.
2. Origem, seleção única: “Navegar em site” ou “Abrir HTML local”.
3. Somente para site: navegador instalado escolhido na lista.
4. Endereço do site ou caminho completo do arquivo, conforme a origem.
5. “Esta rotina pode ser executada isoladamente”.

Site tem cinco informações; HTML local tem quatro, sem seletor de navegador. Todos os valores próprios do cadastro são persistidos. A referência ao navegador/guia detectados do HTML é contexto da execução, não uma escolha a pedir ao usuário nem um browser a fixar silenciosamente para futuras aberturas. G28 mantém a guia aberta após o processo.

## Etapa atual — grill me de UI

Funcionalidades delimitadas pelo usuário como suficientes para este update. Revisar telas AS-IS/TO-BE e ações, registrar aprovação e link shadcn por item no [complemento UI](../../docs/ui/BROWSER-UPDATE-ASIS-TOBE.md). Não reiniciar perguntas funcionais respondidas; questões de UI que alterem comportamento devem ser identificadas como nova decisão.

Pendências técnicas do Browser a resolver na implementação delimitada: evidência de abertura/guia no prazo; browsers homologados versus encontrados; identificação pós-abertura do HTML; contratos de contexto e preservação de proteções existentes. UI ainda define componentes, organização de processos, gatilho/loading da descoberta, rótulos e estados. Login, chamada entre processos e outros modos não entram por essas pendências.

## Registro operacional da elaboração documental

- Task: DISCOVERY-20261031; roadmap: refinamento documental relacionado a P08/P09/P11/P13, sem concluir etapas.
- Autorização: usuário em 31/10/2026 pediu criar discovery dos pontos discutidos sobre o app.
- Produto/repo: `product:redrise-v2` / `repo:redrise-v2`.
- Root: `D:/Correnth/products/redrise-v2/repos/app`; remote esperado: `https://github.com/correnth-ai/redrise_v2.git`; branch observada: `main`; HEAD unborn, sem commit base. Todo conteúdo existente aparece não rastreado e deve ser preservado.
- Objetivo/aceite: documento com decisões confirmadas, propostas separadas, perguntas abertas, evidência e adiamentos preservados; explicar atualização e impacto shadcn/ui.
- Escrita permitida nesta elaboração: esta Work Order, mapa de regras, AS-IS/TO-BE, catálogo de componentes, referências em `docs/ui/references/`, `docs/planning/EXCEL-FUTURE-RULES.md`, checkpoint/handoff e esboços no diretório de visualizações da conversa; sem mutação de código de produção. Discovery anterior preservado como antecedente.
- Não objetivos: código, instalação de dependências/blocos, mudança de baseline/requirements/status, automação nativa, release, commit/push ou publicação.
- Fontes: solicitação atual, instruções/manifesto v2, documentação/código/evidência relevante do app e documentação oficial Microsoft, shadcn/ui e Tauri. Predecessor é a revisão conversacional de 30/10, sem promover seus checks históricos a validação nova.
- Skills: `documentation-decision-log` (SHA256 `94d7404269c6b354a8ba5e1cd0704769b7bdd648e3379f5ddc296a1696bd2d3b`) e `powershell-shell` (SHA256 `35d35be0d16fc63946923ee562365815fb62ca55ca927781f54345c85a206ab6`), lidas integralmente. Recomendações automáticas de segurança sem relação com a tarefa documental não foram aplicadas.
- Memória: workspace `correnth`, project `redrise-v2`; router retornou `MEMORY_UNAVAILABLE`; fallback em fontes canônicas. Classe normative; sem consulta ou rebuild de grafo. Sem delegação.
- Validação: leitura do documento, conferência de links locais, presença das decisões/adiamentos e validator de base. Nenhum teste funcional do produto é necessário para criação isolada de Markdown.
- Parada: documento criado e conferido, perguntas abertas entregues; nenhuma implementação autorizada por esta ordem.
- Recuperação: corrigir somente os dois documentos novos; não apagar ou reescrever material anterior.
- Revisão independente: não alegada; discovery continua aberto à revisão do usuário.
- Próxima ação vigente: handoff manual para engenharia a partir do checkpoint/prompt, com revisão das pendências técnicas e implementação por incrementos. Novo modo de automação somente Browser. O usuário poderá refinar rótulos/posições ainda propostos enquanto a UI é construída com fixtures identificadas.
- G34 concluído documentalmente: criado `docs/APP-RULES.md` em nível 1 com regras, menus, campos condicionais, efeitos esperados de ações no backend e mapa de influências. Validação: 8 links locais válidos nos dois documentos, UTF-8/cercas de código conferidos, grupos de regras/sufixos/prazo presentes; validator de base passou 341 checks. Nenhum teste funcional, UI, instalação ou alteração de código nesta tarefa.
- Conclusão documental: discovery criado com D01–D11 e perguntas abertas. `node scripts/validate-base.mjs` passou 341 checks da base (não funcionais); leitura UTF-8/link check confirmou 9 links locais válidos, decisões presentes e cercas de código balanceadas. Nenhum código, status de release ou evidência histórica alterado. Checks funcionais, UI, migração e prova instalada não executados.
- Refinamento após resposta: D12 registra sequência de ações somente Excel na primeira etapa; substituída a dúvida sobre o modelo por uma proposta de passo a passo a discutir. Limite de campos por etapa e primeiro processo real seguem abertos. Verificação documental por leitura dos trechos alterados; sem novos testes funcionais ou alteração do app.
