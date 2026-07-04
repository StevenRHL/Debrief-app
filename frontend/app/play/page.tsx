"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Domain, fetchScenario, gradeAttempt, listScenarios, Scenario, ScenarioIndexEntry, Verdict } from "../../lib/api";
import { loadSession } from "../../lib/auth";
import { countWords, guardMessage, MIN_WORDS, MAX_WORDS } from "../../lib/guard";

const DOMAINS: { id: Domain; label: string }[] = [
  { id: "f1", label: "F1 Strategy" },
  { id: "valorant", label: "VALORANT" },
  { id: "cs2", label: "CS2" },
];

// Displayed as a quiet tag, not a pass/fail stamp.
const VERDICT_LABEL: Record<Verdict["verdict"], string> = {
  matched_history: "Same call · sound reasoning",
  defensible_alternative: "Defensible alternative",
  flawed_process: "Process to build on",
};

// A debrief opens with a sentence about the thinking, not a score.
const VERDICT_HEADLINE: Record<Verdict["verdict"], string> = {
  matched_history:
    "You reached the same call that was made — and the way you got there shows you earned it, not guessed it.",
  defensible_alternative:
    "You went a different way than the call that was made — and it holds up as a defensible call with its own logic.",
  flawed_process:
    "The answer matters less than the thinking here — and the thinking is where the next gain is.",
};

function reasoningSubhead(reasoning: number): string {
  if (reasoning >= 30) return "Your reasoning did the heavy lifting on this one.";
  if (reasoning >= 18) return "Solid reasoning, with a clear place to sharpen it.";
  if (reasoning >= 10) return "The reasoning is still thin — that's the thing worth building.";
  return "There's almost no reasoning to grade yet — start from the trade-offs.";
}

function Dimension({ label, score, max, feedback }: { label: string; score: number; max: number; feedback: string }) {
  return (
    <div className="dim">
      <div className="top"><span>{label}</span><span>{score}/{max}</span></div>
      <div className="meter"><span style={{ width: `${(score / max) * 100}%` }} /></div>
      <div className="fb">{feedback}</div>
    </div>
  );
}

function PlayInner() {
  const searchParams = useSearchParams();
  const initialMode = (searchParams.get("mode") as Domain) ?? "f1";
  const [domain, setDomain] = useState<Domain>(
    DOMAINS.some((d) => d.id === initialMode) ? initialMode : "f1"
  );
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [scenarioList, setScenarioList] = useState<ScenarioIndexEntry[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [mode, setMode] = useState<string>("");
  const [submitErr, setSubmitErr] = useState<string | null>(null);

  // The picker is progressive enhancement: if listing fails, the domain's
  // default scenario still loads and the loop still works.
  useEffect(() => {
    setScenarioList([]);
    setScenarioId(null);
    listScenarios(domain)
      .then(setScenarioList)
      .catch(() => setScenarioList([]));
  }, [domain]);

  useEffect(() => {
    setScenario(null);
    setLoadErr(null);
    setVerdict(null);
    setText("");
    setSubmitErr(null);
    fetchScenario(domain, scenarioId ?? undefined)
      .then(setScenario)
      .catch((e) => setLoadErr(String(e.message ?? e)));
  }, [domain, scenarioId]);

  const words = countWords(text);
  const clientGuard = guardMessage(text);
  const canSubmit = !clientGuard && !submitting && !!scenario;

  async function onSubmit() {
    if (!scenario) return;
    setSubmitting(true);
    setSubmitErr(null);
    setVerdict(null);
    try {
      const res = await gradeAttempt(scenario.scenario_id, text, loadSession()?.token);
      setVerdict(res.verdict);
      setMode(res.mode);
    } catch (e: any) {
      setSubmitErr(String(e.message ?? e));
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setVerdict(null);
    setText("");
    setSubmitErr(null);
  }

  return (
    <main>
      <p className="tagline">Explain your reasoning. Get a read on how you think, not whether you guessed right.</p>
      <div className="mode-switcher" role="tablist" aria-label="Game mode">
        {DOMAINS.map((d) => (
          <button
            key={d.id}
            role="tab"
            aria-selected={domain === d.id}
            className={`mode-tab${domain === d.id ? " active" : ""}`}
            onClick={() => setDomain(d.id)}
          >
            {d.label}
          </button>
        ))}
      </div>
      {scenarioList.length > 1 && (
        <div className="scenario-picker" role="tablist" aria-label="Scenario">
          {scenarioList.map((s) => (
            <button
              key={s.scenario_id}
              role="tab"
              aria-selected={scenario?.scenario_id === s.scenario_id}
              className={`scenario-chip${scenario?.scenario_id === s.scenario_id ? " active" : ""}`}
              onClick={() => setScenarioId(s.scenario_id)}
            >
              {s.title}
              <span className="diff">{s.difficulty}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mock-banner">
        <strong>Mock mode.</strong> All three modes run against local fixtures, not live grading or game APIs — safe to click through and screen-record.
      </div>

      {loadErr && <div className="card error">Could not load a scenario: {loadErr}<br />Is the local API running on port 8000? <code>MOCK_MODE=true python3 scripts/local_api.py</code></div>}

      {scenario && (
        <div className="card">
          <h2>{scenario.title}</h2>
          <p className="role">{scenario.presented_to_user.role}</p>
          <p>{scenario.presented_to_user.situation}</p>
          <ul className="facts">
            {scenario.presented_to_user.known_facts.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
          <p className="question">{scenario.presented_to_user.question}</p>
        </div>
      )}

      {scenario && !verdict && (
        <div className="card">
          <h2>Your call & reasoning</h2>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What do you do, and why? What are you weighing, what are you betting on, and what would make you wrong?"
            disabled={submitting}
          />
          <div className="row">
            <span className={`count${words < MIN_WORDS || words > MAX_WORDS ? " bad" : ""}`}>
              {words} words · need {MIN_WORDS}–{MAX_WORDS}
            </span>
            <button onClick={onSubmit} disabled={!canSubmit}>
              {submitting ? "Grading…" : "Submit for grading"}
            </button>
          </div>
          {clientGuard && text.length > 0 && <div className="guard-msg">{clientGuard}</div>}
          {submitErr && <div className="guard-msg error">{submitErr}</div>}
        </div>
      )}

      {verdict && (
        <div className="card debrief">
          <span className="kicker">Your debrief</span>
          <div className={`verdict-pill verdict-${verdict.verdict}`}>{VERDICT_LABEL[verdict.verdict]}</div>
          <p className="headline">{VERDICT_HEADLINE[verdict.verdict]}</p>
          <p className="subhead">{reasoningSubhead(verdict.reasoning_score)}</p>

          <h2>What actually happened</h2>
          <div className="reveal">{verdict.what_actually_happened}</div>

          {verdict.strengths.length > 0 && (
            <>
              <h2>What you got right</h2>
              <ul className="strengths">{verdict.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}

          {verdict.key_insight_missed && (
            <>
              <h2>The one thing to take away</h2>
              <p>{verdict.key_insight_missed}</p>
            </>
          )}

          <h2>How your reasoning broke down</h2>
          <div className="scorebar">
            <Dimension label="Reasoning" score={verdict.reasoning_score} max={40} feedback={verdict.reasoning_feedback} />
            <Dimension label="Decision" score={verdict.decision_score} max={20} feedback={verdict.decision_feedback} />
            <Dimension label="Risk awareness" score={verdict.risk_score} max={20} feedback={verdict.risk_feedback} />
            <Dimension label="Calibration" score={verdict.calibration_score} max={20} feedback={verdict.calibration_feedback} />
          </div>

          <p className="score-footnote">
            Overall {verdict.overall_score}/100 — a debrief to learn from, not a leaderboard. Graded in <strong>{mode}</strong> mode.
          </p>

          <p style={{ marginTop: 16 }}>
            <button className="link" onClick={reset}>← Try another explanation</button>
          </p>
        </div>
      )}
    </main>
  );
}

export default function Play() {
  return (
    <Suspense>
      <PlayInner />
    </Suspense>
  );
}
