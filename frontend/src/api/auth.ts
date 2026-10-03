/**
 * Thin wrapper around the backend's auth and health endpoints. Requests
 * go to relative paths (`/api/...` is NOT used -- the backend mounts its
 * routes at the root, e.g. `/auth/login`, `/health`; Vite's dev-server
 * proxy, configured in vite.config.ts, forwards `/api` to the backend,
 * so in production behind a reverse proxy the same relative paths work
 * unchanged as long as the proxy maps them the same way).
 */

export interface LoginResult {
  accessToken: string;
}

export interface MeResult {
  id: string;
  email: string | null;
  memberships: { tenantId: string; role: string }[];
  role: string;
}

export interface HealthResult {
  status: string;
  mongo: "ok" | "unavailable";
}

async function parseEnvelope<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) {
    const message = body?.error?.message ?? "Request failed.";
    throw new Error(message);
  }
  return body.data as T;
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  return parseEnvelope<LoginResult>(response);
}

export async function getMe(accessToken: string): Promise<MeResult> {
  const response = await fetch("/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
    credentials: "include",
  });
  return parseEnvelope<MeResult>(response);
}

export async function getHealth(): Promise<HealthResult> {
  const response = await fetch("/health");
  return response.json();
}
