// Lightweight, dependency-free top-down track map. Takes a normalized track
// outline (points in 0..1, y already SVG-oriented downward) and a list of car
// markers, renders them as an inline SVG. No map libraries.

export interface CarMarker {
  code: string;      // driver 3-letter code, e.g. "LEC"
  name?: string;
  team?: string;
  color: string;     // hex without leading '#', e.g. "E8002D"
  x: number;         // normalized 0..1
  y: number;         // normalized 0..1
  position?: number; // running order
}

export interface TrackMapProps {
  outline: Array<[number, number] | { x: number; y: number }>;
  cars: CarMarker[];
  width?: number;
  height?: number;
  /** When false, a caption marks the map as schematic (not telemetry). */
  isRealTelemetry?: boolean;
  caption?: string;
}

function pt(p: [number, number] | { x: number; y: number }): [number, number] {
  return Array.isArray(p) ? p : [p.x, p.y];
}

export default function TrackMap({
  outline,
  cars,
  width = 460,
  height = 460,
  isRealTelemetry = true,
  caption,
}: TrackMapProps) {
  const pad = 18;
  const sx = (nx: number) => pad + nx * (width - 2 * pad);
  const sy = (ny: number) => pad + ny * (height - 2 * pad);

  const points = outline.map(pt);
  const path =
    points.length > 0
      ? "M " +
        points.map(([x, y]) => `${sx(x).toFixed(1)} ${sy(y).toFixed(1)}`).join(" L ") +
        " Z"
      : "";

  return (
    <div style={{ display: "inline-block" }}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Top-down track map with car positions"
        style={{ background: "#12151b", borderRadius: 12, border: "1px solid #262b36" }}
      >
        {/* Track ribbon: a thick soft stroke under a thin bright centerline. */}
        <path d={path} fill="none" stroke="#2b3444" strokeWidth={16} strokeLinejoin="round" strokeLinecap="round" />
        <path d={path} fill="none" stroke="#5b6a82" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {cars.map((c) => {
          const cx = sx(c.x);
          const cy = sy(c.y);
          return (
            <g key={c.code}>
              <circle cx={cx} cy={cy} r={7} fill={`#${c.color}`} stroke="#0b0d11" strokeWidth={2} />
              <text
                x={cx + 11}
                y={cy + 4}
                fontSize={12}
                fontWeight={700}
                fill="#e6e9ef"
                style={{ paintOrder: "stroke", stroke: "#0b0d11", strokeWidth: 3 }}
              >
                {c.code}
              </text>
            </g>
          );
        })}
      </svg>
      {(!isRealTelemetry || caption) && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: isRealTelemetry ? "#9aa4b2" : "#ffd479",
            maxWidth: width,
          }}
        >
          {!isRealTelemetry && "◆ Schematic — approximate positions, not telemetry. "}
          {caption}
        </div>
      )}
    </div>
  );
}
