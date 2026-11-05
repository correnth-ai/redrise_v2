// Marcado para mim (Processo › Ação): review requests of the signed-in person, by
// status, with the context and results to check. Only the current responsible sees
// Aprovado!; the Core decides who can approve and that it happens once.
// Reference: docs/ui/references/ui-engine-boas-vindas-20261103/acao-marcado-para-mim.png.
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ExecutionLog } from "@/components/blocks";
import { ErrorView } from "@/components/diagnostic";
import type { Execution, Review, StepChange } from "@/data/types";
import { cn, when } from "@/lib/utils";
import { useStore } from "@/state";

export const REVIEW_LABEL: Record<Review["status"], string> = { pending: "Aguardando revisão", approved: "Aprovado" };
const REVIEW_TONE: Record<Review["status"], string> = { pending: "bg-info-soft text-info border-transparent", approved: "bg-ok-soft text-ok border-transparent" };
const REVIEW_MARK: Record<Review["status"], string> = { pending: "bg-info", approved: "bg-ok" };

function ReviewBadge({ status }: { status: Review["status"] }) {
  return <Badge variant="outline" className={cn("font-medium", REVIEW_TONE[status])}>{REVIEW_LABEL[status]}</Badge>;
}

function CountCard({ label, value, mark }: { label: string; value: number; mark: string }) {
  return (
    <Card className="py-0 shadow-none"><CardContent className="flex items-center gap-3 p-4">
      <span aria-hidden className={cn("size-3 shrink-0 rounded-sm", mark)} />
      <span><span className="block text-xs text-muted-foreground">{label}</span><span className="block text-xl font-semibold tabular-nums">{value}</span></span>
    </CardContent></Card>
  );
}

function ReviewCard({ q, onOpen }: { q: Review; onOpen: () => void }) {
  return (
    <li>
      <button type="button" onClick={onOpen} className="flex w-full items-start gap-3 rounded-lg border bg-card p-3 text-left outline-none hover:border-muted-foreground focus-visible:ring-2 focus-visible:ring-ring">
        <span aria-hidden className={cn("mt-1 size-3 shrink-0 rounded-sm", REVIEW_MARK[q.status])} />
        <span className="min-w-0 space-y-1">
          <span className="block text-sm font-medium"><span className="mr-2 text-xs text-muted-foreground">Etapa {q.position}</span>{q.step_name}</span>
          <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <ReviewBadge status={q.status} />
            <span>{q.process_name ?? "Rotina avulsa"}</span>
            <span>Pedida por {q.requested_by_name}</span>
            <span>{q.status === "approved" ? `Aprovado em ${when(q.decided_at)}` : `Aberto em ${when(q.requested_at)}`}</span>
          </span>
        </span>
      </button>
    </li>
  );
}

function Section({ title, items, onOpen, empty }: { title: string; items: Review[]; onOpen: (q: Review) => void; empty: string }) {
  return (
    <section aria-label={title} className="space-y-2">
      <h3 className="text-sm font-semibold">{title} <span className="ml-1 font-normal tabular-nums text-muted-foreground">{items.length}</span></h3>
      {items.length ? <ul className="space-y-2">{items.map((q) => <ReviewCard key={q.id} q={q} onOpen={() => onOpen(q)} />)}</ul>
        : <p className="text-sm text-muted-foreground">{empty}</p>}
    </section>
  );
}

function ChangeCard({ q, highlighted }: { q: StepChange; highlighted: boolean }) {
  const { src, reload, me } = useStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const act = (fn: (id: string) => Promise<void>) => async () => {
    setBusy(true); setError(null);
    try { await fn(q.id); } catch (e) { setError(e); } finally { setBusy(false); await reload(); }
  };
  const status = q.status === "pending" ? "Aguardando aprovação" : q.status === "approved" ? "Aprovada" : "Cancelada";
  return (
    <li className={cn("space-y-2 rounded-lg border bg-card p-3 text-sm", highlighted && "border-primary")}>
      <p className="font-medium">{q.process_name}</p>
      <p>Etapa 1: <span className="text-muted-foreground line-through">{q.old_routine_name}</span> → <b>{q.new_routine_name}</b></p>
      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline" className={cn("font-medium", q.status === "approved" ? REVIEW_TONE.approved : q.status === "pending" ? REVIEW_TONE.pending : "bg-muted text-muted-foreground border-transparent")}>{status}</Badge>
        <span>Pedida por {q.requested_by_name} em {when(q.requested_at)}</span>
        {q.decided_at && <span>{q.status === "approved" ? "Aprovada" : "Cancelada"} por {q.decided_by_name} em {when(q.decided_at)}</span>}
      </p>
      {q.status === "pending" && <div className="flex flex-wrap gap-2">
        {q.can_approve && <Button size="sm" disabled={busy} onClick={act(src.approveStepChange)}>Aprovar substituição</Button>}
        {(q.requested_by === me.id || me.role === "admin") && <Button size="sm" variant="outline" disabled={busy} onClick={act(src.cancelStepChange)}>Cancelar pedido</Button>}
      </div>}
      <ErrorView error={error} />
    </li>
  );
}

export function AssignedToMe({ focus }: { focus?: string }) {
  const { reviews, stepChanges, me } = useStore();
  const [open, setOpen] = useState<string | null>(focus ?? null); // a focus that is not a review (step change) opens nothing
  if (!reviews) return <p className="text-sm text-muted-foreground">Carregando pedidos…</p>;
  const pending = reviews.filter((q) => q.status === "pending");
  const approved = reviews.filter((q) => q.status === "approved");
  const sel = reviews.find((q) => q.id === open) ?? null;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="font-medium">Marcado para mim</h3>
          <p className="text-sm text-muted-foreground">{pending.length === 1 ? "1 pedido pendente" : `${pending.length} pedidos pendentes`}</p>
        </div>
        <span className="text-sm text-muted-foreground">{me.display}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <CountCard label="Aguardando revisão" value={pending.length} mark={REVIEW_MARK.pending} />
        <CountCard label="Aprovados" value={approved.length} mark={REVIEW_MARK.approved} />
      </div>
      <Section title="Aguardando revisão" items={pending} onOpen={(q) => setOpen(q.id)} empty="Nenhum pedido pendente." />
      <Section title="Aprovados" items={approved} onOpen={(q) => setOpen(q.id)} empty="Nenhum pedido aprovado." />
      {!!stepChanges?.length && (
        <section aria-label="Substituições da etapa 1" className="space-y-2">
          <h3 className="text-sm font-semibold">Substituições da etapa 1 <span className="ml-1 font-normal tabular-nums text-muted-foreground">{stepChanges.length}</span></h3>
          <p className="text-xs text-muted-foreground">Alteram o processo, fora de execução. É um pedido à parte da revisão que pausa uma execução.</p>
          <ul className="space-y-2">{stepChanges.map((q) => <ChangeCard key={q.id} q={q} highlighted={q.id === focus} />)}</ul>
        </section>
      )}
      <ReviewSheet review={sel} onClose={() => setOpen(null)} />
    </div>
  );
}

function ReviewSheet({ review, onClose }: { review: Review | null; onClose: () => void }) {
  const { src, reload, me } = useStore();
  const [execution, setExecution] = useState<Execution | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const id = review?.execution_id;
  useEffect(() => {
    let alive = true;
    setExecution(null); setError(null);
    if (id) src.execution(id).then((e) => { if (alive) setExecution(e); }).catch((e) => { if (alive) setError(e); });
    return () => { alive = false; };
  }, [id, review?.status, src]);
  async function approve() {
    if (!review || busy) return;
    setBusy(true); setError(null);
    try { await src.approveReview(review.id); await reload(); } catch (e) { setError(e); await reload(); } finally { setBusy(false); }
  }
  const output = (review?.context as any)?.last?.output_path;
  return (
    <Sheet open={review !== null} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {review && <>
          <SheetHeader>
            <SheetTitle>{review.step_name}</SheetTitle>
            <SheetDescription>{review.process_name ?? "Rotina avulsa"} · etapa {review.position} · pedida por {review.requested_by_name} · aberto em {when(review.requested_at)}</SheetDescription>
          </SheetHeader>
          <div className="space-y-5 px-4 pb-6 text-sm">
            <p className="flex flex-wrap items-center gap-2"><ReviewBadge status={review.status} />
              {review.status === "approved"
                ? <span className="text-muted-foreground">Por {review.decided_by_name} em {when(review.decided_at)}</span>
                : <span className="text-muted-foreground">Responsável: {review.assignee_name}</span>}</p>
            {review.status === "pending" && review.assignee_id === me.id && (
              <div className="rounded-md border p-3">
                <p className="mb-2 text-muted-foreground">Confira o contexto e os resultados abaixo. Ao aprovar, a mesma execução continua na próxima etapa.</p>
                <Button disabled={busy} onClick={approve}>{busy ? "Registrando…" : "Aprovado!"}</Button>
              </div>
            )}
            <ErrorView error={error} />
            {typeof output === "string" && <p>Arquivo salvo: <span className="break-all font-medium">{output}</span></p>}
            {execution ? <ExecutionLog e={execution} /> : <p className="text-muted-foreground">Carregando resultados…</p>}
            {Object.keys(review.context ?? {}).length > 0 && <details open><summary className="cursor-pointer font-medium">Contexto desta execução</summary>
              <pre className="mt-2">{JSON.stringify(review.context, null, 2)}</pre></details>}
          </div>
        </>}
      </SheetContent>
    </Sheet>
  );
}
