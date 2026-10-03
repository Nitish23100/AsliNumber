/**
 * English strings for the Login page, per Requirement 12.6: every
 * user-facing label, message, and error on the page ships with an
 * English and a Hindi string from the start (frontend/src/i18n/hi.ts).
 *
 * Per Requirement 12.4 / docs/design.md section 9: no message here uses
 * "fraud," "fake," or "scam."
 */
export interface Strings {
  pageTitle: string;
  emailLabel: string;
  passwordLabel: string;
  submitButton: string;
  submittingButton: string;
  loginFailedError: string;
  emailRequiredError: string;
  passwordRequiredError: string;
  statusApiLabel: string;
  statusMongoOkLabel: string;
  statusMongoUnavailableLabel: string;
  statusRoleLabel: (role: string) => string;
}

export const en: Strings = {
  pageTitle: "Log in",
  emailLabel: "Email",
  passwordLabel: "Password",
  submitButton: "Log in",
  submittingButton: "Logging in...",
  loginFailedError: "That email or password doesn't match our records.",
  emailRequiredError: "Enter your email.",
  passwordRequiredError: "Enter your password.",
  statusApiLabel: "API reachable",
  statusMongoOkLabel: "Database connected",
  statusMongoUnavailableLabel: "Database unavailable",
  statusRoleLabel: (role: string) => `Signed in as ${role}`,
};
