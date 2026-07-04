// Thin client for the Debrief local API (scripts/local_api.py, mock mode).
// Points at NEXT_PUBLIC_API_BASE, default http://localhost:8000.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Domain = "f1" | "valorant" | "cs2";

export interface PresentedScenario {
  role: string;
  situation: string;
  known_facts: string[];
  question: string;
}

export interface Scenario {
  scenario_id: string;
  domain: Domain;
  title: string;
  difficulty: string;
  presented_to_user: PresentedScenario;
}

export interface Verdict {
  overall_score: number;
  verdict: "matched_history" | "defensible_alternative" | "flawed_process";
  decision_score: number;
  decision_feedback: string;
  reasoning_score: number;
  reasoning_feedback: string;
  risk_score: number;
  risk_feedback: string;
  calibration_score: number;
  calibration_feedback: string;
  what_actually_happened: string;
  key_insight_missed: string;
  strengths: string[];
}

export interface GradeResponse {
  scenario_id: string;
  mode: string;
  verdict: Verdict;
  clamp_adjustments: string[];
}

export interface Session {
  token: string;
  user_id: string;
  username: string;
  expires_in: number;
  mode: string;
}

export interface HistoryAttempt {
  attempt_id: string;
  scenario_id: string;
  scenario_title: string;
  domain: Domain;
  timestamp: string;
  overall_score: number;
  verdict: Verdict["verdict"];
  decision_score: number;
  reasoning_score: number;
  risk_score: number;
  calibration_score: number;
}

export interface HistorySummary {
  attempt_count: number;
  average_score?: number;
  score_trend?: number;
  weakest_dimension?: string;
  per_dimension_averages?: Record<string, { average: number; max: number; pct: number }>;
  by_domain?: Record<string, { attempts: number; average_score: number }>;
}

export interface HistoryResponse {
  user_id: string;
  username: string;
  attempts: HistoryAttempt[];
  summary: HistorySummary;
  mode: string;
}

export interface ScenarioIndexEntry {
  scenario_id: string;
  domain: Domain;
  title: string;
  difficulty: string;
  is_mock_data: boolean;
}

async function jsonOrThrow(res: Response) {
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error ?? `request failed (${res.status})`);
  return data;
}

export async function fetchScenario(domain: Domain = "f1", scenarioId?: string): Promise<Scenario> {
  const params = new URLSearchParams({ domain });
  if (scenarioId) params.set("scenario_id", scenarioId);
  const res = await fetch(`${API_BASE}/fetch-scenario?${params}`);
  return jsonOrThrow(res);
}

export async function listScenarios(domain: Domain): Promise<ScenarioIndexEntry[]> {
  const res = await fetch(`${API_BASE}/list-scenarios?domain=${domain}`);
  const data = await jsonOrThrow(res);
  return data.scenarios;
}

// Returns either a graded response or, on a 400 guard rejection, throws the
// server's guard message so the UI can show it verbatim. Sends the session
// token when one exists so the stored attempt is attributed to the user.
export async function gradeAttempt(scenarioId: string, attemptText: string, token?: string): Promise<GradeResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/grade-attempt`, {
    method: "POST",
    headers,
    body: JSON.stringify({ scenario_id: scenarioId, attempt_text: attemptText }),
  });
  return jsonOrThrow(res);
}

export async function login(username: string, password: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return jsonOrThrow(res);
}

export async function fetchHistory(token: string): Promise<HistoryResponse> {
  const res = await fetch(`${API_BASE}/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return jsonOrThrow(res);
}

// Per-domain mock/live status for the badge. Map of domain -> is_mock.
export type MockStatus = Record<Domain, boolean>;

// Progressive enhancement: if the endpoint is unavailable (older API, deploy),
// return null and let the badge fall back to the generic "MOCK DATA" pill.
export async function getMockStatus(): Promise<MockStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/mock-status`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.domains as MockStatus;
  } catch {
    return null;
  }
}
