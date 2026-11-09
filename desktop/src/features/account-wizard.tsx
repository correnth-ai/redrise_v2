// Configuração › Equipe › + Nova Conta (TEAM-ACCOUNTS-20261108 item 1): one field per step, in the page
// and navigation pattern of Nova Rotina. Nothing is saved before the last step; the Core checks everything
// again and creates an active operator who signs in with this e-mail and password. Passwords live only in
// this component's state and are cleared on cancel and on success; they are never logged or stored.
import { useState } from "react";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorView } from "@/components/diagnostic";
import { AppError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useStore } from "@/state";

const STEPS = ["Nome", "E-mail", "Senha", "Confirmar senha"];
export const MIN_PASSWORD = 8; // the Core minimum (_check_password)
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/; // the Core rule (service._EMAIL)

export function AccountWizard() {
  const { me, go, src } = useStore();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (src.mode === "demo") return <p className="text-sm text-muted-foreground">Gestão de equipe indisponível na demonstração.</p>;
  if (me.role !== "admin") return <p className="text-sm text-muted-foreground">Somente administradores criam contas.</p>;

  const problem = (n: number): string | null =>
    n === 1 ? (name.trim() ? null : "Informe o nome completo da pessoa.")
    : n === 2 ? (EMAIL.test(email.trim()) ? null : "Informe um e-mail válido, como nome@empresa.com.br.")
    : n === 3 ? (password.length >= MIN_PASSWORD ? null : `A senha precisa de pelo menos ${MIN_PASSWORD} caracteres.`)
    : (confirm === password ? null : "As senhas não coincidem.");
  const leave = () => { setPassword(""); setConfirm(""); go({ menu: "configuracao", page: "equipe" }); };
  async function next(ev: React.FormEvent) {
    ev.preventDefault();
    if (busy) return;
    const p = problem(step);
    setHint(p);
    if (p) return;
    if (step < STEPS.length) { setStep(step + 1); return; }
    setBusy(true); setError(null);
    try {
      await api("POST", "/api/v1/accounts", { full_name: name.trim(), email: email.trim(), password });
      leave();
    } catch (e) {
      setError(e); // the context stays for a correction; an e-mail refusal goes back to that field
      if (e instanceof AppError && e.diagnostic.error_code === "ACCOUNT-EXISTS") setStep(2);
    } finally { setBusy(false); }
  }
  const field = [
    { id: "acc-name", label: "Nome completo", type: "text", value: name, set: setName, auto: "name" },
    { id: "acc-email", label: "E-mail", type: "email", value: email, set: setEmail, auto: "email" },
    { id: "acc-pw", label: `Senha (mínimo ${MIN_PASSWORD} caracteres)`, type: "password", value: password, set: setPassword, auto: "new-password" },
    { id: "acc-pw2", label: "Confirmar senha", type: "password", value: confirm, set: setConfirm, auto: "new-password" },
  ][step - 1];
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <ol className="flex flex-wrap items-center gap-2" aria-label="Etapas do cadastro">
        {STEPS.map((s, i) => (
          <li key={s} className="flex flex-1 items-center gap-2">
            <span aria-current={step === i + 1 ? "step" : undefined} className={cn("inline-flex size-7 shrink-0 items-center justify-center rounded-full border text-sm",
              step > i + 1 ? "border-primary bg-primary text-primary-foreground" : step === i + 1 ? "border-primary text-primary" : "text-muted-foreground")}>
              {step > i + 1 ? <Check className="size-4" /> : i + 1}
            </span>
            <span className={cn("text-sm", step === i + 1 ? "font-medium" : "text-muted-foreground")}>{s}</span>
            {i < STEPS.length - 1 && <span aria-hidden className="h-px flex-1 bg-border" />}
          </li>
        ))}
      </ol>
      <Card className="shadow-none"><CardContent className="pt-0">
        <form className="space-y-5" onSubmit={next} noValidate>
          <div className="space-y-2">
            <Label htmlFor={field.id}>{field.label}</Label>
            <Input key={field.id} id={field.id} type={field.type} autoComplete={field.auto} autoFocus value={field.value} maxLength={field.type === "password" ? 256 : field.id === "acc-name" ? 120 : 254}
              aria-invalid={!!hint} aria-describedby={hint ? "acc-hint" : undefined} onChange={(e) => { field.set(e.target.value); setHint(null); }} />
            {hint && <p id="acc-hint" role="alert" className="text-sm text-destructive">{hint}</p>}
            {step === 4 && <p className="text-xs text-muted-foreground">A conta é criada como Operador e já pode entrar com este e-mail e senha.</p>}
          </div>
          <ErrorView error={error} />
          <div className="flex justify-between gap-2 border-t pt-4">
            <Button type="button" variant="ghost" disabled={busy} onClick={leave}>Cancelar</Button>
            <span className="flex gap-2">
              {step > 1 && <Button type="button" variant="outline" disabled={busy} onClick={() => { setHint(null); setStep(step - 1); }}>Voltar</Button>}
              <Button type="submit" disabled={busy}>{step < STEPS.length ? "Continuar" : busy ? "Criando…" : "Criar conta"}</Button>
            </span>
          </div>
        </form>
      </CardContent></Card>
    </div>
  );
}
