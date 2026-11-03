# Aceite do Beta — RedRise v2

Revisão: 27/10/2026. U27-PRACTICAL-TESTING/U27-ERROR-DIAGNOSTICS prevalecem na sequência de validação. Critérios futuros de funcionalidades previstas para a Engine própria; não executados nesta atualização. Registros locais OpenAdapt antigos foram removidos por autorização e não satisfazem esta matriz. Fontes originais 02/05/06 e D01–D51 são aplicadas com U26-ENGINE/U26-INSTALL e [ENGINE.md](ENGINE.md). P13 confirma na mesma build candidata instalada, após o closed beta interno disponível. Aplicar TESTING-STRATEGY.md e ERROR-DIAGNOSTICS.md.

**Regra de escopo:** cada verificador/teste se limita à função real que o RedRise entregar. Não criar verificadores ou fixtures funcionais para cloud/MCP/qualification ou outros recursos que não existirão. Os critérios abaixo só se tornam comandos ao implementar suas respectivas funções; não são alegação de verificadores já existentes.

| ID | Critério obrigatório / efeito observado | Passo |
|---|---|---|
| B01 | Windows 11 x64 no ambiente próprio disponível instala/abre pacote completo; contexto e dependências efetivas registrados, incluindo cenário offline de instalação; sem exigir máquina limpa/VM ou ausência de toolchains | P13 |
| B02 | Runtime privado usa executáveis/bibliotecas incluídos e paths próprios observados; nenhum pip/cache/download inicial exigido do cliente; sem remover/alterar Python global para testar | P13 |
| B03 | Engine própria grava/compila/reproduz Excel real; T01–T09 funcionais adaptados, labels/células do template preservados e duas saídas XLSX conferidas. SHA256 é informativo, não igualdade binária obrigatória | P13 |
| B04 | Browser privado com Playwright/Chromium compatível, sem cache global ou download no primeiro uso; página local offline e efeito independente | P13 |
| B05 | Windows usa Engine/adapter próprios e dependências privadas com lifecycle automático, sessão correta e health real; sem WAA/Flow obrigatório ou agente/porta configurados manualmente | P13 |
| B06 | Uma equipe por servidor, PostgreSQL compartilhado, bootstrap primeiro admin, login/senha e admin/operador aplicados na API | P13 |
| B07 | Um instalador cria host ou conecta estação; host também executa; host e estação compartilham dados/permissões sem DB isolado por cliente, no arranjo real disponível com nós/papéis e limites registrados; sem impor três máquinas limpas | P13 |
| B28 | Instalação Windows por usuário, padrão e sem exigir escolha de diretório: app/Engine/runtime/componentes em `%LOCALAPPDATA%\Programs\@redrise` (U25/U26-INSTALL); LocalAppData real resolvido, dados/configuração/cofre separados; repair/update preservam layout e não exigem plugins/extensões/portas manuais | P13 |
| B08 | Rotina/Ação/Configuração literais, sidebar expansível, fluxo real da UI e histórico persistido vinculado à versão | P13 |
| B09 | Boas-vindas usa UI do editor, texto literal, visual ampliado e Boas_Vindas.txt na Área de Trabalho real/redirecionada, Unicode e colisão explícita | P13 |
| B10 | Catálogo inclui Excel, Browser, abrir Outlook e acessar Gmail; aplicativos/conta ausentes têm motivos específicos, sem envio/leitura ampla por inferência | P13 |
| B11 | Tela bloqueada/sessão ausente aguarda com motivo; retomada revalida; nenhuma operação desktop indevida | P13 |
| B12 | Categorias Browser/Windows/Mac/Linux e SO/arquitetura do Runner real; UI/API/agendamento/retomada rejeitam nativa incompatível antes de efeito | P13 |
| B13 | Adapter ausente/SO desconhecido/permissão ou dependência indisponível bloqueiam com motivo; compatibilidade e prontidão independentes | P13 |
| B14 | Concorrência por sessão, lease/claim, timeout/cancelamento, revogação e duplicação de requisição não geram efeito não autorizado | P13 |
| B15 | Perda de rede após salvar/antes de ack e restart não repetem escrita cegamente; resultado incerto persiste e exige conferência | P13 |
| B16 | Falso sucesso visual/exit code zero/arquivo sem conteúdo não passa no verificador; sucesso, não verificado e falha são distinguíveis | P13 |
| B17 | Banco, versões, execuções e evidências persistem após reinício; backup/restore conjunto em destino isolado foi demonstrado | P13 |
| B18 | Update detectado produz aviso inferior direito e indicador persistente; Ainda não preserva versão/execuções/indicador | P13 |
| B19 | Pode atualizar coordena checkpoint/espera, pacote verificado, componentes próprios, troca e reabertura sem matar documento de terceiro/replay automático | P13 |
| B20 | Update host+estações cobre permissões/compatibilidade, estação offline e backup antes de migration; recuperação real de falha | P13 |
| B21 | Download interrompido/pacote corrompido/assinatura inválida não é instalado; versão anterior/dados continuam recuperáveis | P13 |
| B22 | Site local possui Baixar RedRise/onboarding/instalador completo verificado, demonstração e destinos de acesso preservados; nenhum recurso/link/OS fictício | P13 |
| B23 | Contact Sales real com campos/validações, persistência/envio autorizado, erro/privacidade/abuso; docs/cases/changelog/404/indexação e mobile conforme fontes | P13 |
| B24 | Logos autorizados têm bytes/proveniência; UI/site têm revisão visual/contraste, sem importar toda a stack/design antigo | P13 |
| B25 | Dependências/runtime/browser/templates fixados e inventariados; distribuição/integridade/avisos e mecanismo de assinatura do canal comprovados, sem alegações fictícias | P13 |
| B26 | Piloto da equipe realiza fluxos pela UI, revisão independente dos aceites, zero impeditivo aberto e evidências ligadas às fontes/builds certas | P13 |
| B27 | Documentação de uso/suporte/diagnóstico/recuperação e release notes correspondem ao candidato real; instalador exclui segredos/operação interna | P13 |
| B29 | Engine atende S/O/L/I/D: responsabilidades e portas pequenas, adapters substituíveis e dependências invertidas, com revisão e suíte de conformidade/limites reais | P13 |
| B30 | Captura própria finaliza/cancela no deadline, trata produtor interrompido/fila inconsistente/writer falho e libera recursos; sem busy-loop ou promoção de gravação parcial | P13 |

**Publicação (estado separado):** após autorização, link público entrega o instalador completo/hash/versão anunciados, acesso/demonstração continuam corretos e canal de atualização aponta à release real. Antes disso, `published=false`, mesmo com `beta_ready=true`. Se canal/assinatura exigidos pelo modo de distribuição ainda não estiverem qualificados, registrar bloqueio do candidato correspondente.

Parametrização T10/T11, self-hosted remoto e releases Mac/Linux/ARM não bloqueiam este Beta Windows x64. Seus limites devem aparecer de forma honesta. Monetização/trial/preços não são critérios aprovados. Testes futuros desses alvos não podem ser descritos como já realizados.

## Novos aceites de construção e diagnóstico

| ID | Critério obrigatório | Momento |
|---|---|---|
| B31 | Testes localizados de capacidades e checks de fronteira pertinentes; localizar Excel, iniciar com descritor fornecido e tratar ausência podem ser exercitados separadamente; simulados/nativos declarados | Construção nos incrementos afetados; revisão P13 |
| B32 | Mensagem tem o que aconteceu, concluído/pendente, próxima ação e detalhes técnicos separados; termina com código estável do erro e um ou mais códigos de módulos para investigação; sem causa inventada ou retry cego de efeito incerto | Implementação P05/P07/P08; validação prática P13 |
| B33 | Distingue erro interno, contrato, comunicação, ambiente/pré-condição e desconhecido; preserva origem/fronteira/correlação; mapeia códigos para símbolos/paths reais e trata sugestões como hipóteses quando não confirmadas | Implementação por módulo/fronteira; P13 |

P10 registra disponibilidade do closed beta instalado (build/hash, abertura e bootstrap no ambiente atual). As campanhas E2E desta matriz são executadas depois dessa disponibilidade. Uma campanha não realizada permanece pendente; não bloquear construção por falta de PC formatado, VM ou campanha completa anterior. Teste manual documentado é válido.

Provas anteriores permanecem com o escopo/revisão originais, sem exigir repetição por mudança documental. Novos requisitos de erro/contrato ainda precisam ser implementados e verificados; não são atribuídos retroativamente ao código existente. Caso um aceite precise de topologia/condição ainda indisponível, declarar a cobertura faltante sem inventar sucesso.
