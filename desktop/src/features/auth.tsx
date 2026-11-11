// Access screens. login-03 and signup-03 (shadcn, MIT) adapted to RedRise over
// the landscape supplied by the user: centered brand and card, no split panel. Everything goes to the team Core: sign-up only records the
// account (no e-mail, no confirmation), and an administrator activates it.
// External identity is out for now (user decision of 02/11/2026).
// The team bootstrap (create team / connect to a team) is unchanged.
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ErrorView } from "@/components/diagnostic";
import { api, call, session } from "@/lib/api";
import { label } from "@/lib/locale";

const T = (key: string, values: Record<string, string> = {}) =>
  Object.entries(values).reduce((s, [k, v]) => s.replace(`{${k}}`, v), label(`auth.${key}`, key));

// ---------------------------------------------------------------- shared frame
export function AccessFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 p-6 md:p-10">
      <div className="flex items-center gap-2 rounded-full bg-black/45 px-3 py-1.5 font-medium text-white backdrop-blur-sm">
        <img src="assets/redrise-icon-32x32.png" alt="" className="size-6 rounded-md" />RedRise
      </div>
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}

function FormCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

const Link = ({ onClick, children }: { onClick: () => void; children: React.ReactNode }) => (
  <button type="button" onClick={onClick} className="rounded-sm underline underline-offset-4 outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring">{children}</button>
);

// ---------------------------------------------------------------- access flow
export function AccessPage({ onSignedIn }: { onSignedIn: (out: { token: string }) => void }) {
  const [signup, setSignup] = useState(false);
  return <AccessFrame>{signup ? <SignupCard onBack={() => setSignup(false)} /> : <LoginCard onSignup={() => setSignup(true)} onSignedIn={onSignedIn} />}</AccessFrame>;
}

function LoginCard({ onSignup, onSignedIn }: { onSignup: () => void; onSignedIn: (o: { token: string }) => void }) {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <FormCard title={T("login.title")} description={T("login.subtitle")}>
      <form onSubmit={async (e) => { e.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try { onSignedIn(await api("POST", "/api/v1/login", { username, password })); } catch (err) { setError(err); } finally { setBusy(false); } }}>
        <FieldGroup className="gap-4">
          <Field><FieldLabel htmlFor="login-user">{T("login_id")}</FieldLabel><Input id="login-user" autoComplete="username" autoFocus required value={username} onChange={(e) => setU(e.target.value)} /></Field>
          <Field><FieldLabel htmlFor="login-pw">{T("password")}</FieldLabel><Input id="login-pw" type="password" autoComplete="current-password" required value={password} onChange={(e) => setP(e.target.value)} /></Field>
          <Field>
            <Button type="submit" disabled={busy}>{busy ? T("login.busy") : T("login.submit")}</Button>
            <FieldDescription className="text-center">{T("no_account")} <Link onClick={onSignup}>{T("create_account")}</Link></FieldDescription>
          </Field>
        </FieldGroup>
      </form>
      <ErrorView error={error} />
    </FormCard>
  );
}

function SignupCard({ onBack }: { onBack: () => void }) {
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const short = [...form.password].length < 8;
  const mismatch = form.password !== form.confirm;
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTried(true);
    if (busy || short || mismatch) return;
    setBusy(true); setError(null);
    try { await api("POST", "/api/v1/register", { full_name: form.name, email: form.email, password: form.password }); setDone(true); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }
  if (done) {
    return (
      <FormCard title={T("signup.title")}>
        <div className="space-y-4 text-sm">
          <p role="status">{T("signup.received", { email: form.email.trim() })}</p>
          <Button className="w-full" onClick={onBack}>{T("sign_in")}</Button>
        </div>
      </FormCard>
    );
  }
  return (
    <FormCard title={T("signup.title")} description={T("signup.subtitle")}>
      <form onSubmit={submit}>
        <FieldGroup className="gap-4">
          <Field><FieldLabel htmlFor="su-name">{T("full_name")}</FieldLabel>
            <Input id="su-name" autoComplete="name" autoFocus required maxLength={120} placeholder={T("full_name.placeholder")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field><FieldLabel htmlFor="su-email">{T("email")}</FieldLabel>
            <Input id="su-email" type="email" autoComplete="email" required placeholder={T("email.placeholder")} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field><FieldLabel htmlFor="su-pw">{T("password")}</FieldLabel>
                <Input id="su-pw" type="password" autoComplete="new-password" required aria-invalid={tried && short} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
              <Field><FieldLabel htmlFor="su-pw2">{T("confirm_password")}</FieldLabel>
                <Input id="su-pw2" type="password" autoComplete="new-password" required aria-invalid={tried && mismatch} value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} /></Field>
            </div>
            <FieldDescription>{T("password_hint")}</FieldDescription>
            {tried && !short && mismatch && <FieldError>{T("password_mismatch")}</FieldError>}
            {tried && short && <FieldError>{T("password_short")}</FieldError>}
          </Field>
          <Field>
            <Button type="submit" disabled={busy}>{busy ? T("signup.busy") : T("signup.submit")}</Button>
            <FieldDescription className="text-center">{T("have_account")} <Link onClick={onBack}>{T("sign_in")}</Link></FieldDescription>
          </Field>
        </FieldGroup>
      </form>
      <ErrorView error={error} />
    </FormCard>
  );
}

// ---------------------------------------------------------------- real: team bootstrap
function Brand({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <img src="assets/redrise-icon-64x64.png" alt="" className="size-10 rounded-md" />
      <span className="sr-only">RedRise</span>
      <h1 className="text-xl font-bold">{title}</h1>
      {children}
    </div>
  );
}

/** Role chosen in the installer wizard (PROCESS-LIST-INSTALLER-20261110 item 2), or null: an install made without the
 *  wizard (update, older installer) still offers both. The choice grants nothing; the app consumes it once set up. */
export type SetupRole = "server" | "station" | null;

export function WelcomePage({ onDone, onCreated, role = null }: { onDone: () => void; onCreated: (joinCode: string) => void; role?: SetupRole }) {
  const [h, setH] = useState({ team: "", station: "servidor", username: "", display: "", password: "", password2: "", port: "47800" });
  const [j, setJ] = useState({ code: "", station: "", username: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<void>) => { if (busy) return; setBusy(true); setError(null); try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); } };
  const F = ({ id, label: text, hint, ...p }: { id: string; label: string; hint?: string } & React.ComponentProps<"input">) => (
    <Field><FieldLabel htmlFor={id}>{text}</FieldLabel><Input id={id} {...p} />{hint && <FieldDescription>{hint}</FieldDescription>}</Field>
  );
  const server = role !== "station", station = role !== "server";
  return (
    <div className={`mx-auto space-y-6 overflow-auto p-6 ${role ? "max-w-xl" : "max-w-5xl"}`}>
      <Brand title="Boas-vindas à RedRise">
        {role && <p className="text-sm text-muted-foreground" role="status">
          {role === "server" ? "Escolhido na instalação: servidor da equipe. Configure a equipe e o primeiro administrador."
            : "Escolhido na instalação: estação de operação. Conecte este computador ao servidor de uma equipe existente; depois, cada pessoa entra com a própria conta."}
        </p>}
      </Brand>
      <div className={`grid gap-6 ${role ? "" : "md:grid-cols-2"}`}>
        {server && <Card className="shadow-none"><CardHeader><CardTitle>Criar equipe neste computador</CardTitle>
          <CardDescription>Este computador será o servidor da equipe (dados compartilhados) e também poderá executar rotinas.</CardDescription></CardHeader>
          <CardContent><form onSubmit={(e) => { e.preventDefault(); if (h.password !== h.password2) { setError("As senhas não conferem."); return; }
            void run(async () => {
              const out = await call("host_create", { port: Number(h.port), team: h.team, username: h.username, display: h.display, password: h.password, stationName: h.station });
              const login = await api("POST", "/api/v1/login", { username: h.username, password: h.password });
              session.set(login.token); onCreated(out.join_code);
            }); }}>
            <FieldGroup className="gap-4">
              {F({ id: "h-team", label: "Nome da equipe", required: true, maxLength: 80, value: h.team, onChange: (e) => setH({ ...h, team: e.target.value }) })}
              {F({ id: "h-station", label: "Nome desta estação", required: true, value: h.station, onChange: (e) => setH({ ...h, station: e.target.value }) })}
              {F({ id: "h-user", label: "Usuário administrador", required: true, pattern: "[a-z0-9._-]{3,40}", hint: "letras minúsculas, números, . _ -", value: h.username, onChange: (e) => setH({ ...h, username: e.target.value }) })}
              {F({ id: "h-display", label: "Nome de exibição", required: true, value: h.display, onChange: (e) => setH({ ...h, display: e.target.value }) })}
              {F({ id: "h-pw", label: "Senha", type: "password", required: true, minLength: 8, value: h.password, onChange: (e) => setH({ ...h, password: e.target.value }) })}
              {F({ id: "h-pw2", label: "Confirmar senha", type: "password", required: true, minLength: 8, value: h.password2, onChange: (e) => setH({ ...h, password2: e.target.value }) })}
              {F({ id: "h-port", label: "Porta na rede local", type: "number", min: 1024, max: 65535, value: h.port, onChange: (e) => setH({ ...h, port: e.target.value }),
                hint: "Outras estações conectam por esta porta. O Windows pode pedir permissão de rede; nada é alterado sem sua confirmação." })}
              <Button type="submit" disabled={busy}>Criar equipe</Button>
            </FieldGroup></form></CardContent></Card>}
        {station && <Card className="shadow-none"><CardHeader><CardTitle>Conectar a uma equipe</CardTitle>
          <CardDescription>Use o código exibido em Configuração › Aplicativo no servidor da equipe. Um administrador entra uma vez para registrar esta estação.</CardDescription></CardHeader>
          <CardContent><form onSubmit={(e) => { e.preventDefault(); void run(async () => {
            await call("station_join", { code: j.code, username: j.username, password: j.password, stationName: j.station }); onDone();
          }); }}>
            <FieldGroup className="gap-4">
              {F({ id: "j-code", label: "Código da equipe", required: true, placeholder: "rr1:servidor:47800:…", value: j.code, onChange: (e) => setJ({ ...j, code: e.target.value }) })}
              {F({ id: "j-station", label: "Nome desta estação", required: true, value: j.station, onChange: (e) => setJ({ ...j, station: e.target.value }) })}
              {F({ id: "j-user", label: "Usuário administrador", required: true, value: j.username, onChange: (e) => setJ({ ...j, username: e.target.value }) })}
              {F({ id: "j-pw", label: "Senha", type: "password", required: true, value: j.password, onChange: (e) => setJ({ ...j, password: e.target.value }) })}
              <Button type="submit" disabled={busy}>Conectar</Button>
            </FieldGroup></form></CardContent></Card>}
      </div>
      {/* A station that cannot reach its server stays a station: the connection is pending and can be tried again;
          no local server is created as a fallback. */}
      {error != null && role === "station" && <p role="status" className="text-sm">Conexão pendente: confira o código da equipe e se o servidor está ligado com o RedRise aberto, e tente de novo.</p>}
      <ErrorView error={error} />
    </div>
  );
}
