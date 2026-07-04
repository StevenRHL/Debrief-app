"use client";

import { useEffect, useState } from "react";
import { getMockStatus, MockStatus, Domain } from "../lib/api";

const LABELS: Record<Domain, string> = { f1: "F1", valorant: "VAL", cs2: "CS2" };

// Fixed badge shown on every page. Defaults to the generic "MOCK DATA" pill;
// once per-domain status loads, if any domain is live it spells out which are
// mock vs live so a recording/screenshot can't misrepresent the mode.
export default function MockBadge() {
  const [status, setStatus] = useState<MockStatus | null>(null);

  useEffect(() => {
    let alive = true;
    getMockStatus().then((s) => alive && setStatus(s));
    return () => {
      alive = false;
    };
  }, []);

  // No status yet (loading) or endpoint unavailable → generic all-mock badge.
  if (!status) {
    return (
      <div className="mock-badge" title="Running against fixture data — no live grading call is made.">
        ● MOCK DATA
      </div>
    );
  }

  const domains = Object.keys(status) as Domain[];
  const mock = domains.filter((d) => status[d]);
  const live = domains.filter((d) => !status[d]);

  // Everything mock — keep the familiar badge.
  if (live.length === 0) {
    return (
      <div className="mock-badge" title="Every domain is running against fixture data — no live grading call is made.">
        ● MOCK DATA
      </div>
    );
  }

  // At least one domain is live — spell out the split.
  return (
    <div
      className="mock-badge mock-badge-mixed"
      title={`Live (real calls): ${live.map((d) => LABELS[d]).join(", ")} · Mock (fixtures): ${mock.map((d) => LABELS[d]).join(", ") || "none"}`}
    >
      {mock.length > 0 && <span>● MOCK: {mock.map((d) => LABELS[d]).join(", ")}</span>}
      {mock.length > 0 && live.length > 0 && <span> · </span>}
      {live.length > 0 && <span className="mock-badge-live">◆ LIVE: {live.map((d) => LABELS[d]).join(", ")}</span>}
    </div>
  );
}
