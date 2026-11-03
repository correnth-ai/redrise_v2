# Work Order por incremento

Copie esta estrutura para `delivery/work-orders/<step>-<task>.md` quando houver tarefa autorizada. Preencher é parte do planejamento; não inventar autorização, owner, issue, orçamento ou evidência.

```text
Task ID / Run ID:
Roadmap step:
Human request and authorized scope:
Product: product:redrise-v2
Repository: repo:redrise-v2
Root / remote / branch:
Actual HEAD (or unborn) and source-tree digest:
Existing dirty files to preserve:
Objective and observable acceptance:
Small capability or producer-consumer boundary being changed:
Direct test input / result / side effects / error and module hints (when applicable):
Check kind and scope: component / contract / practical E2E; native or simulated:
Non-objectives:
Predecessor evidence (path + SHA256):
Allowed write set / read sources:
Dependencies and technical decisions to make:
Applicable skills / resolved pins:
Memory workspace/project, availability and primary-source confirmations:
Registered graph root/query or canonical fallback:
Delegation envelope / permissions / expected evidence / stop (if applicable):
Commands or native scenarios proving acceptance:
Expected artifacts / retention and data class:
Stop condition / bounded attempts:
Recovery or rollback without destroying data:
External/interactive/cost/credential/HITL boundaries:
Independent review requirement and reviewer (when known):
Completion / failures / next action:
```

Use dados sintéticos, limite tentativas e declare antes o que fazer diante de efeito incerto. Falha não autoriza outro executor, mudança de fonte/versão ou remoção de segurança sem nova avaliação. Uma nova sessão lê status e evidências, não recomeça por suposição.


U27: aplicar TESTING-STRATEGY.md e ERROR-DIAGNOSTICS.md. Não exigir campanha completa/VM/PC limpo para concluir um incremento localizado; campanha prática ocorre no closed beta instalado. Atualizar contratos/diagnóstico com evidência, preservando checks existentes e resultados históricos.

