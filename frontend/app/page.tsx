import Link from "next/link";

// Landing page — explains the idea in one screen (Phase 2 roadmap item).
const MODES = [
  {
    id: "f1",
    name: "F1 Strategy",
    tag: "Race engineer",
    blurb:
      "A frozen pit-wall moment from a real Grand Prix. Cover the stop or commit to the one-stop — and defend the call.",
  },
  {
    id: "valorant",
    name: "VALORANT",
    tag: "In-game leader",
    blurb:
      "A round from a real match: retake or save, force or reset. Explain the call against the clock, the economy and the information you had.",
  },
  {
    id: "cs2",
    name: "CS2",
    tag: "Buy caller",
    blurb:
      "Economy decisions with the match on the line. Force-buy or full eco — argue it from the loss bonus, the win rates, the sequence.",
  },
];

export default function Landing() {
  return (
    <main>
      <section className="hero">
        <h1>
          Explain the call.<br />Get graded on the <em>thinking</em>.
        </h1>
        <p className="hero-sub">
          Debrief shows you a real decision moment — a pit wall at lap 33, a 3v4 post-plant, a broken
          economy at match point — and asks you to explain what you&apos;d do and why. An AI grades your
          <strong> reasoning</strong> against what actually happened and against sound process, not
          whether you guessed the answer.
        </p>
        <div className="hero-cta">
          <Link href="/play" className="btn-primary">Try a scenario</Link>
          <Link href="/progress" className="btn-ghost">See your progress</Link>
        </div>
      </section>

      <section className="how">
        <div className="how-step">
          <span className="how-n">1</span>
          <h3>See the moment</h3>
          <p>A frozen decision point with the facts as they were known — no hindsight.</p>
        </div>
        <div className="how-step">
          <span className="how-n">2</span>
          <h3>Make the call</h3>
          <p>Type your decision and the reasoning behind it: what you&apos;re weighing, what you&apos;re betting on, what would make you wrong.</p>
        </div>
        <div className="how-step">
          <span className="how-n">3</span>
          <h3>Get the debrief</h3>
          <p>The reveal, what you got right, the one thing to take away — graded on reasoning, decision, risk and calibration.</p>
        </div>
      </section>

      <section className="modes">
        {MODES.map((m) => (
          <Link key={m.id} href={`/play?mode=${m.id}`} className={`mode-card mode-${m.id}`}>
            <span className="mode-tag">{m.tag}</span>
            <h3>{m.name}</h3>
            <p>{m.blurb}</p>
          </Link>
        ))}
      </section>

      <p className="landing-foot">
        A well-argued call that history went against still scores. A lucky guess with no reasoning doesn&apos;t.
      </p>
    </main>
  );
}
