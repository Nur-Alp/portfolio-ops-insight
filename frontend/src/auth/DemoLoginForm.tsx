import { FormEvent, useState } from "react";
import { dashboardApi } from "../api/client";
import { useI18n } from "../i18n";
import type { DemoActor } from "./session";

export function DemoLoginForm({ onSignedIn }: { onSignedIn: (token: string, actor: DemoActor) => void }) {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await dashboardApi.demoLogin(username, password);
      onSignedIn(result.access_token, {
        actorId: result.actor.actor_id,
        username: result.actor.username,
        displayName: result.actor.display_name,
        roles: result.actor.roles,
        domains: result.actor.domains,
        portfolios: result.actor.portfolios
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-state">
      <div className="state-card">
        <strong>{t("auth.demoTitle")}</strong>
        <span>{t("auth.demoSubtitle")}</span>
        <form className="demo-login-form" onSubmit={(event) => void submit(event)}>
          <label>
            {t("auth.username")}
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoFocus
              required
            />
          </label>
          <label>
            {t("auth.password")}
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? <div className="inline-error" role="alert">{error}</div> : null}
          <button type="submit" className="button button--primary" disabled={submitting}>
            {submitting ? t("auth.signingIn") : t("auth.signIn")}
          </button>
        </form>
      </div>
    </main>
  );
}
