// Client-side session storage for the mock auth flow. The token itself is
// issued and verified server-side (lambdas/shared/auth.py); this just remembers
// it between pages. Works identically once the server switches to real Cognito.
import { Session } from "./api";

const KEY = "debrief-session";

export function saveSession(session: Session) {
  if (typeof window !== "undefined") localStorage.setItem(KEY, JSON.stringify(session));
}

export function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function clearSession() {
  if (typeof window !== "undefined") localStorage.removeItem(KEY);
}
