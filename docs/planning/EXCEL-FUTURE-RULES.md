# Excel — decisões preservadas para update futuro

31/10/2026. Fora da implementação e do aceite novos da [work order Browser](../../delivery/work-orders/DISCOVERY-20261031.md). Preservar decisões do grill me sem apresentar opções Excel como parte deste update. Não remover dados/código existentes.

| Origem | Decisão preservada |
|---|---|
| G08/G11 | Separar acessar aplicativo de preparar trabalho. Excel poderá criar arquivo novo ou usar existente. Novo usa planilha padrão; existente referencia caminho completo e nome exato da planilha/aba. |
| G10 aplicado a Excel | Arquivo referenciado, não cópia anexada à rotina; valores salvos no cadastro. |
| G30 | Oferecer salvar no mesmo arquivo ou como outro; pedir destino na segunda opção. Arquivo novo precisa de primeiro destino. |
| G31 | Aba não encontrada: falhar indicando o nome; não criar outra ou selecionar alternativa silenciosamente. |
| G32 | Novo destino existente: `Pedido.xlsx` → `Pedido[1].xlsx` → `Pedido[2].xlsx`; preservar extensão e não sobrescrever arquivos anteriores. Não muda o salvamento explícito no próprio original. Nome efetivo deve chegar ao contexto/resultado/verificador. |

Pendentes para essa futura tarefa: granularidade do preenchimento, formatos, colisões concorrentes, lacunas de numeração e nomes já sufixados. Templates atuais ainda podem recusar colisão; nada foi implementado ou homologado por este documento.
