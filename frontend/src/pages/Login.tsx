import { useState } from "react";

import { getHealth, getMe, login } from "../api/auth";
import { FormField } from "../components/FormField";
import { StatusBadge } from "../components/StatusBadge";
import { en } from "../i18n/en";
import { hi } from "../i18n/hi";

/**
 * The product's login page, per Requirement 12 and docs/design.md's
 * component rules.
 *
 * - §10 custom validation: `novalidate` on the form; blur-then-live
 *   per-field validation; no native browser validation bubbles.
 * - §9 copy rules: errors never say "fraud," "fake," or "scam."
 * - Requirement 12.5: on success, three separate StatusBadge instances
 *   (API reachability, Mongo connectivity, authenticated role) replace
 *   the plan's literal middle-dot-joined "API ok · Mongo ok · role:
 *   admin" example string, which docs/design.md §2 bans as an
 *   anti-pattern -- see requirements.md's note on this requirement.
 */

type FieldName = "email" | "password";

interface AuthenticatedState {
  apiReachable: boolean;
  mongoStatus: "ok" | "unavailable";
  role: string;
}

export function Login() {
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const strings = language === "en" ? en : hi;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState<Record<FieldName, boolean>>({
    email: false,
    password: false,
  });
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [authenticated, setAuthenticated] = useState<AuthenticatedState | null>(null);

  function fieldError(field: FieldName): string | undefined {
    if (!touched[field]) return undefined;
    if (field === "email" && email.trim() === "") return strings.emailRequiredError;
    if (field === "password" && password.trim() === "") return strings.passwordRequiredError;
    return undefined;
  }

  function markTouched(field: FieldName) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTouched({ email: true, password: true });
    setSubmitError(null);

    if (email.trim() === "" || password.trim() === "") {
      return;
    }

    setIsSubmitting(true);
    try {
      const { accessToken } = await login(email, password);
      const [me, health] = await Promise.all([getMe(accessToken), getHealth()]);
      setAuthenticated({
        apiReachable: true,
        mongoStatus: health.mongo,
        role: me.role,
      });
    } catch {
      // Generic message regardless of cause, matching the backend's own
      // non-disclosure rule (invalid credentials vs. locked account vs.
      // unknown email all look the same here too).
      setSubmitError(strings.loginFailedError);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (authenticated) {
    return (
      <main className="min-h-screen bg-paper flex items-center justify-center p-24">
        <div className="flex flex-col gap-16 bg-paper-raised border border-rule rounded-panel p-24 w-full max-w-md">
          <h1 className="font-display text-section-head text-ink">{strings.pageTitle}</h1>
          <StatusBadge
            icon="fa-solid fa-circle-check"
            label={strings.statusApiLabel}
            tone="positive"
          />
          <StatusBadge
            icon={
              authenticated.mongoStatus === "ok"
                ? "fa-solid fa-circle-check"
                : "fa-solid fa-triangle-exclamation"
            }
            label={
              authenticated.mongoStatus === "ok"
                ? strings.statusMongoOkLabel
                : strings.statusMongoUnavailableLabel
            }
            tone={authenticated.mongoStatus === "ok" ? "positive" : "negative"}
          />
          <StatusBadge
            icon="fa-solid fa-user"
            label={strings.statusRoleLabel(authenticated.role)}
            tone="neutral"
          />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-paper flex items-center justify-center p-24">
      <div className="flex flex-col gap-16 bg-paper-raised border border-rule rounded-panel p-24 w-full max-w-md">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-section-head text-ink flex items-center gap-8">
            <i className="fa-solid fa-lock text-accent" aria-hidden="true" />
            {strings.pageTitle}
          </h1>
          <button
            type="button"
            onClick={() => setLanguage(language === "en" ? "hi" : "en")}
            className="text-body text-accent underline"
          >
            {language === "en" ? "हिन्दी" : "English"}
          </button>
        </div>

        <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-16">
          <FormField
            label={strings.emailLabel}
            type="email"
            value={email}
            onChange={setEmail}
            onBlur={() => markTouched("email")}
            error={fieldError("email")}
            autoComplete="email"
            data-testid="email-input"
          />
          <FormField
            label={strings.passwordLabel}
            type="password"
            value={password}
            onChange={setPassword}
            onBlur={() => markTouched("password")}
            error={fieldError("password")}
            autoComplete="current-password"
            data-testid="password-input"
          />

          {submitError && (
            <p role="alert" className="text-body text-high-risk-review">
              {submitError}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-control bg-accent text-paper-raised py-8 px-16 text-body disabled:opacity-60"
          >
            {isSubmitting ? strings.submittingButton : strings.submitButton}
          </button>
        </form>
      </div>
    </main>
  );
}
