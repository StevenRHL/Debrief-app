// Isolated preview of the TrackMap component — a Storybook-style route so the
// component can be reviewed on its own BEFORE it's wired into the /play flow.
// Renders the cached Monza fixture (scripts/fetch_track_layout.py); no OpenF1
// call happens in the browser.

import TrackMap, { CarMarker } from "../../components/TrackMap";
import monza from "../../lib/fixtures/monza-track.json";

export const metadata = { title: "TrackMap preview — Debrief" };

export default function TrackMapPreview() {
  const cars = monza.cars as CarMarker[];
  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: "32px 20px" }}>
      <h1 style={{ marginBottom: 4 }}>TrackMap — isolated preview</h1>
      <p style={{ color: "#9aa4b2", marginTop: 0 }}>
        {monza.circuit} · decision lap {monza.decision_lap} · session {monza.session_key}
      </p>

      <TrackMap
        outline={monza.outline as [number, number][]}
        cars={cars}
        isRealTelemetry={monza.is_real_telemetry}
        caption={`${cars.length} cars · running order at the decision moment`}
      />

      <section style={{ marginTop: 20 }}>
        <h2 style={{ fontSize: 15 }}>Running order (from real data)</h2>
        <ol style={{ color: "#c7cdd8", fontSize: 14, lineHeight: 1.6 }}>
          {cars.map((c) => (
            <li key={c.code}>
              <span style={{ color: `#${c.color}`, fontWeight: 700 }}>{c.code}</span> — {c.name} ({c.team})
            </li>
          ))}
        </ol>
      </section>

      <p style={{ marginTop: 24, fontSize: 12, color: "#7b8494", borderTop: "1px solid #262b36", paddingTop: 12 }}>
        <strong>Fixture source:</strong> {monza.source}
      </p>
    </main>
  );
}
