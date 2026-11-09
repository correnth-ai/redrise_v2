# Work Order — ajustes de uso e entrega do Beta Windows

- **ID:** TEAM-ACCOUNTS-20261108.
- **Data:** 08/11/2026. **Estado em 09/11/2026:** executada; ver seção 10 (registro de execução). **Estado no planejamento (histórico):** preparada para handoff ao agente engenheiro; implementação não iniciada nesta sessão. A submissão do prompt de execução pelo usuário inicia a construção no próximo agente.
- **Pedido:** manter uma única Work Order com os itens 1 a 11: contas, ajustes visuais, detalhes de atividade, estações, remoção de vínculos, exclusão de rotinas, Aplicativo, MediaFire, sidebar, entrega do Beta e controles de janela. ID e arquivo preservados para continuidade. O item 11 deve ser entregue antes do encerramento do item 10.
- **Autorização de entrega registrada:** o item 10 determina, após implementação e testes aprovados, commit, integração à branch principal, nova versão Beta, update do app e reconciliação documental. **Distribuição pelo MediaFire adiada por ordem posterior do usuário; item 8 fora da execução e dos gates desta entrega.** Esta rodada prepara o handoff; não executa essas operações. Não solicitar novamente autorização já fornecida para essas etapas quando a construção for iniciada; push remoto não foi explicitamente solicitado.
- **Produto / repositório:** `product:redrise-v2` / `repo:redrise-v2`.
- **Root / remote / branch:** `D:/Correnth/products/redrise-v2/repos/app` / `https://github.com/correnth-ai/redrise_v2.git` (remote autorizado pelas instruções) / `main`.
- **HEAD observado:** `991ebc5a63ebec4f47ea6181e7e17eb58604731a`; árvore com alterações da S5 e documentação associada, incluindo arquivos novos. Preservar todas as alterações existentes. Este planejamento adiciona somente este arquivo.
- **Roadmap:** ajustes de uso no contexto P13, com empacotamento/update pelo fluxo existente; não reabre nem substitui a S5.
- **Referência visual:** imagem fornecida pelo usuário nesta conversa, `codex-clipboard-482c469e-b86f-4fb1-b1e0-c5409553becb.png` (beta.28). A posição indicada é descrita abaixo, sem depender da permanência do arquivo temporário.

## 1. Escopo solicitado

### 1.1 Botão + Nova Conta

- Em **Configuração › Equipe**, substituir “Adicionar” por **“+ Nova Conta”**, usando o ícone de adição e o padrão visual de “+ Nova Rotina”.
- Posicionar no canto inferior direito da área “Meu perfil”, acima da tabela de usuários, conforme o retângulo indicado pela seta amarela na imagem. Manter espaçamento, sem sobrepor dados; adaptar em janela estreita.
- Remover o formulário horizontal de cadastro abaixo da tabela. O cadastro passa a começar exclusivamente pelo novo botão nessa tela.
- Preservar a restrição atual de gestão de contas a administradores; operadores não recebem a ação nem permissão via API.

### 1.2 Cadastro em quatro etapas

Reaproveitar o padrão de página e navegação de **Rotina › Lista › + Nova Rotina**, sem acoplar o cadastro à execução de rotinas nem criar um framework genérico de wizard.

| Etapa | Campo | Comportamento |
|---|---|---|
| 1 | Nome | Obrigatório; rejeitar somente espaços; representar o nome completo da pessoa. |
| 2 | E-mail | Obrigatório; validar formato e unicidade conforme as regras do Core. |
| 3 | Senha | Campo mascarado; manter mínimo vigente de 8 caracteres, sem checklist adicional. |
| 4 | Confirmar Senha | Campo mascarado; deve coincidir com a senha. Ação final “Criar conta”. |

- Um campo por etapa, exatamente nessa ordem. Exibir progresso e ações Voltar, Continuar e Cancelar no padrão existente.
- Voltar preserva os valores apenas na memória do fluxo. Cancelar não cria conta; cancelar ou concluir limpa as senhas do estado do formulário.
- Validar antes de avançar e validar novamente os dados necessários no servidor ao salvar. Não persistir contas parciais entre etapas.
- Durante o envio, impedir submissões duplicadas e mostrar estado ocupado. Erro preserva o contexto para correção; sucesso só após confirmação do Core.
- Ao concluir, retornar à Equipe e atualizar a lista com nome, e-mail e estado reais. Cadastro e login permanecem locais ao Core, sem e-mail de confirmação nem serviço externo.
- **Complemento confirmado pelo usuário:** toda conta criada por “+ Nova Conta” deve permitir login com o e-mail e a senha cadastrados imediatamente, sem ativação adicional. Desativação/exclusão posteriores continuam retirando o acesso. Testar logout/login e persistência após reinício, sem usar a sessão do administrador como prova do login da nova conta.
- Não registrar senha/confirmar senha em logs, evidências, armazenamento do navegador ou notificações. A confirmação não é um atributo persistido da conta.

### 1.3 Exclusão de conta inativa

- Conta ativa: manter **Desativar**, sem lixeira.
- Após desativação confirmada pelo Core: mostrar **Reativar** e, ao lado, uma lixeira com nome acessível/tooltip **“Excluir conta”**.
- O mesmo vale para contas que já estavam inativas ao abrir a tela.
- Clicar na lixeira abre confirmação simples, identificando a conta, com **Cancelar** e **Excluir conta**. Cancelar não altera nada.
- Excluir deve realizar uma operação persistente no Core; remover a linha apenas depois do sucesso. Falha mantém a conta visível e apresenta diagnóstico.
- O servidor deve exigir administrador e reler o estado inativo na transação. Uma conta reativada por outra sessão não pode ser excluída usando uma tela desatualizada.
- Conta excluída não pode autenticar, ser reativada ou continuar usando sessões anteriores. Preservar a proteção do último administrador ativo.

## 2. Propostas técnicas a fechar no refinamento

Os comportamentos acima são pedidos do usuário. As decisões abaixo são propostas para viabilizá-los, ainda sujeitas ao refinamento desta Work Order:

1. **Sem campo “Usuário”:** gerar o identificador interno no Core, reaproveitando a normalização e resolução de colisões do cadastro local existente; permitir login pelo e-mail. Não modificar identificadores de contas existentes.
2. **Sem campo “Perfil”:** propor novas contas como **Operador**, que já é o padrão do formulário atual; não acrescentar um quinto passo nem conceder administrador implicitamente. A criação como conta ativa e apta a login está confirmada pelo complemento do usuário. O cadastro público continua com sua ativação atual, separado deste fluxo.
3. **Exclusão com histórico preservado:** propor exclusão lógica definitiva da conta, distinta de desativação: sai da lista gerenciável, não volta por Reativar e não pode acessar o app; referências históricas continuam válidas. A base possui vínculos de usuários com execuções, revisões e agendamentos. Não executar exclusão em cascata desses dados. Essa proposta não equivale à eliminação física de dados pessoais.
4. **E-mail de conta excluída:** propor manter reservado nesta primeira entrega, com mensagem clara se houver tentativa de reutilização; decidir isso expressamente antes de implementar. Nunca vincular automaticamente uma nova pessoa ao histórico anterior.
5. **Vínculos da S5:** conta excluída deve continuar inelegível como dona de agendamento; manter pausa/aviso e a retomada explícita por administrador conforme a S5. Não transferir propriedade nem repetir execuções automaticamente. Verificar também revisões pendentes, sem apagá-las ou aprová-las por exclusão de conta.

## 3. Fontes e dependências verificadas

- `desktop/src/features/configuracoes.tsx`: hoje há formulário inline com Usuário, Nome, Senha e Perfil; alternância Desativar/Reativar, sem lixeira.
- `desktop/src/features/routine-wizard.tsx` e `desktop/src/features/processos.tsx`: referência de navegação/apresentação de Nova Rotina.
- `core/redrise_core/service.py`: `create_user` exige username/display/password/role; o cadastro local `register` já recebe nome/e-mail/senha e gera username, mas cria operador inativo. Não trocar um endpoint pelo outro sem preservar as diferenças.
- `core/redrise_core/migrations/`: referências de usuários em sessões, rotinas, processos, execuções, revisões e `010_schedules.sql`.
- `docs/APP-RULES.md`, `AGENTS.md`, `delivery/status.json` e `delivery/work-orders/SCHEDULE-PROCESS-20261107.md`: registram beta.28 instalada e S5 concluída localmente em 08/11, sem publicação. Estado documental consultado; esta tarefa não revalidou a instalação.
- Antes de implementar: reler HEAD, alterações locais, evidência `delivery/evidence/SCHEDULE-PROCESS-20261107/increment-2.json` e registrar seu SHA256 no checkpoint de execução. Não atribuir evidência da S5 a esta entrega.

## 4. Sequência de construção proposta

1. Refinar as propostas técnicas pendentes, reler estado/contratos e preservar o trabalho da S5.
2. Implementar contas e login (item 1), depois proteção/status/exclusão de estações (item 4).
3. Corrigir remoção de vínculos e exclusão de rotinas no Core e UI (itens 5 e 6), com tratamento explícito de dependências.
4. Aplicar os ajustes visuais e de interação dos itens 2, 3, 7, 9 e 11; verificar temas claro/escuro.
5. Executar testes localizados e prova integrada dos itens 1–7, 9 e 11 em candidato/equipe sintética; preparar instalador e artefatos do update local do item 10. Item 8 adiado.
6. Executar a sequência de entrega do item 10, sob a autorização já registrada, somente após os gates. Registrar falhas e não declarar versão oficial concluída antes do update e da documentação.

## 5. Critérios de aceite e verificações previstas

- **UI:** posição e rótulo corretos; ausência do formulário antigo; quatro passos na ordem; avanço/retorno/cancelamento; campos inválidos; senhas divergentes; estado ocupado; erro e sucesso real; navegação por teclado e nomes acessíveis.
- **Criação/Core:** administrador cria uma única conta com nome/e-mail corretos; login pelo e-mail com a senha definida; e-mail duplicado e senha inválida rejeitados; operador e requisição sem sessão recusados; contas antigas continuam funcionando.
- **Exclusão/Core:** ativa não pode ser excluída, inclusive por chamada direta; inativa pode após confirmação na UI; cancelar preserva a conta; sessões revogadas; exclusão permanece após recarregar/reiniciar; reativação concorrente não permite exclusão indevida.
- **Integridade:** excluir conta com histórico não apaga rotinas/processos/execuções/revisões; agendamentos não executam em nome da conta excluída; proteção do último administrador permanece. Verificar a política de reutilização de e-mail escolhida.
- **Checks:** `node scripts/validate-base.mjs`; typecheck e testes de componente via scripts efetivos de `desktop/package.json`; testes de contrato Core/PostgreSQL isolado conforme o harness existente. Registrar comandos exatos e resultados na execução, sem instalar dependências ou inventar provas antecipadamente.
- **Prova prática posterior:** criar conta sintética pelo wizard, verificar login, desativar, cancelar uma exclusão, confirmar outra e reabrir a lista. Usar janela real para validar posição e usabilidade; mocks não provam persistência.

## 6. Limites, write-set e recuperação

- **Agora:** somente `delivery/work-orders/TEAM-ACCOUNTS-20261108.md`.
- **Implementação futura proposta:** `desktop/src/features/{configuracoes,processos,legacy}.tsx`, componente de wizard de conta e navegação estritamente necessária, `desktop/src/components/{data-table,app-sidebar}.tsx`, estilos/componentes de sidebar pertinentes, `desktop/src/data/`, integração local Tauri se necessária para identificar a estação atual, testes correspondentes, `core/redrise_core/{api,service}.py`, nova migração se necessária, testes Core e contratos/máscara de diagnóstico afetados. Entrega: manifests de versão existentes em desktop/Core/Runner conforme componentes alterados, scripts de empacotamento/update somente quando necessário; `docs/APP-RULES.md`, `docs/ui/LIVE-TABLES.md`, decisões de contratos afetadas, `AGENTS.md`, `delivery/status.json` e evidência/checkpoint próprios. Não editar migrações já aplicadas. Delimitar arquivos exatos no início da implementação.
- **Fora do escopo atual:** recuperação de senha, implementação/homologação de VPN/LAN, Mac, site, identidade externa, novos perfis de acesso, mudança funcional do wizard de rotinas, reexecução da S5 ou outros itens da discussão anterior não solicitados nesta WO. MediaFire/publicação externa estão adiados; empacotamento e update Windows do item 10 permanecem incluídos.
- **Dados:** somente sintéticos em testes; nenhuma conta real será criada, desativada ou excluída por este planejamento. Nenhum segredo em Git.
- **Recuperação:** alterações locais isoladas do trabalho existente; antes de testar migração, snapshot/backup da base sintética. Rollback de esquema somente com procedimento compatível e cópia anterior, sem apagar banco nem desfazer mudanças de outros autores.
- **Parada:** nesta sessão, encerrar após preparar o documento e o prompt. No próximo agente, a submissão do prompt autoriza a construção; registrar a resolução das propostas da seção 2 antes das mudanças correspondentes. Na execução, parar a ação afetada diante de perda de integridade, autorização ausente ou efeito incerto; não repetir exclusão cegamente. Distribuição adiada não é bloqueio.
- **Revisão:** revisar autorização, vínculos históricos e concorrência da exclusão antes de considerar a entrega concluída; revisor não designado.

## 7. Rastreabilidade do planejamento

- Classe: `normative` (elaboração de plano), com leitura pontual de código; fontes canônicas diretas, sem consulta ou rebuild de grafo.
- Skill aplicada: `scope-planning`, resolvida pelo catálogo corporativo, SHA256 `fd7b13af53a7853d7cbd43ac9f72e801d602c7fb4e592981ac4842e4ded58bfa`.
- Router completo indisponível por dependência `networkx` ausente; usada a função de seleção do próprio router, sem instalar pacotes. Selecionada somente a capacidade pertinente ao planejamento.
- Memória consultada no escopo explícito `workspace=correnth`, `project=redrise-v2`: indisponível (`MEMORY_UNAVAILABLE`); fallback para fontes primárias. Captura automática permanece desabilitada.
- Reavaliar skills na implementação e diante de alteração de contrato, nova dependência, falha de ambiente ou ampliação material de escopo. Sem delegação nesta tarefa documental.
- **Próxima ação:** agente engenheiro recebe o prompt do usuário, lê esta WO e fontes aplicáveis, verifica o estado real e executa os itens ativos até o encerramento do item 10. Item 8 permanece adiado.

## 8. Complemento de escopo — itens 2 a 11 do usuário

A numeração abaixo corresponde ao pedido, não às seções técnicas anteriores. As seis imagens adicionais são referências visuais da beta.28; os requisitos estão descritos aqui para não depender de arquivos temporários.

### Item 2 — fundo da coluna Ações em Rotina › Lista

- Igualar o fundo da área de botões ao restante da respectiva linha/cabeçalho nos temas claro e escuro. Eliminar a faixa mais clara da coluna Ações.
- Preservar comportamento da coluna fixa, legibilidade, hover e seleção; linha selecionada deve ter o mesmo fundo também nas ações. Usar tokens existentes, sem cores fixas para apenas um tema.
- **Aceite:** comparação visual nos dois temas, normal/hover/selecionada e com rolagem horizontal; sem conteúdo aparecendo por baixo da coluna fixa.

### Item 3 — detalhes de Execuções técnicas

- Em Rotina › Atividade, adicionar botão de olho no fim de cada linha de Execuções técnicas. Somente esse botão (inclusive Enter/Espaço quando focado) abre/fecha os detalhes; clicar no restante da linha não altera a visualização.
- **Interpretação registrada:** visível = olho sem risco; oculto = olho com risco. O pedido escreveu “sem risco” para ambos os estados; esta interpretação segue a alternância mostrar/ocultar mencionada pelo usuário e pode ser corrigida no refinamento.
- Tooltip/nome acessível “Mostrar detalhes” ou “Ocultar detalhes” e `aria-expanded` coerente. Clicar novamente oculta; selecionar outro olho mostra os detalhes da execução correspondente, sem alterar qualquer execução.
- **Aceite:** linha não abre detalhes; olho alterna estado e ícone; os detalhes pertencem à linha escolhida; teclado funciona; nenhuma requisição de execução é disparada.
- **Fonte:** bloco existente em `desktop/src/features/legacy.tsx`.

### Item 4 — estações: exclusão, proteção da estação atual e Status

- Estação revogada deve oferecer lixeira **Excluir estação**, apenas ao administrador, com confirmação. API também exige administrador e estado revogado; falha não remove a linha.
- Não permitir revogar a estação em que a sessão atual do app está sendo usada, inclusive pelo administrador. Mostrar “Esta estação” e ação indisponível com motivo claro. A mesma proteção vale para excluí-la caso já apareça revogada, evitando remover a estação em uso.
- Distinguir conta (`admin.lab`), sessão de login e registro da estação. Não identificar a estação atual pelo nome da conta, hostname livre ou simples igualdade com o servidor. Identificar pelo vínculo autenticado/instalação local; proteger a API contra omissão ou falsificação desse vínculo. Se o contrato atual não permitir isso, implementar a extensão mínima e testá-la.
- Incluir coluna **Status**, separada de **Estado**: Online/Offline representa conectividade real, enquanto revogada/pronta/aguardando representam autorização/prontidão. Online não significa pronta para executar.
- Reaproveitar heartbeat e atualização existentes, sem serviço novo. Hoje o Core calcula online por heartbeat nos últimos 45 s; registrar cadência de atualização da tela e limite observável de detecção. Atualizar sem recarregar manualmente, inclusive quando o tempo expira sem evento novo.
- Servidor inacessível ou falha de leitura deve mostrar estado desconhecido/diagnóstico, não inventar Offline para todas as estações. Estação revogada não deve ser apresentada como conexão válida por um heartbeat antigo.
- Futuras estações cadastradas pela VPN usarão o mesmo Status; configurar VPN não faz parte desta WO.
- Preservar referências de histórico/agendamentos ao excluir estação. Proposta KISS: exclusão lógica do inventário, credenciais revogadas, sem apagar execuções; agendamentos não podem disparar nela. Não recuperar automaticamente a estação já revogada da imagem nesta tarefa.
- **Aceite:** administrador exclui revogada sintética; operador/API sem autorização são recusados; atual não pode ser revogada/excluída; outra estação pode ser revogada; Online muda para Offline no limite documentado e retorna após heartbeat válido; indisponibilidade de leitura é distinta; histórico permanece consultável.

### Item 5 — remover qualquer rotina de um processo

- No editor de Processo › Ação, permitir remover qualquer vínculo, inclusive o primeiro e o único, e salvar. Remover do processo não exclui a rotina de Rotina › Lista nem a retira de outros processos.
- Eliminar o bloqueio atual da primeira rotina tanto na interface (`locked`) quanto no contrato do Core que recusa essa edição. Este pedido altera a regra anterior que exigia aprovação para substituir a etapa 1; reconciliar os documentos/testes desse comportamento especificamente para a remoção solicitada.
- Manter ordem relativa das demais rotinas, renumerar posições e preservar suas opções de continuação. Permitir salvar processo vazio.
- Uma rotina de continuação pode depender do contexto de uma etapa removida. Permitir salvar a composição, mas bloquear a execução manual/agendada de composição inválida com motivo claro, sem promover uma continuação a rotina inicial nem executar parcialmente. Revalidar quando a composição voltar a ser válida.
- Execuções em andamento e histórico preservam seu snapshot; a edição afeta próximas execuções. Tratar pedidos de alteração pendentes sem aplicá-los sobre uma composição incompatível.
- **Aceite:** remover primeira/intermediária/última/única, salvar e reabrir; Cancelar preserva composição; rotina compartilhada permanece nos outros processos; processo vazio ou com início incompatível não executa; histórico e execução iniciada não mudam.

### Item 6 — excluir rotinas em Rotina › Lista

- Tornar exclusão individual e em seleção múltipla funcionais, inclusive para rotinas vinculadas. “Excluir 0” não pode aparecer quando há uma rotina selecionada elegível para essa ação.
- Reutilizar arquivamento persistente existente quando suficiente para remover a rotina do catálogo ativo sem destruir histórico. Não apenas habilitar o ícone: ajustar também a recusa atual do Core.
- A confirmação informa os processos afetados e que a rotina será retirada deles. Confirmar remove seus vínculos dos processos futuros e exclui/arquiva a rotina; cancelar preserva ambos. Aplicar as regras do item 5 para composições vazias ou dependentes de contexto.
- Por rotina, remoção de vínculos e arquivamento devem ser atômicos. Para seleção múltipla, se mantida a operação sequencial atual, informar exatamente o que foi excluído e o que falhou/ficou pendente; atualizar a seleção com os remanescentes, sem alegar sucesso total.
- Preservar versões/snapshots usados por execuções em andamento e históricas. Se houver impedimento real de segurança/transação, informar o motivo e permitir concluir a exclusão quando resolvido, sem bloqueio permanente só por haver vínculo.
- Preservar a permissão administrativa atual, também na API; não criar exclusão de arquivos externos ou dos efeitos de uma rotina.
- **Aceite:** excluir avulsa, vinculada a um processo, vinculada a vários e seleção mista; verificar contagem, listas e vínculos após recarregar; validar cancelamento, erro parcial e falta de permissão; garantir que próximos agendamentos não executem composição inválida e que históricos continuem legíveis.

### Item 7 — reorganizar Configuração › Aplicativo

- Remover da tela o bloco **Navegador do RedRise**, incluindo campo de endereço e botão Abrir, circulado em vermelho/rosa. Isso não autoriza remover o motor de navegador usado pelas automações.
- Mover o conteúdo de **Sobre** (versão, instalação, manifesto e dados) para dentro do bloco superior **Servidor da equipe**, abaixo das informações de conexão, como na seta amarela; eliminar o card separado de Sobre.
- Em instalação somente-estação, preservar a exibição de Sobre em bloco superior apropriado mesmo quando o card de servidor local não existir; não sugerir que uma estação remota é o servidor.
- Subir o bloco de armazenamento para imediatamente abaixo dos cards superiores, ocupando o espaço liberado, mantendo valores reais e layout responsivo.
- **Aceite:** sem bloco Navegador nem card Sobre isolado; metadados e armazenamento continuam reais e visíveis; layout correto nos dois temas e papéis host/estação. Não suprimir diagnósticos de autenticação existentes apenas para limpar a tela.

### Item 8 — distribuição pelo MediaFire — ADIADO

- Por ordem posterior do usuário, não fazer upload, criar link público, configurar conta ou publicar o instalador no MediaFire nesta entrega.
- Preservar o número para rastreabilidade. Nenhum aceite de distribuição pública integra o completion gate atual; sua ausência não bloqueia commit, integração, empacotamento, update local ou documentação.
- Retomar distribuição somente por nova solicitação. Preparar instalador e registrar versão/hash para o update do item 10 continua no escopo.

### Item 9 — hierarquia visual da sidebar

- A linha de hierarquia deve partir de **Empresa**, passar por **Processo** e **Rotina**, e terminar antes de **Configuração**.
- Empresa fica visualmente no nível principal; Processo e Rotina ficam no nível abaixo; Ação/Histórico/Kanban e Lista/Atividade ficam no terceiro nível.
- Configuração permanece no nível principal, separado de Empresa, com Equipe/Estação/Aplicativo abaixo dele.
- Alteração visual: preservar rotas, permissões, cliques, estado ativo, sidebar recolhida e nomenclatura atual singular **Empresa**. Não introduzir agrupamento de dados por empresa ou novos menus.
- **Aceite:** hierarquia evidente em ambos os temas; Configuração fora da linha de Empresa; todas as rotas e navegação por teclado continuam acessíveis; modo recolhido mantém ícones/tooltips úteis.

### Item 10 — testes, commit, integração, Beta e update

Autorização condicional do usuário já registrada: executar a entrega depois que os itens anteriores estiverem implementados e testados. Não marcar nenhuma etapa concluída por existência de arquivos ou teste apenas simulado.

1. Fechar testes de componentes/contratos e prova prática dos itens 1–7, 9 e 11, com equipe sintética. Item 8 adiado. Conferir regressões relevantes da S5, autenticação, histórico e dados reais; nenhum teste destrutivo em contas/rotinas reais.
2. Definir a próxima versão livre do Beta a partir do estado real de entrega. Não fixar beta.29 apenas porque as imagens mostram beta.28. Sincronizar manifests de versão antes do commit/build; registrar versões efetivas de Core/Runner, sem incrementos fictícios de componentes não alterados.
3. Fazer commit do conjunto revisado e integrar à branch principal do app (`main`), preservando alterações de terceiros. Se já estiver em main, registrar que a integração está satisfeita pelo próprio commit; não criar merge artificial. Separar dependências S5 existentes de alterações não relacionadas, sem descartá-las nem incorporá-las indiscriminadamente. Registrar SHA; push remoto fica fora desta autorização explícita.
4. Produzir/validar o instalador e artefatos de update rastreáveis ao commit integrado; repetir os checks afetados se a integração alterar conteúdo. Executar o gate de candidato e prova de atualização/rollback em cópia conforme o fluxo existente; preparar backup recuperável antes de migração.
5. Preparar o instalador aprovado e registrar caminho, versão e SHA256; atualizar o canal local de update existente com os artefatos e assinatura exigidos pelo mecanismo. Sem publicação externa ou MediaFire.
6. Atualizar a instalação real pelo mecanismo de **update** solicitado. Verificar no app reaberto a nova versão, login, preservação de dados e funções modificadas; registrar o resultado efetivo. Coordenar a janela de interação se o computador estiver em uso; não interromper trabalho do usuário.
7. Reconciliar toda a documentação afetada: regras do app, contratos alterados, tabelas reais, instruções locais, status, aceite/versão corrente, instruções de update e evidências/checkpoint da WO. Registrar versão construída e instalada, deixando distribuição pública como adiada; “Beta oficial” designa a versão validada para este canal local, não publicação externa nem homologação irrestrita/VPN. Preservar registros históricos.
8. Se a prova de update produzir documentação posterior ao commit inicial, fazer commit documental complementar sob esta mesma ordem, mantendo rastreabilidade com o commit da build. Não alterar artefatos já publicados silenciosamente.

**Completion gate:** itens 1–7, 9 e 11 comprovados; commit integrado identificado; instalador local validado com hash conferido; canal local e update comprovados; app real na versão esperada; documentação canônica coerente. Item 8 adiado, sem bloqueio. Falha em uma etapa ativa mantém essa etapa pendente, sem apagar evidências anteriores ou declarar conclusão total.

### Item 11 — controles de janela no estilo macOS

- Referência: imagem `codex-clipboard-a19e19d4-070f-40c7-8bdd-acae36bb4322.png`, fornecida pelo usuário. Substituir a aparência dos três controles atuais por pequenos círculos coloridos no estilo da referência, mantendo o conjunto no canto superior direito e o restante da barra na posição atual.
- Ordem obrigatória da esquerda para a direita: **verde → amarelo → vermelho**. Associar as funções às cores da referência: **verde = maximizar/restaurar; amarelo = minimizar; vermelho = fechar**. Assim, os dois primeiros controles trocam de ordem funcional em relação ao layout atual; não usar verde para minimizar apenas para conservar a ordem antiga.
- Tons-base de implementação: verde `#28C840`, amarelo `#FEBC2E`, vermelho `#FF5F57`; conferir visualmente com a referência nos temas claro e escuro. Não usar as cores semânticas genéricas do tema quando alterarem esses tons.
- Manter proporções/espaçamento próximos da referência, com área clicável confortável e foco visível. Os círculos substituem os ícones atuais; estados de hover/foco podem revelar símbolos discretos sem mudar a ordem ou a função.
- Preservar nomes acessíveis e tooltips **Maximizar/Restaurar**, **Minimizar** e **Fechar**, para que a identificação não dependa somente de cor. Preservar arraste e duplo clique da barra; clique nos controles não inicia arraste.
- Mudança visual e de ordem apenas: usar as chamadas nativas existentes, sem adotar fullscreen do macOS, mudar o comportamento de fechamento do host ou adicionar suporte a Mac.
- **Write-set complementar:** `desktop/src/components/window-chrome.tsx`, estilos e testes diretamente associados. Não alterar lifecycle/Core/Runner para imitar o macOS.
- **Aceite:** ordem e tons corretos à direita nos dois temas; verde maximiza e restaura, amarelo minimiza e vermelho fecha conforme o comportamento vigente; verificar funções em janela nativa de laboratório, além dos testes de componente. Testar teclado/foco/tooltips e ausência de regressão no arraste. Não fechar a instalação real durante a elaboração desta WO.
- **Dependência de entrega:** este item integra o mesmo candidato e os testes obrigatórios antes de commit/integração/update do item 10; não é uma alteração posterior à versão oficial.

## 9. Execução — decisões registradas antes da implementação (08/11/2026)

Execução iniciada por ordem do usuário: itens 1–7, 9 e 11 e entrega do item 10; item 8 adiado. Estado conferido antes de editar: repo `D:/Correnth/products/redrise-v2/repos/app`, branch `main`, HEAD `991ebc5`, árvore com a S5 sem commit (preservada); `delivery/evidence/SCHEDULE-PROCESS-20261107/increment-2.json` SHA256 `07ec1d13cac1b2bebb3f77a77462521826ea00e85c49d053d60de5b6430a78b6` (evidência da S5, não desta entrega). Última versão gerada: `0.1.0-beta.28` (pasta de release e canal local); nenhuma beta.29 existente.

Propostas da seção 2 e itens 4–6, fechados assim:

1. **Usuário interno:** gerado no Core a partir do e-mail, com a mesma normalização e resolução de colisão do cadastro local (função única). Identificadores existentes não mudam. Login por e-mail ou usuário, como hoje.
2. **Perfil:** conta nova é **Operador** e **ativa** (login imediato). Rota nova `POST /api/v1/accounts` (nome, e-mail, senha), só administrador. O cadastro público `register` continua criando conta inativa.
3. **Exclusão de conta:** lógica (`users.deleted_at`, migração 011). Só conta inativa, relida com `FOR UPDATE` na transação (a reativação trava a mesma linha); sessões revogadas; sai da lista e de `members`; Reativar recusa; login recusa (conta inativa). Nada em cascata: rotinas, processos, execuções, revisões e agendamentos continuam apontando para a mesma linha. `DELETE /api/v1/users/{id}`. Código novo `ACCOUNT-ACTIVE`.
4. **E-mail de conta excluída:** fica reservado nesta entrega. Criar conta com ele é recusado com `ACCOUNT-EMAIL-RESERVED`; nunca vincula a pessoa nova ao histórico anterior.
5. **Vínculos da S5:** sem mudança de regra: o disparo relê o dono (inativo/excluído pausa com `owner_not_allowed`); revisões pendentes da conta excluída ficam pendentes (não aprovadas nem apagadas) e seguem a troca de responsável já existente.
6. **Estação atual:** a sessão de login guarda a estação de onde entrou (`sessions.station_id`, migração 011). O desktop envia no login o token da estação local, lido pelo próprio app do cofre do Windows (nunca exibido nem gravado); o Core só vincula se o token for de uma estação não revogada. Revogar ou excluir estação exige sessão vinculada (`STATION-SESSION-UNBOUND`, protege contra omissão) e recusa a própria estação (`STATION-IN-USE`); falsificação exige o token da estação. A lista de estações devolve `current`.
7. **Exclusão de estação:** lógica (`stations.deleted_at`), só revogada (`STATION-NOT-REVOKED`), `POST /api/v1/stations/{id}/remove`, administrador. Sai do inventário; execuções e agendamentos mantêm a referência; agendamentos nela continuam pulando (estação revogada). O nome deixa de ser único só entre estações excluídas (índice parcial), para a mesma máquina poder entrar de novo.
8. **Status da estação:** `online` só para estação não revogada com heartbeat nos últimos 45 s. A tela Estação relê a cada 10 s enquanto visível: Online→Offline aparece em até ~55 s sem sinal; falha de leitura mostra Status "Desconhecido" com o diagnóstico, nunca Offline inventado.
9. **Remoção de vínculos (item 5):** salvar a composição só pede aprovação se a etapa 1 atual **continua** no processo e deixa de ser a primeira (troca disfarçada); removê-la é livre. Processo vazio é salvo. Execução manual ou agendada de processo vazio ou começando por follow-up é recusada com `PROCESS-START-INVALID` (o agendamento pausa como `process_unavailable`, como na S5). Pedido de substituição da etapa 1 pendente que ficou incompatível (etapa 1 mudou ou rotina nova saiu) é cancelado na mesma transação, nunca aplicado.
10. **Exclusão de rotinas (item 6):** arquivamento existente, agora atômico com a retirada da rotina de todos os processos (posições renumeradas, continuações preservadas, mesmas regras do item 5). Rotinas do processo pronto Boas-vindas continuam protegidas. Seleção múltipla segue sequencial, com relatório do que foi excluído e do que falhou. `ROUTINE-IN-USE` deixa de ser emitido.

Write-set efetivo: o da seção 6 mais `desktop/src/features/account-wizard.tsx` (novo), `desktop/src/state.tsx` não muda, `desktop/src-tauri/src/{lib,vault}.rs` e `Cargo.toml` (feature `Win32_Security_Credentials` do `windows-sys` já usado; sem crate nova), `core/redrise_core/migrations/011_team_accounts.sql`, `tests/core/test_team_accounts.py`, testes de UI correspondentes e uma prova prática em `proofs/team-accounts/`.

## 10. Registro de execução (08–09/11/2026)

- **Estado:** itens 1–7, 9 e 11 implementados e comprovados; item 10 executado até o update da instalação real; item 8 adiado. Detalhes: [checkpoint](../checkpoints/TEAM-ACCOUNTS-20261108.md) e [evidência](../evidence/TEAM-ACCOUNTS-20261108/evidence.json).
- **Commits (main local, sem push):** `ddd42e2` S5 registrada à parte; `880662e` esta WO (fonte do instalador); `d8682b8`, `fa9347b` prova prática; mais o commit documental que traz este registro.
- **Versão:** 0.1.0-beta.29 (Core 0.3.8, Runner 0.3.11 inalterado), instalador SHA256 `6dedaf96867d6b67066743a74fab54e47683cb7d69e9475e75626d78405aa6e7`; gate aprovado; prova prática com os 11 cenários aprovados; rollback para a beta.28 numa cópia aprovado.
- **Canal e instalação real:** `latest.json` assinado para a beta.29; a instalação real foi atualizada pelo update do app (beta.28 → beta.29) em 09/11 01:35, com backup antes da migração e Core 0.3.8.
- **Completion gate:** atendido exceto pela verificação de login e dados na equipe real, que depende das credenciais do usuário (pendente). Encontrado antes do update e fora desta WO: a estação do servidor real já estava revogada; não foi recuperada (seção 8, item 4).
