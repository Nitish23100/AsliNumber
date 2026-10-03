import { useId } from "react";

/**
 * Shared form-field primitive implementing docs/design.md §10's custom
 * validation states (default / focus / error), used instead of native
 * browser validation. The caller owns `novalidate` on the surrounding
 * `<form>` and the blur-then-live validation timing (§10's "validate on
 * blur the first time, then live on-keystroke once touched" rule) — this
 * component only renders whichever state it's told to render.
 *
 * Error state per §10: 1px high-risk-review-red border, an
 * fa-circle-exclamation icon inside the field (right-aligned), and a
 * single-line message below the field in the same red, 13px.
 */

export interface FormFieldProps {
  label: string;
  type: "email" | "password";
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  error?: string;
  autoComplete?: string;
  "data-testid"?: string;
}

export function FormField({
  label,
  type,
  value,
  onChange,
  onBlur,
  error,
  autoComplete,
  ...rest
}: FormFieldProps) {
  const inputId = useId();
  const errorId = useId();
  const hasError = Boolean(error);

  return (
    <div className="flex flex-col gap-4">
      <label
        htmlFor={inputId}
        className={hasError ? "text-high-risk-review text-body" : "text-ink-soft text-body"}
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={inputId}
          type={type}
          value={value}
          autoComplete={autoComplete}
          aria-invalid={hasError}
          aria-describedby={hasError ? errorId : undefined}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          data-testid={rest["data-testid"]}
          className={[
            "w-full rounded-control border bg-paper-raised px-12 py-8 text-body text-ink",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent",
            hasError ? "border-high-risk-review pr-32" : "border-rule",
          ].join(" ")}
        />
        {hasError && (
          <i
            className="fa-solid fa-circle-exclamation text-high-risk-review absolute right-12 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
        )}
      </div>
      {hasError && (
        <p id={errorId} role="alert" className="text-body text-high-risk-review">
          {error}
        </p>
      )}
    </div>
  );
}
