# Prompt atualizado — capacidades pequenas até o closed beta funcional

Revisão: 27/10/2026, roadmap4 e U27-PRACTICAL-TESTING/U27-ERROR-DIAGNOSTICS. Copie o bloco completo para o agente executor. Criar este arquivo não executa o trabalho; o estado deve ser relido no início.

```text
Continue exclusivamente o RedRise v2 até um closed beta funcional, validado
praticamente e pronto para release. Autorizo pesquisa necessária, desenvolvimento
local, dependências em ambiente isolado e testes locais com dados sintéticos,
seguindo os requisitos atuais. Avance pela implementação; não pare em um plano.

Workspace: D:\Correnth
Root: D:\Correnth\products\redrise-v2\repos\app
Produto/repo: product:redrise-v2 / repo:redrise-v2
Manifesto: D:\Correnth\products\redrise-v2\product.yaml
Remote: https://github.com/correnth-ai/redrise_v2.git
Memória: workspace=correnth, project=redrise-v2
Execução/laboratório: C:\Users\{user}\RedRise-v2-dev, resolvendo o usuário real.
Fontes próprias e evidência sanitizada permanecem em D:.

1. Leia authority, routing matrix e AGENTS aplicáveis. Na root, leia README,
   docs/BASELINE.md, docs/ROADMAP.md, docs/TESTING-STRATEGY.md,
   docs/ERROR-DIAGNOSTICS.md, docs/ENGINE.md, docs/requirements.json,
   docs/BETA-ACCEPTANCE.md e delivery/status.json. Preserve fontes e alterações
   existentes. HEAD pode ser unborn; não invente commit base.

2. Continue do estado real. Investigação I00, Engine E01-E04 e uma prova Excel
   P01 já foram registradas em outra sessão; confirme evidência antes de usar.
   P02/P03/P04 tinham desenvolvimento em andamento na autoria deste prompt.
   Não recomece pesquisa, não refaça provas por mudança documental e não trate
   a antiga espera de clean VM como bloqueio. A instrução atual permite ambiente
   próprio disponível; outro usuário local é uma opção se útil e autorizado.
   Não exija PC formatado, VM, Windows limpo ou remoção de ferramentas globais.

3. Mantenha Engine própria/SOLID integrada ao app, sem herdar cloud/MCP/
   qualification do OpenAdapt. Se faltar pesquisa necessária, use o catálogo
   https://github.com/morluto/awesome-reverse-engineering efetivamente para
   investigar fontes OpenAdapt fixadas, conforme ENGINE-INVESTIGATION-PLAN.md.
   Consulte a investigação existente antes de ampliar. Eventual código derivado
   exige identificação prévia; não incorpore fork completo como código original.

4. Desenvolva uma capacidade observável por vez e faça testes curtos e locais.
   Exemplo Excel:
   a) localizar instalação/ativação e retornar encontrado, ausente ou erro;
   b) iniciar nova planilha recebendo diretamente descritor validado;
   c) apresentar ausência/falha conforme o novo contrato de diagnóstico.
   Teste b com entrada conhecida, sem exigir executar a toda vez; teste c com
   fixture, sem desinstalar Excel. Checks nativos curtos validam só sua operação.
   Conecte automaticamente esses resultados por contratos no aplicativo.
   Não transforme cada operação em microserviço/processo/abstração desnecessária.

5. Ao conectar módulos, confira apenas a fronteira pertinente: formato/versão,
   roteamento, propagação de causa/correlação, timeout e resposta inválida.
   Diferencie defeito interno, contrato, comunicação, ambiente/pré-condição e
   origem desconhecida. Doubles apoiam esses checks; declare seu uso. Não exija
   campanha E2E global para concluir cada componente ou construir UI/instalador.

6. Cada erro apresentado deve conter:
   - o que aconteceu, em linguagem compreensível e sem causa inventada;
   - o que foi concluído, o que ficou pendente e qualquer efeito desconhecido;
   - a próxima ação útil, sem repetir cegamente efeitos incertos;
   - detalhes técnicos separados e sanitizados, com referência da execução.
   A última linha visível deve ser:
   Código: <erro> | Módulos para investigação: <um ou mais códigos>
   Implemente a convenção de ERROR-DIAGNOSTICS.md e mapeie IDs estáveis para
   responsabilidades, símbolos/contratos e paths reais. Preserve causa/origem/
   fronteira ao atravessar camadas. Os códigos apontam onde investigar/ajustar;
   não afirmam defeito ou necessidade de atualização sem evidência. Aplicação
   ausente pode ser só pré-condição. Não exponha segredos ou capturas pessoais.

7. Siga as entregas de construção do roadmap4: concluir componentes privados
   P02-P04 com checks localizados; contratos/diagnóstico P05; Core P06; Runner
   P07; desktop P08; catálogo conectado P09; instalador/closed beta interno P10;
   atualização/recuperação P11 e site local isolado P12. Preserve stack e
   funcionalidades confirmadas de equipe/LAN/PostgreSQL. Não suprima testes
   existentes nem alegue que o novo tratamento de erros já está implementado.

8. Instale pelo produto no ambiente disponível, por usuário e padrão em
   %LOCALAPPDATA%\Programs\@redrise, com Engine/runtime/componentes privados.
   Sem setup manual de plugins/Python/browser/portas/agentes pelo cliente.
   Separe dados/configuração/cofre dos binários. Registre build/versão/hash e
   abertura/bootstrap para closed_beta_available=true; isso só indica que a
   build integrada instalada está disponível para experimentação interna.

9. Depois dessa build instalada, faça P13: campanha prática manual pela UI de
   Excel, Browser, Boas-vindas, Outlook/Gmail conforme pré-condições, equipe/LAN,
   atualização e recuperação. Excel deve gravar/compilar/reproduzir ações UI e
   conferir arquivos por leitor independente; não fabricar o resultado por
   escrita direta em XLSX. Use dados sintéticos e só a superfície autorizada.
   Registre ambiente/nós/papéis reais, passos, esperado, observado e falhas;
   não alegue topologia não exercitada. No caso de cenário/condição ausente,
   explicite a cobertura faltante e continue correções independentes possíveis.

10. Em cada falha, use a mensagem/códigos como ponto de partida, confirme causa,
    corrija módulos ou fronteira pertinentes, rode regressão localizada e repita
    os cenários E2E afetados. Amplie quando houver impacto transversal. Os testes
    manuais documentados são válidos; não automatize toda a matriz por obrigação.
    Obtenha revisão pertinente antes de atribuir aceites verificados.

11. Use Harness/router e skills corporativas locais conforme o próximo trabalho,
    com resolução/pins e leitura. Consulte memória no escopo acima e graphs
    somente para perguntas pertinentes em roots registradas. Se indisponíveis,
    registre e siga fontes/checkpoint, sem rebuild implícito nem sucesso fictício.
    Delegue só frentes independentes delimitadas quando útil, inicialmente até
    dois subagentes read-only, com escopo/permissões/skills/evidência/parada.
    Um escritor por root; sem delegação recursiva automática. Principal integra
    e publica checkpoint compacto, respeitando marker de memória/subagentes.

12. Abra Work Order pequeno por incremento e preserve evidência existente.
    Atualize estado com checks reais de componente/contrato/E2E, identificando
    simulado/nativo e manual/automatizado. Em transição de contexto conclua a ação
    atômica e siga task-context-checkpoint conforme aplicável, com retomada exata.
    Prossiga no escopo já autorizado sem pedir confirmação repetida. Não declare
    tarefa pronta com efeito desconhecido, check obrigatório ausente ou código
    não implementado. Bloqueio real deve indicar a menor ação necessária.

13. Feche P14 com matriz prática atendida na versão candidata, impeditivos
    resolvidos, instalador/hash/inventário, limitações, instruções e release notes.
    beta_ready=true requer evidência real; closed_beta_available é outro estado.
    Não faça commits/pushes/deploys/publicação, gastos, mudanças de produção/
    credenciais ou ações destrutivas sem ordem explícita correspondente.
    published permanece false até publicação autorizada e demonstrada.
```
