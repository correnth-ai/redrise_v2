# Prompt de engenharia — identidade, sessão e UI (02/11/2026)

Copie o texto abaixo para iniciar a implementação. Este arquivo não cria sessão nem executa mudanças por existir.

---

Implemente localmente o update **REDRISE-IDENTITY-UI-20261102** do RedRise v2 até um candidato funcional e testado no escopo autorizado. Siga a work order `delivery/work-orders/IDENTITY-UI-20261102.md` integralmente. Cadastro/login/remember-me precisam de backend e provas reais; demonstração de formulário não conclui a entrega.

## Leitura e estado inicial

Root única de escrita: `D:/Correnth/products/redrise-v2/repos/app`. Leia authority/routing, manifesto, AGENTS aplicáveis, README/baseline/Engine/roadmap/status, a nova work order, `docs/APP-RULES.md`, `docs/identity/SUPABASE-V1-REUSE-20261102.md`, TESTING-STRATEGY e ERROR-DIAGNOSTICS. Leia o checkpoint/evidência `BROWSER-UPDATE-20261101` para preservar beta.14, não reiniciar trabalho Engine/Excel/Browser já comprovado.

As decisões de 02/11 nesta work order substituem menus, login/signup-05 e cadastro sem senha anteriores. Referências antigas são antecedente, não ordens concorrentes. Existe acesso V1 **read-only e seletivo para reaproveitamento de identidade**; leia antes as instruções V1. Não herdar seu runtime, Paperclip ou permissões.

Revalide HEAD/branch/dirty/digest, release efetiva e configuração segura. No planejamento: main, HEAD unborn, beta.14 registrada instalada; nenhum commit/push/publicação externa. Preserve alterações locais. Crie evidência do incremento atual, não reescreva campanha histórica nem status para fingir conclusão.

Execute router para a capacidade atual; resolva e leia somente skills necessárias via catálogo corporativo. Não introduzir Better Auth: referência V1 confirmada é Supabase Auth. Memória explícita `correnth/redrise-v2`; indisponibilidade não bloqueia, usar fontes primárias. Grafo somente root registrada/saudável, sem rebuild. Um escritor por root; delegação somente independente e delimitada.

## O que entregar

1. **Acesso/cadastro reais:** login-03/signup-03, imagem `assets/auth/login-register-background.png` ocupando o fundo, cards centralizados por cima, RedRise e pt-BR por máscaras já incluídas no bundle. Referências em `docs/ui/references/identity-20261102/`. E-mail/senha no login; nome completo/e-mail/senha/confirmar senha no cadastro; única dica estática **A senha deve ter no mínimo 8 caracteres.** Validação backend, confirmação/reenvio e recuperação reais. Google/GitHub preservados conforme configuração; sem Apple e sem sucesso fictício. Nome autenticado em Configuração › Equipe/perfil.
2. **Mesmo projeto Supabase V1:** estudar e reaproveitar contratos/trechos necessários com proveniência. Não criar outro projeto. Resolver os guard triggers e política remota antes de prometer public signUp. Não copiar admin.createUser(email_confirm:true), regra número/símbolo ou chave privilegiada para o cliente. Membership/role do Core V2 continuam no servidor; nenhuma promoção automática de usuário/admin por e-mail/metadata.
3. **Lembrar de mim:** checkbox opt-in, entrada automática em Empresa com sessão válida após fechar/reabrir, reboot e update compatível. Sem senha salva/preenchida. Cofre Windows por usuário, refresh rotativo serializado, access efêmero; prazo técnico de 30 dias absolutos proposto na work order, respeitando limite menor do provedor. Desmarcado: memória apenas. Expiração/revogação pede login; falha de rede é recuperável. Logout/esquecer dispositivo revoga apenas o dispositivo V2 e sessões derivadas, não todos os acessos V1.
4. **Configuração › Estação:** inventário/estação atual separados de **Estações lembradas** do usuário, no mesmo submenu; nome, última atividade, expiração, este dispositivo e Esquecer dispositivo, sem tokens. Remember-me não controla registro/heartbeat do Runner.
5. **Navegação exata, no singular:** Empresa (inicial); Rotina → Lista, Atividade; Processo → Ação, Histórico, Kanban; Configuração → Equipe, Estação, Aplicativo. Sem Gantt. Preservar modelos/gravação/edição/composição/execução e histórico através de acessos contextuais e aliases de rotas; não remover funções/dados por renomear menus.
6. **Empresa:** inspecionar a referência `https://shadcn-nextjs-admincn-admin-template.vercel.app/dashboard/productivity` e seguir o mapa visual da work order: linha temporal larga + lista à direita, dois cards de indicadores/gráficos abaixo, cards de desempenho/recursos e tabela filtrável mais abaixo. Dados fake autorizados só nesse dashboard, selo **Dados demonstrativos**, fixture isolada; nenhuma cobrança/cartão/Stripe ou menus extras do template. Não importar Next.js/servidor do template; respeitar licença.
7. **Achados:** F2 absorvido pela sessão; F3 diagnóstico no detalhe; F5 teclado; F7 máscara pt-BR e nomes legíveis. Depois corrigir F4 polling ocioso, F6 fim da sequência e F8 título após carregamento, com checks pequenos. Não fechar F por renomear tela. F1 é regressão de máscara. Homologação formal Edge/Brave não foi concedida.

## Execução, limites e conclusão

Avance N0–N6 da work order. SOLID e KISS: adapters pequenos com responsabilidades claras; preserve Tauri/React e Core/Runner/Engine. Reuse scripts e componentes existentes, revise fontes/pins antes de adicionar dependências. Os comandos shadcn indicam blocos escolhidos; não executar @latest sem revisão. Código em D:, builds/cache/runtime em C: no laboratório.

Prepare implementação local e propostas externas concretas antes de pedir aprovação para um serviço. Não aplicar mudanças no V1/Supabase/SMTP/callback/credenciais ou fazer cadastro/envio real sem autorização aplicável. Se faltar acesso/configuração, conclua UI/contratos/testes locais e entregue o diff externo revisável; registre **cadastro/login real pendente**, sem alegar entrega funcional por mock. Não criar projeto alternativo, desligar trigger, copiar service_role para cliente, dispensar confirmação ou mudar policy global silenciosamente.

Não alterar hashes/originais, provas passadas, contas do V1, site/domínio público ou dados reais. Sem commit/push/publicação, gastos ou ação destrutiva. Não reiniciar PC/fechar documentos à força. Campanha instalada, assinatura/instalação e reboot seguem autorização/coordenacão concreta.

Checks: typecheck/build; contratos Auth/Core/membership, sessão/cofre/rotação/revogação, isolamento entre contas/dispositivos; senha 7/8, divergência, confirmação/reenvio, nome acentuado e recuperação. Testes focados Core/PostgreSQL e smoke Browser P1/P2. Validador base não prova login real. Campanha instalada deve comprovar cadastro/confirmar/login, Empresa inicial, remember-me nos dois modos, update, logout/esquecer, acessibilidade/pt-BR e V1 sem regressão. Nunca capturar tokens/senhas/contas pessoais nas provas.

Gere evidência em `delivery/evidence/IDENTITY-UI-20261102/`, candidato por versão/hash/inventário e checkpoint compacto. Separe implementado, testado localmente, configurado remotamente, testado instalado e revisado. Não autoaprovar QA; manter `beta_ready/published` conforme prova. Relatório final: entregue, validado, pendente, risco concreto e próxima ação, com arquivos exatos.
