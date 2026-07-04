"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchHistory, HistoryResponse } from "../../lib/api";
import { loadSession } from "../../lib/auth";

const DIM_LABEL: Record<string, string> = {
  decision_score: "Decision",
  reasoning_score: "Reasoning",
  risk_score: "Risk awareness",
  calibration_score: "Calibration",
};

const DOMAIN_LABEL: Record<string, string> = {
  f1: "F1 Strategy",
  valorant: "VALORANT",
  cs2: "CS2",
};

function ScoreSpark({ scores }: { scores: number[] }) {
  // Simple inline SVG line of overall scores over time — no chart dependency.
  const w = 640, h = 120, pad = 8;
  if (scores.length < 2) return null;
  const step = (w - pad * 2) / (scores.length - 1);
  const y = (s: number) => h - pad - (s / 100) * (h - pad * 2);
  const points = scores.map((s, i) => `${pad + i * step},${y(s)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" role="img" aria-label="Score over time">
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      {scores.map((s, i) => (
        <circle key={i} cx={pad + i * step} cy={y(s)} r="3.5" fill="var(--accent)" />
      ))}
    </svg>
  );
}

export default function Progress() {
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [noSession, setNoSession] = useState(false);

  useEffect(() => {
    const session = loadSession();
    if (!session) {
      setNoSession(true);
      return;
    }
    fetchHistory(session.token)
      .then(setData)
      .catch((e) => setErr(String(e.message ?? e)));
  }, []);

  if (noSession) {
    return (
      <main className="narrow">
        <div className="card">
          <h2>Your progress</h2>
          <p>Sign in to see your past attempts, your score over time, and the categories you keep losing points on.</p>
          <p><Link href="/login" className="btn-primary">Sign in</Link></p>
        </div>
      </main>
    );
  }

  const summary = data?.summary;
  const attempts = data?.attempts ?? [];
  const weakest = summary?.weakest_dimension;

  return (
    <main>
      <h1 className="page-title">Your progress</h1>
      {err && <div className="card error">Could not load history: {err}</div>}
      {data && summary && summary.attempt_count > 0 && (
        <>
          <div className="stat-row">
            <div className="stat">
              <span className="stat-n">{summary.attempt_count}</span>
              <span className="stat-l">attempts</span>
            </div>
            <div className="stat">
              <span className="stat-n">{summary.average_score}</span>
              <span className="stat-l">average score</span>
            </div>
            <div className="stat">
              <span className={`stat-n ${Number(summary.score_trend) >= 0 ? "up" : "down"}`}>
                {Number(summary.score_trend) >= 0 ? "+" : ""}{summary.score_trend}
              </span>
              <span className="stat-l">trend (recent vs early)</span>
            </div>
            <div className="stat">
              <span className="stat-n">{weakest ? DIM_LABEL[weakest] : "—"}</span>
              <span className="stat-l">weakest category</span>
            </div>
          </div>

          <div className="card">
            <h2>Score over time</h2>
            <ScoreSpark scores={attempts.map((a) => a.overall_score)} />
          </div>

          <div className="card">
            <h2>Where the points go</h2>
            {weakest && summary.per_dimension_averages && (
              <p className="weak-note">
                You most consistently lose points on <strong>{DIM_LABEL[weakest]}</strong> — averaging{" "}
                {summary.per_dimension_averages[weakest].average}/{summary.per_dimension_averages[weakest].max}{" "}
                ({summary.per_dimension_averages[weakest].pct}%). That&apos;s the dimension to attack next.
              </p>
            )}
            <div className="scorebar">
              {Object.entries(summary.per_dimension_averages ?? {}).map(([field, d]) => (
                <div className="dim" key={field}>
                  <div className="top"><span>{DIM_LABEL[field]}</span><span>{d.average}/{d.max}</span></div>
                  <div className="meter"><span style={{ width: `${d.pct}%` }} /></div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2>Past attempts</h2>
            <table className="history">
              <thead>
                <tr><th>When</th><th>Mode</th><th>Scenario</th><th>Score</th></tr>
              </thead>
              <tbody>
                {[...attempts].reverse().map((a) => (
                  <tr key={a.attempt_id}>
                    <td>{new Date(a.timestamp).toLocaleDateString()}</td>
                    <td>{DOMAIN_LABEL[a.domain] ?? a.domain}</td>
                    <td>{a.scenario_title}</td>
                    <td className="score-cell">{a.overall_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="score-footnote">
            History shown is <strong>{data.mode}</strong> data — generated locally so the progress view is
            demoable before any attempt storage exists.
          </p>
        </>
      )}
    </main>
  );
}
