# Baseline — RedRise v2

ID: `redrise-v2-baseline-20261024`. Revisão: 27/10/2026. Estado executável e provas em delivery/status.json; preservar trabalho já registrado de Engine/Excel. U27 atualiza testes/diagnóstico, sem declarar novas funções implementadas. Fontes e suplementos em [sources.lock.json](sources.lock.json); última instrução específica prevalece no seu escopo.

## Identidade nova

U24-NEW: produto novo `product:redrise-v2`, com mesmo nome comercial RedRise, remote `correnth-ai/redrise_v2` e root própria. Nenhuma migração de dados, feature, contrato ou dependência do produto anterior é presumida. Nenhuma evidência antiga é homologação do v2. Materiais históricos homônimos não são esta root.

U24-LOGO: o usuário autorizou reaproveitar os arquivos de logo existentes em 24/10/2026. Somente a seleção registrada em `assets/brand/redrise/provenance.json` foi copiada. Isso não incorpora código, UI, tema completo, fontes instaladas, licenças de dependências ou decisões do produto anterior.

No manifesto organizacional, `ownership_ref.registry` usa o identificador lógico `registry/ownership.yaml` exigido pelo schema corporativo existente. Sua resolução explícita está em `dependencies.governance.ownership_registry`: `system/registry/ownership.yaml`, único arquivo canônico. Não existe segundo registry e o alias não é um path relativo da aplicação. O owner do produto continua não designado; isso não bloqueia o estabelecimento local autorizado.

## Direção vigente — U26 e requisitos originais compatíveis

- U26-ENGINE altera D02/D08/D10/D11 e o vínculo upstream de D23/D48: **Engine própria, escrita do zero, integrante do RedRise**, com estudo/engenharia reversa delimitados e SOLID. U26-INVESTIGATION exige investigar OpenAdapt usando o catálogo indicado, sem torná-lo executor/compilador/qualification obrigatório. [ENGINE.md](ENGINE.md) define fronteiras, métodos, exclusões e I00/E01–E04; o [plano preparatório](ENGINE-INVESTIGATION-PLAN.md) orienta a pesquisa.
- D01/D08–D13 efetivos: app B2B e Excel Microsoft 365 desktop/Windows 11; U27 substitui a exigência de prova completa antes de UI por capacidades/checks localizados e campanha prática depois do closed beta instalado; preencher pela UI, salvar XLSX e verificar persistência usando a Engine própria. Proibição genérica de inferência própria e Flow publicado-primeiro foram substituídos; inferência avançada/parametrização não são requisitos da primeira fatia nem autorização implícita para cloud/serviços pagos.
- D07 e U26-ENGINE: SOLID em captura/finalização, IR/compilação, execução, verificação e plataforma/lifecycle, com Core/Runner distintos. Não copiar fork completo e chamá-lo original. Eventual código externo exige proveniência/obrigações e escopo explícitos.
- D14–D23/D34: Tauri, TypeScript Vanilla, npm, Vanilla UI, Rust nativo e Core/Runner Python desacoplados. Sidebar expansível; menus literais **Rotina, Ação, Configuração**; sem Motores nem gestão completa de agentes/goals/heartbeat na primeira interface.
- D04–D06/D40–D41: equipe/LAN desde o início, uma equipe por servidor, PostgreSQL compartilhado, vários usuários/máquinas, login/senha administrador/operador e primeiro administrador no setup. Host pode também executar na sessão de usuário.
- D26–D33/D47 e D48 efetivo: Windows x64 primeiro; Python privado sem seletor global/pip manual; dependências completas. Playwright/Chromium privados compatíveis, separados de WebView2. Windows inclui adapter próprio/componentes realmente necessários com lifecycle automático, sem WAA/uiautomation/comtypes upstream obrigatórios. U27 permite validar no ambiente próprio disponível ou outro usuário; sem requisito de PC formatado, Windows limpo ou VM.
- U25-INSTALL-DIR reafirmado por U26-INSTALL: instalação Windows por usuário, padrão, sem escolha obrigatória de pasta, em `%LOCALAPPDATA%\Programs\@redrise` (ex.: `C:\Users\{user}\AppData\Local\Programs\@redrise`). App, Engine, runtime e dependências juntos; dados/configuração/evidências/cofre separados dos binários. Cliente não instala plugins/extensões nem configura portas/agentes. IPC/loopback interno pode existir se app-managed; equipe/LAN segue conexão guiada. Provas/runtimes em C: por U24-DEV-C; fontes/evidência em D:.
- D35–D39: templates instalados/funcionais: Boas-vindas, Excel, Browser, abrir Outlook e acessar Gmail. Excel/Outlook/conta Gmail e permissões externas têm pré-condições próprias; não são redistribuídos ou criados pelo app.
- D36/D46–D51: sessão conectada/desbloqueada; indisponibilidade aguarda com motivo. Categorias **Browser, Windows, Mac, Linux**. Detectar SO/arquitetura do Runner que possui a janela; bloquear incompatível antes de qualquer ação na UI e backend/API/retomada; compatibilidade e prontidão são distintas.
- D42–D44: app avisa update, notificação temporária inferior direita e indicador persistente; confirmação **Pode atualizar / Ainda não**. Adiar preserva tudo; confirmar prepara interrupção segura, atualiza componentes próprios validados e reabre. Não matar documentos de terceiros nem repetir efeitos incertos. Site oferece instalador completo de cada release homologada.
- D45 e documento 03: site acrescenta **Baixar RedRise**, onboarding instalar → criar/conectar equipe → executar, preservando **Agendar Demonstração** e acessos até revisão. Site/identidade editorial têm escopo próprio; novo desktop não determina sua stack.

## Literais e prova mínima

Boas-vindas, conforme 05 §2.1:

> Boas vindas à RedRise! Estamos felizes em tê-los conosco! Esperamos que as automações lhes seja útil!

Abrir Bloco de Notas pela UI, digitar, ampliar a visualização do editor e salvar **Boas_Vindas.txt** na Área de Trabalho real do usuário. Verificar nome, destino, conteúdo Unicode e colisões; TXT não armazena zoom/fonte.

Excel, cenário S1 adaptado à Engine: template mantém labels e B2/B3 vazias; gravação/replay próprios produzem arquivos distintos com B2=`Cliente Teste 01` e B3 numérico `1500`. T01–T09 precisam de prova; T02/T05 validam Engine/prontidão, não Flow/WAA. T07 exige células/labels preservados, não igualdade binária de hash (P01-D6). T10/T11 opcionais; openpyxl lê/verifica, nunca substitui ações UI da Engine.

Os registros locais das tentativas antigas P01 foram removidos a pedido do usuário, sem atribuir sucesso à Engine nem reabrir a tarefa WAA. Verificadores/testes/aceites dizem respeito apenas às funções previstas/entregues do RedRise. Não criar verificadores funcionais ou gates de cloud/MCP/qualification que não integrarão o app. Conferência de persistência dos resultados Excel/Browser e qualidade das capacidades próprias continua pertinente; Harness/skills/graphs/memory pertencem ao desenvolvimento. Não há promessa de zero defeitos ou zero dependências.

## Propostas e detalhes pendentes

Vite (D24), versão Tauri, framework da API (FastAPI é candidato), protocolo e estados de jobs, storage do host, layout de runtime/PyInstaller, updater/assinatura, posicionamento do indicador, frequência de busca de update, redação/layout finais do site, cores complementares e URLs sociais exigem decisão documentada no passo pertinente. Um agente pode resolver escolhas técnicas reversíveis dentro de um Work Order autorizado com justificativa e prova; não pode mudar decisões de produto por conveniência.

Arquitetura: um repositório com desktop/Rust, Core Python, Runner Python, Engine própria, contratos e site isolado. Linguagem/integração concreta da Engine é decisão E01, sem mudar Core/Runner/Rust silenciosamente. Diretórios surgem no passo necessário. Não pressupor Redis, Kubernetes, microserviços ou múltiplos repositórios.

## Fora do Beta inicial

Sem reuso obrigatório, fork Paperclip obrigatório, multi-tenancy SaaS, Stripe/trial/preços ou cloud obrigatória. D25 torna Next/React desktop superados. D27/Mac/Linux/ARM e self-hosted remoto são evolução prevista, não promessa de release Beta. Sessão Windows bloqueada não executa UI; RDP/VM não são fallback implícito.

## Fronteira do site anterior

O v2 terá entrega web própria em P12. O acesso já existente continua preservado no serviço atual: esta root não importa sua autenticação nem altera rotas, domínio, conta ou backend. Antes de integrar/publicar, registrar decisão de destinos e autorização específica. Isso preserva D45 sem transformar o app novo em dependência do anterior. Não reabrir GM23 para repetir decisões já respondidas.


## Direção U27 — testes e erros

Aplicar [TESTING-STRATEGY.md](TESTING-STRATEGY.md) e [ERROR-DIAGNOSTICS.md](ERROR-DIAGNOSTICS.md): construir/testar capacidades pequenas, conferir contratos ao conectá-las e executar campanhas completas no closed beta instalado. Erros apresentam quatro tópicos e rodapé com código do erro e módulos para investigação, sem afirmar causa/atualização necessária sem evidência. Disponibilidade interna, beta_ready e published são estados distintos. As novas exigências não apagam provas existentes nem as promovem a homologação do app instalado.


