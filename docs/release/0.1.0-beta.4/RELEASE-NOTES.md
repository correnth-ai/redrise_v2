# RedRise 0.1.0-beta.4 — closed beta interno (Windows 11 x64)

> **Substituído pela 0.1.0-beta.5.** Revisão independente de 28/10/2026: parte de "O que funciona" foi validada na build 0.1.0-beta.2 (Boas-vindas, Excel, Outlook, Gmail, replay Browser) e apenas reconferida parcialmente na beta.4; a instrução de `uninstall.exe --rollback` não funcionava nesta versão (corrigido na beta.5).

Estado: **candidato interno**. `closed_beta_available=true`, `beta_ready=false`, `published=false`. Não publicado; nenhum download público.

## Instalador
| Item | Valor |
|---|---|
| Arquivo | `RedRise-Setup-0.1.0-beta.4.exe` (instalador completo, offline) |
| SHA-256 | `f9a9dff0e41a4bf9eecf5852cebb344f8d3e2a9c737eb8256048e1f8cfc34c73` |
| Conteúdo verificado (payload) | `e2f668a71ce935bc40e69dd16c0bfa10a6d4d9534fe68df065ef2e86d4c83232` |
| Destino | `%LOCALAPPDATA%\Programs\@redrise` (por usuário, sem administrador) |
| Dados | `%LOCALAPPDATA%\RedRise` (preservados em atualização e desinstalação) |

## Componentes incluídos
- RedRise (Tauri 2.12.5, TypeScript Vanilla) — menus Rotina, Ação, Configuração.
- Engine própria `redrise-engine.exe` (sha256 `5f0c5b3b…563c`): captura só de teclado/mouse físicos, IR, execução com efeito incerto sem repetição automática.
- Runtime privado CPython 3.12.10; Runner; Core (servidor da equipe).
- PostgreSQL 17.6-1 (binários EDB), só em 127.0.0.1, iniciado pelo próprio app.
- Playwright 1.63.0 + Chrome for Testing 153.0.8010.12 (navegador do RedRise, separado do WebView2).
- psycopg 3.2.13, cryptography 46.0.7, cffi 2.1.1, greenlet, pyee, typing-extensions, tzdata — licenças em `licenses/`.
- Modelos: Boas-vindas 1.1.0, Excel: preencher pedido 1.1.0, Abrir Outlook 1.0.0, Acessar Gmail 1.0.0. O modelo Browser-formulário continua candidato (alvo depende de decisão de produto).

## O que funciona (validado na build instalada)
- Instalação por usuário pelo instalador; abertura; criação da equipe neste computador (servidor + estação); login admin/operador.
- Boas-vindas na Área de Trabalho real (inclusive OneDrive), texto literal, colisão recusada sem abrir nada.
- Excel: preencher pedido com conferência independente do arquivo; planilha modelo preservada.
- Abrir Outlook (sem ler mensagens); Gmail informa quando é preciso entrar na conta.
- Rotina Browser gravada, compilada com parâmetro e reproduzida com efeito confirmado no site de teste.
- Erros com quatro partes e rodapé `Código | Módulos para investigação`.
- Atualização assinada pelo app (beta.3 → beta.4) com dados preservados; histórico persistente após fechar/reabrir; atualização de versão pelo instalador preservando dados e mantendo a versão anterior para recuperação.

## Limitações conhecidas (honestas)
- **Gravação no Excel/Windows** aceita somente teclado e mouse físicos; ainda não foi feita por uma pessoa nesta versão (piloto humano pendente).
- **Equipe em rede (LAN):** só testada em um computador. A primeira conexão de outra estação pode exigir permitir a porta 47800 no Firewall do Windows (decisão do usuário).
- Atualização pelo app validada de beta.3 para beta.4 neste computador (aviso, Ainda não, pacote corrompido recusado, Pode atualizar). Atualização com execução em andamento e atualização de servidor + estações separadas não foram exercitadas. Na recusa de pacote inválido, a próxima ação exibida é genérica (melhoria pendente).
- **Instalador sem assinatura de código (Authenticode)**: integridade por SHA-256 e manifesto; canal de atualização assinado com Ed25519.
- Sessão bloqueada: o app aguarda com motivo (teste automatizado); não validado manualmente.
- Site: apenas ambiente local de teste (download, onboarding, 404). Contact Sales real não implementado.
- Correções reconferidas pela UI: navegador do RedRise para login (Configuração), campos de parâmetros de rotinas gravadas, rótulos legíveis, arquivo de entrada ausente identificado, menu lateral fixo. Mensagem de gravação vazia em quatro partes também reconferida.

## Como usar
1. Execute o instalador. 2. No primeiro computador: **Criar equipe neste computador**. 3. Em Rotina: crie a partir de um modelo ou por gravação; Executar. 4. Em Ação: acompanhe estados (Aguardando, Em andamento, Verificada, Concluída não verificada, Incerta — conferir, Falhou, Recusada).

## Diagnóstico
Cada erro mostra o que aconteceu, o resultado, a próxima ação e detalhes; **Copiar diagnóstico** inclui a referência e a última linha `Código: … | Módulos para investigação: …`. Registros: `%LOCALAPPDATA%\RedRise\host\logs` e `%LOCALAPPDATA%\RedRise\agent\agent.log`.

## Atualizar e recuperar
- Atualizar: pelo aviso no app (quando o canal oferecer) ou executando o novo instalador com o RedRise fechado.
- Voltar à versão anterior: com o RedRise fechado, `"%LOCALAPPDATA%\Programs\@redrise\uninstall.exe" --rollback`.
- Backup do servidor da equipe: `runtime\python\python.exe -m redrise_core backup --out <arquivo>`; restauração sempre em banco separado (`restore --target-db <nome>`).
- Desinstalar: Configurações do Windows → Aplicativos → RedRise (dados mantidos).
