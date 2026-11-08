// Empresa: first page after signing in. Every number is a fact read from the Core:
// lists of the shared store (processes, stations, my reviews, recent activity) and
// the execution summary, which the Core counts for the period instead of the capped
// list. Each indicator opens the list it counts, with the same filter and period.
// Missing data shows "—" and the diagnostic; never zero, a rate or a fixture.
import { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ActivityFeed, activityOf, Stats02 } from "@/components/blocks";
import { ErrorView } from "@/components/diagnostic";
import { GROUP_LABEL, type Group } from "@/data/status";
import type { ExecutionSummary, Station } from "@/data/types";
import { useStore } from "@/state";
import { useExecutionSummary } from "@/hooks/use-summary";
import { bytes } from "@/lib/utils";

const GROUPS: Group[] = ["running", "waiting", "attention", "verified"];

/** Connected now (signal in the last 45 s) and with an interactive session ready to run. */
export const available = (s: Station) => !s.revoked && s.online && s.session_state === "ready";

/** Share of verified among the finished ones of the period; null when nothing finished (not 0%). */
export function verifiedShare(s: ExecutionSummary): number | null {
  const finished = s.verified + s.attention;
  return finished ? Math.round((s.verified / finished) * 100) : null;
}

export function EmpresaPage() {
  const { src, processes, stations, reviews, executions, go, error } = useStore();
  const { summary, error: summaryError } = useExecutionSummary();
  const [dbBytes, setDbBytes] = useState<number | null>(null);
  const [storageError, setStorageError] = useState<unknown>(null);

  // Database size is a measurement that costs a little: read once when the page opens.
  useEffect(() => {
    let on = true;
    src.storage().then((s) => { if (on) setDbBytes(s.db_bytes); }, (e) => { if (on) setStorageError(e); });
    return () => { on = false; };
  }, [src]);

  const active = stations?.filter((s) => !s.revoked);
  const ready = active?.filter(available).length;
  const pending = reviews?.filter((q) => q.status === "pending").length;
  const days = summary?.days ?? 30;
  const history = (group?: Group) => () => go({ menu: "processo", page: "historico", id: group, days });
  const share = summary ? verifiedShare(summary) : null;

  return (
    <div className="space-y-6">
      <ErrorView error={error} />
      <Stats02 stats={[
        { metric: "Processos cadastrados", value: processes?.length ?? null, action: "Ver processos", onOpen: () => go({ menu: "processo", page: "acao" }) },
        { metric: `Execuções nos últimos ${days} dias`, value: summary?.total ?? null, action: "Ver no histórico", onOpen: history() },
        { metric: "Marcados para mim", value: pending ?? null, hint: "Revisões pendentes com você", action: "Ver pedidos",
          onOpen: () => go({ menu: "processo", page: "acao", id: "mine", nonce: Date.now() }) },
        { metric: "Estações disponíveis", value: active ? `${ready} de ${active.length}` : null, hint: "Conectadas e com sessão pronta",
          action: "Ver estações", onOpen: () => go({ menu: "configuracao", page: "estacao" }) },
      ]} />

      <section aria-labelledby="empresa-situacao" className="space-y-2">
        <div>
          <h2 id="empresa-situacao" className="font-semibold">Situação das execuções</h2>
          <p className="text-sm text-muted-foreground">Iniciadas nos últimos {days} dias, pela situação atual.</p>
        </div>
        <ErrorView error={summaryError} />
        <Stats02 stats={GROUPS.map((g) => ({
          metric: GROUP_LABEL[g], value: summary ? summary[g] : null, action: "Ver no histórico", onOpen: history(g),
          hint: g === "verified" && summary ? (share === null ? "Nenhuma finalizada no período" : `${share}% das finalizadas no período`) : undefined,
        }))} />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="shadow-none lg:col-span-2">
          <CardHeader className="flex flex-row items-start justify-between gap-2">
            <div><CardTitle>Atividade recente</CardTitle><CardDescription>Etapas registradas nas execuções mais recentes</CardDescription></div>
            <Button size="sm" variant="ghost" onClick={() => go({ menu: "rotina", page: "atividade" })}>Ver atividade <ChevronRight /></Button>
          </CardHeader>
          <CardContent>{executions
            ? <ActivityFeed items={activityOf(executions, (e) => go({ menu: "processo", page: "historico", id: e.id }))} />
            : <p className="text-sm text-muted-foreground">{error ? "Indisponível." : "Carregando…"}</p>}</CardContent>
        </Card>
        <Card className="shadow-none">
          <CardHeader><CardTitle>Armazenamento</CardTitle><CardDescription>Banco de dados da equipe, medido no servidor</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-2xl font-semibold tabular-nums">{dbBytes === null ? "—" : bytes(dbBytes)}</p>
            <ErrorView error={storageError} />
            <Button size="sm" variant="outline" onClick={() => go({ menu: "configuracao", page: "aplicativo" })}>Detalhes em Aplicativo</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
