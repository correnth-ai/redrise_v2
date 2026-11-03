# Evidência e continuidade

Cada passo grava um relatório compacto em `delivery/evidence/<step>/`, com comandos reais, exit codes, resultados observados e hashes. Fixtures/capturas devem ser sintéticas, revisadas e mínimas. Capturas brutas, segredos e dados pessoais ficam fora de Git e de memória. Arquivos grandes necessários permanecem em storage local controlado, com referência e hash; não publicar automaticamente.

Registro mínimo:

```json
{
  "step": "P01",
  "status": "not_started",
  "source_revision": null,
  "source_tree_sha256": null,
  "versions": {},
  "environment": {},
  "checks": [],
  "artifacts": [],
  "review": null,
  "limitations": [],
  "next_action": "Run authorized preflight"
}
```

O exemplo é estrutura, não evidência executada. Para verificar um passo, preencher checks com comando/cenário, resultado esperado/real e exit code; artifacts com path/hash; revisão independente com autor e resultado reais. `verified` exige todas as aceitações obrigatórias. Teste pulado/fixture de protocolo não equivale a teste nativo. Uma prova local não equivale a instalação limpa, LAN, Beta ou publicação.

Se HEAD não existe, registrar `unborn`, não um SHA fictício. Para código não commitado, registrar digest e inventário de fontes relevantes à prova; evidência de release exige revisão fonte e artefatos imutáveis identificáveis. Mudanças materiais invalidam provas dependentes até revalidação. Não promover uma aprovação antiga para novo código ou nova versão do motor.

Atualizar [status.json](../delivery/status.json) somente após aceite. Manter um escritor e revisão independente nos gates do roadmap. Estados permitidos: `not_started`, `in_progress`, `blocked`, `verified`; falhas detalhadas permanecem no relatório. `beta_ready` e `published` são estados distintos.

Na revisão U26-ENGINE o usuário autorizou excluir os registros locais das tentativas P01 antigas. O estado novo não depende deles e não contém tarefa de WAA/manual Desktop. I00 e E01–E04 terão evidência própria e P01 Engine usará `delivery/evidence/P01-engine/`. Fonte original e efeito novo dos requisitos permanecem identificados. Só criar verificadores/QA para funcionalidades efetivas do produto; recursos excluídos não recebem gates ou fixtures funcionais. A remoção de registros antigos não equivale a prova aprovada da Engine.

Antes de encerrar: objetivo, estado, decisões confirmadas/propostas, validações, skills/pins, artefatos/hashes e próxima ação. No workspace, publicar checkpoint pelo Harness na root exata com memória `correnth/redrise-v2`; se indisponível, preservar checkpoint local e registrar degradação. Não criar sessão sucessora, automação, mensagem ou issue sem autorização aplicável.

Registrar apoio de skills/memória/grafos e fallback; em delegações, registrar envelope, achados e sua confirmação em fontes. O principal integra o resultado e publica apenas checkpoint compacto, respeitando o marker que descarta capturas de subagentes. Pesquisa I00 não é teste de Engine implementada.


## Direção U27

Aplicar TESTING-STRATEGY.md e ERROR-DIAGNOSTICS.md. Registrar o tipo de check (component_check, contract_check ou practical_e2e), escopo, input, efeito esperado/observado, ambiente e simulado/nativo/manual/automatizado quando pertinentes. Para erro, registrar código, responsabilidade reportadora, fronteira, módulos sugeridos, causa confirmada ou hipótese, efeito e referência. Não expor dados pessoais/segredos.

P10 pode registrar closed_beta_available com build/instalador identificados, instalação, abertura/bootstrap no ambiente atual. P13 registra aceites completos depois da build instalada; não exigir PC limpo/VM. beta_ready e published continuam separados. Preservar arquivos históricos de provas e sua revisão; os novos erros/checks não foram comprovados por esta atualização documental.
