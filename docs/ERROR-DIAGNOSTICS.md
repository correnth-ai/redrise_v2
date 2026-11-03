# Mensagens de erro e orientação por módulo

Direção U27-ERROR-DIAGNOSTICS, 27/10/2026. Especificação para implementação incremental; os códigos e campos abaixo são convenções planejadas, não alegação de código já implementado. Aplicável às funções reais de app, Core, Runner, Engine e adapters. Sem módulos funcionais de cloud/MCP/qualification excluídos.

## Conteúdo de cada erro

A apresentação ao usuário tem quatro partes e termina com o rodapé de códigos:

1. **O que aconteceu:** descrição simples da operação que falhou; causa somente quando conhecida. Sem stack trace ou nomes internos como explicação principal.
2. **O que foi concluído e o que ficou pendente:** resultado real, efeitos já realizados e estado desconhecido, quando houver. Não afirmar que nada foi alterado sem comprovação.
3. **O que fazer agora:** próxima ação útil e condições para repetir/cancelar. Efeito incerto exige conferência antes de nova execução; erro não autoriza retry cego.
4. **Detalhes para diagnóstico:** seção recolhida/ação de copiar com código estável, referência da execução, versão e contexto técnico sanitizado. Pode dizer que a causa ainda está em investigação. Informações técnicas completas ficam separadas da explicação principal.

**Última linha visível da mensagem:** `Código: <erro> | Módulos para investigação: <um ou mais códigos>`.

### Idioma: backend em inglês, máscara pt-BR na UI (decisão do usuário, 30/10/2026)

- Códigos, mensagens e parâmetros produzidos por backend (Core, Runner, Engine, contratos, host Rust do desktop, saída JSON do instalador) são **inglês ASCII, sem acento**. Catálogo: `contracts/errors.json`; o rodapé técnico do backend é `Code: <erro> | Modules: <códigos>`.
- O texto para a pessoa é uma **máscara** aplicada só na UI: `desktop/locale/pt-BR.json` traz, por `error_code`, os quatro tópicos com os mesmos placeholders, os rótulos (incluindo o rodapé `Código: … | Módulos para investigação: …`) e traduções de valores de parâmetros (`values` exatos e `patterns` com partes variáveis). O diagnóstico carrega `params` (strings sanitizadas) para a UI montar o texto.
- Valor sem tradução aparece como o backend enviou; diagnóstico antigo sem `params` mantém o texto gravado. Diálogos do instalador usam a mesma regra (mensagem em inglês no JSON/log, texto pt-BR no diálogo).
- Testes de contrato garantem: catálogo ASCII; toda entrada do catálogo existe na máscara com os mesmos placeholders; nenhum literal não-ASCII em código de backend. Saídas localizadas do Windows não são lidas como texto (ex.: processos via Win32, não `tasklist`).

O rodapé permanece visível mesmo com detalhes recolhidos. A ação de copiar diagnóstico inclui as quatro partes e o rodapé. Códigos técnicos no rodapé ajudam suporte/agentes a localizar a investigação; o usuário não precisa entendê-los para agir. Não mostrar segredos, capturas brutas, paths pessoais desnecessários ou argumentos completos de processos.

## O que os códigos representam

O código do erro identifica uma condição estável. Os códigos de módulos identificam responsabilidades candidatas a investigar/ajustar. Eles fornecem o norte solicitado pelo usuário e **não provam quais módulos precisam de atualização**. Corrigir pode exigir vários módulos ou somente uma condição do ambiente. Acrescentar mais códigos quando houver evidência de múltiplas fronteiras; não listar todos por precaução.

Classificar a ocorrência como `module_internal`, `contract`, `communication`, `environment`, `precondition` ou `unknown`. Distinguir:

- falha interna confirmada por evidência do módulo;
- contrato/conexão entre produtor e consumidor, inclusive formato/versão inválidos;
- transporte/IPC/timeout, sem confundir ausência de resposta com defeito confirmado;
- aplicação ausente, permissão/sessão/arquivo indisponíveis e outras pré-condições;
- origem ainda não determinada.

Uma pré-condição não satisfeita pode ser esperada e não implica atualização. O módulo que reporta não deve ser automaticamente marcado como causador. Se o domínio da operação é conhecido mas o módulo exato não, usar o código dessa responsabilidade e marcar diagnóstico não confirmado; `RR-DIAG` é o fallback explícito quando não há mapeamento, sem inventar associação.

## Registro inicial de responsabilidades

IDs são estáveis mesmo que arquivos sejam movidos. Antes de emiti-los no código, registrar o símbolo/contrato implementado e o path real. Uma responsabilidade pode estar em submódulo de uma crate/pacote; esta lista não exige microserviços, processos ou pacotes separados.

| Código | Responsabilidade planejada |
|---|---|
| RR-EXCEL-DISC | Descobrir e validar instalação/ativação do Excel |
| RR-EXCEL-START | Iniciar Excel/nova planilha e confirmar prontidão |
| RR-FLOW | Compor e rotear capacidades/resultados da rotina |
| RR-CONTRACT | Validar contratos, versões e fronteiras entre componentes |
| RR-ENGINE-CAP | Captura/finalização da Engine |
| RR-ENGINE-IR | Compilação/representação intermediária |
| RR-ENGINE-EXEC | Execução de ações da Engine |
| RR-RUNNER | Sessão, jobs e coordenação local |
| RR-CORE | Equipe, autorização, persistência e coordenação do servidor |
| RR-RUNTIME | Resolução/lifecycle dos componentes privados |
| RR-UI | Apresentação e interação do desktop |
| RR-DIAG | Diagnóstico ainda sem responsabilidade mapeada |

Ampliar o registro somente com capacidades reais, no incremento correspondente. Preservar aliases de IDs anteriores para interpretar históricos. O registro de implementação deve mapear código → responsabilidade → símbolo/contrato → paths atuais → condições de erro pertinentes.

## Estrutura técnica a consolidar em P05

Campos mínimos propostos: `error_code`, `category`, `user_message`, `completed`, `pending`, `effect_state`, `next_action`, `reported_by`, `boundary` (produtor/consumidor, quando aplicável), `module_hints`, `diagnosis_status`, `correlation_id`, `version` e `technical_details` sanitizados. Fixar schema/versionamento nos contratos do projeto; este documento não altera APIs executáveis existentes.

`effect_state` distingue `none`, `partial`, `confirmed` e `unknown`; separar sucesso do transporte e resultado da operação. `diagnosis_status` distingue sugestão de causa confirmada. Preservar código/causa do produtor ao atravessar camadas; um wrapper pode acrescentar fronteira e módulos relevantes sem substituir tudo por erro genérico. Correlacionar logs na mesma execução. Falha ao renderizar/copiar diagnóstico não pode ocultar a mensagem original.

## Exemplos de apresentação

### Excel ausente

> **O que aconteceu:** O Excel desktop não foi encontrado nesta máquina.
>
> **Resultado:** A verificação terminou. Nenhuma planilha foi aberta; a etapa de inicialização não começou.
>
> **Próxima ação:** Confira se o Excel desktop está instalado e disponível para este usuário e execute a verificação novamente.
>
> **Detalhes para diagnóstico:** Localização retornou NotFound. Pré-condição não satisfeita; defeito no módulo não confirmado. Referência da execução disponível em Detalhes.
>
> Código: EXCEL-NOT-FOUND | Módulos para investigação: RR-EXCEL-DISC

### Resposta incompatível entre capacidades

> **O que aconteceu:** Não foi possível usar a resposta da localização do Excel para iniciar a planilha.
>
> **Resultado:** A resposta foi recebida, mas o contrato foi recusado. A inicialização não foi executada.
>
> **Próxima ação:** Copie o diagnóstico e encaminhe ao suporte. Repetir a mesma operação pode não resolver.
>
> **Detalhes para diagnóstico:** Descritor incompatível na fronteira localizar → iniciar. A origem precisa ser investigada no produtor, consumidor ou composição.
>
> Código: CONTRACT-EXCEL-DESCRIPTOR | Módulos para investigação: RR-EXCEL-DISC, RR-EXCEL-START, RR-CONTRACT, RR-FLOW

### Confirmação incerta

> **O que aconteceu:** Não foi possível confirmar se a planilha foi salva.
>
> **Resultado:** O comando de salvar foi enviado; o resultado no arquivo ainda é desconhecido.
>
> **Próxima ação:** Confira o arquivo antes de executar novamente para evitar repetir alterações.
>
> **Detalhes para diagnóstico:** A confirmação não chegou no prazo. Isso não comprova falha no salvamento. Copie a referência da execução para investigação.
>
> Código: EXCEL-SAVE-UNCONFIRMED | Módulos para investigação: RR-ENGINE-EXEC, RR-RUNNER

Os exemplos são cenários especificados, não eventos ocorridos. Só mostrar esses fatos se a execução real os sustentar; não deduzir que o comando foi enviado apenas de um timeout.

## Checks de implementação

Testar localmente, conforme a função for implementada: quatro partes e rodapé; um/vários módulos; erro interno, contrato, comunicação e pré-condição; causa desconhecida; propagação/correlação e sanitização; estado incerto e ausência de repetição automática. Fixtures não instalam/desinstalam Excel. Em P13, conferir manualmente a mensagem no aplicativo instalado e a utilidade do diagnóstico. Não criar suíte funcional para capacidades ausentes.
