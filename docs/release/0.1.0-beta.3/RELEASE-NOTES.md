# RedRise 0.1.0-beta.3 — closed beta interno (Windows 11 x64)

Estado: **candidato interno**. `closed_beta_available=true`, `beta_ready=false`, `published=false`. Não publicado; nenhum download público.

## Instalador
| Item | Valor |
|---|---|
| Arquivo | `RedRise-Setup-0.1.0-beta.3.exe` (instalador completo, offline) |
| SHA-256 | `3ef717a571337eea760c89504ab1103582fe84e23dde751983866451c33500d8` |
| Conteúdo verificado (payload) | `de1337b8e8be92426f8cbe6469a8a9ef814ee7844caeda19f71f424cbc7f6f45` |
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
- Histórico persistente após fechar/reabrir; atualização de versão pelo instalador preservando dados e mantendo a versão anterior para recuperação.

## Limitações conhecidas (honestas)
- **Gravação no Excel/Windows** aceita somente teclado e mouse físicos; ainda não foi feita por uma pessoa nesta versão (piloto humano pendente).
- **Equipe em rede (LAN):** só testada em um computador. A primeira conexão de outra estação pode exigir permitir a porta 47800 no Firewall do Windows (decisão do usuário).
- **Atualização pelo app** (aviso inferior direito, Pode atualizar / Ainda não, pacote assinado) implementada; teste completo pendente.
- **Instalador sem assinatura de código (Authenticode)**: integridade por SHA-256 e manifesto; canal de atualização assinado com Ed25519.
- Sessão bloqueada: o app aguarda com motivo (teste automatizado); não validado manualmente.
- Site: apenas ambiente local de teste (download, onboarding, 404). Contact Sales real não implementado.
- Correções da beta.3 (navegador para login do Gmail, parâmetros de rotinas gravadas, mensagens de gravação vazia e de arquivo ausente, menu lateral fixo, rótulos) ainda precisam de reconferência pela UI.

## Como usar
1. Execute o instalador. 2. No primeiro computador: **Criar equipe neste computador**. 3. Em Rotina: crie a partir de um modelo ou por gravação; Executar. 4. Em Ação: acompanhe estados (Aguardando, Em andamento, Verificada, Concluída não verificada, Incerta — conferir, Falhou, Recusada).

## Diagnóstico
Cada erro mostra o que aconteceu, o resultado, a próxima ação e detalhes; **Copiar diagnóstico** inclui a referência e a última linha `Código: … | Módulos para investigação: …`. Registros: `%LOCALAPPDATA%\RedRise\host\logs` e `%LOCALAPPDATA%\RedRise\agent\agent.log`.

## Atualizar e recuperar
- Atualizar: pelo aviso no app (quando o canal oferecer) ou executando o novo instalador com o RedRise fechado.
- Voltar à versão anterior: com o RedRise fechado, `"%LOCALAPPDATA%\Programs\@redrise\uninstall.exe" --rollback`.
- Backup do servidor da equipe: `runtime\python\python.exe -m redrise_core backup --out <arquivo>`; restauração sempre em banco separado (`restore --target-db <nome>`).
- Desinstalar: Configurações do Windows → Aplicativos → RedRise (dados mantidos).
